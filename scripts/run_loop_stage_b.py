"""Frozen 32-attempt dev comparison. Dry plan by default; no adaptive retries."""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import httpx
from run_loop_pilot import analyze, read

from paperqa_reflect.config import build_settings, load_config, write_json
from paperqa_reflect.data import jsonl, sha256, validate_corpus
from paperqa_reflect.evaluation import runtime_snapshot
from paperqa_reflect.runner import git_state, inspect_ollama

ROOT = Path(__file__).resolve().parents[1]


def schedule(question_ids):
    if len(question_ids) != 8 or len(set(question_ids)) != 8:
        raise ValueError("Exactly eight unique frozen dev questions required")
    jobs = []
    for seed in (42, 43):
        for index, qid in enumerate(question_ids):
            arms = (1, 3) if (index + seed - 42) % 2 == 0 else (3, 1)
            for n in arms:
                jobs.append({"job": len(jobs) + 1, "question_id": qid, "seed": seed,
                             "n": n, "config": f"configs/loop-evidence-n{n}-s{seed}.json"})
    return jobs


def prepare():
    git = git_state(ROOT)
    if "unavailable" in git or git["status"]:
        raise ValueError("Commit a clean tree before preparing or running Stage B")
    baseline = read(ROOT / "results/baselines/uia-local-reference-v1.json")
    configs = {}
    for seed in (42, 43):
        original_path = ROOT / f"configs/uia-qwen38-dev-s{seed}.json"
        expected_hash = baseline["config_sha256" if seed == 42 else "repeat_config_sha256"]
        if sha256(original_path) != expected_hash:
            raise ValueError("Frozen baseline configuration changed")
        original = load_config(original_path)
        settings = {}
        for n in (1, 3):
            config = load_config(ROOT / f"configs/loop-evidence-n{n}-s{seed}.json")
            if config.provider != "ollama" or config.split != "dev" or config.seed != seed:
                raise ValueError("Local frozen dev configuration required")
            comparable = config.model_dump()
            for field in ("name", "protocol", "agent_evidence_n"):
                comparable[field] = original.model_dump()[field]
            if comparable != original.model_dump():
                raise ValueError("A baseline condition changed")
            validate_corpus(ROOT, config)
            for key, attr in (("questions_sha256", "questions"), ("gold_sha256", "gold"),
                              ("corpus_manifest_sha256", "corpus_manifest")):
                if sha256(ROOT / getattr(config, attr)) != baseline["common_hashes"][key]:
                    raise ValueError("Frozen input bytes changed")
            settings[n] = build_settings(config, ROOT, ROOT / ".cache/check-index",
                                         ROOT / ".cache/check-manifest").model_dump(exclude={"md5"})
            configs[seed, n] = config
        expected = json.loads(json.dumps(settings[1]))
        expected["agent"]["agent_evidence_n"] = 3
        if settings[1]["agent"]["agent_evidence_n"] != 1 or expected != settings[3]:
            raise ValueError("Treatment differs beyond agent_evidence_n")
    packages = {name: version(name) for name in baseline["packages"]}
    if packages != baseline["packages"]:
        raise ValueError("Pinned package versions changed")
    jobs = schedule([q["id"] for q in jsonl(ROOT / configs[42, 1].questions)])
    for job in jobs:
        job["config_sha256"] = sha256(ROOT / job["config"])
    files = [Path(__file__), ROOT / "scripts/run_loop_pilot.py",
             ROOT / "docs/loop-evidence-stage-b-v1.md",
             ROOT / "docs/loop-stage-b-evaluator-freeze.json", ROOT / "uv.lock",
             *sorted((ROOT / "src/paperqa_reflect").glob("*.py"))]
    plan = {"kind": "loop-evidence-stage-b-v1", "git": git, "schedule": jobs,
            "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in files},
            "models": baseline["models"], "packages": packages,
            "input_sha256": baseline["common_hashes"],
            "evaluator": read(ROOT / "docs/loop-stage-b-evaluator-freeze.json"),
            "independent_questions": 8, "attempts": 32, "holdout": False,
            "retry_policy": "none", "runtime": runtime_snapshot()}
    return plan, configs


