"""Pinned upstream high_quality with explicit model and fixed-corpus adaptations."""

import os
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOL_CALL_COMPATIBILITY = (
    "Every controller turn must call a tool. Answer-format instructions in the question apply "
    "to the answer produced by gen_answer, not to controller messages. After gen_answer, "
    "call complete with has_successful_answer=true if the answer is sufficient; otherwise "
    "use tools to improve it or complete with has_successful_answer=false."
)


class LocalSampling(BaseModel):
    """Explicit overrides; omitted values retain the pinned Ollama model defaults."""

    model_config = ConfigDict(extra="forbid")
    temperature: float | None = Field(None, ge=0, le=2)
    top_p: float | None = Field(None, gt=0, le=1)
    top_k: int | None = Field(None, ge=0)
    min_p: float | None = Field(None, ge=0, le=1)
    repeat_penalty: float | None = Field(None, gt=0)
    presence_penalty: float | None = Field(None, ge=-2, le=2)


class ReferenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal["paperqa-high-quality"]
    name: str
    provider: Literal["ollama", "openai"]
    agent_model: str
    summary_model: str
    answer_model: str
    embedding_model: str
    embedding_dimensions: int = Field(gt=0)
    endpoint: str | None = None
    context_tokens: int | None = Field(None, gt=0)
    max_output_tokens: int | None = Field(None, gt=0)
    seed: int | None = None
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None
    agent_reasoning_effort: Literal["none", "low", "medium", "high"] | None = None
    sampling: LocalSampling | None = None
    agent_sampling: LocalSampling | None = None
    tool_call_compatibility: bool = False
    tool_transport: Literal["native", "json-schema-v1"] = "native"
    embedding_batch_tokens: int | None = Field(None, gt=0)
    agent_evidence_n: int | None = Field(None, ge=1)
    request_timeout_seconds: int = Field(600, gt=0)
    agent_timeout_seconds: int = Field(1800, gt=0)
    question_timeout_seconds: int = Field(2400, gt=0)
    max_concurrent_requests: int = Field(1, gt=0)
    # A between-question stop threshold, not a guaranteed provider billing cap.
    stop_after_observed_usd: float | None = Field(None, gt=0)
    corpus_dir: str
    corpus_manifest: str
    questions: str
    gold: str
    protocol: str = "paperqa-hq-fixed-corpus-v1"
    split: Literal["dev", "holdout"] = "dev"
    preindex: Literal[True] = True
    index_timeout_seconds: int = Field(1800, gt=0)

    @property
    def models(self):
        return {self.agent_model, self.summary_model, self.answer_model, self.embedding_model}

    @model_validator(mode="after")
    def validate_routing(self):
        if self.question_timeout_seconds <= self.agent_timeout_seconds:
            raise ValueError("The outer question timeout must exceed the agent timeout.")
        if self.provider == "ollama":
            endpoint = urlparse(self.endpoint or "")
            if (
                endpoint.scheme != "http"
                or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
                or endpoint.path not in {"", "/"}
            ):
                raise ValueError("Local profiles require a loopback Ollama endpoint or SSH tunnel.")
            if any("cloud" in model.lower() or "/" in model for model in self.models):
                raise ValueError(
                    "Use installed local Ollama model names, without provider prefixes."
                )
            if self.context_tokens is None or self.max_output_tokens is None:
                raise ValueError("Local context/output limits must be explicit.")
        else:
            if self.tool_call_compatibility or self.tool_transport != "native":
                raise ValueError(
                    "The upstream OpenAI control keeps its original controller prompt."
                )
            if (
                self.endpoint
                or self.context_tokens
                or self.seed is not None
                or self.embedding_batch_tokens
                or self.sampling is not None
                or self.agent_sampling is not None
            ):
                raise ValueError("Ollama endpoint/context/seed do not apply to the OpenAI control.")
            # This compatibility control is deliberately the exact upstream model snapshot.
            # New model families need an independently tested tool-calling adapter.
            if (
                self.models != {"gpt-4o-2024-11-20", "text-embedding-3-small"}
                or any(
                    model != "gpt-4o-2024-11-20"
                    for model in (self.agent_model, self.summary_model, self.answer_model)
                )
                or self.embedding_model != "text-embedding-3-small"
            ):
                raise ValueError("The OpenAI control uses the pinned upstream model IDs only.")
            if (
                self.max_output_tokens
                or self.reasoning_effort is not None
                or self.agent_reasoning_effort is not None
            ):
                raise ValueError(
                    "Keep the upstream OpenAI control free of local generation limits."
                )
            if self.stop_after_observed_usd is None:
                raise ValueError("Set a between-question spending stop for the paid control.")
        return self


