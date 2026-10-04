"""Observe all LiteLLM requests, including controller and indexing calls."""

import asyncio
import json

from .config import write_json


class UsageLedger:
    def __init__(self, directory, provider, stop_after_usd=None):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.provider = provider
        self.stop_after_usd = stop_after_usd
        self.phase = "indexing"
        self.rows = []
        self.seen = set()
        self.callback = None

    def record(self, kwargs, response, status, start, end):
        # Whitelist fields: no request prompts, credentials, headers or embeddings.
        request_id = kwargs.get("litellm_call_id") or getattr(response, "id", None)
        if request_id and request_id in self.seen:
            return
        if request_id:
            self.seen.add(request_id)
        usage = getattr(response, "usage", None)
        usage = usage.model_dump(mode="json") if hasattr(usage, "model_dump") else usage
        cost = kwargs.get("response_cost")
        if self.provider == "ollama":
            cost = 0.0
        elif status == "success" and cost is None:
            import litellm

            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:  # noqa: BLE001 - unknown provider pricing is retained as missing
                cost = None
        row = {
            "request_id": request_id,
            "phase": self.phase,
            "status": status,
            "requested_model": kwargs.get("model"),
            "response_model": getattr(response, "model", None),
            "usage": usage,
            "estimated_usd": cost,
            "finish_reasons": [
                getattr(choice, "finish_reason", None)
                for choice in getattr(response, "choices", [])
            ],
            "seconds": (end - start).total_seconds(),
        }
        self.rows.append(row)
        with (self.directory / "requests.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.save()

    def totals(self):
        missing = sum(row["estimated_usd"] is None for row in self.rows)
        return {
            "requests": len(self.rows),
            "observed_estimated_usd": sum(row["estimated_usd"] or 0 for row in self.rows),
            "requests_without_cost": missing,
            "cost_complete": bool(self.rows) and missing == 0,
            "stop_after_observed_usd": self.stop_after_usd,
            "note": "Observed estimates, not an invoice or hard cap. In-flight/failed requests may be billed. Local electricity/hardware excluded.",
        }

    def stop_reason(self):
        if self.provider == "ollama":
            return None
        totals = self.totals()
        if not totals["cost_complete"]:
            return "missing API cost accounting; inspect before starting another question"
        if totals["observed_estimated_usd"] >= self.stop_after_usd:
            return "between-question observed spending threshold reached"
        return None

    def save(self):
        write_json(self.directory / "usage.json", self.totals())

    def install(self):
        import litellm
        from litellm.integrations.custom_logger import CustomLogger

        ledger = self

        class Callback(CustomLogger):
            async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
                ledger.record(kwargs, response_obj, "success", start_time, end_time)

            async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
                ledger.record(kwargs, response_obj, "failure", start_time, end_time)

        self.callback = Callback()
        litellm.callbacks.append(self.callback)

    async def flush(self):
        from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

        # LiteLLM schedules its success handler on the next event-loop turn.
        await asyncio.sleep(0)
        await GLOBAL_LOGGING_WORKER.flush()
        self.save()

    def uninstall(self):
        import litellm

        # LiteLLM may copy custom callbacks into these registries during dispatch.
        for name in (
            "callbacks",
            "success_callback",
            "failure_callback",
            "_async_success_callback",
            "_async_failure_callback",
        ):
            callbacks = getattr(litellm, name, [])
            while self.callback in callbacks:
                callbacks.remove(self.callback)
