import json

import pytest
from jsonschema import validate

from paperqa_reflect import pairwise as p
from paperqa_reflect.verifier import read_json, write_json


def plan(tmp_path):
    p.controls(tmp_path / "controls")
    return p.build_plan(
        tmp_path / "controls",
        p.ROOT / "configs/judge-openai-revision-dev-v1.json",
        tmp_path / "plans",
    )


def test_blinding_mirrored_order_and_immutable_mapping(tmp_path):
    path = plan(tmp_path)
    frozen, _, requests = p.load_plan(path)
    assert len(requests) == 8
    assert "expected" not in json.dumps(requests) and '"good"' not in json.dumps(requests)
    mappings = {x["case_id"]: x for x in read_json(path / "mapping.json")}
    for row in frozen["rows"]:
        slot = next(k for k, v in mappings[row["case_id"]]["slots"].items() if v == "good")
        write_json(
            path / (row["anonymous_id"] + ".result.json"),
            {
                "status": "checked",
                "verdict": {
                    "winner": "tie" if row["case_id"].startswith("equivalent") else slot,
                },
            },
        )
    assert p.assess(path)["control_gate_passed"]
    row = next(x for x in frozen["rows"] if x["case_id"] == "number-1")
    # A position-biased answer must produce disagreement, not a hidden majority vote.
    write_json(
        path / (row["anonymous_id"] + ".result.json"),
        {
            "status": "checked",
            "verdict": {"winner": "A"},
        },
    )
    assessment = p.assess(path)
    assert not assessment["control_gate_passed"]
    assert assessment["outcomes"]["order_unstable"] == 1
    (path / "mapping.json").write_text("[]")
    with pytest.raises(ValueError, match="mapping changed"):
        p.load_plan(path)


@pytest.mark.parametrize("bad", ["source", "answer", "missing_loser_issue"])
def test_rejects_unanchored_judgments(tmp_path, monkeypatch, bad):
    path = plan(tmp_path)
    _, config, requests = p.load_plan(path)
    request = next(
        r
        for r in requests.values()
        if json.loads(r["input"][0]["content"])["question"] == "How many samples passed?"
    )
    case = json.loads(request["input"][0]["content"])
    issue = {
        "answer": "B",
        "category": "factual",
        "answer_quote": case["answers"]["B"],
        "source_id": "pqac-s1",
        "source_quote": case["sources"]["pqac-s1"],
        "explanation": "Wrong count",
    }
    if bad in ["source", "answer"]:
        issue[bad + "_quote"] = "NOT PRESENT"
    verdict = {
        "case_id": case["case_id"],
        "winner": "A",
        "reason": "Count matters",
        "issues": [] if bad == "missing_loser_issue" else [issue],
    }
    monkeypatch.setattr(p.judge, "response_text", lambda *a: json.dumps(verdict))
    with pytest.raises(ValueError):
        p.parse_response({}, request, config)


def test_coverage_schema_accepts_absent_answer_span_without_emptying_evidence():
    verdict = {
        "case_id": "c",
        "winner": "A",
        "reason": "B omits temperature",
        "issues": [
            {
                "answer": "B",
                "category": "coverage",
                "answer_quote": "",
                "source_id": "pqac-s1",
                "source_quote": "The temperature was 20 C.",
                "explanation": "Requested temperature absent",
            }
        ],
    }
    validate(verdict, p.SCHEMA)
    assert p.SCHEMA_V1["properties"]["issues"]["items"]["properties"]["source_id"] == {
        "type": "string",
        "minLength": 1,
    }
