# Stage C external evaluation allocation, 5 October 2026

The fixed Stage C inference series produced 30 usable answer pairs: 14 N8/N1
and 16 N8/N3. The N1 startup failure and infrastructure interruption remain
missing answers; no historical substitutions or retries are used. Each pair is
judged in both orders, giving 60 requests with exact raw answers and full original
passages cited by either answer. No gold keys or treatment labels enter requests.

The original Stage B v2.1 evaluator is unchanged. A new budget group
`loop-stage-c-pairwise-v1` has a USD5 limit within the existing cumulative USD100
project ceiling and the original laptop ledger. The previous pilot group cap and
spend are untouched. This allocation implements the explicit requirement in the
Stage C protocol; it is not a reset of project spending.

Only `budget_group` differs from the frozen config. All 60 request bodies and
mirrored plan rows are identical to the originally frozen plan. Model, prompt,
schema, rubric, reasoning, decoding and pricing fields are unchanged. Because the
full recipe hash includes budget metadata, it changes honestly as follows:

- Original: b45a1fde6d323e000193d2015d45b1ce132a763b5e4fe237dd029d1d774681f9
- Execution: 702b7c386893fcdeb98e4b2607ffec0574da19287e98356a24eb63818d8baf6d

Original unpaid plan: 20261005T103632Z-7e2372.
Sole execution plan: 20261005T103734Z-00aaee.

Exact input-token preflight at 10:39:56UTC reserved a whole-plan maximum of
USD3.886388. Project spending before this run was USD3.797204; remaining project
headroom USD96.202796, new group headroom USD5. A maximum reservation is not actual
cost. Generation started after preflight passed; the curated report tracks actual
completion. The API key, cumulative ledger and raw API data stay on the laptop.

The current model pricing and input-token endpoint were rechecked against the
[official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [token-counting guide](https://developers.openai.com/api/docs/guides/token-counting).

Exclusive execution files, request hashes and ledger reservations prohibit
automatic repeats. The old plan also must remain unexecuted. Helpers and their
hashes are retained in [the reproduction supplement](repro/loop-stage-c-v1/README.md).
