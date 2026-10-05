"""Offline Stage C packets for N8/N1 and N8/N3; no API, credentials or ledger.

Default is a read-only audit. --output writes one immutable packet/request plan.
Preserves the inspected failure/interruption and never substitutes historical runs.
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
ORIGIN = "20261004T210539Z-3f1ab1"
ORIGINAL_HEAD = "ad5b60ced2ae4b695c7f7119ddc7e49e5d0b5379"
RECIPE_SHA = "b45a1fde6d323e000193d2015d45b1ce132a763b5e4fe237dd029d1d774681f9"


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
    if freeze["recipe_canonical_sha256"] != RECIPE_SHA:
        raise ValueError("Expected original Stage B v2.1 recipe")
    for name, item in freeze["files"].items():
        if sha((CITATION_ROOT / name).read_bytes()) != item["sha256"]:
            raise ValueError(f"Frozen evaluator file changed: {name}")
    for name, expected in freeze["packages"].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError(f"Evaluator package changed: {name}")
    config = judge.validate_config(freeze["config"])
    recipe = {
        "kind": pairwise.KIND, "prompt": pairwise.PROMPT, "schema": pairwise.SCHEMA,
        "config": config,
        "request_template": pairwise.request_for(freeze["placeholder_case"], config),
    }
    if sha(canonical(recipe)) != RECIPE_SHA:
        raise ValueError("Live evaluator recipe differs from pre-inference freeze")
    return config


def source_union(arms):
    """Keep exact full originals cited by either answer; fail on ID ambiguity."""
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


def validate_schedule(plan):
    if plan["kind"] != "loop-evidence-stage-c-v1":
        raise ValueError("Refusing to relabel a different experiment")
    jobs = plan["schedule"]
    keys = [(j["question_id"], j["seed"], j["n"]) for j in jobs]
    if (len(jobs) != 48 or len(set(keys)) != 48
            or [j["job"] for j in jobs] != list(range(1, 49))
            or len({j["question_id"] for j in jobs}) != 8
            or {j["seed"] for j in jobs} != {42, 43}
            or {j["n"] for j in jobs} != {1, 3, 8}):
        raise ValueError("Incomplete or duplicate frozen schedule")
    pools = defaultdict(set)
    for job in jobs:
        pools[job["question_id"], job["seed"]].add(job["n"])
    if len(pools) != 16 or any(pool != {1, 3, 8} for pool in pools.values()):
        raise ValueError("Exactly three arms per question/seed are required")
    return jobs


def validate_recovery(plan, progress, recovery, recovered):
    jobs = validate_schedule(plan)
    if plan["git"] != {"head": ORIGINAL_HEAD, "status": ""}:
        raise ValueError("Expected original clean Stage C source commit")
    if (recovery["kind"] != "loop-evidence-stage-c-manual-continuation-v1"
            or recovery["origin_git"] != plan["git"] or recovery["git"]["status"]
            or recovery["schedule"] != jobs[10:] or recovery["attempts"] != 38
            or recovery["preserved_completed_jobs"] != list(range(1, 10))
            or recovery["retry_policy"] != "none"):
        raise ValueError("Unexpected continuation scope")
    interrupted = recovery["interrupted_job"]
    if (any(interrupted[k] != v for k, v in jobs[9].items())
            or interrupted["classification"] != "infrastructure_interruption_unavailable"
            or interrupted["retry"] is not False):
        raise ValueError("Unexpected interrupted cell")
    for field in ("models", "packages", "input_sha256", "evaluator"):
        if recovery[field] != plan[field]:
            raise ValueError(f"Continuation condition changed: {field}")
    if any(recovery["source_sha256"].get(k) != v for k, v in plan["source_sha256"].items()):
        raise ValueError("Continuation changed measured source bytes")
    if progress["status"] != "running" or [r["job"] for r in progress["outcomes"]] != list(range(1, 10)):
        raise ValueError("Original frozen prefix was changed")
    if recovered["status"] != "completed" or not recovered.get("original_artifacts_unchanged"):
        raise ValueError("Continuation must be complete with original preservation confirmed")
    if [r["job"] for r in recovered["outcomes"]] != list(range(11, 49)):
        raise ValueError("Continuation lacks its exact 38 outcomes")
    return jobs


def run_path(value):
    run_id = value.replace("\\", "/").rstrip("/").split("/")[-1]
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Missing or invalid recorded run path")
    return LOOP_ROOT / "results/runs" / run_id


def verify_run(job, outcome, expected_plan, artifacts):
    for key, value in job.items():
        if outcome.get(key) != value:
            raise ValueError(f"Outcome disagrees with schedule: job {job['job']}/{key}")
    local = run_path(outcome["run_path"])
    provenance = read(local / "provenance.json", artifacts)
    config = read(local / "config.json", artifacts)
    summary = read(local / "summary.json", artifacts)
    if (provenance["git"] != expected_plan["git"]
            or provenance["config_sha256"] != job["config_sha256"]
            or config["seed"] != job["seed"] or config["agent_evidence_n"] != job["n"]):
        raise ValueError(f"Run source/config mismatch: job {job['job']}")
    if any(provenance[k] != expected_plan["input_sha256"][k] for k in
           ("questions_sha256", "gold_sha256", "corpus_manifest_sha256")):
        raise ValueError(f"Run inputs changed: job {job['job']}")
    if provenance["packages"] != expected_plan["packages"]:
        raise ValueError(f"Run packages changed: job {job['job']}")
    if any(name in expected_plan["source_sha256"] and expected_plan["source_sha256"][name] != digest
           for name, digest in provenance["code_sha256"].items()):
        raise ValueError(f"Run measured source differs: job {job['job']}")
    if (provenance["model_info"]["version"] != "0.35.0" or any(
            provenance["model_info"]["models"][name]["digest"] != digest
            for name, digest in expected_plan["models"].items())):
        raise ValueError(f"Run model/runtime differs: job {job['job']}")
    return local, summary


def collect(stage_dir):
    artifacts = {}
    if stage_dir.name != ORIGIN:
        raise ValueError("This adapter is scoped to the frozen Stage C origin")
    plan = read(stage_dir / "plan.json", artifacts)
    progress = read(stage_dir / "progress.json", artifacts)
    recovery = read(stage_dir / "continuation-v1/plan.json", artifacts)
    recovered = read(stage_dir / "continuation-v1/progress.json", artifacts)
    manifest_path = stage_dir / "continuation-v1/interruption-manifest.json"
    read(manifest_path, artifacts)
    if sha(manifest_path.read_bytes()) != recovery["interruption_manifest_sha256"]:
        raise ValueError("Recovery interruption manifest changed")
    jobs = validate_recovery(plan, progress, recovery, recovered)
    # Verify every locally imported original run/group file covered by the recovery freeze.
    for name, expected in recovery["original_file_sha256"].items():
        if name.startswith((f"results/loop-stage-c/{ORIGIN}/", "results/runs/")):
            path = LOOP_ROOT / name
            if not path.is_file() or sha(path.read_bytes()) != expected:
                raise ValueError(f"Frozen original artifact changed or absent: {name}")
            artifacts[str(path.resolve())] = expected
    freeze = plan["evaluator"]
    config = verify_evaluator(freeze)
    outcomes = progress["outcomes"] + recovered["outcomes"]
    by_job = {x["job"]: x for x in outcomes}
    if len(by_job) != 47 or set(by_job) != set(range(1, 49)) - {10}:
        raise ValueError("Expected 47 recorded outcomes and one preserved interruption")
    groups, run_ids = defaultdict(dict), set()
    audit = {
        "kind": "loop-stage-c-judge-preparation-v1", "generation_status": "completed_with_interruption",
        "scheduled_attempts": 48, "recorded_attempts": 47, "interrupted_attempts": 1,
        "planned_pairs": 32, "maximum_paid_judgments": 64,
        "statuses": {}, "technical_skips": [], "unresolved_citations": [],
        "conflicting_citations": [], "unjudgeable_pairs": [], "pair_audit": [],
        "evaluator_recipe_sha256": RECIPE_SHA,
        "adapter_sha256": sha(Path(__file__).read_bytes()), "input_artifact_sha256": artifacts,
        "no_api_calls": True, "budget_ledger_checked": False,
        "scope": "Original cited passage support only; no claim of expert truth or source completeness.",
        "recovery": {"original_head": plan["git"]["head"], "continuation_head": recovery["git"]["head"],
                     "original_completed_jobs": list(range(1, 10)), "continuation_jobs": list(range(11, 49))},
    }
    statuses = Counter()
    for job in jobs:
        number, qid, seed, n = (job[k] for k in ("job", "question_id", "seed", "n"))
        if number == 10:
            interrupted = recovery["interrupted_job"]
            local, summary = verify_run(job, interrupted, plan, artifacts)
            if (summary["records"] or any((local / qid / name).exists()
                                          for name in ("response.json", "grade.json", "review.json"))):
                raise ValueError("Interrupted attempt acquired a final answer")
            audit["technical_skips"].append({"job": 10, "run_id": local.name, "arm": f"N{n}",
                                             "reason": "infrastructure_interruption_unavailable"})
        else:
            expected_plan = plan if number <= 9 else recovery
            outcome = by_job[number]
            local, summary = verify_run(job, outcome, expected_plan, artifacts)
            if len(summary["records"]) != 1 or summary["records"][0]["id"] != qid:
                raise ValueError(f"Run/question mismatch: job {number}")
            row = summary["records"][0]
            statuses[row["status"]] += 1
            expected_sha = outcome.get("metrics", {}).get("raw_answer_sha256")
            if expected_sha is not None and sha(row["raw_answer"].encode()) != expected_sha:
                raise ValueError(f"Recorded answer hash mismatch: job {number}")
            if row["status"] not in ("success", "unsure") or not row["raw_answer"].strip():
                audit["technical_skips"].append({"job": number, "run_id": local.name, "arm": f"N{n}",
                                                 "status": row["status"], "reason": "no_usable_completed_answer"})
            else:
                review = read(local / qid / "review.json", artifacts)
                if (review["question"]["id"] != qid or row["raw_answer"] != review["raw_answer"]
                        or row["status"] != review["status"]):
                    raise ValueError(f"Review/question/answer mismatch: job {number}")
                groups[qid, seed][f"N{n}"] = {
                    "question": {"question": review["question"]["question"], "options": review["question"]["options"]},
                    "raw_answer": row["raw_answer"], "contexts": review["contexts"],
                    "run_id": local.name, "status": row["status"], "job": number,
                    "segment": "original" if number <= 9 else "continuation",
                }
        if local.name in run_ids:
            raise ValueError("Saved run reused for multiple attempts")
        run_ids.add(local.name)
    pairs = []
    blocks = list(dict.fromkeys((j["question_id"], j["seed"]) for j in jobs))
    for qid, seed in blocks:
        for comparator in ("N1", "N3"):
            labels = ("N8", comparator)
            pair_id = f"{qid}-s{seed}-N8-{comparator}"
            arms = {a: groups[qid, seed][a] for a in labels if a in groups[qid, seed]}
            if set(arms) != set(labels):
                audit["unjudgeable_pairs"].append({"pair_id": pair_id, "reason": "missing_usable_arm",
                                                   "available_arms": sorted(arms)})
                continue
            if arms["N8"]["question"] != arms[comparator]["question"]:
                raise ValueError("Paired question/options differ")
            sources, missing, collisions = source_union(arms)
            audit["unresolved_citations"].extend({"pair_id": pair_id, **x} for x in missing)
            audit["conflicting_citations"].extend({"pair_id": pair_id, **x} for x in collisions)
            if not sources:
                audit["unjudgeable_pairs"].append({"pair_id": pair_id, "reason": "no_original_cited_evidence"})
                continue
            if missing or collisions:
                continue
            pairs.append({"pair_id": pair_id, "arms": list(labels), "question": arms["N8"]["question"],
                          "sources": sources, "answers": {a: item["raw_answer"] for a, item in arms.items()}})
            audit["pair_audit"].append({
                "pair_id": pair_id, "seed": seed, "question_id": qid, "contrast": f"N8/{comparator}",
                "arms": {a: {"run_id": item["run_id"], "status": item["status"], "job": item["job"],
                              "segment": item["segment"], "answer_sha256": sha(item["raw_answer"].encode())}
                         for a, item in arms.items()},
                "source_sha256": {cid: sha(text.encode()) for cid, text in sources.items()},
                "source_characters": sum(map(len, sources.values())),
            })
    audit["statuses"] = dict(statuses)
    audit["eligible_pairs"] = len(pairs)
    audit["eligible_by_contrast"] = dict(Counter(p["contrast"] for p in audit["pair_audit"]))
    audit["planned_judgments"] = len(pairs) * 2
    audit["input_integrity_valid"] = not (audit["unresolved_citations"] or audit["conflicting_citations"])
    audit["packet_ready"] = audit["input_integrity_valid"] and bool(pairs) and len(pairs) <= 32
    audit["judge_ready"] = False
    audit["judge_ready_reason"] = "Separate live budget/token-count preflight and documented series allocation required."
    return pairs, audit, freeze, config


def make_output(destination, pairs, audit, freeze, config):
    if not audit["packet_ready"]:
        raise ValueError("Preparation blocked; no packet written")
    destination.mkdir(parents=True, exist_ok=False)
    packet = destination / "packet"
    pairwise.packet_write(packet, pairs, {
        "kind": audit["kind"], "generation_input_sha256": audit["input_artifact_sha256"],
        "adapter_sha256": audit["adapter_sha256"], "evaluator_recipe_sha256": RECIPE_SHA,
        "evidence_policy": "Full union of original passages cited by either arm; no truncation; no answer keys.",
        "technical_skips": audit["technical_skips"], "unjudgeable_pairs": audit["unjudgeable_pairs"],
        "recovery": audit["recovery"],
    })
    request_plan = pairwise.build_plan(packet, CITATION_ROOT / "configs/judge-openai-revision-dev-v1.json",
                                       destination / "plans")
    _, loaded_config, requests = pairwise.load_plan(request_plan)
    if loaded_config != config or len(requests) != len(pairs) * 2:
        raise ValueError("Prepared plan differs from frozen recipe/count")
    for anonymous_id, request in requests.items():
        payload = json.loads(request["input"][0]["content"])
        if (not re.fullmatch(r"item-[0-9]+", payload["case_id"]) or payload["case_id"] != anonymous_id
                or set(payload) != {"case_id", "question", "sources", "answers"}
                or set(payload["question"]) != {"question", "options"}
                or set(payload["answers"]) != {"A", "B"}):
            raise ValueError("Judge input is not structurally blinded")
    estimate = sum(judge.reserve_cost(judge.offline_input_estimate(req), config) for req in requests.values())
    audit.update(packet=str(packet), request_plan=str(request_plan),
                 offline_conservative_reservation_usd=judge.usd(estimate),
                 estimate_note="Offline byte estimate; token counts and live remaining budget must be checked separately.")
    write(destination / "audit.json", audit)
    write(destination / "evaluator-freeze.json", freeze)


def self_test():
    good = {"raw_answer": "Claim (pqac-a).", "contexts": [{"id": "pqac-a", "text": {"text": "Full source"}}]}
    other = {"raw_answer": "Claim (pqac-b).", "contexts": [{"id": "pqac-b", "text": {"text": "Other full source"}}]}
    sources, missing, conflicts = source_union({"N8": good, "N1": other})
    assert sources == {"pqac-a": "Full source", "pqac-b": "Other full source"}
    assert not missing and not conflicts
    bad = {"raw_answer": "Claim (pqac-a).", "contexts": [{"id": "pqac-a", "text": {"text": "Different source"}}]}
    assert source_union({"N8": good, "N1": bad})[2]
    assert source_union({"N8": {"raw_answer": "Claim (pqac-missing).", "contexts": []}})[1]
    jobs = [{"job": i + 1, "question_id": f"q{q}", "seed": seed, "n": n}
            for i, (q, seed, n) in enumerate((q, seed, n) for seed in (42, 43)
                                             for q in range(8) for n in (1, 3, 8))]
    assert len(validate_schedule({"kind": "loop-evidence-stage-c-v1", "schedule": jobs})) == 48
    malformed = {"kind": "loop-evidence-stage-c-v1", "schedule": jobs[:-1] + [jobs[0]]}
    try:
        validate_schedule(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate schedule accepted")
    config = verify_evaluator(read(LOOP_ROOT / "docs/loop-stage-b-evaluator-freeze.json"))
    case = {"case_id": "item-001", "question": {"question": "Question?", "options": {}},
            "sources": sources, "answers": {"A": good["raw_answer"], "B": other["raw_answer"]}}
    assert json.loads(pairwise.request_for(case, config)["input"][0]["content"]) == case
    return {"self_test": "passed", "api_calls": 0, "files_written": 0,
            "evaluator_recipe_sha256": RECIPE_SHA}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dir", type=Path, nargs="?")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return
    if args.stage_dir is None:
        parser.error("stage_dir is required unless --self-test is used")
    pairs, audit, freeze, config = collect(args.stage_dir)
    if args.output:
        make_output(args.output, pairs, audit, freeze, config)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
