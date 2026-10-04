import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from paperqa_reflect.config import build_settings, load_config, local_runtime
from paperqa_reflect.reference import (
    TOOL_CALL_COMPATIBILITY,
    ReferenceConfig,
    provider_info,
    upstream_settings,
)
from paperqa_reflect.usage import UsageLedger

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "profile,dimension",
    [
        ("local", 1024),
        ("local-qwen35", 1024),
        ("local-qwen35-structured", 1024),
        ("upstream-openai", 1536),
    ],
)
def test_reference_keeps_real_upstream_prompts_and_retrieval(profile, dimension, tmp_path):
    config = load_config(ROOT / f"configs/baseline-{profile}-dev.json")
    settings = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest.csv")
    upstream = upstream_settings()
    expected_prompt = upstream.agent.agent_system_prompt
    if config.tool_call_compatibility:
        expected_prompt += "\n\n" + TOOL_CALL_COMPATIBILITY
    assert settings.agent.agent_system_prompt == expected_prompt
    assert settings.prompts == upstream.prompts
    assert settings.answer.evidence_k == upstream.answer.evidence_k == 20
    assert settings.answer.answer_max_sources == upstream.answer.answer_max_sources == 5
    assert settings.agent.max_timesteps is None
    assert settings.parsing.reader_config == upstream.parsing.reader_config
    # This pinned factory infers known OpenAI dimensions; Ollama reports its
    # dimensions in /api/show and inspect_ollama checks them before inference.
    assert settings.get_embedding_model().ndim == (
        dimension if config.provider == "openai" else None
    )
    assert settings.make_aviary_tool_selector("ToolSelector") is not None
    if config.tool_transport == "json-schema-v1":
        assert settings.local_tool_transport == "json-schema-v1"
        agent_params = settings.get_agent_llm().config["model_list"][0]["litellm_params"]
        assert agent_params["reasoning_effort"] == "low"
        assert (
            settings.get_llm().config["model_list"][0]["litellm_params"]["reasoning_effort"]
            == "none"
        )
    assert not settings.parsing.use_doc_details
    assert not settings.parsing.multimodal
    if config.provider == "ollama":
        assert settings.get_embedding_model().config["kwargs"]["truncate"] is False
        assert settings.get_embedding_model().config["kwargs"]["options"]["num_batch"] == 8192
    for model in (
        settings.get_agent_llm(),
        settings.get_summary_llm(),
        settings.get_llm(),
        settings.get_enrichment_llm(),
    ):
        params = model.config["model_list"][0]["litellm_params"]
        if config.provider == "ollama":
            assert params["api_base"] == config.endpoint
            assert params["num_ctx"] == config.context_tokens
        else:
            assert params["model"] == "gpt-4o-2024-11-20"
            assert not {"api_base", "max_tokens", "reasoning_effort", "num_ctx"} & params.keys()


def test_paid_profile_requires_key_without_logging_it(monkeypatch):
    config = load_config(ROOT / "configs/baseline-upstream-openai-dev.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is absent"):
        provider_info(config)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-not-a-real-key")
    assert "test-secret" not in json.dumps(provider_info(config))


def test_role_sampling_reaches_ollama_wire_without_changing_answer_role(tmp_path):
    from litellm.llms.ollama.chat.transformation import OllamaChatConfig
    from litellm.utils import get_optional_params

    values = load_config(ROOT / "configs/baseline-local-qwen35-structured-dev.json").model_dump()
    config = ReferenceConfig.model_validate(
        values
        | {
            "sampling": {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
                "min_p": 0,
                "repeat_penalty": 1,
                "presence_penalty": 1.5,
            },
            "agent_sampling": {"temperature": 1.0, "top_p": 0.95, "presence_penalty": 0},
        }
    )
    settings = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest.csv")
    for llm, temperature, top_p, think in (
        (settings.get_agent_llm(), 1.0, 0.95, True),
        (settings.get_summary_llm(), 0.7, 0.8, False),
        (settings.get_llm(), 0.7, 0.8, False),
    ):
        params = dict(llm.config["model_list"][0]["litellm_params"])
        params.pop("api_base")
        params.pop("timeout")
        params["model"] = "qwen3.5:9b"
        optional = get_optional_params(custom_llm_provider="ollama_chat", **params)
        wire = OllamaChatConfig().transform_request(
            model=params["model"],
            messages=[{"role": "user", "content": "test"}],
            optional_params=optional,
            litellm_params={},
            headers={},
        )
        assert wire["options"]["temperature"] == temperature
        assert wire["options"]["top_p"] == top_p
        assert wire["options"]["top_k"] == 20
        assert wire["options"]["min_p"] == 0
        assert wire["options"]["repeat_penalty"] == 1
        assert wire["options"]["presence_penalty"] == (0 if think else 1.5)
        assert wire["think"] is think


