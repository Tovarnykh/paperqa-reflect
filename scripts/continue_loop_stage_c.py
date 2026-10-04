"""Explicit one-use continuation of never-started jobs after the UiA autostop.

This is a manual protocol amendment, not retry/resume support for the original driver.
Job 10 and all original artifacts remain untouched. No inference without --run.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

import run_loop_stage_c as stage_c

from paperqa_reflect.config import write_json
from paperqa_reflect.data import sha256
from paperqa_reflect.runner import git_state

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "20261004T210539Z-3f1ab1"
ORIGINAL_HEAD = "ad5b60ced2ae4b695c7f7119ddc7e49e5d0b5379"
ORIGINAL_PID = 1904071
RECOVERY_FILES = {
    "scripts/continue_loop_stage_c.py", "tests/test_loop_stage_c_recovery.py",
    "docs/loop-stage-c-recovery-v1.md", "README.md",
}
DRIVERS = {"run_loop_pilot.py", "run_loop_stage_b.py", "run_loop_stage_c.py",
           "continue_loop_stage_c.py"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def local_path(value, parent):
    path = Path(value).resolve()
    if path.parent != parent.resolve():
        raise ValueError(f"Unexpected original artifact directory: {path}")
    return path


def process_guard(pid, proc=Path("/proc")):
    """Linux-only, fail closed for existing/zombie/reused PIDs and other experiments."""
    if not proc.is_dir():
        raise ValueError("Linux /proc inspection is required for manual recovery")
    if (proc / str(pid)).exists():
        raise ValueError("Original PID still exists (including zombie or reused PID)")
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().decode(errors="replace").split("\0")
        except FileNotFoundError:
            continue  # Process exited during inspection.
        if any(Path(arg).name in DRIVERS for arg in argv) or "paperqa_reflect.cli" in argv:
            raise ValueError(f"Active experiment process must be inspected: PID {entry.name}")


def lock_guard(expected):
    process_guard(ORIGINAL_PID)
    path = ROOT / ".cache/loop-pilot.lock"
    if not path.is_file() or path.read_bytes() != expected:
        raise ValueError("Original shared lock changed or is missing")


def source_guard(original, current):
    for field in ("source_sha256", "input_sha256", "models", "packages", "evaluator",
                  "schedule", "attempts", "retry_policy"):
        if current[field] != original[field]:
            raise ValueError(f"Original Stage C condition changed: {field}")


def git_amendment_guard(original, current):
    if original["head"] != ORIGINAL_HEAD or original["status"] or current["status"]:
        raise ValueError("Original frozen head and a clean recovery commit are required")
    if current["head"] == ORIGINAL_HEAD:
        raise ValueError("Commit the explicit recovery amendment before execution")
    subprocess.run(["git", "merge-base", "--is-ancestor", ORIGINAL_HEAD, current["head"]],
                   cwd=ROOT, check=True, capture_output=True)
    result = subprocess.run(["git", "diff", "--name-only", ORIGINAL_HEAD, current["head"]],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    changed = set(result.stdout.splitlines())
    if not changed or not changed <= RECOVERY_FILES:
        raise ValueError("Recovery Git changes exceed the explicit amendment allowlist")


def history_guard(manifest, original, directory):
    """Validate the exact completed prefix; never infer that an attempted job is new."""
    schedule = original["schedule"]
    if (len(schedule) != 48 or [j["job"] for j in schedule] != list(range(1, 49))
            or original["kind"] != "loop-evidence-stage-c-v1"):
        raise ValueError("Expected original 48-job Stage C schedule")
    progress_path = directory / "progress.json"
    if sha256(progress_path) != manifest["progress_sha256"]:
        raise ValueError("Original progress differs from the interruption inspection")
    progress = read(progress_path)
    completed = progress["outcomes"]
    if progress["status"] != "running" or len(completed) != 9:
        raise ValueError("Expected nine preserved outcomes and stale running status")
    if manifest["completed"] != 9 or manifest["current"] != schedule[9]:
        raise ValueError("Interruption manifest does not identify job 10")
    if read(directory / "current.json") != schedule[9]:
        raise ValueError("Original current job changed")
    cache = ROOT / ".cache/loop-stage-c-v1"
    claim = read(cache / "execution.json")
    if (claim["directory"] != str(directory) or claim["git"] != original["git"]
            or claim["attempts"] != 48 or claim["retry_policy"] != "none"):
        raise ValueError("Original execution claim changed")
    lines = (cache / "driver.log").read_text(encoding="utf-8").splitlines()
    starts = [json.loads(line[6:]) for line in lines if line.startswith("START ")]
    finishes = [json.loads(line[9:]) for line in lines if line.startswith("FINISHED ")]
    if starts != schedule[:10] or finishes != completed:
        raise ValueError("Driver history is not exactly jobs 1-9 finished and job 10 started")
    runs = []
    for job in schedule[:10]:
        log = directory / f"job-{job['job']:02d}.log"
        paths = [line[5:] for line in log.read_text(encoding="utf-8").splitlines()
                 if line.startswith("Run: ")]
        if len(paths) != 1:
            raise ValueError("Each started job must retain exactly one structured run")
        run = local_path(paths[0], ROOT / "results/runs")
        summary = read(run / "summary.json")
        if job["job"] <= 9:
            outcome = completed[job["job"] - 1]
            if (any(outcome.get(k) != v for k, v in job.items())
                    or outcome.get("run_path") != str(run)
                    or len(summary["records"]) != 1
                    or summary["records"][0]["id"] != job["question_id"]):
                raise ValueError("Completed prefix/run artifacts disagree")
        else:
            qdir = run / job["question_id"]
            if (str(run) != manifest["current_run"]["path"] or summary["records"]
                    or (qdir / "response.json").exists() or (qdir / "grade.json").exists()):
                raise ValueError("Interrupted job acquired a completed response or grade")
            events = [json.loads(line) for line in (qdir / "events.jsonl").read_text(
                encoding="utf-8").splitlines() if line]
            if not events or events[-1]["kind"] != "action":
                raise ValueError("Expected an unfinished action in interrupted job 10")
        runs.append(run)
    for path in directory.glob("job-*"):
        if int(path.name.split("-")[1].split(".")[0]) > 10:
            raise ValueError("A supposedly unstarted job already has artifacts")
    if len(set(runs)) != 10:
        raise ValueError("Started jobs must have distinct original run directories")
    return runs


def snapshot_files(paths):
    files = {}
    for path in paths:
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        for item in candidates:
            if item.is_file():
                files[item.relative_to(ROOT).as_posix()] = sha256(item)
    return files


def hash_guard(files):
    if any(not (ROOT / path).is_file() or sha256(ROOT / path) != digest
           for path, digest in files.items()):
        raise ValueError("Frozen source or preserved original artifact changed")


def prepare(manifest_path, expected_sha256):
    manifest_path = Path(manifest_path).resolve()
    if sha256(manifest_path) != expected_sha256:
        raise ValueError("Interruption manifest hash mismatch")
    manifest = read(manifest_path)
    directory = ROOT / "results/loop-stage-c" / ORIGIN
    if (manifest["group"] != str(directory) or manifest["recorded_pid"] != ORIGINAL_PID
            or manifest["pid_exists"] is not False or manifest["active_experiment_processes"]
            or manifest["shared_lock"] != str(ORIGINAL_PID)):
        raise ValueError("Explicit inspected interruption is required")
    continuation = directory / "continuation-v1"
    claim = ROOT / ".cache/loop-stage-c-recovery-v1/execution.json"
    if continuation.exists() or claim.exists():
        raise FileExistsError("Manual continuation was already claimed; no automatic retry")
    original = read(directory / "plan.json")
    current, configs = stage_c.prepare()
    source_guard(original, current)
    git_amendment_guard(original["git"], current["git"])
    runs = history_guard(manifest, original, directory)
    cache = ROOT / ".cache/loop-stage-c-v1"
    if int((cache / "driver.pid").read_text()) != ORIGINAL_PID:
        raise ValueError("Original driver PID record changed")
    lock_bytes = (ROOT / ".cache/loop-pilot.lock").read_bytes()
    if lock_bytes != str(ORIGINAL_PID).encode():
        raise ValueError("Unexpected stale lock bytes")
    lock_guard(lock_bytes)
    original_files = snapshot_files([directory, *runs, cache / "execution.json",
                                     cache / "driver.log", cache / "driver.pid"])
    source_files = {**current["source_sha256"], **snapshot_files(
        [ROOT / path for path in sorted(RECOVERY_FILES)])}
    source_files.update({job["config"]: job["config_sha256"] for job in current["schedule"]})
    plan = {"kind": "loop-evidence-stage-c-manual-continuation-v1",
            "origin": str(directory), "origin_git": original["git"], "git": current["git"],
            "directory": str(continuation), "interruption_manifest_sha256": expected_sha256,
            "interruption_inspected_utc": manifest["checked_utc"],
            "interrupted_job": {**original["schedule"][9],
                                "classification": "infrastructure_interruption_unavailable",
                                "run_path": str(runs[-1]), "retry": False},
            "preserved_completed_jobs": list(range(1, 10)),
            "schedule": original["schedule"][10:], "attempts": 38, "retry_policy": "none",
            "models": original["models"], "packages": original["packages"],
            "input_sha256": original["input_sha256"], "evaluator": original["evaluator"],
            "runtime": current["runtime"], "source_sha256": source_files,
            "original_file_sha256": original_files, "holdout": False}
    return plan, configs, manifest_path, lock_bytes


def claim_and_lock(plan, manifest_path, lock_bytes):
    """Single-use claim first, then archive the verified stale lock before replacing it."""
    if sha256(manifest_path) != plan["interruption_manifest_sha256"]:
        raise ValueError("Interruption manifest changed after preparation")
    if git_state(ROOT) != plan["git"]:
        raise ValueError("Recovery Git state changed after preparation")
    hash_guard(plan["source_sha256"])
    hash_guard(plan["original_file_sha256"])
    lock_guard(lock_bytes)
    claim = ROOT / ".cache/loop-stage-c-recovery-v1/execution.json"
    claim.parent.mkdir(parents=True, exist_ok=True)
    with claim.open("x", encoding="utf-8") as stream:
        json.dump({k: plan[k] for k in ("kind", "git", "directory", "attempts",
                                      "retry_policy", "interruption_manifest_sha256")}, stream)
    directory = Path(plan["directory"])
    directory.mkdir()
    write_json(directory / "plan.json", plan)
    (directory / "driver.py").write_bytes(Path(__file__).read_bytes())
    (directory / "interruption-manifest.json").write_bytes(manifest_path.read_bytes())
    (directory / "original-shared-lock.bin").write_bytes(lock_bytes)
    lock_guard(lock_bytes)
    lock = ROOT / ".cache/loop-pilot.lock"
    lock.unlink()
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    return directory, lock


def main(execute, manifest_path, expected_sha256):
    plan, configs, manifest_path, lock_bytes = prepare(manifest_path, expected_sha256)
    if not execute:
        print(json.dumps(plan, indent=2))
        return
    directory, lock = claim_and_lock(plan, manifest_path, lock_bytes)
    outcomes = []
    try:
        write_json(directory / "progress.json", {"status": "running", "outcomes": outcomes})
        print("STAGE_C_CONTINUATION_DIRECTORY", directory, flush=True)
        for job in plan["schedule"]:
            if git_state(ROOT) != plan["git"]:
                raise ValueError("Recovery Git state changed during execution")
            hash_guard(plan["source_sha256"])
            config = configs[job["seed"], job["n"]]
            stage_c.runtime_check(config, plan["models"])
            write_json(directory / "current.json", job)
            print("START", json.dumps(job), flush=True)
            outcome = stage_c.run_job(job, config, directory)
            outcomes.append(outcome)
            write_json(directory / "progress.json", {"status": "running", "outcomes": outcomes})
            print("FINISHED", json.dumps(outcome), flush=True)
            if (outcome.get("execution_error") or outcome.get("analysis_error")
                    or outcome.get("metrics", {}).get("analysis_error")):
                raise ValueError("Attempt preserved; structural failure needs inspection")
        hash_guard(plan["original_file_sha256"])
        write_json(directory / "progress.json", {"status": "completed", "outcomes": outcomes,
                                                  "original_artifacts_unchanged": True})
        print("STAGE_C_CONTINUATION_COMPLETED", directory, flush=True)
    except BaseException as exc:
        write_json(directory / "progress.json", {"status": "failed", "outcomes": outcomes,
                                                  "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        if lock.exists() and lock.read_text() == str(os.getpid()):
            lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interruption-manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    main(args.run, args.interruption_manifest, args.manifest_sha256)
