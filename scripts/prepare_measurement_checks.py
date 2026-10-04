"""Freeze simple, authored logical controls before model runs. No domain annotation needed."""

from pathlib import Path

from paperqa_reflect.measurement import packet_write
from paperqa_reflect.verifier import digest, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "data/verification/measurement-checks-v1"
    target.mkdir(parents=True, exist_ok=False)
    definitions = [
        (
            "The kit consists of exactly two components: a battery and a cable.",
            ["The kit consists of exactly a battery and a cable."],
            ["faithful"],
            "complete",
        ),
        (
            "The kit consists of exactly two components: a battery and a cable.",
            ["The kit consists of a battery."],
            ["distorted"],
            "incomplete",
        ),
        (
            "The trial enrolled 20 adults: 12 women and 8 men.",
            [
                "The trial enrolled 20 adults.",
                "Twelve enrolled adults were women.",
                "Eight enrolled adults were men.",
            ],
            ["faithful"] * 3,
            "complete",
        ),
        (
            "The trial enrolled 20 adults: 12 women and 8 men.",
            ["The trial enrolled 20 adults."],
            ["faithful"],
            "incomplete",
        ),
        (
            "Bar X is 47.28 cm long and bar Y is 45.89 cm long, so X is longer than Y.",
            ["Bar X is shorter than bar Y."],
            ["distorted"],
            "incomplete",
        ),
        (
            "At temperatures below 5 degrees C, the sensor may lose calibration.",
            ["The sensor always loses calibration at all temperatures."],
            ["distorted"],
            "incomplete",
        ),
        (
            "At temperatures below 5 degrees C, the sensor may lose calibration.",
            ["Below 5 degrees C, loss of calibration is possible for the sensor."],
            ["faithful"],
            "complete",
        ),
        (
            "No increase was detected in the three inspected units; the other units were not inspected.",
            ["An increase was detected in the three inspected units."],
            ["distorted"],
            "incomplete",
        ),
        (
            "These data suggest, but do not establish, that treatment A causes improvement B.",
            [
                "These data suggest that treatment A may cause improvement B, but do not establish that causal relationship."
            ],
            ["faithful"],
            "complete",
        ),
        (
            "The locker contains either a red badge or a blue badge, but not both.",
            ["The locker contains a red badge."],
            ["distorted"],
            "incomplete",
        ),
        (
            "Team Amber reported that device A was faster; Team Blue did not replicate that finding.",
            [
                "Team Amber reported that device A was faster.",
                "Team Blue did not replicate Team Amber's finding that device A was faster.",
            ],
            ["faithful", "faithful"],
            "complete",
        ),
        ("The box contains two red cubes.", [], [], "incomplete"),
    ]
    cases, expected = [], {}
    for i, (source, texts, labels, coverage) in enumerate(definitions, 1):
        cid = f"control-{i:02d}"
        claims = [
            {"claim_id": f"c{j:03d}", "text": text, "quote": source}
            for j, text in enumerate(texts, 1)
        ]
        cases.append({"case_id": cid, "source_text": source, "claims": claims})
        expected[cid] = {
            "fidelity": {row["claim_id"]: label for row, label in zip(claims, labels, strict=True)},
            "coverage": coverage,
        }
    packet_write(target / "controls", cases)
    write_json(target / "control-expectations.json", expected)
    source_texts = [
        "The assembly consists of exactly four solar panels and one battery.",
        "Five large files account for 91.8% of the archive; smaller files account for the remaining 8.2%.",
        "Rod A is 47.28 cm long, rod B is 45.89 cm long, and rod C is 89.58 cm long; A is longer than B but shorter than C.",
        "During run A, voltage dropped by 8% only when the temperature was below 5 degrees C.",
        "None of the twelve inspected containers leaked; the remaining containers were not examined.",
        "The pilot suggests that the alarm may reduce delays, but the effect remains uncertain.",
        "Higher attendance was associated with higher scores, but a causal effect was not established.",
        "The shipment contains either a red badge or a blue badge, but not both.",
        "Team Amber reported that device A was faster; Team Blue did not replicate that finding.",
        "Three defects had been fixed by June; two additional defects were fixed in July.",
        "All six tested devices booted except device D; device D did not boot.",
        "Ranking from longest to shortest: 1. Rod C (89.58 cm), 2. Rod A (47.28 cm), 3. Rod B (45.89 cm).",
    ]
    write_json(
        target / "synthetic-sources.json",
        [
            {"case_id": f"synthetic-{i:02d}", "source_text": text}
            for i, text in enumerate(source_texts, 1)
        ],
    )
    files = [p for p in target.rglob("*") if p.is_file()]
    write_json(
        target / "freeze.json",
        {
            "date": "2026-10-03",
            "control_cases": 12,
            "extraction_inputs": 12,
            "origin": "Assistant-authored logical controls, not independent scientific gold",
            "files": {p.relative_to(target).as_posix(): digest(p.read_bytes()) for p in files},
        },
    )
    print(target)


if __name__ == "__main__":
    main()
