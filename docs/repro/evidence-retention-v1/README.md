# Offline evidence-routing replay

`audit-evidence-paths.py` is the exact executed snapshot of the parent workspace's
`.tmp/audit-evidence-paths.py`. Copy it byte-for-byte to that path before running
with `research/paperqa-loop/.venv/Scripts/python.exe` (Windows). It locates the
workspace from its path. The agent imports none of this code.

It needs the preserved Stage C run states, report JSON and completed assessment
archives on the original laptop. It reads the pinned PaperQA serializer, verifies
state hashes, replays every saved answer context, and joins the existing judge's
issues to source records. It neither invokes a model nor accesses the network.

Output under `.tmp`:

- `evidence-routing-audit.json`: public routing metadata; a measured copy is in
  `results/reports/2026-10-05-evidence-routing-audit.json` in this repository.
- `evidence-routing-private-traces.json`: original passages, summaries and judge
  issues for local inspection. Keep this outside Git and server transfers.

The script SHA256 is recorded in the public JSON. Reproduction requires the
private archives; a fresh clone without them is not a complete replay environment.
Counts do not provide semantic error rates. Manual interpretations are recorded
separately in `docs/evidence-retention-review-2026-10-05.md`.
