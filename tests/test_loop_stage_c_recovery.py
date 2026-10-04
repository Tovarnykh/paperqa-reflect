import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from paperqa_reflect.config import write_json
from paperqa_reflect.data import sha256

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("recovery", SCRIPTS / "continue_loop_stage_c.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


@pytest.fixture
def saved_interruption(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    jobs = recovery.stage_c.schedule([f"q{i}" for i in range(8)])
    for job in jobs:
        config = tmp_path / job["config"]
        config.parent.mkdir(exist_ok=True)
        config.write_text(json.dumps({"seed": job["seed"], "n": job["n"]}))
        job["config_sha256"] = sha256(config)
    old_git = {"head": recovery.ORIGINAL_HEAD, "status": ""}
    new_git = {"head": "recovery-commit", "status": ""}
    original = {"kind": "loop-evidence-stage-c-v1", "git": old_git, "schedule": jobs,
                "attempts": 48, "retry_policy": "none", "source_sha256": {},
                "models": {}, "packages": {}, "input_sha256": {}, "evaluator": {},
                "runtime": {}}
    current = {**original, "git": new_git}
    group = tmp_path / "results/loop-stage-c" / recovery.ORIGIN
    write_json(group / "plan.json", original)
    write_json(group / "current.json", jobs[9])
    outcomes, log_lines, runs = [], [], []
    for job in jobs[:10]:
        run = tmp_path / "results/runs" / f"saved-{job['job']}"
        runs.append(run)
        records = [{"id": job["question_id"], "status": "fail" if job["job"] == 1
                    else "success"}] if job["job"] < 10 else []
        write_json(run / "summary.json", {"records": records})
        (group / f"job-{job['job']:02d}.log").write_text(f"Run: {run}\n")
        log_lines.append("START " + json.dumps(job))
        if job["job"] < 10:
            outcome = {**job, "run_path": str(run), "metrics": {"status": records[0]["status"]}}
            outcomes.append(outcome)
            log_lines.append("FINISHED " + json.dumps(outcome))
        else:
            qdir = run / job["question_id"]
            qdir.mkdir()
            (qdir / "events.jsonl").write_text('{"kind":"action"}\n')
    write_json(group / "progress.json", {"status": "running", "outcomes": outcomes})
    cache = tmp_path / ".cache/loop-stage-c-v1"
    write_json(cache / "execution.json", {"directory": str(group), "git": old_git,
                                          "attempts": 48, "retry_policy": "none"})
    (cache / "driver.log").write_text("\n".join(log_lines) + "\n")
    (cache / "driver.pid").write_text(str(recovery.ORIGINAL_PID))
    (tmp_path / ".cache/loop-pilot.lock").write_bytes(str(recovery.ORIGINAL_PID).encode())
    for name in recovery.RECOVERY_FILES:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("recovery source\n")
    manifest = {"group": str(group), "progress_sha256": sha256(group / "progress.json"),
                "completed": 9, "current": jobs[9], "recorded_pid": recovery.ORIGINAL_PID,
                "pid_exists": False, "active_experiment_processes": [],
                "shared_lock": str(recovery.ORIGINAL_PID),
                "current_run": {"path": str(runs[-1])},
                "checked_utc": "2026-10-04T22:10:59.254996+00:00"}
    path = tmp_path / "interruption.json"
    write_json(path, manifest)
    configs = {(j["seed"], j["n"]): object() for j in jobs}
    monkeypatch.setattr(recovery.stage_c, "prepare", lambda: (current, configs))
    monkeypatch.setattr(recovery, "git_amendment_guard", lambda *_: None)
    monkeypatch.setattr(recovery, "process_guard", lambda *_: None)
    monkeypatch.setattr(recovery, "git_state", lambda _: new_git)
    monkeypatch.setattr(recovery.stage_c, "runtime_check", lambda *_: None)
    return SimpleNamespace(root=tmp_path, group=group, cache=cache, runs=runs, jobs=jobs,
                           original=original, current=current, manifest=path,
                           digest=sha256(path), configs=configs)


def test_dry_plan_keeps_original_files_and_only_never_started_jobs(saved_interruption, capsys):
    saved = saved_interruption
    before = recovery.snapshot_files([saved.root])
    recovery.main(False, saved.manifest, saved.digest)
    plan = json.loads(capsys.readouterr().out)
    assert plan["schedule"] == saved.jobs[10:]
    assert plan["attempts"] == 38
    assert plan["interrupted_job"]["job"] == 10
    assert plan["interrupted_job"]["retry"] is False
    assert plan["preserved_completed_jobs"] == list(range(1, 10))
    assert recovery.snapshot_files([saved.root]) == before


def test_unrecorded_attempt_cannot_be_reclassified_as_unstarted(saved_interruption):
    saved = saved_interruption
    with (saved.cache / "driver.log").open("a") as stream:
        stream.write("START " + json.dumps(saved.jobs[10]) + "\n")
    with pytest.raises(ValueError, match="Driver history"):
        recovery.prepare(saved.manifest, saved.digest)


@pytest.mark.parametrize("artifact", ["response.json", "grade.json"])
def test_completed_interrupted_child_requires_new_inspection(saved_interruption, artifact):
    saved = saved_interruption
    write_json(saved.runs[-1] / saved.jobs[9]["question_id"] / artifact, {})
    with pytest.raises(ValueError, match="completed response or grade"):
        recovery.prepare(saved.manifest, saved.digest)


def test_missing_original_progress_attestation_rejects_recovery(saved_interruption):
    saved = saved_interruption
    with pytest.raises(ValueError, match="manifest hash"):
        recovery.prepare(saved.manifest, "wrong")
    (saved.group / "progress.json").write_text("{}")
    with pytest.raises(ValueError, match="progress differs"):
        recovery.prepare(saved.manifest, saved.digest)


@pytest.mark.parametrize("field", ["source_sha256", "input_sha256", "models", "packages",
                                  "schedule", "evaluator", "attempts", "retry_policy"])
def test_original_frozen_conditions_cannot_change(saved_interruption, field):
    original = saved_interruption.original
    changed = copy.deepcopy(original)
    changed[field] = "drift"
    with pytest.raises(ValueError, match=field):
        recovery.source_guard(original, changed)


def test_unstarted_job_artifact_blocks_recovery(saved_interruption):
    saved = saved_interruption
    (saved.group / "job-11.log").write_text("partial")
    with pytest.raises(ValueError, match="unstarted job"):
        recovery.prepare(saved.manifest, saved.digest)


def test_manual_execution_preserves_failed_and_interrupted_originals(saved_interruption, monkeypatch):
    saved = saved_interruption
    original_files = recovery.snapshot_files([saved.group, *saved.runs, saved.cache])
    called = []

    def run_job(job, *_):
        called.append(job["job"])
        return {**job, "metrics": {"status": "success"}}

    monkeypatch.setattr(recovery.stage_c, "run_job", run_job)
    recovery.main(True, saved.manifest, saved.digest)
    assert called == list(range(11, 49))
    recovery.hash_guard(original_files)
    assert recovery.read(saved.runs[0] / "summary.json")["records"][0]["status"] == "fail"
    assert recovery.read(saved.runs[-1] / "summary.json")["records"] == []
    continuation = saved.group / "continuation-v1"
    progress = recovery.read(continuation / "progress.json")
    assert progress["status"] == "completed"
    assert progress["original_artifacts_unchanged"] is True
    assert [row["job"] for row in progress["outcomes"]] == list(range(11, 49))
    assert (continuation / "original-shared-lock.bin").read_bytes() == b"1904071"
    assert not (saved.root / ".cache/loop-pilot.lock").exists()
    with pytest.raises(FileExistsError, match="already claimed"):
        recovery.main(True, saved.manifest, saved.digest)
    assert called == list(range(11, 49))


def test_continuation_structural_failure_is_preserved_without_retry(saved_interruption, monkeypatch):
    saved = saved_interruption
    calls = []

    def run_job(job, *_):
        calls.append(job["job"])
        return {**job, "analysis_error": "No structured outcome"}

    monkeypatch.setattr(recovery.stage_c, "run_job", run_job)
    with pytest.raises(ValueError, match="structural failure"):
        recovery.main(True, saved.manifest, saved.digest)
    assert calls == [11]
    progress = recovery.read(saved.group / "continuation-v1/progress.json")
    assert progress["status"] == "failed"
    assert progress["outcomes"][0]["job"] == 11
    assert recovery.read(saved.group / "progress.json")["status"] == "running"
    with pytest.raises(FileExistsError):
        recovery.main(True, saved.manifest, saved.digest)
    assert calls == [11]


def test_per_job_guard_stops_source_mutation(saved_interruption, monkeypatch):
    saved = saved_interruption
    calls = []

    def run_job(job, *_):
        calls.append(job["job"])
        (saved.root / "README.md").write_text("changed during execution")
        return {**job, "metrics": {"status": "success"}}

    monkeypatch.setattr(recovery.stage_c, "run_job", run_job)
    with pytest.raises(ValueError, match="Frozen source"):
        recovery.main(True, saved.manifest, saved.digest)
    assert calls == [11]


@pytest.mark.parametrize("state", ["Z", "S"])
def test_existing_zombie_or_reused_pid_is_never_removed(tmp_path, state):
    proc = tmp_path / "proc"
    entry = proc / "1904071"
    entry.mkdir(parents=True)
    (entry / "status").write_text(f"State: {state}")
    with pytest.raises(ValueError, match="PID still exists"):
        recovery.process_guard(1904071, proc)
    assert entry.exists()


@pytest.mark.parametrize("argv", [b"python\0scripts/run_loop_stage_b.py\0--run\0",
                                  b"python\0-m\0paperqa_reflect.cli\0run\0"])
def test_other_active_experiment_blocks_lock_cleanup(tmp_path, argv):
    proc = tmp_path / "proc"
    entry = proc / str(os.getpid() + 1000)
    entry.mkdir(parents=True)
    (entry / "cmdline").write_bytes(argv)
    with pytest.raises(ValueError, match="Active experiment"):
        recovery.process_guard(1904071, proc)


def test_changed_shared_lock_is_preserved(saved_interruption):
    saved = saved_interruption
    lock = saved.root / ".cache/loop-pilot.lock"
    lock.write_bytes(b"different owner")
    with pytest.raises(ValueError, match="lock changed"):
        recovery.lock_guard(b"1904071")
    assert lock.read_bytes() == b"different owner"


@pytest.mark.parametrize("changed", ["manifest", "lock", "original"])
def test_drift_after_preparation_cannot_claim_or_clear_lock(saved_interruption, changed):
    saved = saved_interruption
    plan, _, manifest, lock_bytes = recovery.prepare(saved.manifest, saved.digest)
    lock = saved.root / ".cache/loop-pilot.lock"
    path = {"manifest": manifest, "lock": lock,
            "original": saved.group / "progress.json"}[changed]
    path.write_bytes(b"changed")
    expected_lock = lock.read_bytes()
    with pytest.raises(ValueError):
        recovery.claim_and_lock(plan, manifest, lock_bytes)
    assert lock.read_bytes() == expected_lock
    assert not (saved.root / ".cache/loop-stage-c-recovery-v1/execution.json").exists()


def test_git_allowlist_rejects_inference_source_change(monkeypatch):
    calls = []

    def git(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="src/paperqa_reflect/runner.py\n")

    monkeypatch.setattr(recovery.subprocess, "run", git)
    with pytest.raises(ValueError, match="allowlist"):
        recovery.git_amendment_guard({"head": recovery.ORIGINAL_HEAD, "status": ""},
                                     {"head": "recovery-commit", "status": ""})
    assert len(calls) == 2
