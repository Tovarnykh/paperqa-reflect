# UiA Coder deployment qualification — 1 October 2026

The existing project was transferred to
`/home/coder/advanced-ict-project/research/paperqa-reflect`, preserving Git history,
uncommitted/untracked files, corpus snapshots and historical run evidence. The
parent project wiki and instructions were transferred with it.

## Verification

- Initial snapshot: 2,152 files; individual SHA-256 checks passed.
- Git branch `codex/local-baseline`, HEAD
  `2b398e0df7e58f05d12b39391d8a7f4f49898af1`; initial dirty status matched.
- V100-SXM3, 32 GiB VRAM; cgroup 96 GiB RAM and 6 CPU quota.
- Python 3.12.3; existing `uv.lock`, pinned PaperQA commit and compatibility
  dependencies unchanged. New isolated Linux virtual environment.
- uv 0.11.23, Ollama 0.30.10; official release archive checksum verified.
- 53 tests passed; Ruff passed; hashes for 16 LitQA source documents and the
  single smoke PDF passed. Doctor passed for Gemma/BGE-M3.

## Single-question integration result

Run: `20261001T202036Z-56ad60`.
Config: `configs/compare-gemma4-nothink-dev-s42.json` (unchanged).
Question: first existing LitQA dev question, `22306bd7-7e84-415d-aebb-11c6312eb081`.

- `paper_search` → `gather_evidence` → `gen_answer` → `complete`.
- Status `success`; selected D matches key D; `correct_completed = 1/1`.
- Corpus indexing: about 43.1 seconds; question: 98.983 seconds; invocation wall
  time: 146.196 seconds. This includes initial loading and may overlap model
  downloads; it is not a controlled hardware-speed comparison.
- Ollama logs confirmed V100 offload, enabled flash attention and quantized KV
  cache allocation. The Gemma run reported 43/43 layers offloaded to GPU.
- No hosted API call or holdout question was run. Individual claim support was
  **not** evaluated; the correct answer letter does not establish factual fidelity.

This verifies the transferred pipeline runs on the server. It does not freeze
the research baseline, select a final model, measure a new mechanism, or establish
model-quality improvements over the laptop results.

Evidence: `results/runs/20261001T202036Z-56ad60/` and
`results/deployment/uia-2026-10-01/`. Original failed and successful laptop runs
remain unchanged. Root `SERVER.md` contains operational instructions. Server and
laptop copies do not automatically synchronize.
