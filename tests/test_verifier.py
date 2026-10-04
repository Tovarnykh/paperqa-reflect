import json
from pathlib import Path

import httpx
import pytest

from paperqa_reflect.verifier import (
    check_response,
    digest,
    load_config,
    load_packet,
    observe,
    parse_verdict,
    request_for,
    run,
)
from paperqa_reflect.verifier_report import metrics

ROOT = Path(__file__).resolve().parents[1]
CASE = {"case_id": "sample", "claim": "Q exceeds R.", "passage_ids": ["q", "r"]}
PASSAGES = {"q": "Q measured 47.28 cm.", "r": "R measured 45.89 cm."}


def verdict(label="supported", evidence=None):
    return {
        "case_id": "sample",
        "label": label,
        "evidence": evidence
        if evidence is not None
        else [{"passage_id": "q", "quote": "47.28"}, {"passage_id": "r", "quote": "45.89"}],
        "explanation": "47.28 exceeds 45.89.",
    }


def config():
    return load_config(ROOT / "configs/verifier-qwen38-v1.json")


def body(value=None):
    return {
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 100,
        "eval_count": 30,
        "message": {"content": json.dumps(value or verdict())},
    }


def test_joint_evidence_and_exact_offsets():
    result = parse_verdict(json.dumps(verdict()), CASE, PASSAGES)
    assert len(result["evidence_offsets"]) == 2
    for item, span in zip(result["evidence"], result["evidence_offsets"], strict=True):
        assert PASSAGES[span["passage_id"]][span["start"] : span["end"]] == item["quote"]


@pytest.mark.parametrize(
    "evidence",
    [
        [{"passage_id": "hidden", "quote": "47.28"}],
        [{"passage_id": "q", "quote": "47.29"}],
        [],
        [{"passage_id": "q", "quote": " "}],
    ],
)
def test_reject_fabricated_missing_or_out_of_scope_evidence(evidence):
    with pytest.raises(ValueError):
        parse_verdict(json.dumps(verdict(evidence=evidence)), CASE, PASSAGES)


def test_insufficient_does_not_require_positive_evidence():
    assert (
        parse_verdict(json.dumps(verdict("insufficient", [])), CASE, PASSAGES)["label"]
        == "insufficient"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"done_reason": "length"},
        {"done": False},
        {"prompt_eval_count": 32760},
        {"eval_count": None},
    ],
)
def test_output_limit_and_bad_accounting_are_not_semantic_verdicts(changes):
    with pytest.raises(ValueError):
        check_response({**body(), **changes}, CASE, PASSAGES, config())


def test_loader_refuses_annotations_in_inference_input(tmp_path):
    rows = [{**CASE, "label": "supported"}]
    values = {
        "cases.jsonl": rows,
        "passages.jsonl": [
            {"passage_id": pid, "text": text, "sha256": digest(text.encode())}
            for pid, text in PASSAGES.items()
        ],
    }
    hashes = {}
    for name, rows in values.items():
        data = "".join(json.dumps(row) + "\n" for row in rows).encode()
        (tmp_path / name).write_bytes(data)
        hashes[name] = digest(data)
    (tmp_path / "manifest.json").write_text(json.dumps({"files": hashes}))
    with pytest.raises(ValueError, match="leakage"):
        load_packet(tmp_path)


def test_real_packet_payload_has_only_claim_and_original_passages():
    if not (ROOT / "data/verification/claim-support-dev-v1/passages.jsonl").exists():
        pytest.skip("Local original-passage archive is not part of Git")
    cases, passages = load_packet(ROOT / "data/verification/claim-support-dev-v1")
    for case in cases:
        request = request_for(case, passages, config())
        payload = json.loads(request["messages"][1]["content"])
        assert set(payload) == {"case_id", "claim", "passages"}
        assert all(p["text"] == passages[p["passage_id"]] for p in payload["passages"])
        assert request["think"] is False and request["stream"] is False