def test_gpt_oss_reasoning_level_reaches_ollama_for_all_roles(tmp_path):
    from litellm.llms.ollama.chat.transformation import OllamaChatConfig
    from litellm.utils import get_optional_params

    values = load_config(ROOT / "configs/baseline-local-qwen35-structured-dev.json").model_dump()
    config = ReferenceConfig.model_validate(
        values
        | {
            "agent_model": "gpt-oss:20b",
            "summary_model": "gpt-oss:20b",
            "answer_model": "gpt-oss:20b",
            "reasoning_effort": "low",
            "agent_reasoning_effort": "low",
        }
    )
    settings = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest.csv")
    for llm in (settings.get_agent_llm(), settings.get_summary_llm(), settings.get_llm()):
        params = dict(llm.config["model_list"][0]["litellm_params"])
        params.pop("api_base")
        params.pop("timeout")
        params["model"] = "gpt-oss:20b"
        optional = get_optional_params(custom_llm_provider="ollama_chat", **params)
        wire = OllamaChatConfig().transform_request(
            model=params["model"],
            messages=[{"role": "user", "content": "test"}],
            optional_params=optional,
            litellm_params={},
            headers={},
        )
        assert wire["think"] == "low"


def test_local_sampling_cannot_change_exact_upstream_openai_control():
    values = load_config(ROOT / "configs/baseline-upstream-openai-dev.json").model_dump()
    with pytest.raises(ValueError, match="Ollama"):
        ReferenceConfig.model_validate(values | {"sampling": {"temperature": 1}})


@pytest.mark.parametrize("dimension", [1024, 768, None])
def test_ollama_dimensions_come_from_show_not_tags(monkeypatch, dimension):
    import httpx

    from paperqa_reflect import runner

    config = load_config(ROOT / "configs/baseline-local-dev.json")
    calls = []

    def handle(request):
        calls.append(request.url.path)
        values = {
            "/api/version": {"version": "test"},
            "/api/tags": {"models": [{"name": name, "digest": name} for name in config.models]},
            "/api/show": {"model_info": {"bert.embedding_length": dimension}},
        }
        return httpx.Response(200, json=values[request.url.path])

    client = httpx.Client
    monkeypatch.setattr(
        runner.httpx,
        "Client",
        lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handle)),
    )
    if dimension == 1024:
        assert runner.inspect_ollama(config)["embedding_metadata"]["bert.embedding_length"] == 1024
    else:
        with pytest.raises(ValueError, match="embedding dimension"):
            runner.inspect_ollama(config)
    assert calls == ["/api/version", "/api/tags", "/api/show"]


@pytest.mark.parametrize(
    "update",
    [
        {"endpoint": "https://example.com"},
        {"agent_model": "cloud-model"},
        {"agent_model": "openai/gpt-4o"},
        {"context_tokens": None},
    ],
)
def test_local_profile_cannot_silently_route_to_cloud(update):
    values = load_config(ROOT / "configs/baseline-local-dev.json").model_dump()
    with pytest.raises(ValueError):
        ReferenceConfig.model_validate(values | update)


def test_usage_is_deduplicated_and_retains_missing_cost_and_no_secrets(tmp_path):
    ledger = UsageLedger(tmp_path, "openai", 0.5)
    now = datetime.now(UTC)
    response = SimpleNamespace(id="response-1", model="test", usage=None, choices=[])
    kwargs = {
        "model": "test",
        "litellm_call_id": "1",
        "response_cost": 0.6,
        "api_key": "secret",
        "messages": [{"content": "private"}],
    }
    ledger.record(kwargs, response, "success", now, now)
    ledger.record(kwargs, response, "success", now, now)
    assert ledger.totals()["requests"] == 1
    assert "threshold" in ledger.stop_reason()
    assert "secret" not in (tmp_path / "requests.jsonl").read_text()
    assert "private" not in (tmp_path / "requests.jsonl").read_text()
    ledger.record({"litellm_call_id": "2"}, None, "failure", now, now)
    assert not ledger.totals()["cost_complete"]
    assert "missing" in ledger.stop_reason()


def test_real_litellm_callback_observes_direct_router_without_network(tmp_path):
    # PaperQA's controller calls Router directly, bypassing lmi's CostTracker.
    # A LiteLLM-level callback must see both that route and embedding requests.
    local_runtime(ROOT)
    from litellm import Router

    async def exercise():
        ledger = UsageLedger(tmp_path, "openai", 3)
        ledger.install()
        try:
            router = Router(
                model_list=[
                    {
                        "model_name": "gpt-4o-2024-11-20",
                        "litellm_params": {"model": "gpt-4o-2024-11-20", "api_key": "unused"},
                    }
                ]
            )
            await router.acompletion(
                model="gpt-4o-2024-11-20",
                messages=[{"role": "user", "content": "test"}],
                mock_response="test answer",
            )
            await ledger.flush()
            assert ledger.totals()["requests"] == 1
            assert ledger.rows[0]["usage"] is not None
        finally:
            ledger.uninstall()

    asyncio.run(exercise())
