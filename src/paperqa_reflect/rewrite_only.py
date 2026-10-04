"""One source-grounded rewrite, with generated review ablated from the frozen B1 arm."""

import argparse
import copy
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from jsonschema import ValidationError

from . import pairwise
from . import revision as r
from .verifier import digest, load_config, read_json, write_json

ROOT = r.ROOT
PRIOR = ROOT / "results/dev-comparison/20261003T174838Z-e451ff"
PACKET_SHA = "d359b46743418e96e2ffe86b21d5ee99d0c5129fac966431746d6f6e00512e10"


def ablated_request(request, item):
    """Reject input drift; replace only the generated review, preserving serialization."""
    result = copy.deepcopy(request)
    payload = json.loads(result["messages"][1]["content"])
    common = {
        "question": item["question"],
        "original_answer": item["original_answer"],
        "sources": [{"source_id": k, "text": v} for k, v in item["sources"].items()],
    }
    if set(payload) != {*common, "review"} or any(payload[k] != v for k, v in common.items()):
        raise ValueError("Prior B1 input differs from frozen packet")
    payload["review"] = {"issues": []}
    result["messages"][1]["content"] = json.dumps(payload, ensure_ascii=False)
    return result, payload


def run_arm(client, config, directory, item, prior_request):
    directory.mkdir(parents=True, exist_ok=False)
    expected, payload = ablated_request(prior_request, item)
    start = time.monotonic()
    result = {"answer": item["original_answer"], "status": "fallback_original"}
    try:
        raw = r.local_json(
            client, config, directory / "revision", "answer_revision",
            r.REVISION_PROMPT, payload, r.REVISION_SCHEMA, 65536,
        )
        actual = read_json(directory / "revision/request.json")
        if actual != expected:
            raise ValueError("Request drift beyond removal of generated review")
        result.update(
            answer=r.validate_revision(r.require(raw), item["question"], item["sources"]),
            status="revised",
        )
    except (ValueError, KeyError, TypeError, OSError, ValidationError, httpx.HTTPError) as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)[:600]}
    result["seconds"] = time.monotonic() - start
    result["same_request_as_B1"] = expected == prior_request
    write_json(directory / "answer.json", result)
    return result


def run(prior, config_path, output_root):
    if digest((prior / "input.json").read_bytes()) != PACKET_SHA:
        raise ValueError("Expected frozen all-eight dev packet")
    packet, config = read_json(prior / "input.json"), load_config(config_path)
    if config != read_json(prior / "config.json"):
        raise ValueError("Configuration changed")
    # Same helper/prompt/schema/sampling as B1; detect drift before any inference.
    if Path(r.__file__).read_bytes() != (prior / "revision.py").read_bytes():
        raise ValueError("Frozen revision implementation changed")
    old_requests = {}
    for item in packet["answers"]:
        qid = item["answer_id"]
        old_requests[qid] = read_json(prior / qid / "B1/revision/request.json")
        ablated_request(old_requests[qid], item)
    identifier = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    output = output_root / identifier
    output.mkdir(parents=True, exist_ok=False)
    (output / "input.json").write_bytes((prior / "input.json").read_bytes())
    write_json(output / "config.json", config)
    for module in ["rewrite_only.py", "revision.py", "verifier.py"]:
        (output / module).write_bytes(Path(__file__).with_name(module).read_bytes())
    state = {
        "kind": "rewrite-only-v1", "status": "starting", "prior_run": prior.name,
        "answers_finished": 0, "arm_failures": 0, "API_calls": 0,
        "started_utc": datetime.now(UTC).isoformat(), "packet_sha256": PACKET_SHA,
    }
    write_json(output / "run.json", state)
    print(output, flush=True)
    try:
        with httpx.Client(base_url=config["endpoint"], timeout=config["request_timeout_seconds"]) as c:
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
            if show != read_json(prior / "model-info.json"):
                raise ValueError("Model metadata changed")
            state["status"] = "running"
            for item in packet["answers"]:
                qid = item["answer_id"]
                target = output / qid
                target.mkdir()
                write_json(target / "prior-B1-request.json", old_requests[qid])
                result = run_arm(c, config, target / "B3", item, old_requests[qid])
                result["same_answer_as_B1"] = (
                    result["answer"] == read_json(prior / qid / "B1/answer.json")["answer"]
                )
                write_json(target / "B3/answer.json", result)
                state["answers_finished"] += 1
                state["arm_failures"] += result["status"] != "revised"
                write_json(output / "run.json", state)
                print(qid, result["status"], result["same_answer_as_B1"], flush=True)
            state["status"] = "completed"
    except BaseException:
        state["status"] = "interrupted"
        raise
    finally:
        state["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(output / "run.json", state)
    return output


def prepare_pairs(local, prior, output):
    if read_json(local / "run.json")["status"] != "completed":
        raise ValueError("Generation must finish before evaluation")
    if any(digest((p / "input.json").read_bytes()) != PACKET_SHA for p in [local, prior]):
        raise ValueError("Comparison packets differ")
    pairs = []
    for item in read_json(local / "input.json")["answers"]:
        answers = {
            arm: read_json(prior / item["answer_id"] / arm / "answer.json")["answer"]
            for arm in ["B0", "B1", "B2"]
        }
        answers["B3"] = read_json(local / item["answer_id"] / "B3/answer.json")["answer"]
        if digest(answers["B0"].encode()) != item["answer_sha256"]:
            raise ValueError("Baseline changed")
        for arm in ["B0", "B1", "B2"]:
            pairs.append({
                "pair_id": item["answer_id"] + "-" + arm + "-B3",
                "arms": [arm, "B3"], "answers": answers,
                "question": item["question"], "sources": item["sources"],
            })
    return pairwise.packet_write(output, pairs, {
        "local_run": local.name, "prior_run": prior.name, "input_sha256": PACKET_SHA,
        "evaluation": "All eight dev questions and fallbacks; only three new pairs, both orders",
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "prepare-pairs"])
    parser.add_argument("--prior", type=Path, default=PRIOR)
    parser.add_argument("--local", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        print(run(args.prior, ROOT / "configs/verifier-qwen38-v1.json", ROOT / "results/rewrite-only"))
    else:
        if args.local is None or args.output is None:
            parser.error("prepare-pairs requires --local and --output")
        print(prepare_pairs(args.local, args.prior, args.output))


if __name__ == "__main__":
    main()
