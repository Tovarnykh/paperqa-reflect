# Git organization checkpoint — 4 October 2026

The user approved organizing the accumulated work before developing the loop
mechanism. The previous HEAD was 2b398e0 (19 September); all new commits were made
on 4 October with dependency-ordered, reviewable groups. No history was backdated.

`paperqa-baseline-v1` points to **17e0994**, also `codex/local-baseline` and the
initial `exp/loop`. `exp/citation` adds local verifier, external judge, bounded
revision/measurement, B0/B1/B2 comparison, and B3 ablation in separate commits.
The sibling `research/paperqa-loop` is an ordinary Git worktree: the desktop app
could not create a managed worktree because the enclosing course workspace is
not itself a Git repository. No extra chat was created. Combined integration is
deferred; no empty `exp/combined` branch pretends that it is implemented.

## Verification

- Clean staged baseline: 54 tests passed; Ruff passed. All 12 measured source/
  environment hashes and both seed-config hashes match the frozen manifest.
- Each intermediate citation commit passed its staged-only test suite and Ruff
  using imports from that clean tree, not untracked modules in the active checkout.
- Final clean citation tree: 149 passed, 7 explicitly skipped archive checks.
  Skips require saved baseline/comparison, original-passage or laptop API archives.
  The mock verifier transport test now uses synthetic data and still runs without
  those archives. No production runtime or research prompt was changed.
- The new loop worktree has its own frozen uv environment, a byte-verified copy
  of the corpus, and a successful offline plan. It passes 54 tests and Ruff.
- Staged files were checked for credential patterns; `.env`, ledgers, raw API
  output, weights and corpus files remain excluded. The API template has no key.

## Preservation and cross-host state

Pre-change bundles, binary diffs, file inventories, original README and ZIPs of
accessible dirty/untracked project files are retained under
`.cache/git-reorg/2026-10-04` on each host. The sandbox-owned laptop
`pytest-of-Eier` temporary directory was not readable by the host backup process;
it remains untouched on disk and is now ignored. No research files were deleted.

The server pre-change backup contains 267 dirty/untracked files; the laptop
backup contains 268. The only common file differences were CRLF versus LF in
two historical gpt-oss native configs, with identical parsed JSON settings.
Their original bytes remain in the respective backups and run archives.
`.gitattributes` now preserves exact bytes across platforms.

Raw artifacts remain outside Git; curated results, protocols, configs and code
are committed. The shared parent wiki and SERVER.md are outside this repository
and record subsequent transfer verification. GitHub publication was not performed.
See [working rules](../../docs/git-workflow.md).
