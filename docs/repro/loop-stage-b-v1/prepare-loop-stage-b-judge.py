"""Offline Stage B judge packets; never opens API credentials or the budget ledger.

Run with the citation repository's Python. The default is a check-only audit.
--output creates an immutable packet and frozen request plan only when ready.
--pilot-fixture checks the two saved Stage A pairs without creating a Stage B plan.
"""

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
WORKSPACE = Path(__file__).resolve().parents[1]
CITATION_ROOT = WORKSPACE / "research/paperqa-reflect"
LOOP_ROOT = WORKSPACE / "research/paperqa-loop"
sys.path.insert(0, str(CITATION_ROOT / "src"))
from paperqa_reflect import judge, pairwise

CITATION = re.compile(r"pqac-[a-zA-Z0-9]+")
RUN_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{6}")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def read(path, artifacts=None):
    raw = path.read_bytes()
    if artifacts is not None:
        artifacts[str(path.resolve())] = sha(raw)
    return json.loads(raw)


def write(path, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n"
    with path.open("xb") as stream:
        stream.write(raw)


def verify_evaluator(freeze):
    for name, item in freeze["files"].items():
        if sha((CITATION_ROOT / name).read_bytes()) != item["sha256"]:
            raise ValueError(f"Frozen evaluator file changed: {name}")
    for name, expected in freeze["packages"].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError(f"Evaluator package changed: {name}")
    config = judge.validate_config(freeze["config"])
    recipe = {
        "kind": pairwise.KIND,
        "prompt": pairwise.PROMPT,
        "schema": pairwise.SCHEMA,
        "config": config,
        "request_template": pairwise.request_for(freeze["placeholder_case"], config),
    }
    if sha(canonical(recipe)) != freeze["recipe_canonical_sha256"]:
        raise ValueError("Live evaluator recipe differs from pre-inference freeze")
    return config


def source_union(arms):
    """Preserve every cited ID and full original passage; no summary or truncation."""
    sources, unresolved, conflicts = {}, [], []
    for arm, item in arms.items():
        cited = set(CITATION.findall(item["raw_answer"]))
        available = defaultdict(set)
        for context in item["contexts"]:
            cid = context.get("id")
            if cid in cited:
                text = context.get("text", {}).get("text")
                if isinstance(text, str) and text.strip():
                    available[cid].add(text)
        for cid in sorted(cited):
            candidates = available[cid]
            if not candidates:
                unresolved.append({"arm": arm, "citation_id": cid})
            elif len(candidates) != 1:
                conflicts.append({"arm": arm, "citation_id": cid, "scope": "within_arm"})
            else:
                text = next(iter(candidates))
                if cid in sources and sources[cid] != text:
                    conflicts.append({"arm": arm, "citation_id": cid, "scope": "between_arms"})
                else:
                    sources[cid] = text
    return dict(sorted(sources.items())), unresolved, conflicts


def normalized_schedule(plan, pilot_fixture):
    expected_kind = "loop-evidence-pilot-v1" if pilot_fixture else "loop-evidence-stage-b-v1"
    if plan["kind"] != expected_kind:
        raise ValueError(f"Expected {expected_kind}; refusing to relabel another experiment")
    jobs = []
    for index, row in enumerate(plan["schedule"], 1):
        job = dict(row)
        if pilot_fixture:
            job.update(job=index, seed=42)
        jobs.append(job)
    expected_jobs, expected_questions, expected_seeds = (4, 2, {42}) if pilot_fixture else (32, 8, {42, 43})
    keys = [(j["question_id"], j["seed"], j["n"]) for j in jobs]
    if (len(jobs) != expected_jobs or len(set(keys)) != expected_jobs
            or [j["job"] for j in jobs] != list(range(1, expected_jobs + 1))
            or len({j["question_id"] for j in jobs}) != expected_questions
            or {j["seed"] for j in jobs} != expected_seeds
            or {j["n"] for j in jobs} != {1, 3}):
        raise ValueError("Incomplete or duplicate frozen schedule")
    counts = Counter((j["question_id"], j["seed"]) for j in jobs)
    if any(count != 2 for count in counts.values()):
        raise ValueError("Schedule does not contain exactly two arms per pair")
    return jobs


def collect(stage_dir, pilot_fixture=False):
    artifacts = {}
    plan = read(stage_dir / "plan.json", artifacts)
    progress = read(stage_dir / "progress.json", artifacts)
    jobs = normalized_schedule(plan, pilot_fixture)
    freeze = (read(WORKSPACE / ".tmp/loop-stage-b-evaluator-freeze.json", artifacts)
              if pilot_fixture else plan["evaluator"])
    config = verify_evaluator(freeze)
    outcomes = progress["outcomes"]
    if len({x["job"] for x in outcomes}) != len(outcomes):
        raise ValueError("Duplicate outcome job")
    by_job = {x["job"]: x for x in outcomes}
    if not set(by_job) <= {j["job"] for j in jobs}:
        raise ValueError("Outcome not in frozen schedule")
    groups, run_ids = defaultdict(dict), set()
    audit = {
        "kind": "stage-a-offline-fixture-audit" if pilot_fixture else "loop-stage-b-judge-preparation-v1",
        "generation_status": progress["status"], "scheduled_attempts": len(jobs),
        "recorded_attempts": len(outcomes), "planned_pairs": len(jobs) // 2,
        "statuses": {}, "technical_skips": [], "pending_jobs": [], "unresolved_citations": [],
        "conflicting_citations": [], "unjudgeable_pairs": [], "pair_audit": [],
        "blocking_integrity_errors": [], "evaluator_recipe_sha256": freeze["recipe_canonical_sha256"],
        "adapter_sha256": sha(Path(__file__).read_bytes()), "input_artifact_sha256": artifacts,
        "no_api_calls": True, "budget_ledger_checked": False,
        "scope": "Original cited passage support only; no claim of expert truth or source completeness.",
    }
    statuses = Counter()
    for job in jobs:
        number, qid, seed, n = (job[k] for k in ("job", "question_id", "seed", "n"))
        if number not in by_job:
            audit["pending_jobs"].append(number)
            continue
        outcome = by_job[number]
        for key in ("n", "seed", "question_id"):
            if key in outcome and outcome[key] != job[key]:
                raise ValueError(f"Outcome disagrees with schedule: job {number}/{key}")
        run_path = outcome.get("run_path", "")
        run_id = run_path.replace("\\", "/").rstrip("/").split("/")[-1]
        if not RUN_ID.fullmatch(run_id):
            audit["technical_skips"].append({"job": number, "reason": "missing_valid_run_path"})
            continue
        if run_id in run_ids:
            raise ValueError("One saved run was reused for two attempts")
        run_ids.add(run_id)
        local = LOOP_ROOT / "results/runs" / run_id
        try:
            summary = read(local / "summary.json", artifacts)
            review = read(local / qid / "review.json", artifacts)
            provenance = read(local / "provenance.json", artifacts)
            run_config = read(local / "config.json", artifacts)
        except FileNotFoundError as exc:
            audit["blocking_integrity_errors"].append({"job": number, "missing_artifact": str(exc.filename)})
            continue
        rows = summary["records"]
        if len(rows) != 1 or rows[0]["id"] != qid or review["question"]["id"] != qid:
            raise ValueError(f"Run/question mismatch for job {number}")
        row = rows[0]
        if (provenance["git"]["head"] != plan["git"]["head"] or provenance["git"]["status"]
                or provenance["config_sha256"] != job["config_sha256"]
                or run_config["seed"] != seed or run_config["agent_evidence_n"] != n):
            raise ValueError(f"Run provenance/config mismatch for job {number}")
        if not pilot_fixture:
            if any(provenance[key] != plan["input_sha256"][key] for key in
                   ("questions_sha256", "gold_sha256", "corpus_manifest_sha256")):
                raise ValueError(f"Run inputs differ from frozen Stage B: job {number}")
            if provenance["packages"] != plan["packages"]:
                raise ValueError(f"Run packages differ from frozen Stage B: job {number}")
            for name, digest in provenance["code_sha256"].items():
                if name in plan["source_sha256"] and plan["source_sha256"][name] != digest:
                    raise ValueError(f"Run source differs from frozen Stage B: job {number}/{name}")
        if (provenance["model_info"]["version"] != "0.35.0" or any(
                provenance["model_info"]["models"][name]["digest"] != digest
                for name, digest in plan["models"].items())):
            raise ValueError(f"Run model/runtime differs from frozen plan: job {number}")
        if row["raw_answer"] != review["raw_answer"] or row["status"] != review["status"]:
            raise ValueError(f"Saved answer or status mismatch for job {number}")
        expected_sha = outcome.get("metrics", {}).get("raw_answer_sha256")
        if expected_sha is not None and sha(row["raw_answer"].encode()) != expected_sha:
            raise ValueError(f"Raw answer no longer matches recorded hash: job {number}")
        statuses[row["status"]] += 1
        if row["status"] not in ("success", "unsure") or not row["raw_answer"].strip():
            audit["technical_skips"].append({"job": number, "run_id": run_id,
                                             "status": row["status"], "reason": "no_usable_completed_answer"})
            continue
        groups[qid, seed][f"N{n}"] = {
            "question": {"question": review["question"]["question"], "options": review["question"]["options"]},
            "raw_answer": row["raw_answer"], "contexts": review["contexts"],
            "run_id": run_id, "status": row["status"], "job": number,
        }
    pairs = []
    expected_pairs = list(dict.fromkeys((j["question_id"], j["seed"]) for j in jobs))
    for qid, seed in expected_pairs:
        pair_id = f"{qid}-s{seed}-N1-N3"
        arms = groups[qid, seed]
        if set(arms) != {"N1", "N3"}:
            audit["unjudgeable_pairs"].append({"pair_id": pair_id, "reason": "missing_usable_arm",
                                               "available_arms": sorted(arms)})
            continue
        if arms["N1"]["question"] != arms["N3"]["question"]:
            raise ValueError("Question/options differ between paired arms")
        sources, missing, collisions = source_union(arms)
        audit["unresolved_citations"].extend({"pair_id": pair_id, **x} for x in missing)
        audit["conflicting_citations"].extend({"pair_id": pair_id, **x} for x in collisions)
        if not sources:
            audit["unjudgeable_pairs"].append({"pair_id": pair_id, "reason": "no_original_cited_evidence"})
            continue
        if missing or collisions:
            continue
        pair = {"pair_id": pair_id, "arms": ["N1", "N3"], "question": arms["N1"]["question"],
                "sources": sources, "answers": {a: item["raw_answer"] for a, item in arms.items()}}
        pairs.append(pair)
        audit["pair_audit"].append({
            "pair_id": pair_id, "seed": seed, "question_id": qid,
            "arms": {a: {"run_id": item["run_id"], "status": item["status"],
                          "answer_sha256": sha(item["raw_answer"].encode())} for a, item in arms.items()},
            "source_sha256": {cid: sha(text.encode()) for cid, text in sources.items()},
            "source_characters": sum(map(len, sources.values())),
        })
    audit["statuses"] = dict(statuses)
    audit["eligible_pairs"] = len(pairs)
    audit["planned_judgments"] = len(pairs) * 2
    audit["input_integrity_valid"] = not any(audit[k] for k in (
        "blocking_integrity_errors", "unresolved_citations", "conflicting_citations"))
    audit["packet_ready"] = (not pilot_fixture and progress["status"] == "completed"
                             and not audit["pending_jobs"] and audit["input_integrity_valid"] and bool(pairs))
    # This tool cannot declare paid execution ready without the separate budget preflight.
    audit["judge_ready"] = False
    audit["judge_ready_reason"] = "Separate live budget/token-count preflight required; adapter never accesses API or ledger."
    return pairs, audit, freeze, config


def make_output(destination, pairs, audit, freeze, config):
    if not audit["packet_ready"]:
        raise ValueError("Preparation is blocked; inspect printed audit, no packet written")
    destination.mkdir(parents=True, exist_ok=False)
    packet = destination / "packet"
    pairwise.packet_write(packet, pairs, {
        "kind": audit["kind"], "generation_input_sha256": audit["input_artifact_sha256"],
        "adapter_sha256": audit["adapter_sha256"], "evaluator_recipe_sha256": freeze["recipe_canonical_sha256"],
        "evidence_policy": "Full union of original passages cited by either arm; no truncation; no answer keys.",
        "technical_skips": audit["technical_skips"], "unjudgeable_pairs": audit["unjudgeable_pairs"],
    })
    request_plan = pairwise.build_plan(packet, CITATION_ROOT / "configs/judge-openai-revision-dev-v1.json",
                                       destination / "plans")
    _, loaded_config, requests = pairwise.load_plan(request_plan)
    if loaded_config != config or len(requests) != len(pairs) * 2:
        raise ValueError("Prepared plan differs from frozen recipe/count")
    estimate = sum(judge.reserve_cost(judge.offline_input_estimate(req), config) for req in requests.values())
    audit.update(packet=str(packet), request_plan=str(request_plan),
                 offline_conservative_reservation_usd=judge.usd(estimate),
                 estimate_note="Byte-based offline upper estimate; actual token counting and remaining-budget check still required.")
    write(destination / "audit.json", audit)
    write(destination / "evaluator-freeze.json", freeze)


def self_test():
    good = {"raw_answer": "Claim (pqac-a).", "contexts": [{"id": "pqac-a", "text": {"text": "Full source"}}]}
    other = {"raw_answer": "Claim (pqac-b).", "contexts": [{"id": "pqac-b", "text": {"text": "Other full source"}}]}
    sources, missing, conflicts = source_union({"N1": good, "N3": other})
    assert sources == {"pqac-a": "Full source", "pqac-b": "Other full source"}
    assert not missing and not conflicts
    bad = {"raw_answer": "Claim (pqac-a).", "contexts": [{"id": "pqac-a", "text": {"text": "Different source"}}]}
    assert source_union({"N1": good, "N3": bad})[2]
    assert source_union({"N1": {"raw_answer": "Claim (pqac-missing).", "contexts": []}})[1]
    fixture = LOOP_ROOT / "results/loop-pilot/20261004T114111Z-aeb0a1"
    pairs, audit, _, config = collect(fixture, pilot_fixture=True)
    assert len(pairs) == 2 and audit["input_integrity_valid"]
    assert audit["statuses"] == {"success": 3, "unsure": 1}
    assert not audit["packet_ready"] and not audit["judge_ready"]
    for pair in pairs:
        forward = {"case_id": "item-001", "question": pair["question"], "sources": pair["sources"],
                   "answers": {"A": pair["answers"]["N1"], "B": pair["answers"]["N3"]}}
        reverse = {**forward, "answers": {"A": forward["answers"]["B"], "B": forward["answers"]["A"]}}
        for case in (forward, reverse):
            payload = json.loads(pairwise.request_for(case, config)["input"][0]["content"])
            assert set(payload) == {"case_id", "question", "sources", "answers"}
            assert set(payload["question"]) == {"question", "options"}
            assert payload["sources"] == pair["sources"]
    return {"self_test": "passed", "fixture_kind": audit["kind"], "fixture_pairs": len(pairs),
            "statuses": audit["statuses"], "api_calls": 0, "files_written": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dir", type=Path, nargs="?")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot-fixture", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return
    if args.stage_dir is None:
        parser.error("stage_dir is required unless --self-test is used")
    if args.pilot_fixture and args.output:
        parser.error("Pilot fixture is audit-only and cannot create a Stage B judge plan")
    pairs, audit, freeze, config = collect(args.stage_dir, args.pilot_fixture)
    if args.output:
        if not audit["packet_ready"]:
            print(json.dumps(audit, ensure_ascii=False, indent=2))
            raise SystemExit("Packet blocked; no output was written")
        make_output(args.output, pairs, audit, freeze, config)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
