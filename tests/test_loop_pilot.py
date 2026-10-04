import importlib.util
import json
from pathlib import Path

from paperqa_reflect.config import write_json
from paperqa_reflect.data import sha256

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("loop_pilot", ROOT / "scripts/run_loop_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_repeat_chunk_with_new_summary_is_not_counted_as_no_change(tmp_path):
    qdir = tmp_path / "q1"
    qdir.mkdir()
    events = []
    for i, summary in enumerate(["First summary", "Useful clarification", "Useful clarification"]):
        context = {"context": summary, "text": {"doc": {"dockey": "paper"},
                                                "name": "chunk1", "text": "Original source"}}
        state = qdir / f"state-{i}.json"
        write_json(state, {"contexts": [context]})
        events.extend([
            {"kind": "action", "seconds": i * 10, "value": {"tool_calls": [
                {"function": {"name": "gather_evidence", "arguments": '{"question":"Q"}'}}]}},
            {"kind": "step", "seconds": i * 10 + 2,
             "value": {"state_path": state.name, "state_sha256": sha256(state)}},
        ])
    (qdir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    row = {"id": "q1", "status": "success", "grade": {"correct_completed": True, "selected": "A"},
           "seconds": 22, "actions": ["gather_evidence"] * 3, "raw_answer": "A"}
    write_json(tmp_path / "summary.json", {"records": [row], "usage": {}})
    result = pilot.analyze(tmp_path)
    assert result["controller_turns"] == 3
    assert [x["new_original_chunks"] for x in result["gathers"]] == [1, 0, 0]
    assert [x["new_summary_texts"] for x in result["gathers"]] == [1, 1, 0]
    assert not result["incomplete_action_batch"]


def test_schedule_is_paired_and_counterbalances_arm_order():
    assert [(name, n) for name, _, n in pilot.SCHEDULE] == [
        ("RfaH", 1), ("RfaH", 3), ("COSA-1", 3), ("COSA-1", 1)]
    assert len({qid for _, qid, _ in pilot.SCHEDULE}) == 2
