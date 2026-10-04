"""Freeze one repair experiment before inference; no answer-key or holdout access."""

import json
from pathlib import Path

from paperqa_reflect import measurement as m
from paperqa_reflect import measurement_v2 as v2
from paperqa_reflect import revision
from paperqa_reflect.verifier import digest, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "data/verification/measurement-checks-v2"
    target.mkdir(parents=True, exist_ok=False)
    old = ROOT / "data/verification/measurement-checks-v1"
    controls = m.load_cases(old / "controls")
    expected = read_json(old / "control-expectations.json")
    observed = (
        "During trial B, the sensor recorded a pulse at 3 degrees C and at no other temperature."
    )
    composition = "The assembly consists of exactly two modules: a logger and a timer."
    definitions = [
        (observed, ["During trial B, the sensor recorded a pulse."], ["faithful"], "incomplete"),
        (
            observed,
            ["During trial B, the sensor recorded a pulse.", observed],
            ["faithful", "faithful"],
            "complete",
        ),
        (
            composition,
            [
                "The assembly contains a logger.",
                "The assembly contains a timer.",
                "The assembly contains exactly two modules.",
            ],
            ["faithful"] * 3,
            "complete",
        ),
        (
            "The kit includes a logger and a timer; other components may also be present.",
            ["The kit consists only of a logger and a timer."],
            ["distorted"],
            "incomplete",
        ),
    ]
    for i, (source, texts, labels, coverage) in enumerate(definitions, 13):
        cid = f"control-{i:02d}"
        claims = [
            {"claim_id": f"c{j:03d}", "text": text, "quote": source}
            for j, text in enumerate(texts, 1)
        ]
        controls.append({"case_id": cid, "source_text": source, "claims": claims})
        expected[cid] = {
            "fidelity": {x["claim_id"]: label for x, label in zip(claims, labels, strict=True)},
            "coverage": coverage,
        }
    m.packet_write(target / "controls", controls)
    write_json(target / "control-expectations.json", expected)
    sources = read_json(old / "synthetic-sources.json")
    sources += [
        {
            "case_id": "fresh-01",
            "source_text": "The monitoring group contained nine nodes: six workers and three coordinators. Under load above 70%, two workers may pause; no coordinator paused during the test.",
        },
        {
            "case_id": "fresh-02",
            "source_text": "At pressures above 4 bar, valve V may close; it did not close in any of the seven trials at 2 bar.",
        },
    ]
    prior = m.load_cases(ROOT / "results/measurement/audit-input-v1")
    packet = read_json(ROOT / "data/verification/revision-dev-v1/input.json")
    questions = {x["answer_id"]: x["question"] for x in packet["answers"]}
    for case in prior:
        if case["case_id"].startswith("historical-"):
            aid = case["case_id"].removeprefix("historical-").rsplit("-", 1)[0]
            sources.append(
                {
                    "case_id": case["case_id"],
                    "source_text": case["source_text"],
                    "question": questions[aid],
                    "sources": {
                        cid: ""
                        for cid in sorted(set(revision.CITATION.findall(case["source_text"])))
                    },
                }
            )
    write_json(target / "local-sources.json", sources)
    (target / "extraction-prompt.txt").write_text(revision.EXTRACTION_PROMPT_V2, encoding="utf-8")
    (target / "audit-prompt.txt").write_text(v2.PROMPT, encoding="utf-8")
    files = [p for p in target.rglob("*") if p.is_file()]
    write_json(
        target / "freeze.json",
        {
            "kind": "bounded-measurement-repair-v2",
            "controls": len(controls),
            "local_inputs": len(sources),
            "prior_audit_inputs": len(prior),
            "origin": "Authored logical controls, development inputs and saved model answers; no independent scientific gold",
            "files": {p.relative_to(target).as_posix(): digest(p.read_bytes()) for p in files},
        },
    )
    print(
        json.dumps({"path": str(target), "controls": len(controls), "local_inputs": len(sources)})
    )


if __name__ == "__main__":
    main()
