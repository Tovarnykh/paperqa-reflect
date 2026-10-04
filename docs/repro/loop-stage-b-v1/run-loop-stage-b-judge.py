"""Budget preflight for the frozen Stage B judge; --run sends the fixed plan once."""
import argparse
import importlib.util
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

WORKSPACE = Path(__file__).resolve().parents[1]
CITATION = WORKSPACE / "research/paperqa-reflect"
sys.path.insert(0, str(CITATION / "src"))
from paperqa_reflect import judge, pairwise


def budget_headroom(path, config):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        settings = dict(db.execute("SELECT key,value FROM settings"))
        assert int(settings["project_cap"]) == judge.money(config["project_budget_usd"])
        assert int(settings["group_cap:" + config["budget_group"]]) == judge.money(
            config["group_budget_usd"])
        if db.execute("SELECT 1 FROM calls WHERE state IN ('reserved','overrun')").fetchone():
            raise judge.JudgeError("unsettled_prior_request_requires_inspection")
        project = db.execute("SELECT COALESCE(SUM(charged),0) FROM calls").fetchone()[0]
        group = db.execute("SELECT COALESCE(SUM(charged),0) FROM calls WHERE group_id=?",
                           (config["budget_group"],)).fetchone()[0]
    return {"project_remaining_micro_usd": judge.money(config["project_budget_usd"]) - project,
            "group_remaining_micro_usd": judge.money(config["group_budget_usd"]) - group,
            "project_charged_micro_usd": project, "group_charged_micro_usd": group}


def guard_budget(counts, config, headroom):
    reservation = sum(judge.reserve_cost(n, config) for n in counts.values())
    if reservation > min(headroom["project_remaining_micro_usd"],
                         headroom["group_remaining_micro_usd"]):
        raise judge.JudgeError("whole_plan_exceeds_remaining_budget")
    return reservation


class CountCacheClient:
    """Reuse exact token-count bodies; preserve all paid requests and responses verbatim."""
    def __init__(self, client, bodies):
        self.client, self.bodies = client, bodies

    def request(self, method, url, **kwargs):
        if method == "POST" and url == judge.API + "/responses/input_tokens":
            body = json.dumps(kwargs["json"], sort_keys=True, ensure_ascii=False)
            if body not in self.bodies:
                raise judge.JudgeError("uncounted_request_body")
            return httpx.Response(200, json={"input_tokens": self.bodies[body],
                                           "object": "response.input_tokens"})
        return self.client.request(method, url, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("adapter", WORKSPACE / ".tmp/prepare-loop-stage-b-judge.py")
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    freeze = adapter.read(WORKSPACE / "research/paperqa-loop/docs/loop-stage-b-evaluator-freeze.json")
    adapter.verify_evaluator(freeze)
    plan, config, requests = pairwise.load_plan(args.plan)
    assert config == freeze["config"] and len(requests) == 32
    assert not (args.plan / "run.json").exists(), "Plan has already been attempted"
    key = judge.api_key(CITATION / ".env")
    counts, cache = {}, {}
    with httpx.Client(timeout=config["timeout_seconds"], trust_env=False,
                      follow_redirects=False) as client:
        for cid, request in requests.items():
            body = judge.token_count_body(request)
            result = judge.response_json(client, "POST", "/responses/input_tokens", key, body)
            count = result.get("input_tokens")
            if type(count) is not int or not 0 < count <= config["max_input_tokens"]:
                raise judge.JudgeError("invalid_input_count")
            counts[cid] = count
            cache[json.dumps(body, sort_keys=True, ensure_ascii=False)] = count
        remaining = budget_headroom(judge.DEFAULT_LEDGER, config)
        reservation = sum(judge.reserve_cost(n, config) for n in counts.values())
        preflight = {"checked_utc": datetime.now(UTC).isoformat(), "plan_id": plan["id"],
                     "requests": len(requests), "counts": counts, "remaining": remaining,
                     "reserved_upper_usd": judge.usd(reservation),
                     "fits_remaining": reservation <= min(remaining["project_remaining_micro_usd"],
                                                            remaining["group_remaining_micro_usd"]),
                     "pricing_rechecked": "2026-10-04", "no_paid_requests_yet": True,
                     "pricing_source": "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
                     "tokens_source": "https://developers.openai.com/api/docs/guides/token-counting"}
        judge.write_json(args.plan / "remaining-budget-preflight.json", preflight)
        print("BUDGET_PREFLIGHT", json.dumps({k:v for k,v in preflight.items() if k != "counts"}), flush=True)
        guard_budget(counts, config, remaining)
        if args.run:
            state = judge.run_plan(args.plan, CITATION / ".env", judge.DEFAULT_LEDGER,
                                   client=CountCacheClient(client, cache), recipe=pairwise)
            print("JUDGE_RUN", json.dumps(state), flush=True)
            assessment = pairwise.assess(args.plan)
            judge.write_json(args.plan / "assessment.json", assessment)
            print("ASSESSMENT", json.dumps({k:v for k,v in assessment.items() if k != "pairs"}), flush=True)


if __name__ == "__main__":
    main()
