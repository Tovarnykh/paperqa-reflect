import json
from pathlib import Path

import pytest

from paperqa_reflect import measurement as m
from paperqa_reflect import measurement_v2 as v2
from paperqa_reflect import revision as r
from paperqa_reflect.verifier import read_json

ROOT = Path(__file__).resolve().parents[1]


def test_v1_frozen_audit_plans_still_load_and_v2_cannot_silently_relabel_them():
    p = ROOT / "results/measurement-judge/20261003T164253Z-914c38"
    if not p.exists():
        pytest.skip("Laptop-only API archive")
    assert m.load_plan(p)[0]["cases"] == 12
    with pytest.raises(ValueError, match="plan type"):
        v2.load_plan(p)


def test_v2_plan_freezes_distinct_rubric_and_excludes_expected_labels(tmp_path):
    packet = tmp_path / "packet"
    case = {
        "case_id": "sample",
        "source_text": "A and B are included.",
        "claims": [{"claim_id": "c1", "text": "A is included.", "quote": "A and B are included."}],
    }
    m.packet_write(packet, [case], {"expected": "LABEL_SENTINEL"})
    plan = m.build_plan(
        packet,
        ROOT / "configs/judge-openai-revision-dev-v1.json",
        tmp_path / "plans",
        v2.PROMPT,
        v2.KIND,
    )
    _, _, requests = v2.load_plan(plan)
    assert "LABEL_SENTINEL" not in json.dumps(requests)
    with pytest.raises(ValueError, match="plan type"):
        m.load_plan(plan)
    request_path = plan / "item-001.request.json"
    request_path.write_text(request_path.read_text().replace("A is included", "A is excluded"))
    with pytest.raises(ValueError, match="integrity"):
        v2.load_plan(plan)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_extraction_version_routes_real_stage_with_citations_and_records_profile(
    tmp_path, monkeypatch, version
):
    answer = "The assembly consists of a timer and a logger (pqac-abc)."
    requests = []

    def transport(client, config, directory, role, prompt, payload, schema, context):
        requests.append((prompt, payload, context))
        return {
            "status": "checked",
            "value": {
                "sentences": [
                    {
                        "sentence_id": "s001",
                        "claims": [
                            {
                                "claim": "The assembly consists of a timer and a logger.",
                                "quote": "The assembly consists of a timer and a logger",
                            }
                        ],
                    }
                ]
            },
        }

    monkeypatch.setattr(r, "local_json", transport)
    claims = r.extract(
        None, {}, tmp_path, answer, "Describe the assembly.", {"pqac-abc": "source"}, version
    )
    assert requests[0][0] == {"v1": r.EXTRACTION_PROMPT, "v2": r.EXTRACTION_PROMPT_V2}[version]
    assert requests[0][2] == 32768 and claims[0]["passage_ids"] == ["pqac-abc"]
    assert read_json(tmp_path / "extraction-profile.json")["version"] == version
    assert claims[0]["answer_quote"] in answer
