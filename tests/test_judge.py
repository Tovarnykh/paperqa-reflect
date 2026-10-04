import copy
import json
import platform
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from paperqa_reflect.judge import (
    DEFAULT_CONFIG,
    DEFAULT_PACKET,
    JudgeError,
    Ledger,
    api_key,
    build_plan,
    load_plan,
    money,
    parse_response,
    reserve_cost,
    run_plan,
    usage_cost,
)
from paperqa_reflect.judge_report import build_report
from paperqa_reflect.verifier import digest, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
KEY = "test-secret-never-log"


def fixture_plan(tmp_path, count=2):
    config = read_json(DEFAULT_CONFIG)
    config["execution_host"] = platform.node()
    config["pricing"]["checked_on"] = datetime.now(UTC).date().isoformat()
    config_path = tmp_path / "config.json"
    write_json(config_path, config)
    packet = tmp_path / "packet"
    packet.mkdir()
    values = {
        "cases.jsonl": [
            {
                "case_id": f"original-{i}",
                "claim": "Q exceeds R.",
                "passage_ids": ["original-source"],
            }
            for i in range(count)
        ],
        "passages.jsonl": [
            {
                "passage_id": "original-source",
                "text": "Q=47.28; R=45.89.",
                "sha256": digest(b"Q=47.28; R=45.89."),
            }
        ],
        "provenance.jsonl": [
            {"case_id": f"original-{i}", "origin": "natural", "question_id": "one-question"}
            for i in range(count)
        ],
    }
    hashes = {}
    for name, rows in values.items():
        data = "".join(json.dumps(r) + "\n" for r in rows).encode()
        (packet / name).write_bytes(data)
        hashes[name] = digest(data)
    write_json(packet / "manifest.json", {"files": hashes})
    (packet / "annotations.assistant.jsonl").write_text("DO NOT READ LABEL SENTINEL")
    directory, _ = build_plan(config_path, packet, tmp_path / "plans")
    return directory, packet, config


def response(request):
    payload = json.loads(request["input"][0]["content"])
    verdict = {
        "case_id": payload["case_id"],
        "label": "supported",
        "evidence": [
            {"passage_id": payload["passages"][0]["passage_id"], "quote": "Q=47.28; R=45.89."}
        ],
        "explanation": "47.28 exceeds 45.89.",
    }
    return {
        "id": "resp_test",
        "status": "completed",
        "model": "gpt-6.1-sol",
        "service_tier": "default",
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(verdict)}],
            },
        ],
        "usage": {
            "input_tokens": 500,
            "output_tokens": 200,
            "input_tokens_details": {"cached_tokens": 100},
            "output_tokens_details": {"reasoning_tokens": 150},
        },
    }


def client_with(handler=None, count=500):
    calls = []

    def route(request):
        assert request.url.host == "api.openai.com"
        assert request.headers["authorization"] == "Bearer " + KEY
        calls.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={"id": "gpt-6.1-sol"})
        if request.url.path.endswith("input_tokens"):
            body = json.loads(request.content)
            assert "text" in body and "instructions" in body and body["truncation"] == "disabled"
            return httpx.Response(200, json={"input_tokens": count})
        body = json.loads(request.content)
        return handler(request, body) if handler else httpx.Response(200, json=response(body))

    return httpx.Client(transport=httpx.MockTransport(route)), calls


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)


def test_plan_is_blind_and_uses_full_original_evidence(tmp_path):
    directory, packet, _ = fixture_plan(tmp_path)
    plan, _, requests = load_plan(directory)
    assert plan["requests_sent"] == 0
    assert not plan["annotations_read"]
    for request in requests.values():
        serialized = json.dumps(request)
        assert "LABEL SENTINEL" not in serialized
        assert "original-" not in serialized
        assert "47.28" in serialized and "45.89" in serialized
        assert not request["store"]
        assert "previous_response_id" not in request and "tools" not in request
    assert (packet / "annotations.assistant.jsonl").read_text() == "DO NOT READ LABEL SENTINEL"


def test_actual_dev_packet_all_26_without_annotations(tmp_path):
    if not (DEFAULT_PACKET / "passages.jsonl").exists():
        pytest.skip("Local original-passage archive is not part of Git")
    directory, plan = build_plan(DEFAULT_CONFIG, DEFAULT_PACKET, tmp_path)
    assert plan["cases"] == 26
    assert money(plan["offline_estimated_reservation_usd"]) < 5_000_000
    _, _, requests = load_plan(directory)
    assert all("annotations.assistant" not in json.dumps(r) for r in requests.values())


@pytest.mark.parametrize("target", ["config.json", "prompt.txt", "item-001.request.json"])
def test_frozen_plan_detects_mutation(tmp_path, target):
    directory, _, _ = fixture_plan(tmp_path)
    path = directory / target
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(JudgeError, match="integrity"):
        load_plan(directory)


