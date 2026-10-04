import copy
import json

import pytest

from paperqa_reflect import rewrite_only as b
from paperqa_reflect.verifier import read_json, write_json


def fixture_item():
    item = {
        "question": {"question": "Which?", "options": {"A": "X"}},
        "original_answer": "X (pqac-abc).\nFinal answer: A",
        "sources": {"pqac-abc": "X"},
    }
    payload = {**{k: item[k] for k in ["question", "original_answer"]},
               "sources": [{"source_id": "pqac-abc", "text": "X"}],
               "review": {"issues": [{"issue": "test feedback"}]}}
    request = {"messages": [{"role": "system", "content": "frozen"},
                             {"role": "user", "content": json.dumps(payload)}]}
    return item, request


@pytest.mark.parametrize("fail", [False, True])
def test_exactly_one_rewrite_without_feedback_and_safe_failure(tmp_path, monkeypatch, fail):
    item, request = fixture_item()
    expected, payload = b.ablated_request(request, item)
    calls = []

    def local(client, config, directory, role, prompt, value, schema, context):
        calls.append(role)
        assert value == payload and value["review"] == {"issues": []}
        assert context == 65536 and prompt == b.r.REVISION_PROMPT
        directory.mkdir()
        write_json(directory / "request.json", expected)
        return {"status": "not_checked" if fail else "checked",
                "value": {"answer": item["original_answer"]}}

    monkeypatch.setattr(b.r, "local_json", local)
    result = b.run_arm(None, {}, tmp_path / "B3", item, request)
    assert calls == ["answer_revision"]
    assert result["status"] == ("fallback_original" if fail else "revised")
    assert result["answer"] == item["original_answer"]
    assert not result["same_request_as_B1"]


def test_reject_changed_sources_before_inference():
    item, request = fixture_item()
    item["sources"]["pqac-abc"] = "different source"
    with pytest.raises(ValueError, match="differs"):
        b.ablated_request(request, item)


def test_saved_packet_has_seven_identical_rewrite_inputs():
    if not b.PRIOR.exists():
        pytest.skip("Saved comparison run archive is not part of Git")
    packet = read_json(b.PRIOR / "input.json")
    equal = []
    for item in packet["answers"]:
        request = read_json(b.PRIOR / item["answer_id"] / "B1/revision/request.json")
        before = copy.deepcopy(request)
        ablated, _ = b.ablated_request(request, item)
        assert request == before
        equal.append(ablated == request)
    assert equal == [False, True, True, True, True, True, True, True]
    assert b.Path(b.r.__file__).read_bytes() == (b.PRIOR / "revision.py").read_bytes()


def test_pairs_include_every_question_and_only_three_new_comparisons(tmp_path):
    if not b.PRIOR.exists():
        pytest.skip("Saved comparison run archive is not part of Git")
    local = tmp_path / "local"
    local.mkdir()
    write_json(local / "run.json", {"status": "completed"})
    (local / "input.json").write_bytes((b.PRIOR / "input.json").read_bytes())
    for item in read_json(local / "input.json")["answers"]:
        target = local / item["answer_id"] / "B3"
        target.mkdir(parents=True)
        write_json(target / "answer.json", {"answer": item["original_answer"]})
    output = tmp_path / "pairs"
    assert b.prepare_pairs(local, b.PRIOR, output) == 48
    mappings = read_json(output / "mapping.json")
    assert len({row["pair_id"] for row in mappings}) == 24
    assert all("B3" in row["slots"].values() for row in mappings)
    for case in read_json(output / "cases.json"):
        assert set(case) == {"case_id", "question", "sources", "answers"}
        assert set(case["question"]) == {"question", "options"}
        assert set(case["answers"]) == {"A", "B"}
        request = b.pairwise.request_for({**case, "case_id": "item-001"}, {
            "model": "gpt-6.1-sol", "reasoning_effort": "medium", "max_output_tokens": 4096,
        })
        value = json.loads(request["input"][0]["content"])
        assert value["case_id"] == "item-001"  # Pair/method names never reach the judge.
