"""Frozen eight-question local revision comparison; no gold or external judge feedback."""

import argparse
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from jsonschema import ValidationError

from . import revision as r
from .verifier import digest, load_config, observe, read_json, write_json

ROOT = r.ROOT
RUN = "20261002T175947Z-2dc0f1"
KIND = "all-dev-revision-v1"


def prepare(destination):
    inventory = read_json(ROOT / "data/verification/claim-support-dev-v1/answer-inventory.json")
    selected = sorted((x for x in inventory if x["run_id"] == RUN), key=lambda x: x["question_id"])
    dev = [
        json.loads(s) for s in (ROOT / "data/questions/litqa-dev.jsonl").read_text().splitlines()
    ]
    if len(selected) != 8 or {x["question_id"] for x in selected} != {x["id"] for x in dev}:
        raise ValueError("Must include exactly all eight frozen dev questions")
    answers = []
    for index, entry in enumerate(selected):
        path = ROOT / entry["review_path"]
        review = read_json(path)
        answer = review["raw_answer"]
        if (
            digest(path.read_bytes()) != entry["review_sha256"]
            or digest(answer.encode()) != entry["answer_sha256"]
        ):
            raise ValueError("Saved baseline changed")
        cited = set(r.CITATION.findall(answer))
        available = {c["id"]: c["text"]["text"] for c in review["contexts"]}
        if not cited or not cited <= set(available):
            raise ValueError("Unresolvable baseline citations")
        # Explicit allowlist excludes reference answers/support/metadata from model input.
        question = {key: review["question"][key] for key in ["question", "options"]}
        answers.append(
            {
                "answer_id": f"dev-{index + 1:02d}",
                "question_id": entry["question_id"],
                "question": question,
                "original_answer": answer,
                "sources": {cid: available[cid] for cid in sorted(cited)},
                "review_sha256": entry["review_sha256"],
                "answer_sha256": entry["answer_sha256"],
                "review_path": entry["review_path"],
                "arm_order": ["B1", "B2"] if index % 2 == 0 else ["B2", "B1"],
            }
        )
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json(destination, {"kind": KIND, "baseline_run": RUN, "answers": answers})
    return answers


def verifier_feedback(client, config, directory, item):
    claims = r.extract(
        client, config, directory, item["original_answer"], item["question"], item["sources"], "v2"
    )
    feedback = []
    (directory / "verification").mkdir()
    for claim in claims:
        target = directory / "verification" / claim["case_id"]
        if claim["passage_ids"]:
            result = observe(
                {k: claim[k] for k in ["case_id", "claim", "passage_ids"]},
                item["sources"],
                config,
                client,
                target,
                config["_chat_template"],
                Path(config["server_log"]),
            )
        else:
            target.mkdir(parents=True)
            result = {
                "status": "checked",
                "attempts": 0,
                "seconds": 0,
                "usage": {},
                "reason": "no_citation",
                "verdict": {
                    "label": "insufficient",
                    "evidence": [],
                    "explanation": "No explicit citation on this sentence; citation support not established.",
                },
            }
            write_json(target / "result.json", result)
        feedback.append(
            {
                "claim": claim["claim"],
                "answer_quote": claim["answer_quote"],
                "status": result["status"],
                "verdict": result["verdict"],
            }
        )
    write_json(directory / "feedback.json", feedback)
    if not claims or any(row["status"] != "checked" for row in feedback):
        raise ValueError("Incomplete verifier feedback; original answer retained")
    return {"claim_checks": feedback}


def run_arm(client, config, directory, item, arm):
    directory.mkdir()
    start = time.monotonic()
    result = {"answer": item["original_answer"], "status": "fallback_original"}
    common = {
        "question": item["question"],
        "original_answer": item["original_answer"],
        "sources": [{"source_id": k, "text": v} for k, v in item["sources"].items()],
    }
    try:
        if arm == "B1":
            raw = r.local_json(
                client,
                config,
                directory / "review",
                "ordinary_review",
                r.REVIEW_PROMPT,
                common,
                r.REVIEW_SCHEMA,
                65536,
            )
            notes = r.validate_review(r.require(raw), item["original_answer"], item["sources"])
        elif arm == "B2":
            notes = verifier_feedback(client, config, directory, item)
        else:
            raise ValueError("Unknown intervention")
        raw = r.local_json(
            client,
            config,
            directory / "revision",
            "answer_revision",
            r.REVISION_PROMPT,
            {**common, "review": notes},
            r.REVISION_SCHEMA,
            65536,
        )
        result.update(
            answer=r.validate_revision(r.require(raw), item["question"], item["sources"]),
            status="revised",
        )
    except (ValueError, KeyError, TypeError, OSError, ValidationError, httpx.HTTPError) as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)[:600]}
    result["seconds"] = time.monotonic() - start
    write_json(directory / "answer.json", result)
    return result


def run(packet_path, output_root, config_path):
    packet, config = read_json(packet_path), load_config(config_path)
    if packet["kind"] != KIND or len(packet["answers"]) != 8:
        raise ValueError("Expected frozen eight-question packet")
    identifier = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    output = output_root / identifier
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "input.json", packet)
    write_json(output / "config.json", config)
    for module in ["dev_comparison.py", "revision.py", "verifier.py"]:
        (output / module).write_bytes(Path(__file__).with_name(module).read_bytes())
    state = {
        "status": "starting",
        "answers_finished": 0,
        "arm_failures": 0,
        "API_calls": 0,
        "started_utc": datetime.now(UTC).isoformat(),
        "packet_sha256": digest(packet_path.read_bytes()),
        "extraction_version": "v2",
    }
    write_json(output / "run.json", state)
    print(output, flush=True)
    try:
        with httpx.Client(
            base_url=config["endpoint"], timeout=config["request_timeout_seconds"]
        ) as c:
            if c.get("/api/version").json()["version"] != config["ollama_version"]:
                raise ValueError("Runtime mismatch")
            if not any(
                m["name"] == config["model"] and m["digest"] == config["model_digest"]
                for m in c.get("/api/tags").json()["models"]
            ):
                raise ValueError("Model mismatch")
            show = c.post("/api/show", json={"model": config["model"]}).json()
            config["_chat_template"] = show["template"]
            write_json(output / "model-info.json", show)
            state["status"] = "running"
            for item in packet["answers"]:
                base = output / item["answer_id"]
                (base / "B0").mkdir(parents=True)
                write_json(
                    base / "B0/answer.json",
                    {
                        "answer": item["original_answer"],
                        "status": "original",
                        "seconds": 0,
                    },
                )
                for arm in item["arm_order"]:
                    result = run_arm(c, config, base / arm, item, arm)
                    state["arm_failures"] += result["status"] != "revised"
                    print(item["answer_id"], arm, result["status"], flush=True)
                    write_json(output / "run.json", state)
                state["answers_finished"] += 1
                write_json(output / "run.json", state)
            state["status"] = "completed"
    except BaseException:
        state["status"] = "interrupted"
        raise
    finally:
        state["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(output / "run.json", state)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run"])
    parser.add_argument(
        "--packet", type=Path, default=ROOT / "data/verification/all-dev-revision-v1/input.json"
    )
    args = parser.parse_args()
    if args.command == "prepare":
        print("Prepared", len(prepare(args.packet)), "answers")
    else:
        print(
            run(
                args.packet,
                ROOT / "results/dev-comparison",
                ROOT / "configs/verifier-qwen38-v1.json",
            )
        )


if __name__ == "__main__":
    main()
