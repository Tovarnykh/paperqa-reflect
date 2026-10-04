"""Explicit local model routing and bounded, reproducible experiment settings."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    agent_system_prompt: str
    endpoint: str
    agent_model: str
    summary_model: str
    answer_model: str
    embedding_model: str
    embedding_dimensions: int = Field(gt=0)
    context_tokens: int = Field(8192, gt=0)
    max_output_tokens: int = Field(768, gt=0)
    temperature: float = 0
    seed: int = 42
    reasoning_effort: str = "none"
    request_timeout_seconds: int = Field(240, gt=0)
    agent_timeout_seconds: int = Field(900, gt=0)
    question_timeout_seconds: int = Field(1200, gt=0)
    max_steps: int = Field(8, gt=0)
    evidence_k: int = Field(3, gt=0)
    answer_max_sources: int = Field(3, gt=0)
    chunk_chars: int = Field(3000, gt=0)
    chunk_overlap: int = Field(250, ge=0)
    corpus_dir: str
    corpus_manifest: str
    questions: str
    gold: str
    protocol: str = "smoke-v1"
    split: str = "dev"
    preindex: bool = False
    index_timeout_seconds: int = Field(1800, gt=0)

    @model_validator(mode="after")
    def validate_local_experiment(self):
        endpoint = urlparse(self.endpoint)
        if (
            endpoint.scheme != "http"
            or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.path not in {"", "/"}
        ):
            raise ValueError("Use a loopback Ollama HTTP endpoint (or an SSH tunnel to UiA).")
        if any("cloud" in model.lower() for model in self.models):
            raise ValueError("Cloud models are not part of the local-only protocol.")
        if self.chunk_overlap >= self.chunk_chars:
            raise ValueError("Chunk overlap must be smaller than the chunk size.")
        if self.question_timeout_seconds <= self.agent_timeout_seconds:
            raise ValueError("The outer question timeout must exceed the agent timeout.")
        return self

    @property
    def models(self):
        return {self.agent_model, self.summary_model, self.answer_model, self.embedding_model}


def load_config(path: Path):
    values = json.loads(path.read_text(encoding="utf-8"))
    if values.get("profile") == "paperqa-high-quality":
        from .reference import ReferenceConfig

        return ReferenceConfig.model_validate(values)
    return ExperimentConfig.model_validate(values)


def local_runtime(root: Path):
    # Set before importing PaperQA/LiteLLM. Do not change the user's HOME.
    os.environ["PQA_HOME"] = str(root / ".cache/paperqa")
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["TIKTOKEN_CACHE_DIR"] = str(root / ".cache/tiktoken")


def build_settings(config: ExperimentConfig, root: Path, index_dir: Path, manifest: Path):
    local_runtime(root)
    if getattr(config, "profile", None) == "paperqa-high-quality":
        from .reference import reference_settings

        return reference_settings(config, root, index_dir, manifest)
    from paperqa import Settings

    def llm(model):
        name = f"ollama_chat/{model}"
        return {
            "model_list": [
                {
                    "model_name": name,
                    "litellm_params": {
                        "model": name,
                        "api_base": config.endpoint,
                        "temperature": config.temperature,
                        "seed": config.seed,
                        "num_ctx": config.context_tokens,
                        "max_tokens": config.max_output_tokens,
                        "reasoning_effort": config.reasoning_effort,
                        "timeout": config.request_timeout_seconds,
                    },
                }
            ],
            "router_kwargs": {"num_retries": 0, "timeout": config.request_timeout_seconds},
        }

    return Settings(
        llm=f"ollama_chat/{config.answer_model}",
        llm_config=llm(config.answer_model),
        summary_llm=f"ollama_chat/{config.summary_model}",
        summary_llm_config=llm(config.summary_model),
        embedding=f"ollama/{config.embedding_model}",
        embedding_config={
            "batch_size": 8,
            "kwargs": {
                "api_base": config.endpoint,
                "timeout": config.request_timeout_seconds,
                "num_retries": 0,
            },
        },
        temperature=config.temperature,
        answer={
            "evidence_k": config.evidence_k,
            "answer_max_sources": config.answer_max_sources,
            "max_concurrent_requests": 1,
        },
        parsing={
            "use_doc_details": False,
            "multimodal": False,
            "enrichment_llm": f"ollama_chat/{config.summary_model}",
            "enrichment_llm_config": llm(config.summary_model),
            "reader_config": {"chunk_chars": config.chunk_chars, "overlap": config.chunk_overlap},
        },
        agent={
            "agent_system_prompt": config.agent_system_prompt,
            "agent_llm": f"ollama_chat/{config.agent_model}",
            "agent_llm_config": llm(config.agent_model),
            "timeout": config.agent_timeout_seconds,
            "max_timesteps": config.max_steps,
            "index": {
                "paper_directory": str((root / config.corpus_dir).resolve()),
                "manifest_file": str(manifest.resolve()),
                "index_directory": str(index_dir.resolve()),
                "recurse_subdirectories": False,
                "concurrency": 1,
            },
        },
    )


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
