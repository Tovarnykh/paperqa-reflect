"""Offline audit and preregistered descriptive statistics for the fixed Stage B.

No network, inference, or source-text publication. Run from any working directory.
The standard-library RNG and linearly interpolated percentile calculation are
explicit so the 10,000 question-cluster resamples are exactly reproducible.
"""

import hashlib
import json
import math
import random
import re
import statistics
import zipfile
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
ROOT = WORKSPACE / "research/paperqa-loop"
GROUP = ROOT / "results/loop-stage-b/20261004T130908Z-af58f8"
OUTPUT = WORKSPACE / ".tmp/loop-stage-b-stats.json"
METRICS = (
    "gather_calls", "search_calls", "answer_calls", "controller_turns",
    "question_seconds", "index_seconds", "chat_calls", "chat_input_tokens",
    "chat_output_tokens", "new_original_chunks", "new_summary_texts",
)
BOOTSTRAP_METRICS = (
    "gather_calls", "question_seconds", "chat_input_tokens", "chat_output_tokens",
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return digest(path.read_bytes())


def canonical_sha(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True).encode())


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def normalized_functions(action):
    result = []
    for call in action["value"]["tool_calls"]:
        function = call["function"]
        args = function["arguments"]
        result.append({"name": function["name"],
                       "arguments": json.loads(args) if isinstance(args, str) else args})
    return result


def normalize_seed(value, expected):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "seed":
                assert child == expected, (key, child, expected)
                value[key] = "SEED"
            else:
                normalize_seed(child, expected)
    elif isinstance(value, list):
        for child in value:
            normalize_seed(child, expected)


def percentile(values, fraction):
    ordered = sorted(values)
    location = (len(ordered) - 1) * fraction
    lower, upper = math.floor(location), math.ceil(location)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (location - lower)


def metric_summary(rows):
    result = {"attempts": len(rows), "statuses": dict(Counter(r["status"] for r in rows)),
              "correct_completed": sum(r["correct_completed"] for r in rows),
              "abstentions": sum(r["abstained"] for r in rows),
              "wrong_completed": sum(r["status"] == "success" and not r["correct_completed"]
                                     and not r["abstained"] and r["format_valid"]
                                     for r in rows), "metrics": {}}
    for metric in METRICS:
        values = [r[metric] for r in rows if r[metric] is not None]
        result["metrics"][metric] = {
            "available": len(values), "missing": len(rows) - len(values),
            "total": sum(values) if values else None,
            "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None,
        }
    return result


def regrade(record, expected):
    """Recompute frozen marker grading without importing inference dependencies."""
    def remove_citations(match):
        names = [name.strip() for name in match.group(1).split(",")]
        return "" if all(name in record["citation_ids"] for name in names) else match.group(0)

    clean = re.sub(r"\(([^()\r\n]+)\)", remove_citations, record["raw_answer"]).replace("**", "")
    matches = [s.upper() for s in re.findall(r"(?im)^\s*Final answer:\s*(ABSTAIN|[A-Z])\s*[.!]?\s*$", clean)]
    selected = matches[0] if len(set(matches)) == 1 else None
    if selected not in {"A", "B", "C", "D", "ABSTAIN"}:
        selected = None
    return {"selected": selected, "expected": expected, "format_valid": selected is not None,
            "abstained": selected == "ABSTAIN" or record["declared_success"] is False,
            "option_matches_key": selected == expected,
            "correct_completed": record["status"] == "success" and record["declared_success"] is not False and selected == expected,
            "claim_support_checked": False}


