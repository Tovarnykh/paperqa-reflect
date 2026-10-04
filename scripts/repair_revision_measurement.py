"""Merge corrected citation units, keeping every answer and extracted assertion unchanged."""

import argparse
import shutil
from datetime import UTC, datetime
from pathlib import Path

from paperqa_reflect.revision import rebind_claims, sentences
from paperqa_reflect.verifier import digest, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.is_relative_to(source):
        raise ValueError("Repair output must be a separate sibling directory")
    state = read_json(source / "run.json")
    if state["status"] != "completed":
        raise ValueError("Source generation run is not completed")
    shutil.copytree(source, output, ignore=shutil.ignore_patterns("evaluation-packet"))
    changes = []
    for item in read_json(source / "input.json")["answers"]:
        for variant in ["B0", "B1", "B2"]:
            relative = Path(item["answer_id"]) / variant
            base = source / relative
            answer = read_json(base / "answer.json")["answer"]
            units = sentences(answer)
            old_units = read_json(base / "sentence-units.json")
            if units != old_units:
                old = read_json(base / "claims.json")
                rebound = rebind_claims(old, units)
                write_json(output / relative / "claims.json", rebound)
                write_json(output / relative / "sentence-units.json", units)
                changes.append(
                    {
                        "variant": relative.as_posix(),
                        "old_claims_sha256": digest((base / "claims.json").read_bytes()),
                        "new_claims_sha256": digest(
                            (output / relative / "claims.json").read_bytes()
                        ),
                        "bindings_changed": [
                            a["case_id"]
                            for a, b in zip(old, rebound, strict=True)
                            if a["passage_ids"] != b["passage_ids"]
                        ],
                    }
                )
            assert (source / relative / "answer.json").read_bytes() == (
                output / relative / "answer.json"
            ).read_bytes()
    write_json(
        output / "measurement-repair.json",
        {
            "method": "deterministic sentence-boundary/citation rebinding; no new extraction or answer generation",
            "source_generation_run": str(source),
            "repaired_utc": datetime.now(UTC).isoformat(),
            "model_calls": 0,
            "changes": changes,
        },
    )
    write_json(
        output / "run.json",
        {
            **state,
            "directory": str(output),
            "is_new_generation": False,
            "source_generation_run": str(source),
        },
    )
    (output / "measurement-repair-source.py").write_bytes(Path(__file__).read_bytes())
    print(changes)


if __name__ == "__main__":
    main()
