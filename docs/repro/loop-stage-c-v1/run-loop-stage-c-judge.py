"""Preflight the documented Stage C allocation; --run sends the immutable plan once."""
import argparse
import importlib.util
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".tmp" / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


adapter = module("stage_c_adapter", "prepare-loop-stage-c-judge.py")
prior = module("stage_b_runner", "run-loop-stage-b-judge.py")
judge, pairwise = adapter.judge, adapter.pairwise


def headroom(path, config):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        settings = dict(db.execute("SELECT key,value FROM settings"))
        assert int(settings["project_cap"]) == judge.money(config["project_budget_usd"])
        cap_key = "group_cap:" + config["budget_group"]
        if cap_key in settings:
            assert int(settings[cap_key]) == judge.money(config["group_budget_usd"])
        if db.execute("SELECT 1 FROM calls WHERE state IN ('reserved','overrun')").fetchone():
            raise judge.JudgeError("unsettled_prior_request_requires_inspection")
        project = db.execute("SELECT COALESCE(SUM(charged),0) FROM calls").fetchone()[0]
        group = db.execute("SELECT COALESCE(SUM(charged),0) FROM calls WHERE group_id=?",
                           (config["budget_group"],)).fetchone()[0]
    return {"project_remaining_micro_usd": judge.money(config["project_budget_usd"]) - project,
            "group_remaining_micro_usd": judge.money(config["group_budget_usd"]) - group,
            "project_charged_micro_usd": project, "group_charged_micro_usd": group}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("allocation", type=Path)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    allocation = adapter.read(args.allocation)
    frozen = adapter.verify_evaluator(adapter.read(adapter.LOOP_ROOT / "docs/loop-stage-b-evaluator-freeze.json"))
    directory = Path(allocation["execution_plan"])
    plan, config, requests = pairwise.load_plan(directory)
    old_plan, old_config, old_requests = pairwise.load_plan(Path(allocation["original_plan"]))
    assert not (Path(allocation["original_plan"]) / "run.json").exists(), "Original frozen plan was already attempted"
    assert old_config == frozen
    assert config == {**frozen, "budget_group": "loop-stage-c-pairwise-v1"}
    assert requests == old_requests and plan["rows"] == old_plan["rows"]
    assert len(requests) == allocation["requests"] == 60
    assert allocation["request_bodies_byte_equal"] and allocation["group_budget_usd"] == "5.00"
    assert allocation["project_budget_usd"] == "100.00"
    assert not (directory / "run.json").exists(), "Plan has already been attempted; no retries"
    key = judge.api_key(adapter.CITATION_ROOT / ".env")
    counts, cache = {}, {}
    with httpx.Client(timeout=config["timeout_seconds"], trust_env=False, follow_redirects=False) as client:
        for cid, request in requests.items():
            body = judge.token_count_body(request)
            result = judge.response_json(client, "POST", "/responses/input_tokens", key, body)
            count = result.get("input_tokens")
            if type(count) is not int or not 0 < count <= config["max_input_tokens"]:
                raise judge.JudgeError("invalid_input_count")
            counts[cid] = count
            cache[json.dumps(body, sort_keys=True, ensure_ascii=False)] = count
        remaining = headroom(judge.DEFAULT_LEDGER, config)
        reservation = sum(judge.reserve_cost(n, config) for n in counts.values())
        preflight = {"checked_utc": datetime.now(UTC).isoformat(), "plan_id": plan["id"],
                     "allocation_sha256": judge.digest(args.allocation.read_bytes()),
                     "requests": len(requests), "counts": counts, "remaining": remaining,
                     "reserved_upper_usd": judge.usd(reservation),
                     "fits_remaining": reservation <= min(remaining["project_remaining_micro_usd"],
                                                            remaining["group_remaining_micro_usd"]),
                     "pricing_rechecked": "2026-10-05", "no_paid_requests_yet": True,
                     "pricing_source": "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
                     "tokens_source": "https://developers.openai.com/api/docs/guides/token-counting"}
        judge.write_json(directory / "remaining-budget-preflight.json", preflight)
        print("BUDGET_PREFLIGHT", json.dumps({k: v for k, v in preflight.items() if k != "counts"}), flush=True)
        prior.guard_budget(counts, config, remaining)
        if args.run:
            (directory / "executed-stage-c-runner.py").write_bytes(Path(__file__).read_bytes())
            (directory / "executed-preflight-support.py").write_bytes((ROOT / ".tmp/run-loop-stage-b-judge.py").read_bytes())
            state = judge.run_plan(directory, adapter.CITATION_ROOT / ".env", judge.DEFAULT_LEDGER,
                                   client=prior.CountCacheClient(client, cache), recipe=pairwise)
            print("JUDGE_RUN", json.dumps(state), flush=True)
            assessment = pairwise.assess(directory)
            judge.write_json(directory / "assessment.json", assessment)
            print("ASSESSMENT", json.dumps({k: v for k, v in assessment.items() if k != "pairs"}), flush=True)


if __name__ == "__main__":
    main()
