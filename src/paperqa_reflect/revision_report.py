"""Export all B0/B1/B2 cited claims for blinded judging; retain uncited claims in metrics."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .judge import load_plan
from .verifier import digest, load_packet, read_json, write_json

ROOT = Path(__file__).resolve().parents[2]


def jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def export(run, output):
    state = read_json(run / "run.json")
    if state["status"] != "completed":
        raise ValueError("Only completed engineering runs can be exported")
    packet = read_json(run / "input.json")
    cases, mapping, sources, hashes = [], [], {}, {}
    hashes["input.json"] = digest((run / "input.json").read_bytes())
    for item in packet["answers"]:
        aid = item["answer_id"]
        for pid, text in item["sources"].items():
            if pid in sources and sources[pid] != text:
                raise ValueError("Source ID collision")
            sources[pid] = text
        for variant in ["B0", "B1", "B2"]:
            base = run / aid / variant
            for name in ["answer.json", "claims.json", "sentence-units.json"]:
                hashes[(base / name).relative_to(run).as_posix()] = digest(
                    (base / name).read_bytes()
                )
            claims = read_json(base / "claims.json")
            for claim in claims:
                cid = f"{aid}-{variant}-{claim['case_id']}"
                mapping.append(
                    {
                        "case_id": cid,
                        "answer_id": aid,
                        "variant": variant,
                        "claim": claim["claim"],
                        "passage_ids": claim["passage_ids"],
                        "answer_quote": claim["answer_quote"],
                        "disposition": "judge" if claim["passage_ids"] else "no_citation",
                    }
                )
                if claim["passage_ids"]:
                    cases.append({k: mapping[-1][k] for k in ["case_id", "claim", "passage_ids"]})
    if not cases:
        raise ValueError("No cited claims to evaluate")
    output.mkdir(parents=True, exist_ok=False)
    jsonl(output / "cases.jsonl", cases)
    jsonl(
        output / "passages.jsonl",
        [
            {"passage_id": pid, "text": text, "sha256": digest(text.encode())}
            for pid, text in sorted(sources.items())
        ],
    )
    write_json(
        output / "mapping.json",
        {
            "source_run": str(run.resolve()),
            "source_run_hashes": hashes,
            "claims": mapping,
            "note": "No-citation claims are excluded from API calls, never from metric denominators.",
        },
    )
    write_json(
        output / "manifest.json",
        {
            "kind": "bounded-revision-external-judge-v1",
            "files": {
                name: digest((output / name).read_bytes())
                for name in ["cases.jsonl", "passages.jsonl", "mapping.json"]
            },
        },
    )
    load_packet(output)
    return {
        "total_claims": len(mapping),
        "judge_claims": len(cases),
        "no_citation": len(mapping) - len(cases),
    }


def summarize_rows(rows):
    labels = Counter(row["label"] for row in rows)
    n = len(rows)
    return {
        "claims": n,
        "labels": dict(labels),
        "supported_fraction_lower": labels["supported"] / n if n else 0,
        "supported_fraction_upper": (labels["supported"] + labels["not_checked"]) / n if n else 0,
    }


def added_work(run, answer_id, variant):
    """Separate intervention work from extraction done only for outcome measurement."""
    base = run / answer_id
    if variant == "B0":
        return {
            "measurement_available": True,
            "calls": 0,
            "seconds": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "load_seconds": 0,
        }
    if variant == "B1":
        paths = [base / "ordinary-review/result.json", base / "B1/revision/result.json"]
    else:
        paths = [base / "B0/extraction/result.json", base / "B2/revision/result.json"]
        paths += list((base / "verification").glob("*/result.json"))
    if not all(p.exists() for p in paths):
        return {"measurement_available": False}
    results = [read_json(p) for p in paths]
    usage = [r.get("usage", {}) for r in results]
    return {
        "measurement_available": True,
        "calls": sum(r.get("attempts", 0) for r in results),
        "seconds": sum(r.get("seconds", 0) for r in results),
        "input_tokens": sum(u.get("prompt_eval_count") or 0 for u in usage),
        "output_tokens": sum(u.get("eval_count") or 0 for u in usage),
        "load_seconds": sum(u.get("load_duration") or 0 for u in usage) / 1e9,
    }


def merge_judgments(plan_paths, packet_path):
    """Reuse only identical claim/evidence inputs; reject duplicates and changed scope."""
    cases, passages = load_packet(packet_path)
    cases = {c["case_id"]: c for c in cases}
    judgments, config = {}, None
    for plan_path in plan_paths:
        plan, current_config, requests = load_plan(plan_path)
        if config is not None and current_config != config:
            raise ValueError("Judge profiles differ")
        config = current_config
        for row in plan["rows"]:
            cid = row["case_id"]
            if cid not in cases or cid in judgments:
                raise ValueError("Unknown or duplicate judged claim")
            payload = json.loads(requests[row["anonymous_id"]]["input"][0]["content"])
            actual = {
                row["passage_mapping"][p["passage_id"]]: p["text"] for p in payload["passages"]
            }
            expected = {pid: passages[pid] for pid in cases[cid]["passage_ids"]}
            if payload["claim"] != cases[cid]["claim"] or actual != expected:
                raise ValueError("Reused judgment has different claim or evidence scope")
            path = plan_path / (row["anonymous_id"] + ".result.json")
            result = read_json(path) if path.exists() else {"status": "not_run"}
            judgments[cid] = {
                **result,
                "judge_plan": str(plan_path),
                "anonymous_id": row["anonymous_id"],
            }
    if set(judgments) != set(cases):
        raise ValueError("Merged plans do not cover the final cited-claim packet")
    return config, judgments


def report(run, packet_path, judge_path, output, supplements=None):
    manifest = read_json(packet_path / "manifest.json")
    for name, expected in manifest["files"].items():
        if digest((packet_path / name).read_bytes()) != expected:
            raise ValueError("Evaluation packet changed")
    mapping = read_json(packet_path / "mapping.json")
    for path, expected in mapping["source_run_hashes"].items():
        if digest((run / path).read_bytes()) != expected:
            raise ValueError("Source revision run changed")
    if supplements:
        config, judgments = merge_judgments([judge_path, *supplements], packet_path)
    else:
        plan, config, _ = load_plan(judge_path)
        for name, expected in plan["packet_hashes"].items():
            if digest((packet_path / name).read_bytes()) != expected:
                raise ValueError("Judge used a different packet")
        judgments = {}
        for item in plan["rows"]:
            path = judge_path / (item["anonymous_id"] + ".result.json")
            result = read_json(path) if path.exists() else {"status": "not_run"}
            judgments[item["case_id"]] = result
    rows = []
    for original in mapping["claims"]:
        row = dict(original)
        if row["disposition"] == "no_citation":
            row.update(label="no_citation", explanation="No explicit citation on the sentence.")
        else:
            result = judgments.get(row["case_id"], {"status": "not_run"})
            verdict = result.get("verdict") if result["status"] == "checked" else None
            row.update(
                label=verdict["label"] if verdict else "not_checked",
                explanation=verdict["explanation"] if verdict else result["status"],
                judge_plan=result.get("judge_plan", str(judge_path)),
            )
        rows.append(row)
    answers = []
    for item in read_json(run / "input.json")["answers"]:
        review_path = ROOT / item["source_review_path"]
        if digest(review_path.read_bytes()) != item["source_review_sha256"]:
            raise ValueError("Original review changed before key scoring")
        # Answer keys are read only after generation and external citation judging.
        key = read_json(review_path)["reference"]["answer"]
        for variant in ["B0", "B1", "B2"]:
            aid = item["answer_id"]
            answer = read_json(run / aid / variant / "answer.json")
            choice = re.search(r"Final answer:\s*([A-Z]|UNSURE)\s*$", answer["answer"])
            selected = choice.group(1) if choice else None
            selected_rows = [r for r in rows if r["answer_id"] == aid and r["variant"] == variant]
            answers.append(
                {
                    "answer_id": aid,
                    "variant": variant,
                    "status": answer["status"],
                    "choice": selected,
                    "key_match": selected == key,
                    "added_work": added_work(run, aid, variant),
                    **summarize_rows(selected_rows),
                }
            )
    result = {
        "kind": "engineering-pilot-only",
        "judge_model": config["model"],
        "independent_human_gold": False,
        "answers": answers,
        "claims": rows,
        "completeness_assessed": False,
        "limits": "Two selected known dev failures; model extraction and one model judge. Citation placement affects score. No final quality claim.",
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "assessment.json", result)
    lines = [
        "# Bounded revision: diagnostic citation support\n\n",
        "Two known dev failures. External LLM reference, not human gold. Completeness remains ungraded.\n\n",
        "| Answer | Variant | Claims | Supported | No citation | Contradicted | Insufficient | Unchecked | Key match |\n",
        "|---|---|---:|---:|---:|---:|---:|---:|---|\n",
    ]
    for a in answers:
        c = Counter(a["labels"])
        lines.append(
            f"| {a['answer_id']} | {a['variant']} | {a['claims']} | {c['supported']} | "
            f"{c['no_citation']} | {c['contradicted']} | {c['insufficient']} | "
            f"{c['not_checked']} | {a['key_match']} |\n"
        )
    lines.append("\n## Non-supported claims\n\n")
    for row in rows:
        if row["label"] != "supported":
            lines.append(
                f"- {row['case_id']} ({row['label']}): {row['claim']} — {row['explanation']}\n"
            )
    lines.append(
        "\n## Added local work\n\nIncludes model load time; sequential engineering run, not an optimized latency benchmark. Outcome-only B1/B2 claim extraction is excluded.\n\n"
    )
    for answer in answers:
        work = answer["added_work"]
        lines.append(f"- {answer['answer_id']} {answer['variant']}: {json.dumps(work)}\n")
    (output / "assessment.md").write_text("".join(lines), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    exporting = sub.add_parser("export")
    exporting.add_argument("run", type=Path)
    exporting.add_argument("output", type=Path)
    reporting = sub.add_parser("report")
    reporting.add_argument("run", type=Path)
    reporting.add_argument("packet", type=Path)
    reporting.add_argument("judge", type=Path)
    reporting.add_argument("output", type=Path)
    reporting.add_argument("--supplement", type=Path, action="append")
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export(args.run, args.output)))
    else:
        print(
            json.dumps(
                report(args.run, args.packet, args.judge, args.output, args.supplement)["answers"]
            )
        )


if __name__ == "__main__":
    main()
