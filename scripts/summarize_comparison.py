"""Aggregate saved comparison artifacts offline; never perform model inference."""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from paperqa_reflect.config import write_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main(directories, output):
    rows = []
    for directory in directories:
        for outcome in read(directory / "outcomes.json"):
            run = Path(outcome["run_path"])
            summary = read(run / "summary.json")
            provenance = read(run / "provenance.json")
            requests = lines(run / "requests.jsonl")
            telemetry = lines(directory / (Path(outcome["config"]).stem + "-telemetry.jsonl"))
            gpu_samples = []
            resident = defaultdict(list)
            for sample in telemetry:
                text = sample["runtime"].get("nvidia_smi") or ""
                memory = re.search(r",\s*\d+ MiB,\s*(\d+) MiB,", text)
                if memory:
                    gpu_samples.append(int(memory.group(1)))
                for model in sample.get("resident_models", {}).get("models", []):
                    resident[model["name"]].append(model["size_vram"])
            tool_seconds = defaultdict(float)
            for question in run.glob("*/events.jsonl"):
                action = None
                for event in lines(question):
                    if event["kind"] == "action":
                        names = [
                            c["function"]["name"] for c in event["value"].get("tool_calls", [])
                        ]
                        action = ("+".join(names), event["seconds"])
                    elif event["kind"] == "step" and action:
                        tool_seconds[action[0]] += event["seconds"] - action[1]
                        action = None
            rows.append(
                {
                    **outcome,
                    "raw_option_matches": sum(
                        r["grade"]["option_matches_key"] for r in summary["records"]
                    ),
                    "indexing": read(run / "indexing.json"),
                    "request_count": len(requests),
                    "request_statuses": dict(Counter(r["status"] for r in requests)),
                    "finish_reasons": dict(
                        Counter(f for r in requests for f in r.get("finish_reasons", []))
                    ),
                    "maximum_reported_prompt_tokens": max(
                        (
                            (r.get("usage") or {}).get("prompt_tokens") or 0
                            for r in requests
                            if "bge-m3" not in r.get("requested_model", "")
                        ),
                        default=0,
                    ),
                    "power_states": dict(
                        Counter(s["runtime"].get("ac_line_status", "unknown") for s in telemetry)
                    ),
                    "system_gpu_mib_observed_min_max": [min(gpu_samples), max(gpu_samples)]
                    if gpu_samples
                    else None,
                    "model_size_vram_bytes_observed_max": {
                        name: max(values) for name, values in resident.items()
                    },
                    "tool_execution_seconds": {
                        name: round(value, 3) for name, value in tool_seconds.items()
                    },
                    "hashes": {
                        key: provenance.get(key)
                        for key in (
                            "code_sha256",
                            "questions_sha256",
                            "gold_sha256",
                            "corpus_manifest_sha256",
                        )
                    },
                    "per_question": [
                        {
                            "id": r["id"],
                            "status": r["status"],
                            "seconds": r["seconds"],
                            **r["grade"],
                        }
                        for r in summary["records"]
                    ],
                }
            )
    write_json(
        output,
        {
            "note": "All attempts retained. Option match is not claim support. Timing includes model swaps. VRAM samples include desktop use and omit short peaks; model API size excludes some CPU/auxiliary allocations.",
            "runs": rows,
        },
    )
    for row in rows:
        print(
            json.dumps(
                {key: value for key, value in row.items() if key not in {"hashes", "per_question"}},
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.directories, args.output)
