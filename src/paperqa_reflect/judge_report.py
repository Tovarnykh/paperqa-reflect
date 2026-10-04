"""Compare a saved local observer with an external judge, never with assumed human gold."""

import argparse
import json
from pathlib import Path

from .judge import DEFAULT_PACKET, JudgeError, load_plan
from .verifier import LABELS, digest, read_json, write_json
from .verifier_report import divide, metrics


def build_report(plan_directory, observer_directory, packet, output):
    plan, config, _ = load_plan(plan_directory)
    run = read_json(plan_directory / "run.json")
    observer = read_json(observer_directory / "run.json")
    for name, expected in plan["packet_hashes"].items():
        if digest((packet / name).read_bytes()) != expected:
            raise JudgeError("report_packet_mismatch")
        if observer["packet_hashes"].get(name) != expected:
            raise JudgeError("observer_packet_mismatch")
    manifest = read_json(packet / "manifest.json")
    if digest((packet / "provenance.jsonl").read_bytes()) != manifest["files"]["provenance.jsonl"]:
        raise JudgeError("provenance_integrity")
    provenance = {
        r["case_id"]: r
        for r in map(
            json.loads, (packet / "provenance.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    rows, annotations = [], []
    for item in plan["rows"]:
        cid = item["case_id"]
        path = plan_directory / (item["anonymous_id"] + ".result.json")
        result = read_json(path) if path.exists() else {"status": "not_run"}
        local_path = observer_directory / cid / "result.json"
        local = read_json(local_path) if local_path.exists() else {"status": "not_run"}
        ref = result["verdict"] if result["status"] == "checked" else None
        pred = local["verdict"] if local["status"] == "checked" else None
        if ref and ref["label"] not in LABELS:
            raise JudgeError("invalid_reference_label")
        if cid not in observer["planned_case_ids"]:
            raise JudgeError("case_not_in_local_run")
        rows.append(
            {
                "case_id": cid,
                "origin": provenance[cid]["origin"],
                "question_id": provenance[cid]["question_id"],
                "label": ref["label"] if ref else None,
                "prediction": pred["label"] if pred else None,
                "judge_status": result["status"],
                "local_status": local["status"],
                "judge_explanation": ref["explanation"] if ref else None,
                "local_explanation": pred["explanation"] if pred else None,
            }
        )
        if ref:
            annotations.append(
                {
                    "case_id": cid,
                    "label": ref["label"],
                    "evidence": ref["evidence"],
                    "rationale": ref["explanation"],
                    "reviewer_id": config["model"],
                    "reference_type": "external_llm_judge",
                    "independently_adjudicated": False,
                }
            )
    groups = {}
    for origin in sorted({row["origin"] for row in rows}):
        group = [row for row in rows if row["origin"] == origin]
        judged = [row for row in group if row["label"] is not None]
        matched = sum(row["label"] == row["prediction"] for row in judged)
        groups[origin] = {
            "planned": len(group),
            "reference_checked": len(judged),
            "reference_coverage": divide(len(judged), len(group)),
            "unjudged_reference": len(group) - len(judged),
            "metrics_on_available_reference": metrics(judged),
            "agreement_all_lower": divide(matched, len(group)),
            "agreement_all_upper": divide(matched + len(group) - len(judged), len(group)),
        }
    report = {
        "reference_type": "external_llm_judge",
        "independent_human_gold": False,
        "judge_model": config["model"],
        "judge_run_status": run["status"],
        "observer_run_status": observer["status"],
        "packet_hashes": plan["packet_hashes"],
        "interpretation": "Agreement with external model, not validated factual accuracy.",
        "metrics_by_origin": groups,
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "assessment.json", report)
    (output / "annotations.external-judge.jsonl").write_text(
        "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in annotations), encoding="utf-8"
    )
    lines = [
        "# External judge versus local verifier\n\n",
        (
            "Reference: external model labels; no independent human gold. "
            "Unjudged cases remain visible, natural/controlled cases are separate.\n\n"
        ),
        "| Origin | Judge coverage | Local agreement on available references |\n",
        "|---|---:|---:|\n",
    ]
    for origin, group in groups.items():
        m = group["metrics_on_available_reference"]
        lines.append(
            f"| {origin} | {group['reference_checked']}/{group['planned']} "
            f"| {m['correct']}/{m['planned']} |\n"
        )
    lines.append("\n## Disagreements or missing checks\n\n")
    for row in rows:
        if row["label"] is not None and row["label"] == row["prediction"]:
            continue
        lines.append(
            f"- {row['case_id']}: judge={row['label'] or row['judge_status']}; "
            f"local={row['prediction'] or row['local_status']}. "
            f"Judge: {row['judge_explanation'] or 'not available'}\n"
        )
    (output / "assessment.md").write_text("".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("observer", type=Path)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.plan, args.observer, args.packet, args.output)
    print(
        json.dumps(
            {
                "reference_type": report["reference_type"],
                "metrics_by_origin": report["metrics_by_origin"],
            }
        )
    )


if __name__ == "__main__":
    main()
