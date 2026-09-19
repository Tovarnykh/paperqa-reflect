import json
import subprocess
import sys
from pathlib import Path

import pytest

from paperqa_reflect.corpus import jats_text
from paperqa_reflect.data import grade, jsonl, question_prompt
from paperqa_reflect.evaluation import aggregate, evidence_diagnostics

ROOT = Path(__file__).resolve().parents[1]


def test_variable_option_count_and_invalid_choice():
    options = dict(zip("ABCDEFG", map(str, range(7))))
    assert "A, B, C, D, E, F, G" in question_prompt({"question": "?", "options": options})
    assert grade("Final answer: G", "G", "success", True, valid_options=tuple(options))[
        "correct_completed"
    ]
    assert not grade("Final answer: H", "G", "success", True, valid_options=tuple(options))[
        "format_valid"
    ]
    assert not grade("Final answer: A\nFinal answer: H", "A", "success", True)["format_valid"]


def test_citation_presence_is_distinct_from_support():
    session = {
        "contexts": [{"id": "c1", "text": {"doc": {"citation": "doi:10.1234/example."}}}],
        "used_contexts": [],
    }
    diagnostic = evidence_diagnostics(session, {"source_dois": ["10.1234/example"]})
    assert diagnostic["reference_in_evidence"]
    assert not diagnostic["reference_cited"]
    assert not diagnostic["claim_support_checked"]
    session["used_contexts"] = ["c1"]
    assert evidence_diagnostics(session, {"source_dois": ["10.1234/example"]})["reference_cited"]
    assert not evidence_diagnostics(session, {"source_dois": ["10.1234/examp"]})["reference_cited"]


def test_metrics_count_failure_and_abstention_in_accuracy_denominator():
    rows = []
    for status, answer, declared in [
        ("success", "B", True),
        ("success", "A", True),
        ("unsure", "ABSTAIN", False),
        ("error", "B", None),
    ]:
        rows.append(
            {
                "status": status,
                "seconds": 10,
                "actions": ["paper_search"],
                "grade": grade("Final answer: " + answer, "B", status, declared),
            }
        )
    metrics = aggregate(rows)
    assert metrics["accuracy"] == 0.25
    assert metrics["coverage"] == 0.5
    assert metrics["precision_when_answered"] == 0.5
    assert metrics["explicit_or_declared_abstentions"] == 1
    assert aggregate([])["accuracy"] is None
    assert not aggregate(rows[:1], planned_questions=4)["series_complete"]
    assert aggregate(rows[:1], planned_questions=4)["accuracy"] is None
    assert aggregate(rows, planned_questions=4)["accuracy"] == 0.25


def test_frozen_splits_have_disjoint_source_dois_and_valid_keys():
    ids, sources = [], []
    for split in ("dev", "holdout"):
        questions = jsonl(ROOT / f"data/questions/litqa-{split}.jsonl")
        keys = {row["id"]: row for row in jsonl(ROOT / f"data/gold/litqa-{split}.jsonl")}
        assert len(questions) == 8
        assert {q["id"] for q in questions} == keys.keys()
        assert all(keys[q["id"]]["answer"] in q["options"] for q in questions)
        ids.append(set(keys))
        sources.append({doi for key in keys.values() for doi in key["source_dois"]})
    assert not ids[0] & ids[1]
    assert not sources[0] & sources[1]
    manifest = json.loads((ROOT / "data/manifests/litqa-pilot.json").read_text(encoding="utf-8"))
    assert len(manifest["documents"]) == 16
    assert len({doc["pmcid"] for doc in manifest["documents"]}) == 16


def test_jats_keeps_body_captions_tables_but_not_references():
    xml = (
        "<article><front><article-meta><title-group><article-title>Title</article-title></title-group><abstract><p>Abstract.</p></abstract></article-meta></front><body><sec><title>Results</title><p>"
        + "Main text. " * 600
        + "</p><fig><caption><p>Figure caption.</p></caption></fig><table-wrap><table><tr><td>Cell 1</td><td>Cell 2</td></tr></table></table-wrap></sec></body><back><ref-list>REFERENCE_ONLY</ref-list></back></article>"
    ).encode()
    text = jats_text(xml).decode()
    assert "Abstract." in text and "Figure caption." in text and "Cell 1 Cell 2" in text
    assert "REFERENCE_ONLY" not in text
    with pytest.raises(ValueError, match="no main body"):
        jats_text(b"<article/>")


def test_real_upstream_reader_preserves_scientific_unicode_in_utf8_mode(tmp_path):
    path = tmp_path / "article.txt"
    expected = "Greek α β, 300 Å, ±, ×, −, and yeast DNA."
    path.write_text(expected, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            "from paperqa.readers import parse_text; import sys; print(parse_text(sys.argv[1]).content)",
            str(path),
        ],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout.strip() == expected


def test_cli_restarts_safely_with_utf8_from_path_containing_spaces():
    result = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-m", "paperqa_reflect.cli", "--help"],
        capture_output=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    assert "prepare-corpus" in result.stdout
