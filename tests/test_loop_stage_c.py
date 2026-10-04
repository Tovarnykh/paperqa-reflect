import importlib.util
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from paperqa_reflect.config import build_settings, load_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("stage_c", SCRIPTS / "run_loop_stage_c.py")
stage_c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_c)


def test_schedule_covers_every_cell_with_balanced_frozen_orders():
    ids = [f"q{i}" for i in range(8)]
    jobs = stage_c.schedule(ids)
    assert len(jobs) == 48
    assert [job["job"] for job in jobs] == list(range(1, 49))
    assert {(j["question_id"], j["seed"], j["n"]) for j in jobs} == set(
        itertools.product(ids, (42, 43), (1, 3, 8)))
    blocks = [jobs[offset:offset + 3] for offset in range(0, 48, 3)]
    orders = Counter(tuple(j["n"] for j in block) for block in blocks)
    assert set(orders) == set(itertools.permutations((1, 3, 8)))
    assert sorted(orders.values()) == [2, 2, 3, 3, 3, 3]
    for number, block in enumerate(blocks, 1):
        assert {j["block"] for j in block} == {number}
        assert [j["position"] for j in block] == [1, 2, 3]
        assert len({(j["question_id"], j["seed"]) for j in block}) == 1
    for position in (1, 2, 3):
        counts = Counter(j["n"] for j in jobs if j["position"] == position)
        assert sorted(counts.values()) == [5, 5, 6]
    for qid in ids:
        orders = [[j["n"] for j in jobs if j["question_id"] == qid and j["seed"] == seed]
                  for seed in (42, 43)]
        assert orders[0] != orders[1]


@pytest.mark.parametrize("ids", [list(range(7)), list(range(9)), [0] * 8])
def test_invalid_question_set_cannot_launch(ids):
    with pytest.raises(ValueError, match="eight unique"):
        stage_c.schedule(ids)


@pytest.mark.parametrize("seed", [42, 43])
def test_actual_configs_change_only_controller_visibility(seed, tmp_path):
    original = load_config(ROOT / f"configs/uia-qwen38-dev-s{seed}.json")
    settings = {}
    for n in (1, 3, 8):
        config = load_config(ROOT / f"configs/loop-evidence-n{n}-s{seed}.json")
        stage_c.check_config(config, original, seed, n)
        settings[n] = build_settings(config, tmp_path, tmp_path / "index",
                                     tmp_path / "manifest").model_dump(exclude={"md5"})
    stage_c.check_settings(settings)
    assert settings[8]["answer"]["answer_max_sources"] == 5


@pytest.mark.parametrize("change", [
    {"agent_evidence_n": 3}, {"split": "holdout"}, {"seed": 43},
    {"summary_model": "another-model"}, {"context_tokens": 32768},
    {"question_timeout_seconds": 3600},
])
def test_schedule_config_guard_rejects_drift(change):
    original = load_config(ROOT / "configs/uia-qwen38-dev-s42.json")
    config = load_config(ROOT / "configs/loop-evidence-n8-s42.json").model_copy(update=change)
    with pytest.raises(ValueError):
        stage_c.check_config(config, original, 42, 8)


def test_settings_guard_rejects_hidden_answer_change():
    settings = {n: {"agent": {"agent_evidence_n": n}, "answer": {"max_sources": 5}}
                for n in (1, 3, 8)}
    settings[8]["answer"]["max_sources"] = 8
    with pytest.raises(ValueError, match="beyond agent_evidence_n"):
        stage_c.check_settings(settings)


def test_persistent_claim_blocks_second_execution_and_preserves_first(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_c, "ROOT", tmp_path)
    plan = {"kind": "loop-evidence-stage-c-v1", "git": {"commit": "frozen"}, "attempts": 48}
    first = tmp_path / "results/loop-stage-c/first"
    stage_c.claim_execution(plan, first)
    claim = tmp_path / ".cache/loop-stage-c-v1/execution.json"
    initial = claim.read_bytes()
    with pytest.raises(FileExistsError):
        stage_c.claim_execution(plan, tmp_path / "results/loop-stage-c/second")
    assert claim.read_bytes() == initial
    assert json.loads(initial)["directory"] == str(first)


def test_dirty_tree_cannot_prepare_or_start(monkeypatch):
    monkeypatch.setattr(stage_c, "git_state", lambda _: {"status": " M script.py"})
    with pytest.raises(ValueError, match="clean tree"):
        stage_c.prepare()


def test_changed_evaluator_manifest_cannot_prepare(monkeypatch):
    monkeypatch.setattr(stage_c, "git_state", lambda _: {"status": ""})
    monkeypatch.setattr(stage_c, "sha256", lambda _: "changed")
    with pytest.raises(ValueError, match="Frozen evaluator"):
        stage_c.prepare()


def test_dry_plan_cannot_claim_or_execute(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stage_c, "ROOT", tmp_path)
    monkeypatch.setattr(stage_c, "prepare", lambda: ({"attempts": 48}, {}))
    stage_c.main(False)
    assert json.loads(capsys.readouterr().out) == {"attempts": 48}
    assert not (tmp_path / ".cache").exists()


def test_structured_unsure_is_preserved_without_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_c, "ROOT", tmp_path)
    run = tmp_path / "results/runs/example"
    run.mkdir(parents=True)
    log = tmp_path / "job.log"
    log.write_text(f"Run: {run}\n")
    monkeypatch.setattr(stage_c, "analyze", lambda _: {"status": "unsure"})
    outcome = stage_c.job_outcome({"job": 1}, log, 1, 12)
    assert outcome["metrics"]["status"] == "unsure"
    assert "analysis_error" not in outcome


def test_structural_failure_stops_series_without_retry_and_keeps_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_c, "ROOT", tmp_path)
    git = {"commit": "frozen", "status": ""}
    jobs = [{"job": number, "config": "config.json", "config_sha256": "fixed", "seed": 42,
             "n": 8} for number in (1, 2)]
    plan = {"kind": "loop-evidence-stage-c-v1", "git": git, "attempts": 48,
            "schedule": jobs, "source_sha256": {}, "models": {}}
    monkeypatch.setattr(stage_c, "prepare", lambda: (plan, {(42, 8): object()}))
    monkeypatch.setattr(stage_c, "git_state", lambda _: git)
    monkeypatch.setattr(stage_c, "sha256", lambda _: "fixed")
    monkeypatch.setattr(stage_c, "runtime_check", lambda *_: None)
    called = []

    def failed_job(job, *_):
        called.append(job["job"])
        return {**job, "analysis_error": "No complete structured run"}

    monkeypatch.setattr(stage_c, "run_job", failed_job)
    with pytest.raises(ValueError, match="structural failure"):
        stage_c.main(True)
    assert called == [1]
    assert not (tmp_path / ".cache/loop-pilot.lock").exists()
    claim = json.loads((tmp_path / ".cache/loop-stage-c-v1/execution.json").read_text())
    progress = json.loads((Path(claim["directory"]) / "progress.json").read_text())
    assert progress["status"] == "failed"
    assert [row["job"] for row in progress["outcomes"]] == [1]
    with pytest.raises(FileExistsError):
        stage_c.main(True)
    assert called == [1]
