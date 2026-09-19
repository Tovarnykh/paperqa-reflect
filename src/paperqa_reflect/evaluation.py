"""Transparent run-level metrics; citation presence does not prove entailment."""

import ctypes
import platform
import re
import statistics
import subprocess
from collections import Counter


def runtime_snapshot():
    result = {"system": platform.platform()}
    if platform.system() == "Windows":

        class PowerStatus(ctypes.Structure):
            _fields_ = [
                ("ac", ctypes.c_ubyte),
                ("flags", ctypes.c_ubyte),
                ("percent", ctypes.c_ubyte),
                ("reserved", ctypes.c_ubyte),
                ("seconds", ctypes.c_ulong),
                ("full_seconds", ctypes.c_ulong),
            ]

        power = PowerStatus()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
            result["ac_line_status"] = {0: "offline", 1: "online", 255: "unknown"}.get(power.ac)
            result["battery_percent"] = power.percent
    try:
        sample = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu,power.draw",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        result["nvidia_smi"] = sample.stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        result["nvidia_smi_unavailable"] = str(error)
    return result


def evidence_diagnostics(session: dict, reference: dict) -> dict:
    contexts = session.get("contexts", [])
    used = set(session.get("used_contexts", []))
    dois = {doi.lower() for doi in reference.get("source_dois", [])}
    matching = []
    for context in contexts:
        citation = context.get("text", {}).get("doc", {}).get("citation", "").lower()
        cited_dois = {
            value.rstrip(".;)]}") for value in re.findall(r"10\.\d{4,9}/[^\s,]+", citation)
        }
        if dois.intersection(cited_dois):
            matching.append(context["id"])
    return {
        "reference_in_evidence": bool(matching) if dois else None,
        "reference_cited": bool(used.intersection(matching)) if dois else None,
        "reference_context_ids": matching,
        "cited_contexts": len(used),
        "claim_support_checked": False,
        "note": "Source DOI presence only; does not establish that any claim is supported.",
    }


def aggregate(records: list[dict], planned_questions: int | None = None) -> dict:
    n = len(records)
    complete = planned_questions is None or n == planned_questions
    if planned_questions is not None and n > planned_questions:
        raise ValueError("More results than planned questions")
    answered = [
        r
        for r in records
        if r["status"] == "success" and r["grade"]["format_valid"] and not r["grade"]["abstained"]
    ]
    correct = sum(r["grade"]["correct_completed"] for r in records)
    return {
        "questions": n,
        "planned_questions": planned_questions if planned_questions is not None else n,
        "series_complete": complete,
        "correct_completed": correct,
        "accuracy": correct / n if n and complete else None,
        "answered_completed": len(answered),
        "coverage": len(answered) / n if n and complete else None,
        "precision_when_answered": correct / len(answered) if answered and complete else None,
        "explicit_or_declared_abstentions": sum(r["grade"]["abstained"] for r in records),
        "invalid_answer_formats": sum(not r["grade"]["format_valid"] for r in records),
        "statuses": dict(Counter(r["status"] for r in records)),
        "total_question_seconds": round(sum(r["seconds"] for r in records), 3),
        "median_question_seconds": statistics.median(r["seconds"] for r in records) if n else None,
        "tool_calls": dict(Counter(action for r in records for action in r["actions"])),
    }
