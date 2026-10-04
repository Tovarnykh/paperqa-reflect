"""Post-run observer diagnostics; draft agreement is not independent accuracy."""

import argparse
import json
from pathlib import Path

from .verifier import LABELS, digest, read_json, write_json


def divide(a, b):
    return a / b if b else None


def metrics(rows):
    checked = [r for r in rows if r["prediction"] in LABELS]
    matrix = {truth: {pred: 0 for pred in LABELS} for truth in LABELS}
    for row in checked:
        matrix[row["label"]][row["prediction"]] += 1
    by_class = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[t][label] for t in LABELS if t != label)
        fn = sum(matrix[label][p] for p in LABELS if p != label)
        by_class[label] = {
            "precision": divide(tp, tp + fp),
            "recall_checked": divide(tp, tp + fn),
            "f1_checked": divide(2 * tp, 2 * tp + fp + fn),
        }
    flags = [r for r in checked if r["prediction"] != "supported"]
    true_flags = sum(r["label"] != "supported" for r in flags)
    false_flags = len(flags) - true_flags
    supported = sum(r["label"] == "supported" for r in checked)
    problems = sum(r["label"] != "supported" for r in checked)
    correct = sum(r["label"] == r["prediction"] for r in checked)
    f1s = [by_class[c]["f1_checked"] for c in LABELS]
    return {
        "planned": len(rows),
        "checked": len(checked),
        "not_checked": len(rows) - len(checked),
        "coverage": divide(len(checked), len(rows)),
        "correct": correct,
        "agreement_checked": divide(correct, len(checked)),
        "agreement_all": divide(correct, len(rows)),
        "confusion_checked": matrix,
        "per_class": by_class,
        "macro_f1_checked": sum(f1s) / len(f1s) if all(x is not None for x in f1s) else None,
        "true_flags": true_flags,
        "false_flags": false_flags,
        "flag_precision": divide(true_flags, len(flags)),
        "flag_recall_checked": divide(true_flags, problems),
        "supported_false_flag_rate_checked": divide(false_flags, supported),
    }


def build_report(directory, packet, annotations_path=None):
    run = read_json(directory / "run.json")
    for filename in ["cases.jsonl", "passages.jsonl", "manifest.json"]:
        if digest((packet / filename).read_bytes()) != run["packet_hashes"][filename]:
            raise ValueError("Report packet differs from inference packet")
    if annotations_path is None:
        annotations_path = packet / "annotations.assistant.jsonl"
    annotations = [
        json.loads(s) for s in annotations_path.read_text(encoding="utf-8").splitlines() if s
    ]
    if len({a["case_id"] for a in annotations}) != len(annotations):
        raise ValueError("Duplicate annotation ID")
    labels = {a["case_id"]: a for a in annotations}
    provenance = {
        r["case_id"]: r
        for r in map(
            json.loads, (packet / "provenance.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    cases = {
        r["case_id"]: r
        for r in map(json.loads, (packet / "cases.jsonl").read_text(encoding="utf-8").splitlines())
    }
    rows = []
    for case_id in run["planned_case_ids"]:
        if case_id not in labels or labels[case_id]["label"] not in LABELS:
            raise ValueError("Every planned case needs a valid, explicit annotation")
        path = directory / case_id / "result.json"
        result = read_json(path) if path.exists() else {"status": "not_run", "verdict": None}
        pred = result["verdict"]["label"] if result["status"] == "checked" else None
        rows.append(
            {
                "case_id": case_id,
                "origin": provenance[case_id]["origin"],
                "question_id": provenance[case_id]["question_id"],
                "label": labels[case_id]["label"],
                "prediction": pred,
                "status": result["status"],
                "seconds": result.get("seconds", 0),
                "usage": result.get("usage", {}),
                "error": result.get("error"),
            }
        )
    independent = all(labels[r["case_id"]].get("independently_adjudicated") is True for r in rows)
    report = {
        "run_status": run["status"],
        "annotation_file": str(annotations_path),
        "annotation_sha256": digest(annotations_path.read_bytes()),
        "independent_annotation": independent,
        "interpretation": "agreement with supplied labels; not baseline quality or end-to-end improvement",
        "metrics_by_origin": {
            origin: metrics([r for r in rows if r["origin"] == origin])
            for origin in sorted({r["origin"] for r in rows})
        },
        "seconds_total": sum(r["seconds"] for r in rows),
        "tokens": {
            key: sum(r["usage"].get(key, 0) for r in rows)
            for key in ["prompt_eval_count", "eval_count"]
        },
        "rows": rows,
    }
    write_json(directory / "assessment.json", report)
    lines = [
        "# Local verifier observer diagnostics\n\n",
        f"Run status: **{run['status']}**. Independent annotation: **{independent}**.\n\n",
        (
            "Agreement with assistant draft labels is provisional, not validated accuracy. "
            "Natural and constructed examples remain separate.\n\n"
        ),
        "| Origin | Checked/planned | Agreement | True flags | False flags |\n",
        "|---|---:|---:|---:|---:|\n",
    ]
    for origin, m in report["metrics_by_origin"].items():
        lines.append(
            f"| {origin} | {m['checked']}/{m['planned']} | {m['correct']}/{m['planned']} | {m['true_flags']} | {m['false_flags']} |\n"
        )
    lines.append(f"\nWall time of cases: {report['seconds_total']:.1f}s, including model load.\n\n")
    lines.append("## Cases\n\n| Case | Origin | Draft label | Prediction |\n|---|---|---|---|\n")
    for r in rows:
        lines.append(
            f"| {r['case_id']} | {r['origin']} | {r['label']} | {r['prediction'] or r['status']} |\n"
        )
    lines.append("\n## Disagreements and technical failures\n\n")
    for row in rows:
        if row["label"] == row["prediction"]:
            continue
        case_id = row["case_id"]
        result = (
            read_json(directory / case_id / "result.json")
            if (directory / case_id / "result.json").exists()
            else {}
        )
        lines.append(f"### {case_id}\n\n{cases[case_id]['claim']}\n\n")
        lines.append(
            f"Draft: {row['label']}; prediction: {row['prediction'] or row['status']}.\n\n"
        )
        verdict = result.get("verdict")
        lines.append((verdict["explanation"] if verdict else json.dumps(row["error"])) + "\n\n")
    (directory / "assessment.md").write_text("".join(lines), encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--packet", type=Path, default=Path("data/verification/claim-support-dev-v1")
    )
    parser.add_argument("--annotations", type=Path)
    args = parser.parse_args()
    result = build_report(args.run, args.packet, args.annotations)
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "run_status",
                    "independent_annotation",
                    "metrics_by_origin",
                    "seconds_total",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
