import json

import httpx
import pytest

from paperqa_reflect import revision as r

SOURCES = {"pqac-abc": "X is 47.28 and Y is 45.89."}
QUESTION = {"question": "Which is larger?", "options": {"A": "X", "B": "Y"}}


def test_sentence_spans_citations_and_decimal_values():
    answer = "  X is 47.28 (pqac-abc). Y is 45.89.\n\nFinal answer: A"
    units = r.sentences(answer)
    assert len(units) == 2
    assert units[0]["citation_ids"] == ["pqac-abc"]
    assert units[1]["citation_ids"] == []  # No implicit inheritance from earlier sentence.
    for unit in units:
        assert answer[unit["start"] : unit["end"]] == unit["text"]


def test_numbered_lists_are_not_standalone_numbers_and_filler_can_have_zero_claims():
    units = r.sentences("Ranking:\n1. X (47.28 Mb)\n2. Y (45.89 Mb)")
    assert [u["text"] for u in units] == ["Ranking:", "1. X (47.28 Mb)", "2. Y (45.89 Mb)"]
    claims = r.parse_extraction(
        {
            "sentences": [
                {"sentence_id": "s001", "claims": []},
                {
                    "sentence_id": "s002",
                    "claims": [{"claim": "X has length 47.28 Mb.", "quote": "X (47.28 Mb)"}],
                },
                {
                    "sentence_id": "s003",
                    "claims": [{"claim": "Y has length 45.89 Mb.", "quote": "Y (45.89 Mb)"}],
                },
            ]
        },
        units,
        {},
    )
    assert len(claims) == 2


def test_inline_enumeration_keeps_its_citation_but_numeric_sentence_ends_split():
    answer = "Ranking: 1. X (47.28 Mb), 2. Y (45.89 Mb) (pqac-abc). The count is 2. Next fact."
    units = r.sentences(answer)
    assert len(units) == 3
    assert units[0]["text"] == "Ranking: 1. X (47.28 Mb), 2. Y (45.89 Mb) (pqac-abc)."
    assert units[0]["citation_ids"] == ["pqac-abc"]
    assert units[1]["text"] == "The count is 2."


@pytest.mark.parametrize("defect", ["missing", "duplicate", "quote", "citation", "blank"])
def test_extraction_rejects_missing_scope_or_fabricated_spans(defect):
    units = r.sentences("X is 47.28 (pqac-abc). Y is 45.89 (pqac-abc).")
    value = {
        "sentences": [
            {
                "sentence_id": unit["sentence_id"],
                "claims": [{"claim": unit["text"], "quote": unit["text"]}],
            }
            for unit in units
        ]
    }
    if defect == "missing":
        value["sentences"].pop()
    elif defect == "duplicate":
        value["sentences"][1] = value["sentences"][0]
    elif defect == "quote":
        value["sentences"][0]["claims"][0]["quote"] = "invented"
    elif defect == "citation":
        units[0]["citation_ids"] = ["pqac-missing"]
    else:
        value["sentences"][0]["claims"][0]["quote"] = " "
    with pytest.raises(ValueError):
        r.parse_extraction(value, units, SOURCES)


def test_boundary_repair_preserves_assertion_and_rejects_noncontained_spans():
    units = r.sentences("Ranking: 1. X (47.28 Mb), 2. Y (45.89 Mb) (pqac-abc).")
    old = {
        "case_id": "c",
        "claim": "X is 47.28 Mb.",
        "answer_quote": "X (47.28 Mb)",
        "answer_span": [12, 26],
        "passage_ids": [],
        "sentence_id": "old",
    }
    repaired = r.rebind_claims([old], units)[0]
    assert repaired["claim"] == old["claim"] and repaired["answer_quote"] == old["answer_quote"]
    assert repaired["passage_ids"] == ["pqac-abc"]
    assert old["passage_ids"] == []
    with pytest.raises(ValueError, match="preserve"):
        r.rebind_claims([{**old, "answer_span": [0, 1000]}], units)


def test_revision_rejects_new_sources_and_invalid_choice():
    for answer in ["X (pqac-new).\nFinal answer: A", "X (pqac-abc).\nFinal answer: Z"]:
        with pytest.raises(ValueError):
            r.validate_revision({"answer": answer}, QUESTION, SOURCES)
    assert r.validate_revision({"answer": "Final answer: UNSURE"}, QUESTION, SOURCES)


def test_packet_does_not_forward_answer_key_or_rcs(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "ROOT", tmp_path)
    selected = [
        ("20261002T175947Z-2dc0f1", "7a88e6f7-fb8e-4a24-b08d-9b7a6edafe57"),
        ("20261002T215145Z-f6be20", "ae02d0e9-edf5-4c39-a215-3cbc8f4c565d"),
    ]
    entries = []
    answer = "X is 47.28 (pqac-abc)."
    for index, (run_id, question_id) in enumerate(selected):
        path = tmp_path / f"review-{index}.json"
        r.write_json(
            path,
            {
                "question": QUESTION,
                "raw_answer": answer,
                "reference": "SECRET_KEY",
                "contexts": [
                    {
                        "id": "pqac-abc",
                        "context": "RCS_MUST_NOT_PASS",
                        "text": {"text": SOURCES["pqac-abc"]},
                    }
                ],
            },
        )
        entries.append(
            {
                "run_id": run_id,
                "question_id": question_id,
                "review_path": path.name,
                "review_sha256": r.digest(path.read_bytes()),
                "answer_sha256": r.digest(answer.encode()),
                "seed": 42,
            }
        )
    inventory = tmp_path / "inventory.json"
    r.write_json(inventory, entries)
    output = tmp_path / "input.json"
    r.prepare_packet(inventory, output)
    text = output.read_text()
    assert "SECRET_KEY" not in text and "RCS_MUST_NOT_PASS" not in text
    assert len(json.loads(text)["answers"]) == 2
    with pytest.raises(FileExistsError):
        r.prepare_packet(inventory, output)
    (tmp_path / entries[0]["review_path"]).write_text("changed")
    with pytest.raises(ValueError, match="integrity"):
        r.prepare_packet(inventory, tmp_path / "other.json")


@pytest.mark.parametrize("failure", [None, "timeout", "truncation", "schema", "length", "budget"])
def test_transport_failures_never_become_semantic_feedback(tmp_path, failure):
    log = tmp_path / "server.log"
    log.write_text("")
    config = {"model": "local", "server_log": str(log), "_chat_template": "template"}
    calls = []

    def respond(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("timed out")
        if failure == "truncation":
            log.write_text("truncating input prompt")
        value = {"bad": "field"} if failure == "schema" else {"answer": "Final answer: A"}
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "length" if failure == "length" else "stop",
                "prompt_eval_count": 100,
                "eval_count": 20,
                "message": {"content": json.dumps(value)},
            },
        )

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        result = r.local_json(
            client,
            config,
            tmp_path / "stage",
            "test",
            "Prompt",
            {"question": "x" * (40000 if failure == "budget" else 1)},
            r.REVISION_SCHEMA,
            32768,
        )
    assert result["status"] == ("checked" if failure is None else "not_checked")
    assert len(calls) == (0 if failure == "budget" else 1)
    if failure:
        assert result["value"] is None
    assert (tmp_path / "stage/result.json").exists()


def test_review_rejects_invented_quotes_and_sources():
    for quote, source in [("invented", "pqac-abc"), ("X", "pqac-hidden"), (" ", "pqac-abc")]:
        with pytest.raises(ValueError):
            r.validate_review(
                {"issues": [{"quote": quote, "issue": "wrong", "source_ids": [source]}]},
                "X is 47.28",
                SOURCES,
            )
