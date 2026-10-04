import json

import pytest

from paperqa_reflect import revision_report as r
from paperqa_reflect.verifier import digest, load_packet, write_json


def synthetic_run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    write_json(run / "run.json", {"status": "completed"})
    write_json(
        run / "input.json",
        {
            "answers": [
                {
                    "answer_id": "dev-01",
                    "sources": {"pqac-abc": "X is 1."},
                    "source_review_path": "original.json",
                    "source_review_sha256": "placeholder",
                }
            ]
        },
    )
    for variant in ["B0", "B1", "B2"]:
        d = run / "dev-01" / variant
        d.mkdir(parents=True)
        write_json(
            d / "answer.json",
            {"answer": "X is 1 (pqac-abc).\nFinal answer: A", "status": "original"},
        )
        write_json(d / "sentence-units.json", [])
        write_json(
            d / "claims.json",
            [
                {
                    "case_id": "claim-001",
                    "claim": "X is 1.",
                    "passage_ids": ["pqac-abc"],
                    "answer_quote": "X is 1",
                },
                {
                    "case_id": "claim-002",
                    "claim": "Y is 2.",
                    "passage_ids": [],
                    "answer_quote": "Y is 2",
                },
            ],
        )
    return run


def test_export_keeps_uncited_claims_in_mapping_without_sending_them(tmp_path):
    run = synthetic_run(tmp_path)
    packet = tmp_path / "packet"
    result = r.export(run, packet)
    assert result == {"total_claims": 6, "judge_claims": 3, "no_citation": 3}
    cases, _ = load_packet(packet)
    assert len(cases) == 3
    assert all(set(c) == {"case_id", "claim", "passage_ids"} for c in cases)
    assert len(json.loads((packet / "mapping.json").read_text())["claims"]) == 6
    with pytest.raises(FileExistsError):
        r.export(run, packet)


def test_metric_denominator_includes_uncited_unchecked_and_handles_empty():
    result = r.summarize_rows(
        [{"label": x} for x in ["supported", "no_citation", "not_checked", "insufficient"]]
    )
    assert result["supported_fraction_lower"] == 0.25
    assert result["supported_fraction_upper"] == 0.5
    assert r.summarize_rows([])["supported_fraction_upper"] == 0


def test_reporting_uses_frozen_inputs_and_keeps_unjudged_claims(tmp_path, monkeypatch):
    run = synthetic_run(tmp_path)
    original = tmp_path / "original.json"
    write_json(original, {"reference": {"answer": "A"}})
    payload = json.loads((run / "input.json").read_text())
    payload["answers"][0]["source_review_sha256"] = digest(original.read_bytes())
    write_json(run / "input.json", payload)
    monkeypatch.setattr(r, "ROOT", tmp_path)
    packet = tmp_path / "packet"
    r.export(run, packet)
    plan = {
        "packet_hashes": {
            n: digest((packet / n).read_bytes())
            for n in ["manifest.json", "cases.jsonl", "passages.jsonl"]
        },
        "rows": [
            {"case_id": f"dev-01-{v}-claim-001", "anonymous_id": f"item-{i}"}
            for i, v in enumerate(["B0", "B1", "B2"])
        ],
    }
    monkeypatch.setattr(r, "load_plan", lambda _: (plan, {"model": "external"}, []))
    judge = tmp_path / "judge"
    judge.mkdir()
    write_json(
        judge / "item-0.result.json",
        {"status": "checked", "verdict": {"label": "supported", "explanation": "exact"}},
    )
    result = r.report(run, packet, judge, tmp_path / "report")
    a = result["answers"]
    assert len(a) == 3 and all(row["key_match"] for row in a)
    assert a[0]["supported_fraction_lower"] == 0.5
    assert a[1]["labels"] == {"not_checked": 1, "no_citation": 1}
    assert not result["completeness_assessed"]
    (run / "dev-01/B0/answer.json").write_text("changed")
    with pytest.raises(ValueError, match="Source revision run changed"):
        r.report(run, packet, judge, tmp_path / "bad")


def test_incomplete_run_cannot_look_like_successful_comparison(tmp_path):
    run = synthetic_run(tmp_path)
    write_json(run / "run.json", {"status": "interrupted"})
    with pytest.raises(ValueError, match="completed"):
        r.export(run, tmp_path / "packet")


def test_added_work_excludes_outcome_only_extraction(tmp_path):
    paths = [
        "B0/extraction",
        "B1/revision",
        "B1/extraction",
        "B2/revision",
        "B2/extraction",
        "ordinary-review",
        "verification/claim-001",
    ]
    for name in paths:
        path = tmp_path / "dev-01" / name
        path.mkdir(parents=True)
        write_json(
            path / "result.json",
            {
                "attempts": 1,
                "seconds": 10,
                "usage": {
                    "prompt_eval_count": 100,
                    "eval_count": 20,
                    "load_duration": 1_000_000_000,
                },
            },
        )
    b1 = r.added_work(tmp_path, "dev-01", "B1")
    b2 = r.added_work(tmp_path, "dev-01", "B2")
    assert b1["calls"] == 2 and b1["seconds"] == 20
    assert b2["calls"] == 3 and b2["input_tokens"] == 300 and b2["load_seconds"] == 3
    assert r.added_work(tmp_path, "dev-01", "B0")["seconds"] == 0


@pytest.mark.parametrize("defect", [None, "claim", "scope", "duplicate", "missing", "profile"])
def test_reused_judgments_require_exact_input_scope_and_full_unique_coverage(
    tmp_path, monkeypatch, defect
):
    run = synthetic_run(tmp_path)
    packet = tmp_path / "packet"
    r.export(run, packet)
    cases, _ = load_packet(packet)
    plans, paths = {}, []
    for i, case in enumerate(cases):
        path = tmp_path / f"plan-{i}"
        path.mkdir()
        paths.append(path)
        payload = {"claim": case["claim"], "passages": [{"passage_id": "s", "text": "X is 1."}]}
        row = {
            "case_id": case["case_id"],
            "anonymous_id": "item-1",
            "passage_mapping": {"s": "pqac-abc"},
        }
        config = {"model": "external"}
        if i == 1:
            if defect == "claim":
                payload["claim"] = "Changed assertion."
            if defect == "scope":
                payload["passages"][0]["text"] = "Changed source."
            if defect == "duplicate":
                row["case_id"] = cases[0]["case_id"]
            if defect == "profile":
                config["model"] = "another"
        plans[path] = (
            {"rows": [row]},
            config,
            {"item-1": {"input": [{"content": json.dumps(payload)}]}},
        )
    monkeypatch.setattr(r, "load_plan", lambda path: plans[path])
    if defect == "missing":
        paths.pop()
    if defect:
        with pytest.raises(ValueError):
            r.merge_judgments(paths, packet)
    else:
        _, judgments = r.merge_judgments(paths, packet)
        assert len(judgments) == 3 and all(r["status"] == "not_run" for r in judgments.values())
