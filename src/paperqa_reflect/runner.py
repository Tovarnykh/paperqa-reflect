"""Run the real PaperQA tool-selection loop and retain its evidence and failures."""

import asyncio
import importlib.metadata
import json
import locale
import logging
import platform
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from .config import build_settings, write_json
from .data import grade, jsonl, paperqa_manifest, question_prompt, sha256, validate_corpus
from .evaluation import aggregate, evidence_diagnostics, runtime_snapshot
from .reference import provider_info, settings_changes
from .usage import UsageLedger


def inspect_ollama(config):
    with httpx.Client(base_url=config.endpoint, timeout=15, trust_env=False) as client:
        version = client.get("/api/version")
        version.raise_for_status()
        tags = client.get("/api/tags")
        tags.raise_for_status()
    available = {item["name"]: item for item in tags.json()["models"]}
    missing = config.models - available.keys()
    if missing:
        raise ValueError(f"Models missing from Ollama: {sorted(missing)}. No models downloaded.")
    selected = {name: available[name] for name in sorted(config.models)}
    if any(model.get("remote_host") or model.get("remote_model") for model in selected.values()):
        raise ValueError("Remote/cloud Ollama models are not allowed in this local configuration.")
    # Verify embedding dimensions against /api/show metadata without inference.
    with httpx.Client(base_url=config.endpoint, timeout=15, trust_env=False) as client:
        shown = client.post("/api/show", json={"model": config.embedding_model})
        shown.raise_for_status()
    metadata = shown.json().get("model_info", {})
    embedding_length = next(
        (value for key, value in metadata.items() if key.endswith(".embedding_length")), None
    )
    if embedding_length != config.embedding_dimensions:
        raise ValueError(
            f"Unexpected or missing embedding dimension from Ollama: {embedding_length}"
        )
    return {
        "version": version.json()["version"],
        "models": selected,
        "embedding_metadata": metadata,
    }


def git_state(root):
    def git(*args):
        result = subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    try:
        return {"head": git("rev-parse", "HEAD"), "status": git("status", "--porcelain")}
    except (OSError, subprocess.CalledProcessError) as error:
        return {"unavailable": str(error)}


def code_hashes(root):
    paths = [root / "pyproject.toml", root / "uv.lock"]
    paths += sorted((root / "src").rglob("*.py"))
    return {str(path.relative_to(root)): sha256(path) for path in paths if path.is_file()}


class QuestionTrace:
    """Keep callbacks and state scoped to one question, including failure paths."""

    def __init__(self, directory):
        self.directory = directory
        self.started = time.perf_counter()
        self.state = None
        self.actions = []

    def event(self, kind, value):
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "seconds": time.perf_counter() - self.started,
                        "kind": kind,
                        "value": value,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    async def reset(self, state):
        self.state = state
        self.event("reset", {"question": state.session.question})

    async def action(self, message, _state):
        value = message.model_dump(mode="json")
        names = [call["function"]["name"] for call in value.get("tool_calls", [])]
        self.actions.extend(names)
        self.event("action", value)
        print(f"  {self.directory.name}: {', '.join(names)}", flush=True)

    async def step(self, observations, reward, done, truncated):
        self.event(
            "step",
            {
                "observations": [obs.model_dump(mode="json") for obs in observations],
                "reward": reward,
                "done": done,
                "truncated": truncated,
            },
        )
        if self.state:
            write_json(
                self.directory / "session-progress.json", self.state.session.model_dump(mode="json")
            )

    async def snapshot(self, state):
        write_json(self.directory / "evidence-progress.json", state.session.model_dump(mode="json"))