def test_missing_key_stops_before_any_network_or_run_file(tmp_path, monkeypatch):
    directory, _, _ = fixture_plan(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY")
    client, calls = client_with()
    with pytest.raises(JudgeError, match="missing_openai_api_key"):
        run_plan(directory, tmp_path / "missing.env", tmp_path / "ledger", client)
    assert calls == []
    assert not (directory / "run.json").exists()


def test_key_file_not_executed_or_printed(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    path = tmp_path / ".env"
    path.write_text('IGNORED=$(anything)\nOPENAI_API_KEY="' + KEY + '"\n')
    assert api_key(path) == KEY


def test_mocked_run_retains_responses_offsets_and_cost(tmp_path):
    directory, _, config = fixture_plan(tmp_path)
    client, calls = client_with()
    state = run_plan(directory, None, tmp_path / "ledger", client)
    assert state["status"] == "completed" and state["requests_sent"] == 2
    assert calls.count("/v1/responses/input_tokens") == 2
    assert calls.count("/v1/responses") == 2
    result = read_json(directory / "item-001.result.json")
    assert result["status"] == "checked"
    assert result["verdict"]["case_id"].startswith("original-")
    assert result["verdict"]["evidence"][0]["passage_id"] == "original-source"
    assert result["verdict"]["evidence_offsets"][0]["end"] == len("Q=47.28; R=45.89.")
    # 500 input * max(2,2.5) + 200 total output * 10; reasoning already in total output.
    assert money(state["accounted_upper_usd"]) == 2 * 3250
    assert reserve_cost(500, config) > 3250
    assert all(KEY not in p.read_text(encoding="utf-8") for p in directory.glob("*.json"))
    with pytest.raises(FileExistsError):
        run_plan(directory, None, tmp_path / "ledger", client)
    assert calls.count("/v1/responses") == 2


def test_timeout_keeps_reservation_and_never_retries(tmp_path):
    directory, _, config = fixture_plan(tmp_path)

    def timeout(request, body):
        raise httpx.ReadTimeout("secret=" + KEY, request=request)

    client, calls = client_with(timeout)
    with pytest.raises(httpx.ReadTimeout):
        run_plan(directory, None, tmp_path / "ledger", client)
    assert calls.count("/v1/responses") == 1
    state = read_json(directory / "run.json")
    assert state["status"] == "failed"
    assert money(state["project_ledger"]["reserved"]["usd"]) == reserve_cost(500, config)
    assert all(KEY not in p.read_text(encoding="utf-8") for p in directory.glob("*.json"))


def test_auth_failure_redacts_remote_body_and_stops(tmp_path):
    directory, _, _ = fixture_plan(tmp_path)
    client, calls = client_with(
        lambda req, body: httpx.Response(401, json={"error": {"message": "Incorrect key: " + KEY}})
    )
    with pytest.raises(JudgeError, match="http_401"):
        run_plan(directory, None, tmp_path / "ledger", client)
    assert calls.count("/v1/responses") == 1
    assert not (directory / "item-001.response.json").exists()
    assert all(KEY not in p.read_text(encoding="utf-8") for p in directory.glob("*.json"))


@pytest.mark.parametrize("kind", ["incomplete", "bad_quote", "refusal", "invalid_schema"])
def test_invalid_semantic_results_do_not_become_insufficient(tmp_path, kind):
    directory, _, _ = fixture_plan(tmp_path, count=1)

    def invalid(request, body):
        raw = response(body)
        if kind == "incomplete":
            raw["status"] = "incomplete"
        elif kind == "refusal":
            raw["output"][-1]["content"] = [{"type": "refusal", "refusal": "No"}]
        else:
            part = raw["output"][-1]["content"][0]
            verdict = json.loads(part["text"])
            if kind == "bad_quote":
                verdict["evidence"][0]["quote"] = "invented quotation"
            else:
                verdict["label"] = "maybe"
            part["text"] = json.dumps(verdict)
        return httpx.Response(200, json=raw)

    client, _ = client_with(invalid)
    state = run_plan(directory, None, tmp_path / "ledger", client)
    result = read_json(directory / "item-001.result.json")
    assert state["status"] == "completed"
    assert result["status"] == "not_checked" and result["verdict"] is None
    assert "accounted" in state["project_ledger"]


def test_full_plan_over_budget_stops_before_generation(tmp_path):
    directory, _, _ = fixture_plan(tmp_path, count=26)
    # Each request is within the input cap, but the series exceeds $5 including output caps.
    client, calls = client_with(count=60000)
    with pytest.raises(JudgeError, match="whole_plan_exceeds"):
        run_plan(directory, None, tmp_path / "ledger", client)
    assert "/v1/responses" not in calls


def test_durable_ledger_limits_pending_costs_across_instances(tmp_path):
    _, _, config = fixture_plan(tmp_path)
    path = tmp_path / "ledger"
    first, second = Ledger(path, config), Ledger(path, config)
    identifier = first.reserve("plan1", "hash1", 4_000_000)
    with pytest.raises(JudgeError, match="pilot_budget"):
        second.reserve("plan2", "hash2", 2_000_000)
    with pytest.raises(JudgeError, match="already_attempted"):
        second.reserve("plan1", "hash1", 100)
    first.settle(identifier, 1_000_000)
    second.reserve("plan2", "hash2", 2_000_000)
    changed = copy.deepcopy(config)
    changed["execution_host"] = "another-host"
    with pytest.raises(JudgeError, match="ledger_settings"):
        Ledger(path, changed)


def test_usage_overrun_is_recorded_and_blocks_further_calls(tmp_path):
    _, _, config = fixture_plan(tmp_path)
    ledger = Ledger(tmp_path / "ledger", config)
    identifier = ledger.reserve("one", "hash", 100)
    with pytest.raises(JudgeError, match="exceeded_reservation"):
        ledger.settle(identifier, 200)
    assert ledger.summary()["overrun"]["usd"] == "0.000200"
    with pytest.raises(JudgeError, match="prior_cost_overrun"):
        ledger.reserve("two", "next", 100)


def test_usage_cost_uses_all_output_including_reasoning(tmp_path):
    directory, _, config = fixture_plan(tmp_path)
    _, _, requests = load_plan(directory)
    raw = response(next(iter(requests.values())))
    cost, usage = usage_cost(raw, config)
    assert cost == 3250
    raw["usage"]["output_tokens_details"]["reasoning_tokens"] = 0
    assert usage_cost(raw, config)[0] == cost
    assert usage["output_tokens"] == 200


def test_wrong_model_keeps_unknown_reservation(tmp_path):
    directory, _, _ = fixture_plan(tmp_path, count=1)

    def mismatch(request, body):
        raw = response(body)
        raw["model"] = "unexpected-expensive-model"
        return httpx.Response(200, json=raw)

    client, _ = client_with(mismatch)
    with pytest.raises(JudgeError, match="unqualified_response_pricing"):
        run_plan(directory, None, tmp_path / "ledger", client)
    assert "reserved" in read_json(directory / "run.json")["project_ledger"]


def test_report_labels_are_explicitly_model_reference_and_missing_stays_visible(tmp_path):
    directory, packet, _ = fixture_plan(tmp_path, count=2)
    client, _ = client_with()
    run_plan(directory, None, tmp_path / "ledger", client)
    plan = read_json(directory / "plan.json")
    # Simulate one technically failed judge result, preserving the saved raw response.
    path = directory / "item-002.result.json"
    failed = read_json(path)
    failed.update(status="not_checked", verdict=None)
    write_json(path, failed)
    observer = tmp_path / "observer"
    observer.mkdir()
    write_json(
        observer / "run.json",
        {
            "status": "completed",
            "packet_hashes": plan["packet_hashes"],
            "planned_case_ids": [r["case_id"] for r in plan["rows"]],
        },
    )
    for row in plan["rows"]:
        p = observer / row["case_id"]
        p.mkdir()
        write_json(
            p / "result.json",
            {
                "status": "checked",
                "verdict": {"label": "supported", "explanation": "local explanation"},
            },
        )
    report = build_report(directory, observer, packet, tmp_path / "report")
    group = report["metrics_by_origin"]["natural"]
    assert not report["independent_human_gold"]
    assert group["reference_coverage"] == 0.5 and group["unjudged_reference"] == 1
    assert group["agreement_all_lower"] == 0.5 and group["agreement_all_upper"] == 1
    labels = (tmp_path / "report/annotations.external-judge.jsonl").read_text()
    assert '"independently_adjudicated": false' in labels


def test_two_hosts_cannot_run_same_profile(tmp_path, monkeypatch):
    directory, _, _ = fixture_plan(tmp_path)
    monkeypatch.setattr(platform, "node", lambda: "different-host")
    client, calls = client_with()
    with pytest.raises(JudgeError, match="wrong_execution_host"):
        run_plan(directory, None, tmp_path / "ledger", client)
    assert calls == []


def test_parse_response_rejects_multiple_verdicts(tmp_path):
    directory, _, config = fixture_plan(tmp_path)
    _, _, requests = load_plan(directory)
    request = next(iter(requests.values()))
    raw = response(request)
    raw["output"].append(copy.deepcopy(raw["output"][-1]))
    with pytest.raises(JudgeError, match="expected_one_verdict"):
        parse_response(raw, request, config)


def test_project_budget_survives_new_pilot_groups(tmp_path):
    _, _, config = fixture_plan(tmp_path)
    path = tmp_path / "ledger"
    ledger = Ledger(path, config)
    # Represents earlier accounted project calls, rather than bypassing the group cap.
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO calls VALUES (?,?,?,?,?,?,?)",
            ("past", "past-plan", "other", "past-hash", 99_000_000, 99_000_000, "accounted"),
        )
    with pytest.raises(JudgeError, match="project_budget"):
        ledger.reserve("new", "new-hash", 2_000_000)
