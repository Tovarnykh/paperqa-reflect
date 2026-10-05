"""Document a separate USD5 Stage C allowance without changing paid request bodies."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("adapter", ROOT / ".tmp/prepare-loop-stage-c-judge.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
pairwise, judge = adapter.pairwise, adapter.judge
freeze = adapter.read(adapter.LOOP_ROOT / "docs/loop-stage-b-evaluator-freeze.json")
original = adapter.verify_evaluator(freeze)
base = adapter.LOOP_ROOT / "results/loop-stage-c/20261004T210539Z-3f1ab1/assessment-v1"
audit = adapter.read(base / "audit.json")
old_plan, old_config, old_requests = pairwise.load_plan(Path(audit["request_plan"]))
assert old_config == original and len(old_requests) == 60
execution = base / "stage-c-allocation-v1"
execution.mkdir(exist_ok=False)
config = {**original, "budget_group": "loop-stage-c-pairwise-v1"}
assert [k for k in config if config[k] != original[k]] == ["budget_group"]
adapter.write(execution / "config.json", config)
new_path = pairwise.build_plan(base / "packet", execution / "config.json", execution / "plans")
new_plan, new_config, new_requests = pairwise.load_plan(new_path)
assert old_requests == new_requests and new_config == config
assert old_plan["rows"] == new_plan["rows"]
assert (Path(audit["request_plan"]) / "mapping.json").read_bytes() == (new_path / "mapping.json").read_bytes()
recipe = {"kind": pairwise.KIND, "prompt": pairwise.PROMPT, "schema": pairwise.SCHEMA,
          "config": config, "request_template": pairwise.request_for(freeze["placeholder_case"], config)}
record = {
    "kind": "stage-c-evaluation-budget-allocation-v1",
    "reason": "Separate fixed series allocation; existing pilot group and cumulative ledger remain unchanged.",
    "config_changes": {"budget_group": {"before": original["budget_group"], "after": config["budget_group"]}},
    "group_budget_usd": config["group_budget_usd"], "project_budget_usd": config["project_budget_usd"],
    "original_recipe_sha256": adapter.RECIPE_SHA,
    "execution_recipe_sha256": adapter.sha(adapter.canonical(recipe)),
    "recipe_note": "Full recipe hash differs only because budget_group is included. Prompt, rubric, model, decoding, exact request bodies and mirrored mapping are unchanged.",
    "request_bodies_byte_equal": all((Path(audit["request_plan"]) / f"{cid}.request.json").read_bytes() == (new_path / f"{cid}.request.json").read_bytes() for cid in old_requests),
    "original_plan": audit["request_plan"], "execution_plan": str(new_path),
    "requests": 60, "pairs": 30, "ledger": str(judge.DEFAULT_LEDGER),
    "paid_calls_sent": 0,
    "execution_condition": "Exact live token count for all60; full maximum reservation fits this USD5 allocation and cumulative USD100 project budget; no retries."
}
assert record["request_bodies_byte_equal"]
adapter.write(execution / "allocation.json", record)
print(json.dumps(record, indent=2))