def runtime_check(config, models):
    info = inspect_ollama(config)
    if info["version"] != "0.35.0" or any(
        info["models"][name]["digest"] != value for name, value in models.items()
    ):
        raise ValueError("Frozen runtime/model mismatch")
    with httpx.Client(base_url=config.endpoint, timeout=60, trust_env=False) as client:
        response = client.get("/api/ps")
        response.raise_for_status()
        for model in response.json().get("models", []):
            client.post("/api/generate", json={"model": model["name"],
                                               "keep_alive": 0}).raise_for_status()


def job_outcome(job, log, exit_code, seconds, error=None):
    outcome = {**job, "exit_code": exit_code, "wall_seconds": seconds}
    if error:
        outcome["execution_error"] = error
    paths = [Path(line[5:]) for line in log.read_text(encoding="utf-8").splitlines()
             if line.startswith("Run: ")]
    if len(paths) == 1:
        path = paths[0].resolve()
        if path.parent != (ROOT / "results/runs").resolve():
            raise ValueError("Unexpected run directory")
        outcome["run_path"] = str(path)
        try:
            outcome["metrics"] = analyze(path)
        except Exception as exc:  # noqa: BLE001 - archive any analysis failure before stopping
            outcome["analysis_error"] = f"{type(exc).__name__}: {exc}"
    else:
        outcome["analysis_error"] = "Expected exactly one structured run directory"
    return outcome


def run_job(job, config, directory):
    start = time.monotonic()
    log = directory / f"job-{job['job']:02d}.log"
    error = None
    process = None
    try:
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-m", "paperqa_reflect.cli", "run",
                 "--config", job["config"], "--limit", "1", "--question-id", job["question_id"]],
                cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
            with (directory / f"job-{job['job']:02d}-telemetry.jsonl").open("w") as stream:
                while process.poll() is None:
                    sample = {"seconds": time.monotonic() - start, "runtime": runtime_snapshot()}
                    try:
                        response = httpx.get(config.endpoint + "/api/ps", timeout=3,
                                             trust_env=False)
                        response.raise_for_status()
                        sample["models"] = response.json()
                    except httpx.HTTPError as exc:
                        sample["monitor_error"] = type(exc).__name__
                    stream.write(json.dumps(sample) + "\n")
                    stream.flush()
                    if time.monotonic() - start > 4500:
                        raise TimeoutError("Attempt exceeded fixed 4500-second wall limit")
                    time.sleep(10)
    except Exception as exc:  # noqa: BLE001 - preserve failed attempt; caller stops the series
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=30)
    return job_outcome(job, log, process.returncode if process else None,
                       time.monotonic() - start, error)


def main(execute):
    plan, configs = prepare()
    if not execute:
        print(json.dumps(plan, indent=2))
        return
    # Share Stage A's lock so the two drivers cannot overlap.
    lock = ROOT / ".cache/loop-pilot.lock"
    lock.parent.mkdir(exist_ok=True)
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    outcomes, directory = [], None
    try:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
        directory = ROOT / "results/loop-stage-b" / stamp
        directory.mkdir(parents=True)
        write_json(directory / "plan.json", plan)
        (directory / "driver.py").write_bytes(Path(__file__).read_bytes())
        write_json(directory / "progress.json", {"status": "running", "outcomes": outcomes})
        print("STAGE_B_DIRECTORY", directory, flush=True)
        for job in plan["schedule"]:
            # Stop on any code/config mutation rather than mix experiment versions.
            if git_state(ROOT) != plan["git"] or any(
                sha256(ROOT / path) != digest for path, digest in plan["source_sha256"].items()
            ) or sha256(ROOT / job["config"]) != job["config_sha256"]:
                raise ValueError("Experiment source/config changed during execution")
            config = configs[job["seed"], job["n"]]
            runtime_check(config, plan["models"])
            write_json(directory / "current.json", job)
            print("START", json.dumps(job), flush=True)
            outcome = run_job(job, config, directory)
            outcomes.append(outcome)
            write_json(directory / "progress.json", {"status": "running", "outcomes": outcomes})
            print("FINISHED", json.dumps(outcome), flush=True)
            if (outcome.get("execution_error") or outcome.get("analysis_error")
                    or outcome.get("metrics", {}).get("analysis_error")):
                raise ValueError("Attempt preserved; structural failure needs inspection")
        write_json(directory / "progress.json", {"status": "completed", "outcomes": outcomes})
        print("STAGE_B_COMPLETED", directory, flush=True)
    except BaseException as exc:
        if directory is not None:
            write_json(directory / "progress.json", {"status": "failed", "outcomes": outcomes,
                                                      "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    main(parser.parse_args().run)
