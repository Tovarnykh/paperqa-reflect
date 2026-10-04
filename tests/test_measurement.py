import json
import platform
from pathlib import Path

import httpx
import pytest

from paperqa_reflect import judge
from paperqa_reflect import measurement as m
from paperqa_reflect.verifier import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
CASE = {
    "case_id": "original",
    "source_text": "The box consists of a battery and a cable.",
    "claims": [
        {"claim_id": "c001", "text": "The box consists of a battery.", "quote": "a battery"}
    ],
}


def fixture_plan(tmp_path):
    packet = tmp_path / "packet"
    m.packet_write(packet, [CASE], {"expected": "LABEL_SENTINEL"})
    config = read_json(ROOT / "configs/judge-openai-revision-dev-v1.json")
    config["execution_host"] = platform.node()
    write_json(tmp_path / "config.json", config)
    path = m.build_plan(packet, tmp_path / "config.json", tmp_path / "plans")
    return path, config


def verdict(case_id="item-001"):
    return {
        "case_id": case_id,
        "claims": [
            {
                "claim_id": "c001",
                "fidelity": "distorted",
                "source_quote": CASE["source_text"],
                "reason": "Exhaustive composition loses the cable.",
            }
        ],
        "coverage": "incomplete",
        "omissions": [
            {"source_quote": "a cable", "reason": "No faithful representation of cable membership."}
        ],
        "summary": "Composition changed.",
    }


def response(value):
    return {
        "status": "completed",
        "model": "gpt-6.1-sol",
        "service_tier": "default",
        "output": [
            {
                "type": "message",
                "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(value)}],
            }
        ],
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def test_audit_plan_is_blind_frozen_and_does_not_read_expected_fields(tmp_path):
    path, _ = fixture_plan(tmp_path)
    plan, _, requests = m.load_plan(path)
    request = next(iter(requests.values()))
    assert plan["cases"] == 1 and "LABEL_SENTINEL" not in json.dumps(request)
    assert json.loads(request["input"][0]["content"])["case_id"] == "item-001"
    assert not request["store"] and "tools" not in request and "previous_response_id" not in request
    (path / "prompt.txt").write_text("changed")
    with pytest.raises(ValueError, match="prompt"):
        m.load_plan(path)


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "quote", "no_omission", "false_complete", "blank_reason"]
)
def test_fidelity_response_guards(tmp_path, defect):
    path, config = fixture_plan(tmp_path)
    request = m.load_plan(path)[2]["item-001"]
    value = verdict()
    if defect == "missing":
        value["claims"] = []
    elif defect == "duplicate":
        value["claims"] *= 2
    elif defect == "quote":
        value["claims"][0]["source_quote"] = "battery ... cable"
    elif defect == "no_omission":
        value["omissions"] = []
    elif defect == "false_complete":
        value["coverage"] = "complete"
    else:
        value["claims"][0]["reason"] = " "
    with pytest.raises(ValueError):
        m.parse_response(response(value), request, config)


def test_refuses_annotations_and_nonexact_quotes_in_inference_input(tmp_path):
    for i, changes in enumerate(
        [{"expected": "faithful"}, {"claims": [{**CASE["claims"][0], "quote": "invented"}]}]
    ):
        path = tmp_path / str(i)
        m.packet_write(path, [{**CASE, **changes}])
        with pytest.raises(ValueError):
            m.load_cases(path)


def test_custom_recipe_uses_same_ledger_and_keeps_ids_without_citation_remapping(
    tmp_path, monkeypatch
):
    path, _ = fixture_plan(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key-do-not-use")
    calls = []

    def route(request):
        calls.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={"id": "gpt-6.1-sol"})
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": 1000})
        return httpx.Response(200, json=response(verdict()))

    with httpx.Client(transport=httpx.MockTransport(route)) as client:
        state = judge.run_plan(path, None, tmp_path / "ledger.sqlite3", client, recipe=m)
    assert state["status"] == "completed" and state["requests_sent"] == 1
    result = read_json(path / "item-001.result.json")
    assert result["verdict"]["case_id"] == "original"
    assert result["verdict"]["claims"][0]["fidelity"] == "distorted"
    assert state["project_ledger"]["accounted"]["requests"] == 1
    assert (path / "executed-recipe.py").exists()
    expected = {"original": {"fidelity": {"c001": "distorted"}, "coverage": "incomplete"}}
    write_json(tmp_path / "expected.json", expected)
    report = m.assessment(path, tmp_path / "assessment", tmp_path / "expected.json")
    assert report["control_gate_passed"]
    for p in path.glob("*.json"):
        assert "fake-test-key-do-not-use" not in p.read_text()


def test_empty_factual_extraction_is_not_a_perfect_control(tmp_path):
    path, _ = fixture_plan(tmp_path)
    value = verdict("original")
    value["coverage"] = "complete"
    value["omissions"] = []
    write_json(path / "item-001.result.json", {"status": "checked", "verdict": value})
    write_json(
        tmp_path / "expected.json",
        {"original": {"fidelity": {"c001": "distorted"}, "coverage": "incomplete"}},
    )
    report = m.assessment(path, tmp_path / "assessment", tmp_path / "expected.json")
    assert not report["control_gate_passed"]


def test_original_judge_recipe_remains_loadable():
    # Existing archived requests are not rewritten by adding a new task recipe.
    path = ROOT / "results/judge/20261003T145512Z-24c127"
    if not path.exists():
        pytest.skip("Laptop-only API archive")
    plan, _, _ = judge.load_plan(path)
    assert plan["cases"] == 26
