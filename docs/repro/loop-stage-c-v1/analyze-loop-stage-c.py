"""Offline Stage C audit with explicit missing-data and recovery handling.

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
GROUP = ROOT / "results/loop-stage-c/20261004T210539Z-3f1ab1"
OUTPUT = WORKSPACE / ".tmp/loop-stage-c-stats.json"
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
    progress_path = GROUP / "progress.json"
    continuation = GROUP / "continuation-v1"
    plan = read(GROUP / "plan.json")
    recovery = read(continuation / "plan.json")
    progress = read(progress_path)
    recovered = read(continuation / "progress.json")
    assert recovered["status"] == "completed"
    assert recovered["original_artifacts_unchanged"]
    assert len(progress["outcomes"]) == 9 and len(recovered["outcomes"]) == 38
    assert len(plan["schedule"]) == 48
    assert recovery["preserved_completed_jobs"] == list(range(1, 10))
    assert recovery["schedule"] == plan["schedule"][10:]
    assert recovery["origin_git"] == plan["git"]
    assert recovery["retry_policy"] == plan["retry_policy"] == "none"
    assert file_sha(continuation / "driver.py") == recovery["source_sha256"]["scripts/continue_loop_stage_c.py"]
    for field in ("input_sha256", "models", "packages", "evaluator"):
        assert plan[field] == recovery[field]
    for key, value in plan["source_sha256"].items():
        assert recovery["source_sha256"][key] == value
    preserved_checked, preserved_unavailable = 0, []
    for name, expected in recovery["original_file_sha256"].items():
        path = ROOT / name
        if path.is_file():
            assert file_sha(path) == expected
            preserved_checked += 1
        else:
            assert name in {".cache/loop-stage-c-v1/execution.json", ".cache/loop-stage-c-v1/driver.log", ".cache/loop-stage-c-v1/driver.pid"}
            preserved_unavailable.append(name)
    outcomes = progress["outcomes"] + recovered["outcomes"]
    jobs = plan["schedule"][:9] + plan["schedule"][10:]
    assert plan["independent_questions"] == 8 and not plan["holdout"]
    assert file_sha(GROUP / "driver.py") == plan["source_sha256"]["scripts/run_loop_stage_c.py"]
    config = read(ROOT / plan["schedule"][0]["config"])
    assert file_sha(ROOT / config["gold"]) == plan["input_sha256"]["gold_sha256"]
    gold = {row["id"]: row for row in jsonl(ROOT / config["gold"])}
    common_inputs = common_settings = None
    rows, first_gathers, diagnostics = [], {}, []
    state_count = source_file_count = observation_count = 0
    for outcome, job in zip(outcomes, jobs, strict=True):
        assert all(outcome[key] == value for key, value in job.items())
        run = ROOT / "results/runs" / Path(outcome["run_path"]).name
        qid, seed, arm = job["question_id"], job["seed"], job["n"]
        provenance = read(run / "provenance.json")
        assert provenance["git"] == (plan if job["job"] <= 9 else recovery)["git"]
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
        chat_usage_complete = all(r["usage"] is not None for r in chat)
        chat_input = sum(r["usage"]["prompt_tokens"] for r in chat) if chat_usage_complete else None
        chat_output = sum(r["usage"]["completion_tokens"] for r in chat) if chat_usage_complete else None
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
                    shown_counts, eligible_counts = [], []
                    for gather_function, observation in zip(gather_functions, observations, strict=True):
                        question = gather_function["arguments"]["question"]
                        eligible = sorted([c for c in contexts if c.get("question") in (None, question)],
                                          key=lambda c: c["score"], reverse=True)
                        eligible_counts.append(len(eligible))
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
                        "eligible_pool_sizes": eligible_counts,
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
            "segment": "original" if job["job"] <= 9 else "continuation",
            "source_commit": provenance["git"]["head"],
            "run_id": run.name, "status": record["status"], "exit_code": outcome["exit_code"],
            "selected": record["grade"]["selected"], "correct_completed": record["grade"]["correct_completed"],
            "abstained": record["grade"]["abstained"], "format_valid": record["grade"]["format_valid"],
            "controller_turns": len(actions), "tool_counts": dict(counts),
            "gather_calls": counts["gather_evidence"], "search_calls": counts["paper_search"],
            "answer_calls": counts["gen_answer"], "question_seconds": record["seconds"],
            "index_seconds": index["seconds"] if index else None,
            "index_status": index["status"] if index else None,
            "wall_seconds": outcome["wall_seconds"], "chat_calls": len(chat),
            "chat_input_tokens": chat_input, "chat_output_tokens": chat_output, "chat_token_usage_complete": chat_usage_complete,
            "new_original_chunks": len(seen_chunks), "new_summary_texts": len(seen_summaries),
            "gathers": gathers, "all_requests": len(requests),
            "request_statuses": dict(Counter(r["status"] for r in requests)),
            "chat_finish_reasons": dict(Counter(reason for r in chat for reason in r["finish_reasons"])),
            "max_chat_prompt_tokens": max((r["usage"]["prompt_tokens"] for r in chat if r["usage"] is not None), default=None),
            "max_chat_completion_tokens": max((r["usage"]["completion_tokens"] for r in chat if r["usage"] is not None), default=None),
            "first_chat_seconds": chat[0]["seconds"] if chat else None,
            "truncated_steps": truncated_steps, "incomplete_action_batch": pending is not None,
            "execution_error": outcome.get("execution_error"), "analysis_error": outcome.get("analysis_error"),
            "hashes": {name: file_sha(run / name) for name in (
                "summary.json", "requests.jsonl", "provenance.json", "settings.json", "source-snapshot.zip",
            )}, "events_sha256": file_sha(run / qid / "events.jsonl"),
        }
        rows.append(row)

    # Interrupted job is audited but never supplied as a graded or zero-time cell.
    interrupted = recovery["interrupted_job"]
    assert interrupted["job"] == 10 and interrupted["n"] == 1
    partial_run = ROOT / "results/runs" / Path(interrupted["run_path"]).name
    partial_summary = read(partial_run / "summary.json")
    assert not partial_summary["records"]
    partial_question = partial_run / interrupted["question_id"]
    assert not (partial_question / "response.json").exists()
    assert not (partial_question / "grade.json").exists()
    partial_provenance = read(partial_run / "provenance.json")
    assert partial_provenance["git"] == plan["git"]
    for key, value in common_inputs.items():
        assert partial_provenance[key] == value
    assert partial_provenance["config_sha256"] == interrupted["config_sha256"]
    assert partial_provenance["model_info"]["version"] == "0.35.0"
    assert {k: v["digest"] for k, v in partial_provenance["model_info"]["models"].items()} == plan["models"]
    partial_settings = json.loads((partial_run / "settings.json").read_text(encoding="utf-8").replace(partial_run.name, "RUN_ID"))
    partial_settings.pop("md5", None)
    assert partial_settings["agent"]["agent_evidence_n"] == 1
    partial_settings["agent"]["agent_evidence_n"] = "ARM"
    normalize_seed(partial_settings, interrupted["seed"])
    assert partial_settings == common_settings
    partial_states, partial_pending, partial_actions = 0, None, Counter()
    partial_events_path = partial_run / interrupted["question_id"] / "events.jsonl"
    for event in jsonl(partial_events_path):
        if event["kind"] == "action":
            assert partial_pending is None
            partial_pending = event
            partial_actions.update(f["name"] for f in normalized_functions(event))
        elif event["kind"] == "step":
            assert partial_pending is not None
            state_path = partial_events_path.parent / event["value"]["state_path"]
            assert file_sha(state_path) == event["value"]["state_sha256"]
            partial_states += 1
            partial_pending = None
    assert partial_pending is not None
    with zipfile.ZipFile(partial_run / "source-snapshot.zip") as archive:
        assert set(archive.namelist()) == set(partial_provenance["code_sha256"])
        for name, expected in partial_provenance["code_sha256"].items():
            assert digest(archive.read(name)) == expected
    partial_requests = jsonl(partial_run / "requests.jsonl")
    partial_audit = {
        "job": 10, "question_id": interrupted["question_id"], "seed": interrupted["seed"],
        "n": 1, "run_id": partial_run.name, "classification": interrupted["classification"],
        "final_response_and_grade_available": False, "retry": False,
        "state_hashes_verified": partial_states,
        "source_files_verified": len(partial_provenance["code_sha256"]),
        "settings_models_and_config_match": True,
        "started_tool_calls": dict(partial_actions), "incomplete_action_batch": True,
        "requests": len(partial_requests),
        "request_statuses": dict(Counter(r["status"] for r in partial_requests)),
        "hashes": {name: file_sha(partial_run / name) for name in (
            "provenance.json", "requests.jsonl", "settings.json", "source-snapshot.zip")},
        "events_sha256": file_sha(partial_events_path),
    }
    question_ids = list(dict.fromkeys(j["question_id"] for j in plan["schedule"]))
    assert len(question_ids) == 8
    lookup = {(r["question_id"], r["seed"], r["n"]): r for r in rows}
    assert len(lookup) == 47
    blocks = []
    for seed in (42, 43):
        for qid in question_ids:
            block = {"question_id": qid, "seed": seed, "arms": {}}
            for arm in (1, 3, 8):
                row = lookup.get((qid, seed, arm))
                block["arms"][str(arm)] = ({
                    "run_id": row["run_id"], "status": row["status"],
                    "correct_completed": row["correct_completed"], "selected": row["selected"],
                    "segment": row["segment"], "metrics": {m: row[m] for m in METRICS},
                } if row else {"run_id": partial_run.name, "status": "infrastructure_interrupted",
                               "correct_completed": None, "selected": None, "metrics": None,
                               "segment": "original"})
            blocks.append(block)

    contrasts = {}
    for comparator in (1, 3):
        pairs, excluded = [], []
        for block in blocks:
            qid, seed = block["question_id"], block["seed"]
            candidate, reference = lookup[qid, seed, 8], lookup.get((qid, seed, comparator))
            if reference is None or reference["status"] != "success" or candidate["status"] != "success":
                excluded.append({"question_id": qid, "seed": seed,
                                 "n8_status": candidate["status"],
                                 "reference_status": reference["status"] if reference else "infrastructure_interrupted",
                                 "reason": "No matched pair of technically successful completed trajectories"})
                continue
            initial8 = first_gathers.get((qid, seed, 8))
            initial_ref = first_gathers.get((qid, seed, comparator))
            initial_comparison = None
            if initial8 and initial_ref:
                initial_comparison = {
                    "first_action_equal": initial8["first_action_sha256"] == initial_ref["first_action_sha256"],
                    "actions_through_first_gather_equal": initial8["pre_gather_actions_sha256"] == initial_ref["pre_gather_actions_sha256"],
                    "first_gather_arguments_equal": initial8["arguments_sha256"] == initial_ref["arguments_sha256"],
                    "first_gather_context_set_equal": initial8["context_set_sha256"] == initial_ref["context_set_sha256"],
                }
            pairs.append({
                "question_id": qid, "seed": seed, "n8_run_id": candidate["run_id"],
                "reference_run_id": reference["run_id"], "n8_selected": candidate["selected"],
                "reference_selected": reference["selected"],
                "n8_correct": candidate["correct_completed"], "reference_correct": reference["correct_completed"],
                "n8_segment": candidate["segment"], "reference_segment": reference["segment"],
                "difference_n8_minus_reference": {m: candidate[m] - reference[m]
                    if candidate[m] is not None and reference[m] is not None else None for m in METRICS},
                "early_trajectory_comparison": initial_comparison,
            })
        per_question = []
        for qid in question_ids:
            available = [p for p in pairs if p["question_id"] == qid]
            per_question.append({"question_id": qid, "available_seed_pairs": len(available),
                                 "available_seeds": [p["seed"] for p in available],
                                 "mean_difference_n8_minus_reference": {
                                     m: statistics.mean(p["difference_n8_minus_reference"][m] for p in available)
                                     if available and all(p["difference_n8_minus_reference"][m] is not None for p in available)
                                     else None for m in METRICS}})
        matched_keys = {(p["question_id"], p["seed"]) for p in pairs}
        matched8 = [r for r in rows if r["n"] == 8 and (r["question_id"], r["seed"]) in matched_keys]
        matched_ref = [r for r in rows if r["n"] == comparator and (r["question_id"], r["seed"]) in matched_keys]
        complete_clusters = [q for q in per_question if q["available_seed_pairs"] == 2]
        rng = random.Random(20261004)
        samples = [[rng.randrange(len(complete_clusters)) for _ in complete_clusters] for _ in range(10000)]
        bootstraps = {}
        for metric in BOOTSTRAP_METRICS:
            deltas = [q["mean_difference_n8_minus_reference"][metric] for q in complete_clusters]
            assert all(value is not None for value in deltas)
            distribution = [statistics.mean(deltas[i] for i in sample) for sample in samples]
            bootstraps[metric] = {
                "mean_difference_n8_minus_reference": statistics.mean(deltas),
                "percentile_95_interval": [percentile(distribution, .025), percentile(distribution, .975)],
                "complete_question_clusters": len(deltas), "paired_observations": len(deltas) * 2,
            }
        diagnostics = []
        for field in ("first_action_equal", "actions_through_first_gather_equal", "first_gather_arguments_equal", "first_gather_context_set_equal"):
            values = [p["early_trajectory_comparison"][field] for p in pairs if p["early_trajectory_comparison"] is not None]
            diagnostics.append({"comparison": field, "equal": sum(values), "different": len(values)-sum(values), "available_pairs": len(values)})
        contrasts[f"n8_vs_n{comparator}"] = {
            "reference_n": comparator, "matched_successful_pairs": len(pairs), "excluded_pairs": excluded,
            "matched_n8": metric_summary(matched8), "matched_reference": metric_summary(matched_ref),
            "mean_difference_over_available_pairs": {
                m: statistics.mean(p["difference_n8_minus_reference"][m] for p in pairs)
                if all(p["difference_n8_minus_reference"][m] is not None for p in pairs) else None for m in METRICS},
            "per_question": per_question, "pairs": pairs,
            "exploratory_bootstrap_complete_questions_only": {
                "seed": 20261004, "resamples": 10000,
                "question_ids": [q["question_id"] for q in complete_clusters],
                "excluded_question_ids": [q["question_id"] for q in per_question if q["available_seed_pairs"] != 2],
                "method": "Resample complete question clusters, retaining both seeds, Python random.Random and linearly interpolated percentiles. Missing or failed cells are not imputed; reduced N8/N1 sample differs from all available pairs.",
                "results": bootstraps},
            "early_trajectory_comparison_totals": diagnostics,
        }

    telemetry_count = monitor_errors = empty_residency = 0
    residency, telemetry_segments = {}, {}
    gpu_samples = Counter()
    for job in plan["schedule"]:
        location = GROUP if job["job"] <= 10 else continuation
        segment = "original" if job["job"] <= 10 else "continuation"
        count = 0
        for sample in jsonl(location / f"job-{job['job']:02d}-telemetry.jsonl"):
            count += 1
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
        telemetry_segments[segment] = telemetry_segments.get(segment, 0) + count
    for stats in residency.values():
        for field in ("context_lengths", "digests"):
            stats[field] = sorted(stats[field])
    pool_sizes = {}
    for arm in (1, 3, 8):
        arm_rows = [r for r in rows if r["n"] == arm]
        eligible = [n for r in arm_rows for g in r["gathers"] for n in g["eligible_pool_sizes"]]
        shown = [n for r in arm_rows for g in r["gathers"] for n in g["shown_summaries_per_call"]]
        pool_sizes[str(arm)] = {"gather_calls_audited": len(eligible), "eligible_sizes": dict(Counter(eligible)),
                                "actual_shown_sizes": dict(Counter(shown)), "maximum_eligible": max(eligible, default=None),
                                "pools_above_eight": sum(n > 8 for n in eligible),
                                "multi_gather_batches": sum(g["gather_calls_in_batch"] > 1 for r in arm_rows for g in r["gathers"])}
    arms = {}
    for arm in (1, 3, 8):
        arm_rows = [r for r in rows if r["n"] == arm]
        arms[str(arm)] = {
            "scheduled": 16, "recorded_outcomes": len(arm_rows),
            "technically_successful": sum(r["status"] == "success" for r in arm_rows),
            "startup_failures": sum(r["status"] == "fail" and r["controller_turns"] == 0 for r in arm_rows),
            "infrastructure_interruptions": int(arm == 1),
            "correct_completed": sum(r["correct_completed"] for r in arm_rows),
            "all_recorded_attempts": metric_summary(arm_rows),
            "successful_only": metric_summary([r for r in arm_rows if r["status"] == "success"]),
        }
    result = {
        "schema": "loop-stage-c-offline-audit-v1", "group": GROUP.name,
        "status": "completed_after_explicit_recovery_with_one_interruption",
        "scheduled_attempts": 48, "recorded_outcomes": 47, "interrupted_attempts": 1,
        "source_commits": {"original": plan["git"]["head"], "continuation": recovery["git"]["head"]},
        "analysis_script_sha256": file_sha(Path(__file__)),
        "plan_sha256": file_sha(GROUP / "plan.json"), "progress_sha256": file_sha(progress_path),
        "continuation_plan_sha256": file_sha(continuation / "plan.json"),
        "continuation_progress_sha256": file_sha(continuation / "progress.json"),
        "validation": {
            "all_47_recorded_outcomes_reconciled_with_schedule_and_progress": True,
            "all_47_effective_settings_match_after_arm_seed_and_run_path_normalization": True,
            "all_47_models_inputs_packages_and_source_snapshots_match": True,
            "state_hashes_verified_completed_runs": state_count,
            "source_files_in_archives_verified_completed_runs": source_file_count,
            "gather_observations_reconstructed_completed_runs": observation_count,
            "all_47_recorded_options_regraded_against_frozen_gold": True,
            "normalized_effective_settings_sha256": canonical_sha(common_settings),
            "interrupted_run_audited_separately": True,
            "preserved_original_artifact_hashes_rechecked": preserved_checked,
            "original_runtime_files_not_imported_locally": preserved_unavailable,
        },
        "arms": arms, "rows": rows, "blocks": blocks, "primary_contrasts": contrasts,
        "interrupted_run": partial_audit, "eligible_pools_and_actual_visibility": pool_sizes,
        "runtime_diagnostics": {
            "recorded_run_requests": sum(r["all_requests"] for r in rows),
            "recorded_run_chat_requests": sum(r["chat_calls"] for r in rows),
            "request_statuses": dict(sum((Counter(r["request_statuses"]) for r in rows), Counter())),
            "chat_finish_reasons": dict(sum((Counter(r["chat_finish_reasons"]) for r in rows), Counter())),
            "max_chat_prompt_tokens": max(r["max_chat_prompt_tokens"] for r in rows if r["max_chat_prompt_tokens"] is not None),
            "max_chat_completion_tokens": max(r["max_chat_completion_tokens"] for r in rows if r["max_chat_completion_tokens"] is not None),
            "truncated_steps_completed_runs": sum(r["truncated_steps"] for r in rows),
            "incomplete_action_batches_completed_runs": sum(r["incomplete_action_batch"] for r in rows),
            "telemetry_including_interrupted_run": {"samples": telemetry_count, "segment_samples": telemetry_segments,
                "monitor_errors": monitor_errors, "no_loaded_model_samples": empty_residency,
                "gpu_device_samples": dict(gpu_samples), "model_residency": residency},
        },
        "limitations": [
            "Eight selected development questions and two repeated seeds are not 16 independent questions; no holdout used.",
            "N1 has one startup failure and one infrastructure interruption; these are not wrong answers or model abstentions.",
            "Efficiency contrasts use matched technically successful trajectories: 14 N8/N1 pairs and 16 N8/N3 pairs. Failed and partial costs remain recorded separately.",
            "The all-eight-question paired bootstrap is unavailable for N8/N1. Its exploratory complete-cluster bootstrap uses six questions/twelve pairs; it does not summarize all fourteen available pairs and cannot remove missingness bias.",
            "Correct options do not establish source fidelity; frozen external evaluation remains separate.",
            "Fresh trajectories can diverge before the intervention; random IDs, ordering, cache, startup conditions and Coder recovery limit causal timing claims.",
            "Visibility reconstruction and initial contexts use batch-end snapshots; multi-gather batches are not individually timed or state-isolated.",
            "Stage A/B are not pooled; no attempts are retried or replaced; interrupted job10 is not scored or imputed.",
        ],
    }
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    notes = ["# Stage C offline audit", "", "48 scheduled; 47 recorded outcomes plus one infrastructure interruption.", "",
             "| Arm | Correct completed | Startup failure | Interrupted |", "|---|---:|---:|---:|"]
    for arm, value in arms.items():
        notes.append(f"| N{arm} | {value['correct_completed']} | {value['startup_failures']} | {value['infrastructure_interruptions']} |")
    for name, contrast in contrasts.items():
        notes += ["", f"## {name}: {contrast['matched_successful_pairs']} matched successful pairs", "",
                  "| Metric | Reference total | N8 total | N8 minus reference |", "|---|---:|---:|---:|"]
        for metric in METRICS:
            before = contrast["matched_reference"]["metrics"][metric]["total"]
            after = contrast["matched_n8"]["metrics"][metric]["total"]
            notes.append(f"| {metric} | {before} | {after} | {after-before if after is not None and before is not None else None} |")
    notes += ["", "## Limits", "", *["- " + item for item in result["limitations"]], ""]
    OUTPUT.with_suffix(".md").write_bytes("\n".join(notes).encode())
    print(json.dumps({"output": str(OUTPUT), "validation": result["validation"],
                      "arms": {k: {field: v[field] for field in ("scheduled", "recorded_outcomes", "technically_successful", "startup_failures", "infrastructure_interruptions", "correct_completed")} for k, v in arms.items()},
                      "primary_contrasts": {k: {field: v[field] for field in ("matched_successful_pairs", "mean_difference_over_available_pairs")} for k, v in contrasts.items()},
                      "eligible_pools_and_actual_visibility": pool_sizes,
                      "runtime_diagnostics": result["runtime_diagnostics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

