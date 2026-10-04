"""Replay one saved controller state, without executing tools or reading gold."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from paperqa_reflect.config import build_settings, load_config, write_json
from paperqa_reflect.tool_transport import request_schema, wire_messages


async def main(args):
    root = Path(__file__).resolve().parents[1]
    config = load_config(args.config)
    if config.provider != "ollama":
        raise ValueError("Local diagnostic only.")
    if args.reasoning:
        config.agent_reasoning_effort = args.reasoning
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = root / "results/diagnostics" / f"{stamp}-controller-replay"
    output.mkdir(parents=True)
    settings = build_settings(config, root, output / "index", output / "manifest.csv")
    from paperqa.agents.env import settings_to_tools

    tools = settings_to_tools(settings)
    settings.adjust_tools_for_agent_llm(tools)
    definitions = [tool.model_dump(by_alias=True, exclude_none=True) for tool in tools]
    events = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines()]
    messages = [
        {"role": "system", "content": settings.agent.agent_system_prompt},
        {
            "role": "user",
            "content": settings.agent.agent_prompt.format(
                question=events[0]["value"]["question"],
                status="Status: Paper Count=0 | Relevant Papers=0 | Current Evidence=0 | Current Cost=$0.0000",
                complete_tool_name="complete",
            ),
        },
    ]
    if not args.initial:
        for event in events[1:]:
            if event["kind"] == "action":
                messages.append(event["value"])
            elif event["kind"] == "step":
                messages.extend(event["value"]["observations"])
    payload = {
        "model": settings.agent.agent_llm,
        "messages": wire_messages(messages, definitions),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "tool_request",
                "schema": request_schema(definitions),
                "strict": True,
            },
        },
        **(settings.agent.agent_config or {}),
    }
    write_json(output / "request.json", payload)
    write_json(output / "config.json", config.model_dump())
    write_json(
        output / "provenance.json",
        {
            "events": str(args.events.resolve()),
            "initial_only": args.initial,
            "purpose": "Transport diagnosis; no tools executed, no answer key read.",
        },
    )
    response = await settings.get_agent_llm().get_router().acompletion(**payload)
    write_json(output / "response.json", response.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "output": str(output),
                "finish": response.choices[0].finish_reason,
                "content": response.choices[0].message.content,
                "tool_calls": response.choices[0].message.tool_calls,
            },
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("events", type=Path)
    parser.add_argument("--initial", action="store_true")
    parser.add_argument("--reasoning", choices=["none", "low"])
    asyncio.run(main(parser.parse_args()))