async def run(config, config_path: Path, root: Path, limit: int, question_id: str | None = None):
    documents = validate_corpus(root, config)
    if (
        any(doc["file"].endswith(".txt") for doc in documents)
        and locale.getpreferredencoding(False).lower().replace("-", "") != "utf8"
    ):
        raise ValueError(
            "Text-corpus inference requires UTF-8 mode; run Python with -X utf8 or use the CLI."
        )
    questions = jsonl(root / config.questions)
    if question_id:
        questions = [question for question in questions if question["id"] == question_id]
        if not questions:
            raise ValueError(f"Unknown question ID: {question_id}")
    questions = questions[:limit]
    model_info = provider_info(config)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    output = root / "results/runs" / run_id
    output.mkdir(parents=True)
    log_handler = logging.FileHandler(output / "paperqa.log", encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(log_handler)
    logging.getLogger("paperqa").setLevel(logging.INFO)
    manifest = output / "paperqa-manifest.csv"
    paperqa_manifest(manifest, documents)
    # A fresh index per run prevents stale embeddings across model/config comparisons.
    settings = build_settings(config, root, output / "index", manifest)
    settings.make_aviary_tool_selector("ToolSelector")  # Detect dependency API drift early.
    from paperqa.agents import agent_query

    write_json(output / "config.json", config.model_dump())
    write_json(output / "settings.json", settings.model_dump(mode="json"))
    if getattr(config, "profile", None):
        write_json(output / "upstream-deviations.json", settings_changes(settings))
    with zipfile.ZipFile(output / "source-snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in code_hashes(root):
            archive.write(root / relative, relative)
    write_json(
        output / "provenance.json",
        {
            "run_id": run_id,
            "started_utc": datetime.now(UTC).isoformat(),
            "python": platform.python_version(),
            "python_utf8_mode": sys.flags.utf8_mode,
            "default_text_encoding": locale.getpreferredencoding(False),
            "platform": platform.platform(),
            "git": git_state(root),
            "code_sha256": code_hashes(root),
            "config_sha256": sha256(config_path),
            "questions_sha256": sha256(root / config.questions),
            "gold_sha256": sha256(root / config.gold),
            "corpus_manifest_sha256": sha256(root / config.corpus_manifest),
            "corpus": documents,
            "provider": getattr(config, "provider", "ollama"),
            "model_info": model_info,
            "runtime_start": runtime_snapshot(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in ("paper-qa", "paper-qa-pypdf", "fhlmi", "fhaviary", "litellm", "pypdf")
            },
            "question_ids": [question["id"] for question in questions],
            "timing": (
                "Index measured separately; question time includes model loading/switching. Warmness uncontrolled."
                if config.preindex
                else "Per-question wall time includes indexing on first question; model warmness uncontrolled."
            ),
            "protocol": config.protocol,
            "split": config.split,
        },
    )
    print(f"Run: {output}", flush=True)
    records = []
    ledger = UsageLedger(
        output,
        getattr(config, "provider", "ollama"),
        getattr(config, "stop_after_observed_usd", None),
    )
    ledger.install()

    def save_summary():
        write_json(
            output / "summary.json",
            {
                "run_id": run_id,
                "planned_questions": len(questions),
                "completed_questions": len(records),
                "correct_completed": sum(row["grade"]["correct_completed"] for row in records),
                "records": records,
                "metrics": aggregate(records, len(questions)),
                "usage": ledger.totals(),
                "protocol": config.protocol,
                "warning": "Pilot only; not a full LitQA2 evaluation or citation entailment verification.",
            },
        )

    save_summary()
    try:
        if config.preindex:
            from paperqa.agents.search import get_directory_index

            started = time.perf_counter()
            try:
                async with asyncio.timeout(config.index_timeout_seconds):
                    index = await get_directory_index(settings=settings)
                    indexed = await index.index_files
                if set(indexed) != {doc["file"] for doc in documents}:
                    raise ValueError("PaperQA did not index every manifest document")
                write_json(
                    output / "indexing.json",
                    {
                        "seconds": round(time.perf_counter() - started, 3),
                        "documents": len(indexed),
                        "status": "success",
                    },
                )
                settings.agent.rebuild_index = False
                print(
                    f"  Indexed {len(indexed)} documents in {time.perf_counter() - started:.1f} s",
                    flush=True,
                )
            except Exception as error:
                write_json(
                    output / "indexing.json",
                    {
                        "seconds": round(time.perf_counter() - started, 3),
                        "status": "error",
                        "error": f"{type(error).__name__}: {error}",
                    },
                )
                raise
        for question in questions:
            await ledger.flush()
            stop_reason = ledger.stop_reason()
            if stop_reason:
                write_json(
                    output / "stopped.json",
                    {
                        "reason": stop_reason,
                        "planned_questions": len(questions),
                        "completed_questions": len(records),
                    },
                )
                print(f"  Stopped: {stop_reason}", flush=True)
                break
            ledger.phase = question["id"]
            qdir = output / question["id"]
            qdir.mkdir()
            prompt = question_prompt(question)
            (qdir / "question.txt").write_text(prompt, encoding="utf-8")
            trace = QuestionTrace(qdir)
            settings.agent.callbacks = {
                "gather_evidence_completed": [trace.snapshot],
                "gen_answer_completed": [trace.snapshot],
            }
            record = {"id": question["id"], "raw_answer": "", "citation_ids": []}
            try:
                # PaperQA's own timeout permits a fallback answer; this outer bound also covers it.
                async with asyncio.timeout(config.question_timeout_seconds):
                    response = await agent_query(
                        prompt,
                        settings=settings,
                        on_env_reset_callback=trace.reset,
                        on_agent_action_callback=trace.action,
                        on_env_step_callback=trace.step,
                    )
                write_json(qdir / "response.json", response.model_dump(mode="json"))
                record.update(
                    {
                        "status": response.status.value,
                        "answer": response.session.answer,
                        "raw_answer": response.session.raw_answer,
                        "citation_ids": [context.id for context in response.session.contexts],
                        "declared_success": response.session.has_successful_answer,
                        "contexts": len(response.session.contexts),
                        "token_counts": response.session.token_counts,
                        "tool_history": response.session.tool_history,
                    }
                )
                (qdir / "answer.md").write_text(
                    response.session.formatted_answer or response.session.answer, encoding="utf-8"
                )
            except Exception as error:  # noqa: BLE001 - persist provider/parser failures per question
                record.update(
                    {
                        "status": "outer_timeout" if isinstance(error, TimeoutError) else "error",
                        "answer": "",
                        "declared_success": None,
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
                (qdir / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
                if trace.state:
                    write_json(
                        qdir / "session-on-error.json", trace.state.session.model_dump(mode="json")
                    )
            record.update(
                {"seconds": round(time.perf_counter() - trace.started, 3), "actions": trace.actions}
            )
            # The answer key is opened only after inference; never passed to PaperQA.
            keys = {item["id"]: item for item in jsonl(root / config.gold)}
            key = keys[question["id"]]
            record["grade"] = grade(
                record["raw_answer"],
                key["answer"],
                record["status"],
                record["declared_success"],
                tuple(record["citation_ids"]),
                tuple(question["options"]),
            )
            session = trace.state.session.model_dump(mode="json") if trace.state else {}
            record["evidence_diagnostics"] = evidence_diagnostics(session, key)
            record["runtime_end"] = runtime_snapshot()
            evidence_path = qdir / "evidence-progress.json"
            full_evidence = (
                json.loads(evidence_path.read_text(encoding="utf-8"))
                if evidence_path.exists()
                else session
            )
            write_json(
                qdir / "review.json",
                {
                    "question": question,
                    "reference": key,
                    "answer": record.get("answer", ""),
                    "raw_answer": record["raw_answer"],
                    "status": record["status"],
                    "used_contexts": session.get("used_contexts", []),
                    "contexts": full_evidence.get("contexts", []),
                    "review_status": "pending; no claim-level judge has been run",
                },
            )
            write_json(qdir / "grade.json", {**record["grade"], "reference": key})
            records.append(record)
            await ledger.flush()
            save_summary()
            print(
                f"  {question['id']}: {record['status']}, {record['seconds']} s, "
                f"selected={record['grade']['selected']}",
                flush=True,
            )
    finally:
        try:
            await ledger.flush()
        finally:
            ledger.uninstall()
            save_summary()
            logging.getLogger().removeHandler(log_handler)
            log_handler.close()
    return output, len(records) == len(questions) and all(
        row["status"] == "success" for row in records
    )
