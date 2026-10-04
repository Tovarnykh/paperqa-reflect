"""Summarize the frozen B3 ablation and new mirrored judgments, retaining prior results."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from paperqa_reflect import pairwise
from paperqa_reflect.data import grade
from paperqa_reflect.verifier import digest, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def summarize(local, plan, prior_report):
    prior = read_json(prior_report)
    state = read_json(local / "run.json")
    if state["status"] != "completed" or prior["local_run"] != state["prior_run"]:
        raise ValueError("Incomplete run or wrong prior report")
    if digest((local / "input.json").read_bytes()) != prior["input_sha256"]:
        raise ValueError("Packet changed")
    assessment = pairwise.assess(plan)
    gold = {
        x["id"]: x["answer"] for x in (
            json.loads(line) for line in (ROOT / "data/gold/litqa-dev.jsonl").read_text().splitlines()
        )
    }
    questions, totals = [], Counter()
    for item in read_json(local / "input.json")["answers"]:
        aid = item["answer_id"]
        path = local / aid / "B3"
        answer = read_json(path / "answer.json")
        original = next(row for row in prior["questions"] if row["answer_id"] == aid)
        result = read_json(path / "revision/result.json")
        usage = result.get("usage", {})
        choice = grade(
            answer["answer"], gold[item["question_id"]], "success", True,
            tuple(item["sources"]), tuple(item["question"]["options"]),
        )["selected"]
        cost = Counter(
            requests=result["attempts"], seconds=answer["seconds"],
            input_tokens=usage.get("prompt_eval_count") or 0,
            output_tokens=usage.get("eval_count") or 0,
            load_seconds=(usage.get("load_duration") or 0) / 1e9,
            correct=int(choice == gold[item["question_id"]]),
            revised=int(answer["status"] == "revised"),
            fallbacks=int(answer["status"] == "fallback_original"),
            stage_failures=int(result["status"] != "checked"),
            same_request_as_B1=int(answer["same_request_as_B1"]),
            same_answer_as_B1=int(answer["same_answer_as_B1"]),
        )
        totals.update(cost)
        questions.append({
            "answer_id": aid, "question_id": item["question_id"], "question": item["question"],
            "sources": item["sources"],
            "arms": {**original["arms"], "B3": {
                **answer, "choice": choice, "correct": choice == gold[item["question_id"]],
                "cost": dict(cost), "answer_sha256": digest(answer["answer"].encode()),
            }},
            "comparisons": [x for x in assessment["pairs"] if x["pair_id"].startswith(aid + "-")],
        })
    comparisons = defaultdict(Counter)
    for pair in assessment["pairs"]:
        comparisons[pair["pair_id"].split("-", 2)[2]][pair["outcome"]] += 1
    return {
        "local_run": local.name, "judge_plan": plan.name, "run": state,
        "prior_report": prior_report.name, "prior_report_sha256": digest(prior_report.read_bytes()),
        "input_sha256": prior["input_sha256"],
        "wall_seconds": (datetime.fromisoformat(state["finished_utc"])
                         - datetime.fromisoformat(state["started_utc"])).total_seconds(),
        "totals": {**prior["totals"], "B3": dict(totals)},
        "comparisons": dict(comparisons), "external_checked": assessment["checked"],
        "questions": questions, "judge_run": read_json(plan / "run.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = summarize(args.local, args.plan, ROOT / "results/reports/2026-10-03-main-dev-comparison.json")
    write_json(args.output, report)
    print(json.dumps({k: report[k] for k in ["totals", "comparisons", "external_checked", "wall_seconds"]}))


if __name__ == "__main__":
    main()
