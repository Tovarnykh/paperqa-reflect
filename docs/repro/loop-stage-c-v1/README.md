# Stage C exact analysis supplements

These are exact standalone helper snapshots from the parent workspace `.tmp`.
Copy them byte-for-byte into that directory before execution; they locate the
workspace from their own path. Use sibling `research/paperqa-loop` and
`research/paperqa-reflect`, with the original raw archives and frozen evaluator.
The agent imports none of these helpers. Hashes are in helper-sha256.json.

- analyze-loop-stage-c.py: offline original/recovery audit, 48 scheduled attempts,
  47 recorded outcomes, one interrupted attempt, matched metrics and explicitly
  restricted complete-question bootstrap for the N8/N1 missing cells.
- prepare-loop-stage-c-judge.py: frozen citation .venv; pass the imported Stage C
  group. Offline audit by default; --output NEW_PATH writes the exact-answer/full-
  cited-passage packets, anonymous requests and source audit, without API access.
- allocate-loop-stage-c-judge.py: offline one-use documented budget allocation.
  Its paths identify the measured packet. Changes only budget_group, rebuilds
  the execution plan, and verifies all 60 paid request bodies and mirrored rows
  remain identical. Full recipe hashes differ because config includes the group.
- run-loop-stage-c-judge.py: takes allocation.json. Authenticated exact token-count
  preflight by default; --run executes generation only after maximum reservation
  for the entire packet fits both remaining caps. Uses the original cumulative
  laptop ledger and the unchanged pairwise evaluator. No automatic retries.
- run-loop-stage-b-judge.py: exact earlier support dependency for cost guard and
  token-count cache; do not invoke its main function for this series.

The original frozen plan was not paid. Only execution plan 20261005T103734Z-00aaee
was launched, on 5 October 2026. Do not launch either plan again or regenerate an
equivalent plan to bypass one-use guards. External evaluation is nondeterministic;
any repeat would be a new experiment. Raw requests/responses, credentials and the
budget ledger remain private on the original laptop, outside Git and server sync.

The historical price recheck is not a future price guarantee. The unchanged
evaluator also enforces its pricing validity period and single execution host.
