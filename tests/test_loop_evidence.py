import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from paperqa_reflect.config import build_settings, load_config
from paperqa_reflect.data import sha256
from paperqa_reflect.reference import ReferenceConfig
from paperqa_reflect.runner import QuestionTrace

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("seed", [42, 43])
def test_only_controller_observation_count_changes_and_n1_preserves_baseline(seed, tmp_path):
    baseline = load_config(ROOT / f"configs/uia-qwen38-dev-s{seed}.json")
    original = build_settings(baseline, tmp_path, tmp_path / "index", tmp_path / "manifest")
    arms = {}
    for n in [1, 3]:
        config = load_config(ROOT / f"configs/loop-evidence-n{n}-s{seed}.json")
        arms[n] = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest")
    assert original.model_dump() == arms[1].model_dump()
    # md5 is a computed checksum of settings, not a second intervention.
    expected = arms[1].model_dump(exclude={"md5"})
    expected["agent"]["agent_evidence_n"] = 3
    assert arms[3].model_dump(exclude={"md5"}) == expected
    assert arms[1].prompts == arms[3].prompts
    assert arms[1].answer == arms[3].answer


def test_invalid_evidence_count_rejected():
    config = load_config(ROOT / "configs/uia-qwen38-dev-s42.json").model_dump()
    with pytest.raises(ValueError):
        ReferenceConfig.model_validate({**config, "agent_evidence_n": 0})


@pytest.mark.parametrize("n,visible", [(1, ["best"]), (3, ["best", "second", "general"])])
def test_real_upstream_gather_filters_ranks_and_only_changes_observation(tmp_path, n, visible):
    from paperqa.agents.tools import GatherEvidence

    config = load_config(ROOT / f"configs/loop-evidence-n{n}-s42.json")
    settings = build_settings(config, tmp_path, tmp_path / "index", tmp_path / "manifest")
    contexts = [SimpleNamespace(context=text, question=question, score=score)
                for text, question, score in [("second", "Q", 7), ("best", "Q", 9),
                                               ("unrelated", "other Q", 10),
                                               ("general", None, 6)]]
    session = SimpleNamespace(question="original question", contexts=contexts)
    gather = AsyncMock(return_value=session)
    state = SimpleNamespace(session=session, status="Status: unchanged",
                            docs=SimpleNamespace(docs={"paper": object()}, aget_evidence=gather))
    # Exercise the installed upstream tool method; only network clients are stubbed.
    tool = GatherEvidence.model_construct(settings=settings, summary_llm_model=None,
                                         embedding_model=None, partitioning_fn=None)
    result = asyncio.run(tool.gather_evidence("Q", state))
    assert result == ("Added 0 pieces of evidence. Best evidence(s) for the current question:\n\n"
                      + "\n\n".join("- " + text for text in visible) + "\n\nStatus: unchanged")
    assert state.session.contexts is contexts and len(contexts) == 4
    assert state.session.question == "original question"
    gather.assert_awaited_once()


def test_intermediate_evidence_snapshots_survive_later_state_changes(tmp_path):
    from paperqa.types import PQASession

    session = PQASession(question="Synthetic question", answer="first state")
    trace = QuestionTrace(tmp_path)
    trace.state = SimpleNamespace(session=session)
    asyncio.run(trace.step([], 0, False, False))
    session.answer = "later state"
    asyncio.run(trace.step([], 0, True, False))
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    for event, expected in zip(events, ["first state", "later state"], strict=True):
        path = tmp_path / event["value"]["state_path"]
        assert sha256(path) == event["value"]["state_sha256"]
        assert json.loads(path.read_text())["answer"] == expected
