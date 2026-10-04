# paperqa-reflect

UiA IKT464 research repository: reproducible local PaperQA and separately evaluated
extensions. The fixed development corpus has eight questions; the reserved split
is for final evaluation after configurations are frozen.

## Current citation branch

This checkout is `exp/citation`; independent loop development is in the sibling
`../paperqa-loop` worktree on `exp/loop`, starting at `paperqa-baseline-v1`.
The Git checkpoints were created on 4 October from preserved experiment files;
they are not historical September commits. [Organization checks](results/reports/2026-10-04-git-organization.md).

The completed citation dev cycle compares B0 baseline, B1 ordinary review plus
rewrite, B2 local claim verification plus rewrite, and B3 one rewrite without
review. B3 used 8 local calls / 167.609 seconds; 7 answers exactly matched B1.
The fixed external judge rated B3 above B0 in 7 cases, tied in 1, and tied with B1
in all 8. All variants retained 8/8 correct options. B2 did not outperform B1.
These are dev findings, not independent generalization evidence. B3 is the
economical candidate; the verifier result is retained even though it is negative.

- [B0/B1/B2 comparison](results/reports/2026-10-03-main-dev-comparison.md)
- [B3 ablation and limitations](results/reports/2026-10-03-rewrite-only-ablation.md)
- [Local verifier](docs/local-verifier.md) and [external evaluator](docs/external-judge.md)
- [Measurement v2](docs/measurement-repair-v2.md); use explicit `--extraction-version v2`
- [Original README checkpoint history](docs/history/README-before-git-organization.md)

No loop intervention has been implemented. The next research step is a narrow
controller-evidence hypothesis on `exp/loop`. Combine mechanisms only in a later
separate experiment. No model/API runs are part of Git organization.

## Frozen working baseline

The selected comparator is **Qwen3.8 27B Q4_K_M + BGE-M3**, PaperQA pinned through
`uv.lock`, Ollama 0.35.0 on the UiA V100 32 GiB. Seeds 42 and 43 each completed 8/8
dev questions with correct options. These repeated questions are not independent
validation, and correct options do not establish faithful source attribution.

- [Frozen manifest, model digests and source hashes](results/baselines/uia-local-reference-v1.json)
- [Selection results and limitations](results/reports/2026-10-02-uia-model-selection.md)
- [Selection protocol](docs/uia-baseline-selection-v1.md)
- [Data and evaluation protocol](docs/evaluation-protocol-v1.md)
- [Branches, worktrees and artifact policy](docs/git-workflow.md)

`paperqa-baseline-v1` identifies this comparator, including its measured local
tool transport and runtime configuration. It is not an unmodified upstream clone
or a reproduction of the published PaperQA2 benchmark. No claim verifier, answer
rewrite or loop intervention is included in the tagged baseline tree.

## Setup and checks

Use Python 3.12 and run from this repository root:

```sh
uv sync --frozen
uv run --frozen python -X utf8 -m pytest -q
uv run --frozen ruff check .
uv run --frozen python scripts/verify_baseline.py
```

Source documents and run archives are deliberately outside Git. Restore the
exact corpus using its manifest, or copy the already verified corpus into the
new worktree; do not regenerate the dev/holdout selection:

```sh
uv run --frozen pqa-reflect prepare-corpus --config configs/uia-qwen38-dev-s42.json
uv run --frozen pqa-reflect doctor --config configs/uia-qwen38-dev-s42.json
```

The selected profiles require the local Ollama endpoint `127.0.0.1:11436` and the
exact model digests in the frozen manifest. The existing UiA runtime/model store
lives outside this repository under `/home/coder/advanced-ict-project/.runtime`.
Starting that runtime is a separate operation; the older smoke startup helpers
default to port 11435 and are not the selected server profile. No models or paid
API calls are needed for the offline tests above.

A full dev run is explicit and uses GPU time:

```sh
uv run --frozen pqa-reflect run --config configs/uia-qwen38-dev-s42.json --limit 8
```

Use the s43 profile for the paired repeat. Never time two experiments concurrently
on the same GPU. Preserve failed attempts as well as successful runs.

## Earlier engineering work

The laptop profiles, smoke fixtures and reports are retained for provenance;
they do not replace the selected UiA comparator. See
[laptop comparison](results/reports/2026-10-01-local-model-comparison.md),
[local reference setup](docs/strong-baseline.md) and
[debugging walkthrough](docs/debug-walkthrough.md).
Only `data/corpus/<set>` is indexed. Questions, keys, reports and the parent
workspace wiki must never enter the retrieval corpus.
