"""Run qualified dev profiles sequentially, recording cold starts and GPU residency."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from paperqa_reflect.config import load_config, write_json
from paperqa_reflect.evaluation import runtime_snapshot


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(paths):
    root = Path(__file__).resolve().parents[1]
    configs = [load_config(path) for path in paths]
    if any(config.split != "dev" or config.provider != "ollama" for config in configs):
        raise ValueError("This comparison driver accepts local dev configurations only.")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    directory = root / "results/comparisons" / stamp
    directory.mkdir(parents=True)
    write_json(
        directory / "plan.json",
        {
            "started_utc": datetime.now(UTC).isoformat(),
            "driver_sha256": sha256(Path(__file__)),
            "configs": [{"path": str(path), "sha256": sha256(path)} for path in paths],
            "note": "Sequential cold starts on the project server; system GPU telemetry includes desktop processes. No model downloads or concurrent probes during scoring.",
        },
    )
    outcomes = []
    for config_path, config in zip(paths, configs, strict=True):
        output_log = directory / f"{config_path.stem}.log"
        telemetry = directory / f"{config_path.stem}-telemetry.jsonl"
        with httpx.Client(base_url=config.endpoint, timeout=30) as client:
            # The experiment's own Ollama server; unload only its resident models.
            resident = client.get("/api/ps")
            resident.raise_for_status()
            for model in resident.json().get("models", []):
                response = client.post(
                    "/api/generate", json={"model": model["name"], "keep_alive": 0}
                )
                response.raise_for_status()
            write_json(
                directory / f"{config_path.stem}-model-metadata.json",
                {
                    model: client.post("/api/show", json={"model": model}).json()
                    for model in sorted(config.models)
                },
            )
        print(f"Starting {config.name}; log {output_log}", flush=True)
        started = time.monotonic()
        with output_log.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-m",
                    "paperqa_reflect.cli",
                    "run",
                    "--config",
                    str(config_path.resolve()),
                    "--limit",
                    "8",
                ],
                cwd=root,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
            try:
                while process.poll() is None:
                    sample = {
                        "utc": datetime.now(UTC).isoformat(),
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "runtime": runtime_snapshot(),
                    }
                    try:
                        response = httpx.get(config.endpoint + "/api/ps", timeout=2)
                        response.raise_for_status()
                        sample["resident_models"] = response.json()
                    except httpx.HTTPError as error:
                        sample["monitor_error"] = str(error)
                    with telemetry.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(sample) + "\n")
                    time.sleep(10)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=30)
        run_path = None
        for line in output_log.read_text(encoding="utf-8").splitlines():
            if line.startswith("Run: "):
                run_path = Path(line[5:])
                break
        outcome = {
            "config": str(config_path),
            "name": config.name,
            "exit_code": process.returncode,
            "run_path": str(run_path) if run_path else None,
            "wall_seconds": round(time.monotonic() - started, 3),
        }
        if run_path and (run_path / "summary.json").exists():
            summary = json.loads((run_path / "summary.json").read_text(encoding="utf-8"))
            outcome["metrics"] = summary.get("metrics")
        outcomes.append(outcome)
        write_json(directory / "outcomes.json", outcomes)
        print(json.dumps(outcome), flush=True)
    print(f"Comparison: {directory}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs="+", type=Path)
    main(parser.parse_args().configs)
