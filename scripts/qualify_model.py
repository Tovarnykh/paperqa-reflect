"""Small synthetic compatibility probes, separate from the scored PaperQA runs."""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from paperqa_reflect.config import build_settings, load_config, write_json
from paperqa_reflect.evaluation import runtime_snapshot


async def main(config_path):
    root = Path(__file__).resolve().parents[1]
    config = load_config(config_path)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    directory = root / "results/diagnostics" / f"{stamp}-{config_path.stem}"
    directory.mkdir(parents=True)
    settings = build_settings(config, root, directory / "index", directory / "manifest.csv")
    write_json(directory / "config.json", config.model_dump())
    from aviary.core import Message
    from paperqa.agents.env import settings_to_tools

    client = httpx.Client(base_url=config.endpoint, timeout=30)
    metadata = {}
    for model in sorted(config.models):
        response = client.post("/api/show", json={"model": model})
        response.raise_for_status()
        metadata[model] = response.json()
    write_json(directory / "models.json", metadata)
    selector = settings.make_aviary_tool_selector("ToolSelector")
    tools = settings_to_tools(settings)
    results = []
    messages = [
        Message(role="system", content=settings.agent.agent_system_prompt),
        Message(role="user", content="Find research on wing pattern evolution in butterflies."),
    ]
    for name, call in [
        ("controller_real_tools", lambda: selector(messages, tools)),
        (
            "source_reading",
            lambda: (
                settings.get_summary_llm()
                .get_router()
                .acompletion(
                    model=settings.summary_llm,
                    messages=[
                        {"role": "system", "content": "Answer from the supplied source only."},
                        {
                            "role": "user",
                            "content": (
                                "Source: In a synthetic experiment, rod Q was 24.5 cm. "
                                "Other rods were 51.2, 19.7, 15.0 and 10.3 cm. "
                                "Q was second longest overall. What was Q's rank and length? "
                                "Reply in one sentence."
                            ),
                        },
                    ],
                )
            ),
        ),
    ]:
        start = time.perf_counter()
        try:
            response = await call()
            item = {"probe": name, "response": response.model_dump(mode="json"), "error": None}
        except Exception as error:  # noqa: BLE001 - preserve failed compatibility attempts
            item = {"probe": name, "error": f"{type(error).__name__}: {error}"}
        item["seconds"] = round(time.perf_counter() - start, 3)
        item["runtime"] = runtime_snapshot()
        item["resident_models"] = client.get("/api/ps").json()
        results.append(item)
        write_json(directory / "probes.json", results)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    client.close()
    print(f"Diagnostics: {directory}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    asyncio.run(main(parser.parse_args().config))