def upstream_settings():
    from paperqa import Settings

    # Read the PACKAGE preset directly; from_name can prefer a mutable user preset.
    preset = files("paperqa.configs").joinpath("high_quality.json").read_text(encoding="utf-8")
    return Settings.model_validate_json(preset)


def reference_settings(config, root: Path, index_dir: Path, manifest: Path):
    from paperqa import Settings

    values = upstream_settings().model_dump(mode="json")

    def name(model, embedding=False):
        if config.provider == "openai":
            return model
        return f"{'ollama' if embedding else 'ollama_chat'}/{model}"

    def llm(model, agent=False):
        params = {"model": name(model), "temperature": 0, "timeout": config.request_timeout_seconds}
        if config.provider == "ollama":
            params.update(
                api_base=config.endpoint,
                num_ctx=config.context_tokens,
                max_tokens=config.max_output_tokens,
            )
            if config.seed is not None:
                params["seed"] = config.seed
            if config.reasoning_effort is not None:
                params["reasoning_effort"] = config.reasoning_effort
            if agent and config.agent_reasoning_effort is not None:
                params["reasoning_effort"] = config.agent_reasoning_effort
            if config.sampling is not None:
                params.update(config.sampling.model_dump(exclude_none=True))
            if agent and config.agent_sampling is not None:
                params.update(config.agent_sampling.model_dump(exclude_none=True))
            if "presence_penalty" in params:
                # Ollama supports it; this pinned LiteLLM needs an explicit pass-through.
                params["allowed_openai_params"] = ["presence_penalty"]
        return {
            "model_list": [{"model_name": name(model), "litellm_params": params}],
            "router_kwargs": {"num_retries": 0, "timeout": config.request_timeout_seconds},
        }

    values.update(
        llm=name(config.answer_model),
        llm_config=llm(config.answer_model),
        summary_llm=name(config.summary_model),
        summary_llm_config=llm(config.summary_model),
        embedding=name(config.embedding_model, embedding=True),
    )
    embed_kwargs = {"timeout": config.request_timeout_seconds, "num_retries": 0}
    if config.provider == "ollama":
        embed_kwargs["api_base"] = config.endpoint
        embed_kwargs["truncate"] = False
        if config.embedding_batch_tokens:
            embed_kwargs["options"] = {"num_batch": config.embedding_batch_tokens}
    values["embedding_config"] = {
        "batch_size": 8,
        "kwargs": embed_kwargs,
    }
    values["answer"]["max_concurrent_requests"] = config.max_concurrent_requests
    values["parsing"].update(
        use_doc_details=False,
        multimodal=False,
        enrichment_llm=name(config.summary_model),
        enrichment_llm_config=llm(config.summary_model),
    )
    values["agent"].update(
        agent_llm=name(config.agent_model),
        agent_llm_config=llm(config.agent_model, agent=True),
        timeout=config.agent_timeout_seconds,
    )
    if config.agent_evidence_n is not None:
        values["agent"]["agent_evidence_n"] = config.agent_evidence_n
    if config.tool_call_compatibility:
        values["agent"]["agent_system_prompt"] += "\n\n" + TOOL_CALL_COMPATIBILITY
    values["agent"]["index"].update(
        paper_directory=str((root / config.corpus_dir).resolve()),
        manifest_file=str(manifest.resolve()),
        index_directory=str(index_dir.resolve()),
        recurse_subdirectories=False,
        concurrency=1,
    )
    # Only the explicit local tool-call adaptation can extend the agent prompt.
    # No step cap or changed RCS/answer prompt. agent_evidence_n changes only
    # the existing GatherEvidence observation, not retrieval or answer evidence caps.
    if config.tool_transport == "json-schema-v1":
        from .tool_transport import LocalStructuredSettings

        return LocalStructuredSettings.model_validate(values)
    return Settings.model_validate(values)


def settings_changes(settings):
    """Enumerate every deviation, including harness paths and model routing."""

    def flatten(value, prefix=""):
        result = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, dict) and item:
                result.update(flatten(item, path))
            else:
                result[path] = item
        return result

    before = flatten(upstream_settings().model_dump(mode="json"))
    after = flatten(settings.model_dump(mode="json"))
    return {
        key: {"upstream": before.get(key), "configured": after.get(key)}
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }


def provider_info(config):
    if getattr(config, "provider", "ollama") == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is absent. Set it locally; never put it in a config or chat."
            )
        return {
            "provider": "openai",
            "credential_present": True,
            "availability": "not probed; actual API access is checked by inference",
        }
    from .runner import inspect_ollama

    return inspect_ollama(config)
