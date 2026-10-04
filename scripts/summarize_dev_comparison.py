"""Aggregate completed local arms and mirrored external verdicts, without gold in inference."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from paperqa_reflect import pairwise
from paperqa_reflect.data import grade
from paperqa_reflect.verifier import digest, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def summarize(local, plan):
    packet = read_json(local / "input.json")
    state = read_json(local / "run.json")
    if state["status"] != "completed":
        raise ValueError("Local run incomplete")
    assessment = pairwise.assess(plan)
    gold = {
        x["id"]: x
        for x in (
            json.loads(line)
            for line in (ROOT / "data/gold/litqa-dev.jsonl").read_text().splitlines()
        )
    }
    questions, totals = [], defaultdict(Counter)
    for item in packet["answers"]:
        aid = item["answer_id"]
        row = {
            "answer_id": aid,
            "question_id": item["question_id"],
            "question": item["question"],
            "arm_order": item["arm_order"],
            "arms": {},
        }
        for arm in ["B0", "B1", "B2"]:
            path = local / aid / arm
            answer = read_json(path / "answer.json")
            choice = grade(
                answer["answer"],
                gold[item["question_id"]]["answer"],
                "success",
                True,
                tuple(item["sources"]),
                tuple(item["question"]["options"]),
            )["selected"]
            correct = choice == gold[item["question_id"]]["answer"]
            requests = [read_json(p) for p in path.rglob("result.json")]
            counts = Counter(
                requests=sum(x["attempts"] for x in requests),
                input_tokens=sum(
                    x.get("usage", {}).get("prompt_eval_count") or 0 for x in requests
                ),
                output_tokens=sum(x.get("usage", {}).get("eval_count") or 0 for x in requests),
                load_seconds=sum(x.get("usage", {}).get("load_duration") or 0 for x in requests)
                / 1e9,
                seconds=answer["seconds"],
                correct=int(correct),
                revised=int(answer["status"] == "revised"),
                fallbacks=int(answer["status"] == "fallback_original"),
                stage_failures=sum(x["status"] != "checked" for x in requests),
                unchanged_text=int(answer["answer"].strip() == item["original_answer"].strip()),
            )
            totals[arm].update(counts)
            row["arms"][arm] = {
                **answer,
                "choice": choice,
                "correct": correct,
                "cost": dict(counts),
                "answer_sha256": digest(answer["answer"].encode()),
            }
        row["comparisons"] = [p for p in assessment["pairs"] if p["pair_id"].startswith(aid + "-")]
        feedback = local / aid / "B2/feedback.json"
        row["verifier_labels"] = (
            dict(
                Counter(
                    x["verdict"]["label"] if x["status"] == "checked" else "not_checked"
                    for x in read_json(feedback)
                )
            )
            if feedback.exists()
            else {}
        )
        questions.append(row)
    comparisons = defaultdict(Counter)
    for p in assessment["pairs"]:
        comparison = p["pair_id"].split("-", 2)[2]
        comparisons[comparison][p["outcome"]] += 1
    return {
        "local_run": local.name,
        "judge_plan": plan.name,
        "run": state,
        "wall_seconds": (
            datetime.fromisoformat(state["finished_utc"])
            - datetime.fromisoformat(state["started_utc"])
        ).total_seconds(),
        "input_sha256": digest((local / "input.json").read_bytes()),
        "totals": dict(totals),
        "comparisons": dict(comparisons),
        "external_checked": assessment["checked"],
        "questions": questions,
        "judge_run": read_json(plan / "run.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = summarize(args.local, args.plan)
    write_json(args.output, report)
    print(
        json.dumps(
            {k: report[k] for k in ["totals", "comparisons", "external_checked", "wall_seconds"]}
        )
    )


if __name__ == "__main__":
    main()
