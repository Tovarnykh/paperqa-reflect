# External judge pilot A completed

On 3 October 2026 the user supplied the local API key. The saved plan
`results/judge/20261003T145512Z-24c127` ran once, on the laptop, with
gpt-6.1-sol / medium. All 26 responses passed the schema, citation quote and
completion checks. No automatic retries or holdout questions were used.

| Group | External checks completed | Agreement with local verifier | External labels |
|---|---:|---:|---|
| Natural, hand-selected dev claims | 20/20 | 20/20 | 15 supported, 2 contradicted, 3 insufficient |
| Synthetic controls | 6/6 | 5/6 | 2 supported, 2 contradicted, 2 insufficient |

Both models flagged the same five natural problems and four control problems.
On `cv-024`, the local verifier called the claim contradicted while the external
judge called it insufficient: the source discusses asparagine catabolism, and
does not establish or explicitly exclude arginine catabolism. This is a subtype
error, retained as observed. No prompt adjustment or rerun concealed it.

This is agreement with one external model on a small development packet, **not
expert gold, final verifier accuracy or a demonstrated improvement to PaperQA**.
The natural claims were manually selected during development from nine saved
answers covering eight questions. A claim can be supported by its source without
being established scientific truth. The initial assistant labels were not sent
to the external model and are not used as the reference in this comparison.

Usage: 68,731 input tokens, 3,909 output tokens; elapsed run 123.01 seconds.
Ledger accounts **USD 0.210922 conservatively**, charging all input at the upper
input/cache-write rate. This is not an exact provider invoice. All 26 ledger
entries are accounted; none remain reserved/unknown. Original pilot cap USD 5,
project cap USD 100. Credentials, raw API responses and ledger stay on the laptop.

Evidence: `run.json`, `input-counts.json`, anonymous request/response/result files,
`comparison/assessment.json`, `comparison/assessment.md`, and
`comparison/annotations.external-judge.jsonl` in that run directory. The executed
judge source is archived there; original local verifier run is
`results/verifier/20261003T134932Z-f2aafd`. Baseline and labels are preserved.

The next step is the [bounded-revision engineering pilot](../../docs/bounded-revision-pilot.md):
two known dev failure answers, B0 original / B1 ordinary revision / B2 verifier
feedback revision. This report does not claim that later experiment is completed.
