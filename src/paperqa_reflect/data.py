"""Keep source documents, questions and answer keys separate."""

import csv
import hashlib
import json
import re
from pathlib import Path

import httpx


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    ids = [row["id"] for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError(f"Empty dataset or duplicate IDs: {path}")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", item) for item in ids):
        raise ValueError("Question IDs must be safe directory names.")
    return rows


def manifest_documents(root: Path, config) -> list[dict]:
    documents = json.loads((root / config.corpus_manifest).read_text(encoding="utf-8"))["documents"]
    names = [doc["file"] for doc in documents]
    if not names or len(names) != len(set(names)):
        raise ValueError("The manifest must contain unique source files.")
    if any(Path(name).name != name or Path(name).suffix.lower() != ".pdf" for name in names):
        raise ValueError("The smoke corpus accepts plain PDF filenames only.")
    return documents


def corpus_directory(root: Path, config) -> Path:
    corpus = (root / config.corpus_dir).resolve()
    base = (root / "data/corpus").resolve()
    if corpus == base or not corpus.is_relative_to(base):
        raise ValueError(
            "Use a dedicated subdirectory of data/corpus, never the project/wiki root."
        )
    for path in (config.questions, config.gold, config.corpus_manifest):
        if (root / path).resolve().is_relative_to(corpus):
            raise ValueError("Questions, answer keys and manifest must be outside the corpus.")
    return corpus


def prepare_corpus(root: Path, config, source: Path | None = None):
    corpus = corpus_directory(root, config)
    documents = manifest_documents(root, config)
    if source and len(documents) != 1:
        raise ValueError("--source supports only a single-document manifest.")
    corpus.mkdir(parents=True, exist_ok=True)
    for doc in documents:
        target = corpus / doc["file"]
        if target.exists():
            if sha256(target) != doc["sha256"]:
                raise ValueError(f"Existing corpus file has an unexpected hash: {target}")
            continue
        if source:
            payload = source.read_bytes()
        else:
            response = httpx.get(doc["url"], timeout=120, follow_redirects=True)
            response.raise_for_status()
            payload = response.content
        if hashlib.sha256(payload).hexdigest() != doc["sha256"]:
            raise ValueError(f"Source hash mismatch for {doc['file']}")
        target.write_bytes(payload)
    return validate_corpus(root, config)


def validate_corpus(root: Path, config) -> list[dict]:
    corpus = corpus_directory(root, config)
    documents = manifest_documents(root, config)
    actual = {path.name for path in corpus.iterdir()}
    if actual != {doc["file"] for doc in documents}:
        raise ValueError("Corpus content must exactly match its manifest (no extra files/folders).")
    for doc in documents:
        if sha256(corpus / doc["file"]) != doc["sha256"]:
            raise ValueError(f"Corpus hash mismatch: {doc['file']}")
    return documents


def paperqa_manifest(path: Path, documents: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["file_location", "title", "doi", "citation", "year", "authors", "journal"],
        )
        writer.writeheader()
        for doc in documents:
            writer.writerow(
                {
                    "file_location": doc["file"],
                    **{key: doc[key] for key in ("title", "doi", "citation", "year", "journal")},
                    "authors": json.dumps(doc["authors"]),
                }
            )


def question_prompt(question: dict) -> str:
    # Whitelist the input fields: even an accidentally merged key is never passed to the model.
    options = "\n".join(f"{key}. {value}" for key, value in question["options"].items())
    return (
        f"{question['question']}\n\n{options}\n\n"
        "Use evidence from the available papers and cite the relevant passage. "
        "End your answer with one line in the exact format 'Final answer: X', "
        "where X is A, B, C or D. If the evidence is insufficient, "
        "write 'Final answer: ABSTAIN'."
    )


def grade(
    answer: str,
    expected: str,
    status: str,
    declared_success: bool | None,
    citation_ids: tuple[str, ...] = (),
) -> dict:
    # Grade the raw answer. Remove only parenthesized citations that refer to actual contexts.
    # An unknown citation or an aside such as '(or C)' must not be silently discarded.
    def remove_known_citations(match):
        ids = [item.strip() for item in match.group(1).split(",")]
        return "" if all(item in citation_ids for item in ids) else match.group(0)

    clean = re.sub(r"\(([^()\r\n]+)\)", remove_known_citations, answer)
    clean = clean.replace("**", "")
    matches = re.findall(r"(?im)^\s*Final answer:\s*(ABSTAIN|[A-D])\s*[.!]?\s*$", clean)
    selected = matches[0].upper() if len(set(matches)) == 1 else None
    # Accuracy is separate from successful termination and from source/claim verification.
    return {
        "selected": selected,
        "expected": expected,
        "format_valid": selected is not None,
        "abstained": selected == "ABSTAIN" or declared_success is False,
        "option_matches_key": selected == expected,
        "correct_completed": status == "success"
        and declared_success is not False
        and selected == expected,
        "claim_support_checked": False,
    }
