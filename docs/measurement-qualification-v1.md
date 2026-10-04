# Measurement qualification v1

Predeclared 2026-10-03, before new inference. User authorized checking measurement.
This qualifies extraction fidelity, not citation truth, agent effectiveness or a
new PaperQA baseline. All original runs remain immutable; no holdout use.

## Procedure

1. Freeze 12 simple authored text/extraction controls covering complete faithful
   paraphrase, distortion and omitted information. They are logical unit controls,
   not independent expert scientific annotations. Expected decisions are stored
   separately and never passed to a model.
2. A separate OpenAI request judges each extraction against its original text:
   each claim is faithful / distorted / unclear; coverage is complete / incomplete /
   unclear. One neutral ID per item, shuffled order, no source role or expected labels.
   The judge must account for every claim and quote exact original spans for
   distortion/omission. Schema/quote validation alone does not prove meaning.
3. Gate: all 12 controls checked, expected per-claim classifications and coverage
   match. Failure/uncertainty blocks treating the judge as qualified; retain and
   analyze outputs. Passing is only engineering calibration, not universal accuracy.
4. The unchanged current Qwen extractor runs on 12 new synthetic source texts
   with composition, quantities, comparisons, conditionality, negation, uncertainty,
   attribution, disjunction, timing and lists. Freeze the original prompt/schema and
   model identity. Stop neither early for favorable results nor retry for better ones.
   Per-case technical failures are recorded; continue remaining cases.
5. Once the external judge passes controls, audit all technically completed synthetic
   outputs and the six saved B0/B1/B2 answer extractions from the prior pilot.
   Judge input contains original text and extracted claims; no papers, answer keys,
   baseline/verifier names or previous quality verdicts. Source truth is not asked.
6. Report technical completion, faithful/distorted/unclear claim counts, complete
   coverage by input, exact failing examples and cost. Qualification requires no
   detected distortion or omission in this small check; any unclear case stays open.
   Do not repair old labels, rank methods or spend the reserved evaluation questions.

Local inference: frozen Qwen3.8 27B / Ollama 0.35.0; existing extraction prompt,
seed 42, temperature 0, thinking off, context 32768 / output 4096. External audit:
existing gpt-6.1-sol / medium profile and shared USD 5 pilot, USD 100 project ledger;
output cap 4096. Credentials/API responses/ledger remain laptop-only.

The audit separates fidelity (no unsupported change/addition) from coverage (no
source content lost). Harmless rephrasing and equivalent splitting may be faithful.
Component lists must not become exclusive compositions; constraints, negation,
conditions and uncertainty remain attached to their claims. Empty extraction from
factual source is incomplete, never a perfect result. One judge is fallible; this
test does not replace broader evaluation, citation scope or whole-answer quality.

API format follows [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs):
strict JSON schema plus separate validation of semantic identifiers and evidence.
