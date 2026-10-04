import asyncio
import json
from pathlib import Path

import pytest

from paperqa_reflect.config import build_settings, load_config, local_runtime

ROOT = Path(__file__).resolve().parents[1]
local_runtime(ROOT)

from aviary.core import MalformedMessageError, Message, ToolSelector
from litellm.types.utils import ModelResponse
from paperqa.agents.env import settings_to_tools

from paperqa_reflect.tool_transport import (
    StructuredToolCompletion,
    request_schema,
    wire_messages,
)


@pytest.fixture
def real_tools(tmp_path):
    config = load_config(ROOT / "configs/baseline-local-qwen35-dev.json")
    settings = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest")
    return settings_to_tools(settings)


def test_schema_and_history_preserve_available_actions(real_tools):
    tools = [tool.model_dump(by_alias=True, exclude_none=True) for tool in real_tools]
    schema = request_schema(tools)
    branches = schema["properties"]["tool_calls"]["items"]["anyOf"]
    assert {row["properties"]["name"]["const"] for row in branches} == {
        tool.info.name for tool in real_tools
    }
    messages = [
        {"role": "system", "content": "Original system instruction."},
        {"role": "user", "content": "Original question."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "gather_evidence", "arguments": '{"question":"Q"}'},
                }
            ],
        },
        {"role": "tool", "name": "gather_evidence", "tool_call_id": "call_1", "content": "E"},
    ]
    before = json.dumps(messages)
    converted = wire_messages(messages, tools)
    assert json.dumps(messages) == before
    assert converted[0]["content"].startswith("Original system instruction.")
    assert converted[1] == messages[1]
    assert json.loads(converted[2]["content"])["tool_calls"][0]["arguments"] == {"question": "Q"}
    assert json.loads(converted[3]["content"])["tool_result"]["content"] == "E"


@pytest.mark.parametrize(
    "payload,finish,valid",
    [
        (
            {"tool_calls": [{"name": "gather_evidence", "arguments": {"question": "Q"}}]},
            "stop",
            True,
        ),
        (
            {"tool_calls": [{"name": "complete", "arguments": {"has_successful_answer": False}}]},
            "stop",
            True,
        ),
        ({"tool_calls": []}, "stop", False),
        ({"tool_calls": [{"name": "invented", "arguments": {}}]}, "stop", False),
        ({"tool_calls": [{"name": "gather_evidence", "arguments": {}}]}, "stop", False),
        (
            {"tool_calls": [{"name": "complete", "arguments": {"has_successful_answer": "yes"}}]},
            "stop",
            False,
        ),
        (
            {"tool_calls": [{"name": "complete", "arguments": {"has_successful_answer": True}}]},
            "length",
            False,
        ),
    ],
)
def test_real_aviary_selector_validates_requests_without_inventing_success(
    real_tools, payload, finish, valid
):
    response = ModelResponse(
        model="test",
        choices=[
            {
                "index": 0,
                "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(payload)},
            }
        ],
        usage={"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
    )

    async def completion(model, **kwargs):
        assert "tools" not in kwargs and "tool_choice" not in kwargs
        assert kwargs["response_format"]["type"] == "json_schema"
        return response

    selector = ToolSelector(model_name="test", acompletion=StructuredToolCompletion(completion))
    call = selector([Message(role="user", content="Question")], real_tools)
    if valid:
        result = asyncio.run(call)
        assert result.info["usage"] == (12, 4)
        assert result.tool_calls[0].function.name == payload["tool_calls"][0]["name"]
        assert result.tool_calls[0].function.arguments == payload["tool_calls"][0]["arguments"]
        assert response.choices[0].finish_reason == "stop"
        assert not response.choices[0].message.tool_calls
    else:
        with pytest.raises(MalformedMessageError):
            asyncio.run(call)
