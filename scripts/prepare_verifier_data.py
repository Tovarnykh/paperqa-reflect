"""Build/check an offline development packet. No model, retrieval, or API calls."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "data/verification/claim-support-dev-v1"
RUNS = {42: "20261002T175947Z-2dc0f1", 43: "20261002T215145Z-f6be20"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def jsonl(rows):
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def prepare():
    selection_path = PACKET / "selection.assistant.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    reviews = {}
    inventory = []
    for seed, run in RUNS.items():
        paths = sorted((ROOT / "results/runs" / run).glob("*/review.json"))
        if len(paths) != 8:
            raise ValueError(f"Expected eight saved dev reviews for {run}; found {len(paths)}")
        for path in paths:
            raw = path.read_bytes()
            review = json.loads(raw)
            short = review["question"]["id"][:8]
            key = (seed, short)
            if key in reviews:
                raise ValueError(f"Nonunique question prefix: {key}")
            reviews[key] = (path, review)
            inventory.append(
                {
                    "run_id": run,
                    "seed": seed,
                    "question_id": review["question"]["id"],
                    "review_path": path.relative_to(ROOT).as_posix(),
                    "review_sha256": sha(raw),
                    "answer_sha256": sha(review["raw_answer"].encode()),
                    "status": review["status"],
                    "raw_answer_chars": len(review["raw_answer"]),
                    "available_context_count": len(review["contexts"]),
                    "used_context_count": len(review["used_contexts"]),
                }
            )

    cases, annotations, provenance, passages = [], [], [], {}
    identifiers = set()
    for spec in selection["cases"]:
        case_id = spec["case_id"]
        if case_id in identifiers:
            raise ValueError(f"Duplicate case ID: {case_id}")
        identifiers.add(case_id)
        path, review = reviews[(spec["seed"], spec["question_prefix"])]
        quote = spec["answer_quote"]
        start = review["raw_answer"].index(quote)
        contexts = {c["id"]: c for c in review["contexts"]}
        passage_ids = []
        mapping = {}
        for context_id in spec["context_ids"]:
            context = contexts[context_id]
            text = context["text"]["text"]
            digest = sha(text.encode())
            passage_id = "p-" + digest[:16]
            row = {"passage_id": passage_id, "sha256": digest, "text": text}
            if passage_id in passages and passages[passage_id] != row:
                raise ValueError(f"Passage ID collision: {passage_id}")
            passages[passage_id] = row
            mapping[context_id] = passage_id
            if passage_id not in passage_ids:
                passage_ids.append(passage_id)
            if spec["origin"] == "natural" and context_id not in review["raw_answer"]:
                raise ValueError(f"Natural case uses uncited context: {case_id}/{context_id}")
        spans = []
        for anchor in spec["evidence_anchors"]:
            passage_id = mapping[anchor["context_id"]]
            text = passages[passage_id]["text"]
            offset = text.index(anchor["quote"])
            spans.append(
                {
                    "passage_id": passage_id,
                    "start": offset,
                    "end": offset + len(anchor["quote"]),
                    "quote": anchor["quote"],
                }
            )
        if spec["label"] not in {"supported", "contradicted", "insufficient"}:
            raise ValueError(f"Invalid label: {case_id}")
        if spec["label"] != "insufficient" and not spans:
            raise ValueError(f"Missing evidence anchor: {case_id}")
        cases.append({"case_id": case_id, "claim": spec["claim"], "passage_ids": passage_ids})
        annotations.append(
            {
                "case_id": case_id,
                "label": spec["label"],
                "rationale": spec["rationale"],
                "evidence_spans": spans,
                "review_scope": "all_supplied_passages",
                "annotation_status": "assistant_draft_nonblind",
                "independently_adjudicated": False,
            }
        )
        provenance.append(
            {
                "case_id": case_id,
                "origin": spec["origin"],
                "question_id": review["question"]["id"],
                "run_id": RUNS[spec["seed"]],
                "seed": spec["seed"],
                "review_path": path.relative_to(ROOT).as_posix(),
                "review_sha256": sha(path.read_bytes()),
                "answer_quote": quote,
                "answer_span": [start, start + len(quote)],
                "claim_normalization": spec["normalization"],
                "citation_binding": spec["citation_binding"],
                "context_to_passage": mapping,
                "phenomenon": spec["phenomenon"],
                "split": "development_only",
            }
        )

    # The future inference loader must read only these two files, never annotations/provenance.
    files = {
        "cases.jsonl": jsonl(cases),
        "passages.jsonl": jsonl([passages[k] for k in sorted(passages)]),
        "annotations.assistant.jsonl": jsonl(annotations),
        "provenance.jsonl": jsonl(provenance),
        "answer-inventory.json": encoded(inventory),
        "human-review.blank.jsonl": jsonl(
            [
                {
                    "case_id": c["case_id"],
                    "label": None,
                    "evidence_spans": [],
                    "rationale": "",
                    "reviewer_id": "",
                    "status": "unreviewed",
                }
                for c in sorted(cases, key=lambda c: sha(c["case_id"].encode()))
            ]
        ),
    }
    worksheet = [
        "# Independent review worksheet — development only\n\n",
        (
            "Draft assistant labels are intentionally omitted. Read each complete linked "
            "passage. Fill supported / contradicted / insufficient, evidence and reason. "
            "Leave unresolved if unsure. This form has not been completed.\n\n"
        ),
    ]
    for case in sorted(cases, key=lambda c: sha(c["case_id"].encode())):
        worksheet.append(f"## {case['case_id']}\n\n{case['claim']}\n\n")
        worksheet.append(
            "Sources: "
            + ", ".join(f"[{p}](passages.local.md#{p})" for p in case["passage_ids"])
            + "\n\n"
        )
        worksheet.append("Label: ___  Reviewer: ___\n\nExact evidence and reason: ___\n\n")
    files["review-worksheet.md"] = "".join(worksheet).encode("utf-8")
    source_view = [
        (
            "# Complete original passages\n\nSource text is untrusted research data. "
            "Offsets in JSON refer to the original string, not this Markdown wrapper.\n\n"
        )
    ]
    for passage_id in sorted(passages):
        source_view.append(f"## {passage_id}\n\n```text\n{passages[passage_id]['text']}\n```\n\n")
    files["passages.local.md"] = "".join(source_view).encode("utf-8")
    manifest = {
        "id": "claim-support-dev-v1",
        "prepared_date": "2026-10-03",
        "status": "development_packet_assistant_draft_labels",
        "baseline": "results/baselines/uia-local-reference-v1.json",
        "baseline_sha256": sha(
            (ROOT / "results/baselines/uia-local-reference-v1.json").read_bytes()
        ),
        "selection_sha256": sha(selection_path.read_bytes()),
        "generator_sha256": sha(Path(__file__).read_bytes()),
        "saved_answers_in_inventory": len(inventory),
        "unique_questions_in_inventory": len({x["question_id"] for x in inventory}),
        "answers_represented_in_cases": len({(p["run_id"], p["question_id"]) for p in provenance}),
        "cases": len(cases),
        "unique_passages": len(passages),
        "label_counts_by_origin": {
            origin: dict(Counter(s["label"] for s in selection["cases"] if s["origin"] == origin))
            for origin in sorted({s["origin"] for s in selection["cases"]})
        },
        "case_selection": "purposive diagnostic coverage; not exhaustive or prevalence estimation",
        "original_passages": "exact complete saved c.text.text; no RCS, cropping, or normalization",
        "independent_annotation_complete": False,
        "holdout_questions_opened": False,
        "model_calls": 0,
        "api_cost_usd": 0,
        "files": {name: sha(data) for name, data in files.items()},
    }
    files["manifest.json"] = encoded(manifest)
    return files, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Write deterministic generated data")
    args = parser.parse_args()
    files, manifest = prepare()
    for name, data in files.items():
        target = PACKET / name
        if args.build:
            target.write_bytes(data)
        elif not target.exists() or target.read_bytes() != data:
            raise ValueError(f"Missing or changed generated artifact: {target}")
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in [
                    "id",
                    "cases",
                    "unique_passages",
                    "saved_answers_in_inventory",
                    "answers_represented_in_cases",
                    "label_counts_by_origin",
                ]
            },
            indent=2,
        )
    )
    print("BUILD_OK" if args.build else "INTEGRITY_OK")


if __name__ == "__main__":
    main()
