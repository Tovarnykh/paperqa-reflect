# Rewrite-only ablation v1 — frozen before generation

## Question and boundary

Does removing the ordinary review call retain the improvements from B1's single
source-grounded rewrite? This closes the current dev investigation of citation
support; a positive verifier result is not required. No further prompt tuning is
planned. At most one repeat may be justified by an unresolved stability problem.
Holdout remains reserved for final project evaluation. These bounds are a working
proposal, not a lecturer requirement.

## Intervention

- B0/B1/B2 are reused unchanged from `20261003T174838Z-e451ff`.
- B3 uses every one of the same eight seed42 original answers and cited full
  passages. One local rewrite, no generated review, extraction or verifier.
- Use the frozen B1 revision implementation/prompt/schema, Qwen3.8 27B digest,
  Ollama version, seed42, temperature0, context65536 and output4096.
- Set `review` to `{"issues": []}`; keep every other request field unchanged.
  This controls for the existing rewrite instruction (including its reference to
  review), rather than introducing a new prompt simultaneously.
- Prior B1 review was already empty in seven questions. Their requests therefore
  repeat the prior rewrite exactly. Record request and answer equality explicitly.
  Only one question supplies a nonempty-feedback contrast; neither equality nor
  eight development outcomes establishes general equivalence of review methods.
- Run all eight in saved order; no retries or selection based on outputs. Keep
  failures with the original answer as fallback. No new retrieval or gold input.

## Evaluation

All B0/B3, B1/B3 and B2/B3 pairs in both presentation orders: 48 new calls through
the unchanged external pairwise v2.1 recipe. Keep the existing 8/8 format-control
gate (`20261003T175619Z-cd8813`), model/config and cumulative USD5 pilot/USD100
project ledger. Do not resend old B0/B1/B2 pairs or tune the judge. Audit the exact
new payload against the public corpus before API transmission. Judge input uses
anonymous method labels, public questions/passages and generated answers only.

Report substantive source fidelity, citation attribution, required coverage,
correct final options, failures, model calls and runtime. Preserve order
disagreements; do not majority-vote them away. Compare local request/output hashes.
Separate warm/cold loading and sequential replay effects from intervention cost.
An external LLM is a fallible measurement tool, not scientific ground truth.

## Next boundary

After this ablation and error analysis, archive a bounded conclusion and move to
agent-loop continuation/stopping decisions. Local role-model choice/efficiency is
the other candidate direction and was partly explored in baseline selection.
Final report scope follows completed evidence, not a promise of three full studies.