@pytest.mark.parametrize(
    "mode", ["ok", "timeout", "bad_quote", "truncated_log", "truncated_flag", "overflow"]
)
def test_observer_preserves_attempt_and_separates_failures(tmp_path, mode):
    log = tmp_path / "server.log"
    log.write_text("")
    calls = []

    def handler(request):
        calls.append(request)
        if mode == "timeout":
            raise httpx.ReadTimeout("slow model", request=request)
        if mode == "truncated_log":
            log.write_text("truncating input prompt limit=100\n")
        if mode == "truncated_flag":
            log.write_text("slot release: stop processing: n_tokens = 100, truncated = 1\n")
        value = (
            verdict(evidence=[{"passage_id": "q", "quote": "999"}])
            if mode == "bad_quote"
            else verdict()
        )
        return httpx.Response(200, json=body(value))

    settings = config()
    if mode == "overflow":
        settings["context_tokens"] = 1100
    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://127.0.0.1"
    ) as client:
        result = observe(CASE, PASSAGES, settings, client, tmp_path / "case", "", log)
    assert result["status"] == ("checked" if mode == "ok" else "not_checked")
    assert (tmp_path / "case/result.json").exists()
    assert len(calls) == (0 if mode == "overflow" else 1)
    if mode != "ok":
        assert result["verdict"] is None and result["error"]


def test_metrics_keep_technical_failure_in_all_case_denominator():
    result = metrics(
        [
            {"label": "supported", "prediction": "supported"},
            {"label": "contradicted", "prediction": None},
            {"label": "insufficient", "prediction": "supported"},
        ]
    )
    assert result["agreement_all"] == 1 / 3
    assert result["agreement_checked"] == 1 / 2
    assert result["coverage"] == 2 / 3
    assert result["flag_precision"] is None
    assert result["not_checked"] == 1


def test_loopback_restriction(tmp_path):
    settings = config()
    settings["endpoint"] = "https://api.example.com"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(settings))
    with pytest.raises(ValueError, match="loopback"):
        load_config(path)


@pytest.mark.parametrize("changed_digest", [False, True])
def test_complete_run_pins_model_and_preserves_source(tmp_path, changed_digest):
    settings = config()
    log = tmp_path / "server.log"
    log.write_text("")
    settings["server_log"] = str(log)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(settings))
    # This transport/snapshot check needs no real scientific text or local archive.
    packet = tmp_path / "packet"
    packet.mkdir()
    hashes = {}
    values = {
        "cases.jsonl": [CASE],
        "passages.jsonl": [
            {"passage_id": pid, "text": text, "sha256": digest(text.encode())}
            for pid, text in PASSAGES.items()
        ],
    }
    for name, rows in values.items():
        data = "".join(json.dumps(row) + "\n" for row in rows).encode()
        (packet / name).write_bytes(data)
        hashes[name] = digest(data)
    (packet / "manifest.json").write_text(json.dumps({"files": hashes}))
    cases, passages = load_packet(packet)
    case = cases[0]
    pid = case["passage_ids"][0]
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": settings["ollama_version"]})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": settings["model"],
                            "digest": "0" * 64 if changed_digest else settings["model_digest"],
                        }
                    ]
                },
            )
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"template": ""})
        value = {
            "case_id": case["case_id"],
            "label": "supported",
            "explanation": "Test fixture.",
            "evidence": [{"passage_id": pid, "quote": passages[pid][:20]}],
        }
        return httpx.Response(200, json=body(value))

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url=settings["endpoint"]
    ) as client:
        if changed_digest:
            with pytest.raises(ValueError, match="digest"):
                run(config_path, packet, tmp_path / "runs", [case["case_id"]], client=client)
        else:
            run(config_path, packet, tmp_path / "runs", [case["case_id"]], client=client)
    directory = next((tmp_path / "runs").iterdir())
    snapshot = json.loads((directory / "run.json").read_text())
    assert digest((directory / "verifier-source.py").read_bytes()) == snapshot["code_sha256"]
    assert snapshot["status"] == ("failed" if changed_digest else "completed")
    assert calls.count("/api/chat") == (0 if changed_digest else 1)
