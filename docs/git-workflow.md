# Experiment branches and worktrees

The history was organized on 4 October 2026 from preserved work and run manifests.
These commits were created on that date, not retroactively during the experiments.

| Ref | Purpose |
| --- | --- |
| `paperqa-baseline-v1` | Immutable tag for the measured local PaperQA comparator B0 |
| `exp/citation` | Separate citation verification / answer rewriting and evaluation |
| `exp/loop` | Independent controller-loop research, starting exactly at B0 |
| `exp/combined` | Future integration, created only after individual effects are measured |

The existing `research/paperqa-reflect` checkout is the citation branch. The
sibling `research/paperqa-loop` is the loop worktree on both laptop and UiA.
The old `main` and remote-tracking refs are preserved; local organization does not
publish anything to GitHub. `codex/local-baseline` ends at the baseline checkpoint.

## Work discipline

1. Check `git status --short` and `git branch --show-current` before edits.
2. Commit one meaningful change after its offline checks. Keep implementation,
   experiment protocol/configuration, and measured results distinguishable. Include
   the hypothesis and fixed comparison conditions in the experiment documentation.
3. Make future common runtime or evaluation fixes available identically to both
   directions. Never silently modify the frozen tag; record the changed comparator
   explicitly. Do not cherry-pick citation interventions into the loop branch.
4. Record commit, dirty diff, configuration, dependency/model digests, seed and
   hardware/runtime for each measured run. Do not rely on branch names alone.
5. Compare B0, B0+C, B0+L, and later B0+L+C under the same corpus, questions, models,
   seeds and evaluator. Retrieved evidence may differ because that is part of L.
   In the combined variant, C processes the new output of L, not an old B0 answer.

C is the explicitly selected answer-processing treatment: B3 single rewrite is
the current economical dev candidate; B2 verifier is retained as a negative
finding. Neither is part of B0. A settings ablation is not a new architecture.
Combining mechanisms does not imply that their improvements will add together.

## Data, environments and evaluation

Each worktree has its own `.venv`, `.cache`, configuration and `results/runs`.
Copy the fixed corpus byte-for-byte or restore it with `prepare-corpus`; keep it
unchanged. Share the already installed Ollama runtime/model store, and schedule
GPU measurements sequentially. A worktree per seed/run is unnecessary.

Raw run/API archives, credentials, ledgers, model weights, diagnostics and corpus
documents are ignored and preserved locally. Git contains code, frozen configs,
manifests, protocols and curated reports. A fresh clone can run the offline unit
suite without those archives; explicitly identified archive-integration checks
skip when their local archive is absent. On a populated research checkout they
run normally. Do not interpret skipped archive checks as fresh model validation.

For now the fixed external evaluator lives on the citation branch because it
shares support code with those experiments. It can assess saved outputs from
either branch. Importing that evaluator is not a loop treatment; before L runs,
freeze its exact version, inputs and rubric in the comparison protocol. The loop
worktree itself contains no citation modules and does not need the API key.

The parent project wiki and SERVER.md provide shared context but are outside this
Git repository. Synchronize them explicitly; the Windows and Coder copies do not
synchronize automatically. Never send the laptop's API key, raw API archive or
budget ledger with Git bundles. Retain pre-organization bundles and dirty-file
archives under `.cache/git-reorg/2026-10-04` on the corresponding host.

`.gitattributes` disables implicit newline conversion so that measured byte hashes
survive Windows/Linux checkouts. Avoid wholesale reformatting of frozen files.
Use `python scripts/verify_baseline.py` on a baseline checkout to verify the twelve
measured source/environment files and two selected configurations.
