import csv
import json
from pathlib import Path

import pytest

from paperqa_reflect.config import ExperimentConfig, build_settings, load_config
from paperqa_reflect.data import (
    corpus_directory,
    grade,
    jsonl,
    manifest_documents,
    paperqa_manifest,
    question_prompt,
    sha256,
    validate_corpus,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return load_config(ROOT / "configs/local-qwen3-8b.json")


@pytest.mark.parametrize("status", ["truncated", "fail", "error", "outer_timeout", "unsure"])
def test_correct_letter_after_failure_is_not_successful_accuracy(status):
    result = grade("An explanation.\nFinal answer: B", "B", status, True)
    assert result["option_matches_key"]
    assert not result["correct_completed"]


@pytest.mark.parametrize(
    "answer", ["The answer might be B", "Final answer: B\nFinal answer: C", ""]
)
def test_grader_does_not_guess_an_answer(answer):
    result = grade(answer, "B", "success", True)
    assert result["selected"] is None
    assert not result["correct_completed"]


def test_abstention_and_declared_unsureness():
    assert grade("Final answer: ABSTAIN", "B", "unsure", False)["abstained"]
    assert not grade("Final answer: B", "B", "success", False)["correct_completed"]
    assert grade("Final answer: B", "B", "success", True)["correct_completed"]


def test_grader_accepts_only_known_trailing_citations():
    answer = "**Final answer: B** (pqac-abcd1234)"
    assert grade(answer, "B", "success", True, ("pqac-abcd1234",))["correct_completed"]
    assert not grade(answer, "B", "success", True)["format_valid"]
    assert not grade("Final answer: B (or C)", "B", "success", True)["format_valid"]


def test_gold_never_enters_question_prompt():
    prompt = question_prompt(
        {
            "question": "Question?",
            "options": {"A": "One", "B": "Two"},
            "answer": "SECRET_ANSWER",
            "support": "SECRET_SUPPORT",
        }
    )
    assert "SECRET" not in prompt


def test_fixture_keys_cover_every_question():
    questions = jsonl(ROOT / "data/questions/smoke.jsonl")
    keys = {row["id"]: row for row in jsonl(ROOT / "data/gold/smoke.jsonl")}
    assert {q["id"] for q in questions} == keys.keys()
    assert all(keys[q["id"]]["answer"] in q["options"] for q in questions)


def test_duplicate_questions_rejected(tmp_path):
    path = tmp_path / "questions.jsonl"
    path.write_text('{"id":"q1"}\n{"id":"q1"}\n')
    with pytest.raises(ValueError, match="duplicate"):
        jsonl(path)


@pytest.mark.parametrize("directory", [".", "..", "data", "data/corpus"])
def test_project_cannot_be_used_as_corpus(config, tmp_path, directory):
    config.corpus_dir = directory
    with pytest.raises(ValueError, match="dedicated"):
        corpus_directory(tmp_path, config)


def test_gold_cannot_be_stored_inside_corpus(config, tmp_path):
    config.gold = config.corpus_dir + "/answers.jsonl"
    with pytest.raises(ValueError, match="outside"):
        corpus_directory(tmp_path, config)


def test_corpus_integrity_and_no_extra_files(config, tmp_path):
    corpus = tmp_path / config.corpus_dir
    corpus.mkdir(parents=True)
    pdf = corpus / "test.pdf"
    pdf.write_bytes(b"fixture for hash verification")
    manifest = tmp_path / config.corpus_manifest
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"documents": [{"file": "test.pdf", "sha256": sha256(pdf)}]}))
    assert len(validate_corpus(tmp_path, config)) == 1
    (corpus / "answers.txt").write_text("unexpected answer key")
    with pytest.raises(ValueError, match="extra"):
        validate_corpus(tmp_path, config)
    (corpus / "answers.txt").unlink()
    pdf.write_bytes(b"modified source")
    with pytest.raises(ValueError, match="hash"):
        validate_corpus(tmp_path, config)


def test_nonlocal_endpoint_rejected(config):
    values = config.model_dump() | {"endpoint": "https://api.example.com"}
    with pytest.raises(ValueError, match="loopback"):
        ExperimentConfig(**values)


def test_actual_paperqa_routes_all_roles_locally(config, tmp_path):
    # Exercise the real pinned library API: it nests embedding config differently from LLM config.
    settings = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest.csv")
    for model in (
        settings.get_llm(),
        settings.get_summary_llm(),
        settings.get_agent_llm(),
        settings.get_enrichment_llm(),
    ):
        assert len(model.config["model_list"]) == 1
        assert model.config["model_list"][0]["litellm_params"]["api_base"] == config.endpoint
        assert model.config["model_list"][0]["litellm_params"]["model"].startswith("ollama_chat/")
    embedding = settings.get_embedding_model()
    assert embedding.config["kwargs"]["api_base"] == config.endpoint
    assert embedding.name.startswith("ollama/")
    assert settings.make_aviary_tool_selector("ToolSelector") is not None
    assert not settings.parsing.use_doc_details
    assert not settings.parsing.multimodal


def test_paperqa_keeps_known_authors_in_citations(config, tmp_path):
    from paperqa.agents.search import fetch_kwargs_from_manifest

    documents = manifest_documents(ROOT, config)
    path = tmp_path / "manifest.csv"
    paperqa_manifest(path, documents)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = {row["file_location"]: row for row in csv.DictReader(stream)}
    details = fetch_kwargs_from_manifest(documents[0]["file"], rows, "unused")
    assert details["authors"] == documents[0]["authors"]
    assert "Wellawatte" in details["citation"]
    assert "Unknown" not in details["citation"]
