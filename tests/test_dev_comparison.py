import pytest

from paperqa_reflect import dev_comparison as d


@pytest.mark.parametrize("failed_arm", ["B1", "B2"])
def test_failed_review_preserves_original_and_other_arm_can_run(tmp_path, monkeypatch, failed_arm):
    item = {
        "question": {"question": "Which?", "options": {"A": "X"}},
        "original_answer": "X (pqac-abc).\nFinal answer: A",
        "sources": {"pqac-abc": "X"},
    }

    def review(*args):
        if failed_arm == "B2":
            raise ValueError("incomplete verifier feedback")
        return {"claim_checks": []}

    def local(*args):
        if args[3] == "ordinary_review":
            if failed_arm == "B1":
                return {"status": "not_checked"}
            return {"status": "checked", "value": {"issues": []}}
        return {"status": "checked", "value": {"answer": item["original_answer"]}}

    monkeypatch.setattr(d, "verifier_feedback", review)
    monkeypatch.setattr(d.r, "local_json", local)
    failed = d.run_arm(None, {}, tmp_path / failed_arm, item, failed_arm)
    assert failed["status"] == "fallback_original"
    assert failed["answer"] == item["original_answer"]
    other = "B2" if failed_arm == "B1" else "B1"
    assert d.run_arm(None, {}, tmp_path / other, item, other)["status"] == "revised"


def test_packet_contains_every_dev_question_and_no_gold(tmp_path):
    if not (d.ROOT / "results/runs" / d.RUN).exists():
        pytest.skip("Saved baseline run archive is not part of Git")
    answers = d.prepare(tmp_path / "input.json")
    assert len(answers) == 8
    assert len({x["question_id"] for x in answers}) == 8
    assert sum(x["arm_order"][0] == "B1" for x in answers) == 4
    assert all(set(x["question"]) == {"question", "options"} for x in answers)
    with pytest.raises(FileExistsError):
        d.prepare(tmp_path / "input.json")
