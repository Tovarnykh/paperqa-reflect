import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("stage_b", SCRIPTS / "run_loop_stage_b.py")
stage_b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_b)


def test_schedule_covers_all_cells_and_reverses_each_pair():
    ids = [f"q{i}" for i in range(8)]
    jobs = stage_b.schedule(ids)
    assert len(jobs) == 32
    assert len({(j["question_id"], j["seed"], j["n"]) for j in jobs}) == 32
    for index, qid in enumerate(ids):
        pairs = [[j["n"] for j in jobs if j["question_id"] == qid and j["seed"] == seed]
                 for seed in (42, 43)]
        assert pairs[0] == list(reversed(pairs[1]))
        assert pairs[0] == ([1, 3] if index % 2 == 0 else [3, 1])
    first_arms = Counter(j["n"] for j in jobs[::2])
    assert first_arms == {1: 8, 3: 8}


@pytest.mark.parametrize("ids", [list(range(7)), list(range(9)), [0] * 8])
def test_invalid_question_set_cannot_launch(ids):
    with pytest.raises(ValueError):
        stage_b.schedule(ids)


def test_unstructured_failed_attempt_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_b, "ROOT", tmp_path)
    log = tmp_path / "failed.log"
    log.write_text("Failed before run directory\n")
    result = stage_b.job_outcome({"job": 1}, log, 1, 12.5, "failure")
    assert result["exit_code"] == 1
    assert result["wall_seconds"] == 12.5
    assert result["execution_error"] == "failure"
    assert result["analysis_error"]


def test_unsure_structured_attempt_is_a_result_not_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_b, "ROOT", tmp_path)
    path = tmp_path / "results/runs/example"
    path.mkdir(parents=True)
    log = tmp_path / "unsure.log"
    log.write_text(f"Run: {path}\n")
    monkeypatch.setattr(stage_b, "analyze", lambda path: {"status": "unsure"})
    result = stage_b.job_outcome({"job": 1}, log, 1, 45)
    assert result["metrics"]["status"] == "unsure"
    assert "analysis_error" not in result