def main():
    progress_path = GROUP / "export-progress-32.json"
    plan = read(GROUP / "plan.json")
    progress = read(progress_path)
    assert progress["status"] == "completed"
    assert len(progress["outcomes"]) == len(plan["schedule"]) == 32
    assert plan["independent_questions"] == 8 and not plan["holdout"]
    assert file_sha(GROUP / "driver.py") == plan["source_sha256"]["scripts/run_loop_stage_b.py"]
    config = read(ROOT / plan["schedule"][0]["config"])
    assert file_sha(ROOT / config["gold"]) == plan["input_sha256"]["gold_sha256"]
    gold = {row["id"]: row for row in jsonl(ROOT / config["gold"])}
    common_inputs = common_settings = None
    rows, first_gathers, diagnostics = [], {}, []
    state_count = source_file_count = observation_count = 0
    for outcome, job in zip(progress["outcomes"], plan["schedule"], strict=True):
        assert all(outcome[key] == value for key, value in job.items())
        run = ROOT / "results/runs" / Path(outcome["run_path"]).name
        qid, seed, arm = job["question_id"], job["seed"], job["n"]
        provenance = read(run / "provenance.json")
        assert provenance["git"] == plan["git"]
        assert provenance["config_sha256"] == job["config_sha256"]
        assert provenance["packages"] == plan["packages"]
        assert provenance["question_ids"] == [qid]
        assert provenance["split"] == "dev" and provenance["provider"] == "ollama"
        assert provenance["model_info"]["version"] == "0.35.0"
        assert {k: v["digest"] for k, v in provenance["model_info"]["models"].items()} == plan["models"]
        for key in ("questions_sha256", "gold_sha256", "corpus_manifest_sha256"):
            assert provenance[key] == plan["input_sha256"][key]
        inputs = {key: provenance[key] for key in (
            "questions_sha256", "gold_sha256", "corpus_manifest_sha256", "corpus",
            "code_sha256", "packages",
        )}
        if common_inputs is None:
            common_inputs = inputs
        assert inputs == common_inputs
        with zipfile.ZipFile(run / "source-snapshot.zip") as archive:
            assert set(archive.namelist()) == set(provenance["code_sha256"])
            for name, expected in provenance["code_sha256"].items():
                assert digest(archive.read(name)) == expected
                if name in plan["source_sha256"]:
                    assert expected == plan["source_sha256"][name]
                source_file_count += 1
        settings = json.loads((run / "settings.json").read_text(encoding="utf-8").replace(run.name, "RUN_ID"))
        settings.pop("md5", None)
        assert settings["agent"]["agent_evidence_n"] == arm
        settings["agent"]["agent_evidence_n"] = "ARM"
        normalize_seed(settings, seed)
        if common_settings is None:
            common_settings = settings
        assert settings == common_settings, f"Unexpected setting difference in job {job['job']}"

        summary = read(run / "summary.json")
        assert len(summary["records"]) == 1 and summary["records"][0]["id"] == qid
        record = summary["records"][0]
        assert record["grade"] == regrade(record, gold[qid]["answer"])
        requests = jsonl(run / "requests.jsonl")
        events = jsonl(run / qid / "events.jsonl")
        chat = [request for request in requests if "qwen" in request["requested_model"]]
        assert summary["usage"]["requests"] == len(requests)
        chat_input = sum(r["usage"]["prompt_tokens"] for r in chat)
        chat_output = sum(r["usage"]["completion_tokens"] for r in chat)
        if record.get("token_counts"):
            totals = [sum(v[i] for v in record["token_counts"].values()) for i in (0, 1)]
            assert totals == [chat_input, chat_output], (run.name, totals, chat_input, chat_output)
        actions, counts, pending, gathers, pre_gather_actions = [], Counter(), None, [], []
        seen_chunks, seen_summaries = set(), set()
        truncated_steps = 0
        for event in events:
            if event["kind"] == "action":
                assert pending is None
                pending = event
                functions = normalized_functions(event)
                actions.append(functions)
                counts.update(function["name"] for function in functions)
                if not gathers:
                    pre_gather_actions.append(functions)
            elif event["kind"] == "step":
                assert pending is not None
                value = event["value"]
                state_path = run / qid / value["state_path"]
                assert file_sha(state_path) == value["state_sha256"]
                state = read(state_path)
                state_count += 1
                truncated_steps += int(value["truncated"])
                functions = normalized_functions(pending)
                gather_functions = [f for f in functions if f["name"] == "gather_evidence"]
                if gather_functions:
                    observations = [obs for obs in value["observations"] if obs.get("name") == "gather_evidence"]
                    assert len(observations) == len(gather_functions)
                    contexts = state["contexts"]
                    shown_counts = []
                    for gather_function, observation in zip(gather_functions, observations, strict=True):
                        question = gather_function["arguments"]["question"]
                        eligible = sorted([c for c in contexts if c.get("question") in (None, question)],
                                          key=lambda c: c["score"], reverse=True)
                        shown = eligible[:arm]
                        block = "\n\n".join("- " + c["context"] for c in shown)
                        assert block in observation["content"], (run.name, value["state_path"])
                        assert observation["content"].count("\n- ") == len(shown)
                        shown_counts.append(len(shown))
                        observation_count += 1
                    chunks, summaries, context_hashes = set(), set(), []
                    for context in contexts:
                        text = context["text"]
                        chunk = canonical_sha([str(text["doc"]["dockey"]), text["name"], text["text"]])
                        summary_hash = digest(context["context"].encode())
                        chunks.add(chunk)
                        summaries.add((chunk, summary_hash))
                        context_hashes.append((chunk, summary_hash, context["score"]))
                    detail = {
                        "batch_seconds": event["seconds"] - pending["seconds"],
                        "mixed_tool_batch": len(functions) != 1,
                        "gather_calls_in_batch": len(gather_functions),
                        "new_original_chunks": len(chunks - seen_chunks),
                        "new_summary_texts": len(summaries - seen_summaries),
                        "current_contexts": len(contexts), "shown_summaries_per_call": shown_counts,
                        "state_path": value["state_path"], "state_sha256": value["state_sha256"],
                        "arguments_sha256": canonical_sha(gather_functions),
                        "context_set_sha256": canonical_sha(sorted(context_hashes)),
                    }
                    if not gathers:
                        first_gathers[qid, seed, arm] = {
                            "pre_gather_actions_sha256": canonical_sha(pre_gather_actions),
                            "first_action_sha256": canonical_sha(actions[0]),
                            **{k: detail[k] for k in ("arguments_sha256", "context_set_sha256", "current_contexts")},
                        }
                    gathers.append(detail)
                    seen_chunks.update(chunks)
                    seen_summaries.update(summaries)
                pending = None
        flat_actions = [f["name"] for batch in actions for f in batch]
        assert record["actions"] == flat_actions
        assert summary["metrics"]["tool_calls"] == dict(counts)
        saved = outcome["metrics"]
        assert saved["status"] == record["status"]
        assert saved["question_seconds"] == record["seconds"]
        assert saved["correct_completed"] == record["grade"]["correct_completed"]
        assert saved["selected"] == record["grade"]["selected"]
        assert saved["controller_turns"] == len(actions)
        assert saved["tool_counts"] == dict(counts)
        assert saved["raw_answer_sha256"] == digest(record["raw_answer"].encode())
        assert saved["incomplete_action_batch"] == (pending is not None)
        assert len(saved["gathers"]) == len(gathers)
        for reported, checked in zip(saved["gathers"], gathers, strict=True):
            for field in ("new_original_chunks", "new_summary_texts", "current_contexts", "state_sha256", "mixed_tool_batch"):
                assert reported[field] == checked[field]
            assert abs(reported["batch_seconds"] - checked["batch_seconds"]) < 1e-8
        index = read(run / "indexing.json") if (run / "indexing.json").exists() else None
        row = {
            "job": job["job"], "question_id": qid, "seed": seed, "n": arm,
            "run_id": run.name, "status": record["status"], "exit_code": outcome["exit_code"],
            "selected": record["grade"]["selected"], "correct_completed": record["grade"]["correct_completed"],
            "abstained": record["grade"]["abstained"], "format_valid": record["grade"]["format_valid"],
            "controller_turns": len(actions), "tool_counts": dict(counts),
            "gather_calls": counts["gather_evidence"], "search_calls": counts["paper_search"],
            "answer_calls": counts["gen_answer"], "question_seconds": record["seconds"],
            "index_seconds": index["seconds"] if index else None,
            "index_status": index["status"] if index else None,
            "wall_seconds": outcome["wall_seconds"], "chat_calls": len(chat),
            "chat_input_tokens": chat_input, "chat_output_tokens": chat_output,
            "new_original_chunks": len(seen_chunks), "new_summary_texts": len(seen_summaries),
            "gathers": gathers, "all_requests": len(requests),
            "request_statuses": dict(Counter(r["status"] for r in requests)),
            "chat_finish_reasons": dict(Counter(reason for r in chat for reason in r["finish_reasons"])),
            "max_chat_prompt_tokens": max((r["usage"]["prompt_tokens"] for r in chat), default=None),
            "max_chat_completion_tokens": max((r["usage"]["completion_tokens"] for r in chat), default=None),
            "first_chat_seconds": chat[0]["seconds"] if chat else None,
            "truncated_steps": truncated_steps, "incomplete_action_batch": pending is not None,
            "execution_error": outcome.get("execution_error"), "analysis_error": outcome.get("analysis_error"),
            "hashes": {name: file_sha(run / name) for name in (
                "summary.json", "requests.jsonl", "provenance.json", "settings.json", "source-snapshot.zip",
            )}, "events_sha256": file_sha(run / qid / "events.jsonl"),
        }
        rows.append(row)

    question_ids = list(dict.fromkeys(j["question_id"] for j in plan["schedule"]))
    assert len(question_ids) == 8
    lookup = {(r["question_id"], r["seed"], r["n"]): r for r in rows}
    assert len(lookup) == 32
    pairs = []
    for seed in (42, 43):
        for qid in question_ids:
            first, third = lookup[qid, seed, 1], lookup[qid, seed, 3]
            initial1, initial3 = first_gathers.get((qid, seed, 1)), first_gathers.get((qid, seed, 3))
            initial_comparison = None if initial1 is None or initial3 is None else {
                "first_action_equal": initial1["first_action_sha256"] == initial3["first_action_sha256"],
                "actions_through_first_gather_equal": initial1["pre_gather_actions_sha256"] == initial3["pre_gather_actions_sha256"],
                "first_gather_arguments_equal": initial1["arguments_sha256"] == initial3["arguments_sha256"],
                "first_gather_context_set_equal": initial1["context_set_sha256"] == initial3["context_set_sha256"],
                "n1_initial_contexts": initial1["current_contexts"], "n3_initial_contexts": initial3["current_contexts"],
            }
            pairs.append({
                "question_id": qid, "seed": seed, "n1_run_id": first["run_id"], "n3_run_id": third["run_id"],
                "n1_status": first["status"], "n3_status": third["status"],
                "n1_correct": first["correct_completed"], "n3_correct": third["correct_completed"],
                "n1_selected": first["selected"], "n3_selected": third["selected"],
                "difference_n3_minus_n1": {metric: third[metric] - first[metric]
                                           if first[metric] is not None and third[metric] is not None else None
                                           for metric in METRICS},
                "early_trajectory_comparison": initial_comparison,
            })
    per_question = []
    for qid in question_ids:
        paired = [p for p in pairs if p["question_id"] == qid]
        per_question.append({
            "question_id": qid, "seed_pairs": len(paired),
            "n1": metric_summary([r for r in rows if r["question_id"] == qid and r["n"] == 1]),
            "n3": metric_summary([r for r in rows if r["question_id"] == qid and r["n"] == 3]),
            "mean_difference_n3_minus_n1": {
                metric: statistics.mean(p["difference_n3_minus_n1"][metric] for p in paired)
                if all(p["difference_n3_minus_n1"][metric] is not None for p in paired) else None
                for metric in METRICS
            },
        })
    rng = random.Random(20261004)
    samples = [[rng.randrange(8) for _ in range(8)] for _ in range(10000)]
    bootstraps = {}
    for metric in BOOTSTRAP_METRICS:
        deltas = [q["mean_difference_n3_minus_n1"][metric] for q in per_question]
        assert all(v is not None for v in deltas), f"Missing {metric}; do not impute failure as zero"
        distribution = [statistics.mean(deltas[index] for index in sample) for sample in samples]
        bootstraps[metric] = {
            "mean_difference_n3_minus_n1": statistics.mean(deltas),
            "percentile_95_interval": [percentile(distribution, 0.025), percentile(distribution, 0.975)],
            "complete_question_clusters": len(deltas), "paired_observations": len(pairs),
        }
    for field in ("first_action_equal", "actions_through_first_gather_equal", "first_gather_arguments_equal", "first_gather_context_set_equal"):
        values = [p["early_trajectory_comparison"][field] for p in pairs if p["early_trajectory_comparison"] is not None]
        diagnostics.append({"comparison": field, "equal": sum(values), "different": len(values)-sum(values), "available_pairs": len(values)})
    telemetry_count = monitor_errors = empty_residency = 0
    residency = {}
    gpu_samples = Counter()
    for job in plan["schedule"]:
        for sample in jsonl(GROUP / f"job-{job['job']:02d}-telemetry.jsonl"):
            telemetry_count += 1
            monitor_errors += int("monitor_error" in sample)
            device = sample.get("runtime", {}).get("nvidia_smi", "unavailable").split(",")[0]
            gpu_samples[device] += 1
            models = sample.get("models", {}).get("models", [])
            empty_residency += int(not models)
            for model in models:
                stats = residency.setdefault(model["name"], {"samples": 0, "fully_resident_samples": 0,
                    "other_residency_samples": 0, "context_lengths": set(), "digests": set()})
                stats["samples"] += 1
                full = model["size"] == model["size_vram"]
                stats["fully_resident_samples"] += int(full)
                stats["other_residency_samples"] += int(not full)
                stats["context_lengths"].add(model.get("context_length"))
                stats["digests"].add(model["digest"])
    for stats in residency.values():
        for field in ("context_lengths", "digests"):
            stats[field] = sorted(stats[field])
    result = {
        "schema": "loop-stage-b-offline-audit-v1", "group": GROUP.name, "status": progress["status"],
        "run_source_commit": plan["git"]["head"], "analysis_script_sha256": file_sha(Path(__file__)),
        "plan_sha256": file_sha(GROUP / "plan.json"), "progress_sha256": file_sha(progress_path),
        "validation": {
            "all_32_actual_outcomes_reconciled_with_progress": True, "all_effective_settings_match_after_arm_seed_and_run_path_normalization": True,
            "all_models_inputs_packages_and_source_snapshots_match": True,
            "state_hashes_verified": state_count, "source_files_in_archives_verified": source_file_count,
            "gather_observations_reconstructed": observation_count,
            "all_32_final_options_regraded_against_frozen_gold": True,
            "normalized_effective_settings_sha256": canonical_sha(common_settings),
        },
        "arms": {str(arm): metric_summary([r for r in rows if r["n"] == arm]) for arm in (1, 3)},
        "seeds": {str(seed): {str(arm): metric_summary([r for r in rows if r["n"] == arm and r["seed"] == seed]) for arm in (1, 3)} for seed in (42, 43)},
        "rows": rows, "pairs": pairs, "per_question": per_question,
        "bootstrap": {"seed": 20261004, "resamples": 10000, "method": "Python random.Random; sample 8 question clusters with replacement, retain both seeds, percentile interval with linear interpolation", "results": bootstraps},
        "early_trajectory_comparison_totals": diagnostics,
        "runtime_diagnostics": {
            "requests": sum(r["all_requests"] for r in rows),
            "chat_requests": sum(r["chat_calls"] for r in rows),
            "request_statuses": dict(sum((Counter(r["request_statuses"]) for r in rows), Counter())),
            "chat_finish_reasons": dict(sum((Counter(r["chat_finish_reasons"]) for r in rows), Counter())),
            "max_chat_prompt_tokens": max(r["max_chat_prompt_tokens"] for r in rows),
            "max_chat_completion_tokens": max(r["max_chat_completion_tokens"] for r in rows),
            "truncated_steps": sum(r["truncated_steps"] for r in rows),
            "incomplete_action_batches": sum(r["incomplete_action_batch"] for r in rows),
            "telemetry": {"samples": telemetry_count, "monitor_errors": monitor_errors,
                          "no_loaded_model_samples": empty_residency, "gpu_device_samples": dict(gpu_samples),
                          "model_residency": residency},
        },
        "limitations": ["Eight selected development questions, with two repeat seeds each; not 16 independent questions.",
                        "Correct options do not establish explanation or citation fidelity; separate frozen external evaluation required.",
                        "Fresh trajectories can diverge before controller visibility changes; this is not identical-state replay.",
                        "Warmness and filesystem cache remain uncontrolled; observed times are not guaranteed causal speedups.",
                        "Gather details and initial context comparisons use batch-end snapshots; one controller batch can contain multiple gather calls, with no individual tool durations.",
                        "Stage A is not pooled; no holdout or adaptive retries were used."],
    }
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"output": str(OUTPUT), "validation": result["validation"], "arms": result["arms"], "bootstrap": result["bootstrap"], "early_trajectory_comparison_totals": diagnostics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
