"""Fixed paired N=1/N=3 local pilot; no inference unless --run is supplied."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from paperqa_reflect.config import build_settings, load_config, write_json
from paperqa_reflect.data import jsonl, sha256, validate_corpus
from paperqa_reflect.evaluation import runtime_snapshot
from paperqa_reflect.runner import git_state, inspect_ollama

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = [
    ("RfaH", "b105af85-833e-48bc-ac78-48f73c9673fd", 1),
    ("RfaH", "b105af85-833e-48bc-ac78-48f73c9673fd", 3),
    ("COSA-1", "487539f9-2f17-4009-aa4a-c41322445f11", 3),
    ("COSA-1", "487539f9-2f17-4009-aa4a-c41322445f11", 1),
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(run_path):
    summary = read(run_path / "summary.json")
    if len(summary["records"]) != 1:
        return {"analysis_error": "Expected one completed question record"}
    row = summary["records"][0]
    qdir = run_path / row["id"]
    events = [json.loads(line) for line in (qdir / "events.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    return analyze_events(run_path, row, events, summary)


def analyze_events(run_path, row, events, summary):
    qdir = run_path / row["id"]
    counts = Counter()
    turns = 0
    pending = None
    gathers = []
    seen_chunks, seen_summaries = set(), set()
    for event in events:
        if event["kind"] == "action":
            if pending is not None:
                raise ValueError("Unpaired controller action")
            pending = event
            turns += 1
            counts.update(c["function"]["name"] for c in event["value"]["tool_calls"])
        elif event["kind"] == "step" and pending is not None:
            calls = pending["value"]["tool_calls"]
            if any(c["function"]["name"] == "gather_evidence" for c in calls):
                value = event["value"]
                path = qdir / value["state_path"]
                if sha256(path) != value["state_sha256"]:
                    raise ValueError("Intermediate evidence snapshot changed")
                contexts = read(path)["contexts"]
                chunks, summaries = set(), set()
                for context in contexts:
                    text = context["text"]
                    chunk = hashlib.sha256(json.dumps(
                        [str(text["doc"]["dockey"]), text["name"], text["text"]],
                        ensure_ascii=False).encode()).hexdigest()
                    chunks.add(chunk)
                    summaries.add((chunk, context["context"]))
                gathers.append({
                    "batch_seconds": event["seconds"] - pending["seconds"],
                    "mixed_tool_batch": len(calls) != 1,
                    "new_original_chunks": len(chunks - seen_chunks),
                    "new_summary_texts": len(summaries - seen_summaries),
                    "current_contexts": len(contexts),
                    "state_sha256": value["state_sha256"],
                })
                seen_chunks.update(chunks)
                seen_summaries.update(summaries)
            pending = None
    return {
        "run_id": run_path.name, "question_id": row["id"], "status": row["status"],
        "correct_completed": row["grade"]["correct_completed"],
        "selected": row["grade"]["selected"], "question_seconds": row["seconds"],
        "controller_turns": turns, "tool_counts": dict(counts), "actions": row["actions"],
        "token_counts": row.get("token_counts"), "gathers": gathers,
        "incomplete_action_batch": pending is not None,
        "raw_answer_sha256": hashlib.sha256(row["raw_answer"].encode()).hexdigest(),
        "indexing": read(run_path / "indexing.json") if (run_path / "indexing.json").exists() else None,
        "usage": summary["usage"],
    }


def main(execute):
    git = git_state(ROOT)
    if "unavailable" in git or git["status"]:
        raise ValueError("Freeze a clean Git commit before preparing or running the pilot")
    configs = {n: load_config(ROOT / f"configs/loop-evidence-n{n}-s42.json") for n in [1, 3]}
    settings = {}
    for n, config in configs.items():
        if config.provider != "ollama" or config.split != "dev" or config.seed != 42:
            raise ValueError("Pilot is local dev seed42 only")
        validate_corpus(ROOT, config)
        settings[n] = build_settings(config, ROOT, ROOT / ".cache/check-index",
                                     ROOT / ".cache/check-manifest").model_dump(exclude={"md5"})
    expected = json.loads(json.dumps(settings[1]))
    expected["agent"]["agent_evidence_n"] = 3
    if expected != settings[3] or settings[1]["agent"]["agent_evidence_n"] != 1:
        raise ValueError("Settings differ beyond controller evidence visibility")
    baseline = read(ROOT / "results/baselines/uia-local-reference-v1.json")
    original = load_config(ROOT / baseline["recommended_config"]).model_dump()
    for config in configs.values():
        comparable = config.model_dump()
        for field in ["name", "protocol", "agent_evidence_n"]:
            comparable[field] = original[field]
        if comparable != original:
            raise ValueError("Model, sampling or another baseline condition changed")
    for key, attr in [("questions_sha256", "questions"),
                      ("corpus_manifest_sha256", "corpus_manifest")]:
        if sha256(ROOT / getattr(configs[1], attr)) != baseline["common_hashes"][key]:
            raise ValueError("Frozen dev inputs changed")
    ids = {q["id"] for q in jsonl(ROOT / configs[1].questions)}
    if not {q for _, q, _ in SCHEDULE} <= ids:
        raise ValueError("Pilot questions must belong to dev")
    plan = {"kind": "loop-evidence-pilot-v1", "git": git,
            "driver_sha256": sha256(Path(__file__)),
            "schedule": [{"case": case, "question_id": qid, "n": n,
                          "config_sha256": sha256(ROOT / f"configs/loop-evidence-n{n}-s42.json")}
                         for case, qid, n in SCHEDULE],
            "models": baseline["models"], "limitations": "Selected two-case diagnostic; not general efficacy"}
    if not execute:
        print(json.dumps(plan, indent=2))
        return
    lock = ROOT / ".cache/loop-pilot.lock"
    lock.parent.mkdir(exist_ok=True)
    with lock.open("x") as output:
        output.write(str(os.getpid()))
    directory = None
    outcomes = []
    try:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
        directory = ROOT / "results/loop-pilot" / stamp
        directory.mkdir(parents=True)
        write_json(directory / "plan.json", plan)
        (directory / "driver.py").write_bytes(Path(__file__).read_bytes())
        write_json(directory / "progress.json", {"status": "running", "outcomes": outcomes})
        print("PILOT_DIRECTORY", directory, flush=True)
        for index, (case, qid, n) in enumerate(SCHEDULE, 1):
            config = configs[n]
            info = inspect_ollama(config)
            if info["version"] != "0.35.0" or any(
                info["models"][name]["digest"] != value for name, value in baseline["models"].items()
            ):
                raise ValueError("Frozen runtime/model mismatch")
            with httpx.Client(base_url=config.endpoint, timeout=60, trust_env=False) as client:
                resident = client.get("/api/ps")
                resident.raise_for_status()
                for model in resident.json().get("models", []):
                    client.post("/api/generate", json={"model": model["name"],
                                                       "keep_alive": 0}).raise_for_status()
            start = time.monotonic()
            write_json(directory / "current.json", {"job": index, "case": case, "n": n})
            log = directory / f"job-{index}.log"
            print(f"START {index}/4 {case} N={n}", flush=True)
            with log.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [sys.executable, "-X", "utf8", "-m", "paperqa_reflect.cli", "run",
                     "--config", f"configs/loop-evidence-n{n}-s42.json", "--limit", "1",
                     "--question-id", qid], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
                try:
                    with (directory / f"job-{index}-telemetry.jsonl").open("w") as telemetry:
                        while process.poll() is None:
                            sample = {"seconds": time.monotonic() - start,
                                      "runtime": runtime_snapshot()}
                            try:
                                response = httpx.get(config.endpoint + "/api/ps", timeout=3,
                                                     trust_env=False)
                                response.raise_for_status()
                                sample["models"] = response.json()
                            except httpx.HTTPError as error:
                                sample["monitor_error"] = type(error).__name__
                            telemetry.write(json.dumps(sample) + "\n")
                            telemetry.flush()
                            if time.monotonic() - start > 4500:
                                raise TimeoutError("Pilot job exceeded indexing and question limits")
                            time.sleep(10)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=30)
            outcome = {"job": index, "case": case, "n": n, "exit_code": process.returncode,
                       "wall_seconds": time.monotonic() - start}
            run_paths = [Path(line[5:]) for line in log.read_text(encoding="utf-8").splitlines()
                         if line.startswith("Run: ")]
            if len(run_paths) == 1:
                outcome["run_path"] = str(run_paths[0])
                outcome["metrics"] = analyze(run_paths[0])
            outcomes.append(outcome)
            write_json(directory / "progress.json", {"status": "running", "outcomes": outcomes})
            print("FINISHED", json.dumps(outcome), flush=True)
            if not run_paths or "analysis_error" in outcome.get("metrics", {}):
                raise ValueError("Missing structured run outcome; inspect before further inference")
        write_json(directory / "progress.json", {"status": "completed", "outcomes": outcomes})
        print("PILOT_COMPLETED", directory, flush=True)
    except Exception as error:
        if directory is not None:
            write_json(directory / "progress.json", {"status": "failed", "outcomes": outcomes,
                                                      "error": str(error)})
        raise
    finally:
        lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    main(parser.parse_args().run)
