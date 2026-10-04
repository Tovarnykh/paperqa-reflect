# Extraction measurement qualification, 3 October 2026

The current extraction procedure **did not pass qualification**. It reproduced a
meaning-changing composition split on a new synthetic example and on the saved
B2 answer. Baseline-versus-verifier ranking remains blocked by measurement quality.
This experiment checked **original answer → extracted claims**, not scientific
truth, source citation support, or completeness of an answer to its question.

## Frozen procedure and completed runs

[Protocol](../../docs/measurement-qualification-v1.md) and
[fixture freeze](../../data/verification/measurement-checks-v1/freeze.json) were saved
before inference. Twelve assistant-authored logical controls had separately stored
expected labels; those labels, method names and scientific answer keys were absent
from API inputs. These are engineering controls, not independent expert annotations.

- External calibration: `results/measurement-judge/20261003T164253Z-914c38`.
  All **12/12** controls checked and matched expected per-claim fidelity and coverage.
- Local unchanged Qwen extraction: `results/measurement/20261003T164401Z-8e8318`.
  **12/12** new synthetic inputs completed, **33** claims, zero technical failures,
  **99.915 seconds** including model loading. No retries or prompt tuning.
- Audit input: `results/measurement/audit-input-v1`. It includes all 12 synthetic
  outputs plus six saved B0/B1/B2 extractions, **125 claims** in total.
- External audit: `results/measurement-judge/20261003T164633Z-d5f3ca`.
  **18/18** checked; no truncations, refusals or missing verdicts. Final assessments
  are in each plan's `assessment/assessment.json`.

Local model/runtime: frozen Qwen3.8 27B Q4_K_M, Ollama 0.35.0, V100 32 GiB,
seed 42, temperature 0, thinking off, context 32768 / output 4096. The prompt,
runtime response, model digest and executable source snapshots are archived.
External evaluator: existing gpt-6.1-sol / medium, strict schema, output cap 4096,
shared budget ledger. It only assessed saved text; its feedback did not guide the
local extractor or any agent revision.

## Raw external judgments — diagnostics, not accuracy

| Inputs | Faithful claims | Flagged distorted | Unclear | Complete coverage | Incomplete coverage |
|---|---:|---:|---:|---:|---:|
| 12 synthetic texts | 30 | 3 | 0 | 11 | 1 |
| Six saved answers | 86 | 6 | 0 | 3 | 3 |
| Total | 116 | 9 | 0 | 14 | 4 |

For the saved answers, dev-01 B0/B1/B2 had 9/6/7 faithful claims and complete
coverage. Dev-02 B0/B1/B2 had respectively 33/19/12 faithful claims plus two
composition flags each, with incomplete coverage. These are **extraction audit
outcomes**, not evidence that one answer-generation method is better.

## Clear defect and rubric-sensitive judgments

The new source was: “The assembly consists of exactly four solar panels and one
battery.” The extractor returned “The assembly consists of exactly four solar
panels.” and “The assembly consists of one battery.” Both independently describe
the whole assembly using only one component group. Their quotes are exact source
substrings, but the claims change the complete composition. This reproduces the
same two `consists of` errors in saved dev-02 B2, claims 002 and 003.

Assistant review agrees with these **four clear composition flags across two
inputs**. This conclusion requires no scientific domain expertise. It is sufficient
to fail the predeclared qualification gate; it does not establish a general error rate.

The remaining **five flags need more precise rubric treatment**:

- Four dev-02 B0/B1 flags use `comprises`. The judge treats the word as describing
  an exhaustive composition. An inclusion reading changes that judgment; these
  should remain explicit interpretation-sensitive flags rather than unquestioned
  ground truth. Raw verdicts have not been relabeled.
- Synthetic-04 says the voltage dropped by 8% during run A only below 5 degrees C.
  Claim 1 reports the 8% drop during A; claim 2 preserves the entire condition.
  The judge flags claim 1 for dropping the condition but marks coverage complete.
  Under an entailment-based definition, the shorter event statement can be a true
  weaker statement; under a requirement that every claim retain all qualifications,
  it fails. The current rubric mixes these notions. Do not count this automatically
  as an invented fact, especially when the complete extraction retains the qualifier.

Passing the 12 calibration examples did not resolve these boundary cases. The
judge returned zero `unclear` labels, but that is not evidence of zero ambiguity.
New balanced controls should distinguish semantic contradiction/addition, faithful
weakening, and missing information before using a single fidelity score.

A useful positive check: dev-02 B0's erroneous comparison between chromosome
lengths was classified as faithfully reproduced from the answer. That is correct
for this task: faithful extraction may preserve an answer's scientific or numerical
error. Scientific truth belongs to the separate citation/source evaluation.

## Decision and next implementation step

Retain the frozen baseline, generation outputs and all original verdicts. Do not
rank B0/B1/B2, start the eight reserved questions, or silently remove flagged claims
from the denominator. No student domain annotation is required.

Next proposed work is a separately versioned extraction v2: preserve exhaustive
composition as a complete proposition, retain conditions/negation/modality and
enough original context, and avoid forced splitting when it changes meaning.
Clarify the audit rubric above before running v2 on the existing regression set
and new balanced examples. Check fidelity and coverage separately. Citation scope
and whole-answer question coverage still require qualification after this repair.
No v2 extractor or repaired quality scores were produced in this run.

## Cost, verification and storage

Calibration: **USD 0.034502**; audit: **USD 0.113133**; this measurement check:
**USD 0.147635 / 30 paid calls**. Persistent project ledger:
**USD 0.943683 / 123 paid calls**, all accounted, no unresolved reservations.
These are conservative usage-based costs, not a provider invoice.

Windows: **139 tests passed** and Ruff clean. UiA: **138 passed, one skipped** and
Ruff clean; the skip checks a historical raw API plan deliberately absent from the
server. Existing citation-judge plan compatibility is covered on Windows.
All 94 transferred local-run/job files match their SHA-256 manifest.

The first request to send the 18-case audit was rejected by automatic approval
review as potentially sensitive. No request ran then. Inspection of the complete
packet confirmed only authored examples and model answers about public scientific
facts, with no personal data or credentials; the checked input schema contains only
text/claims and neutral identifiers. Existing user authorization for API evaluation
was supplied with that evidence. Review then allowed the same audited request.

API credentials, budget ledger, frozen external requests and raw API responses stay
on the laptop. Server receives code, local outputs, aggregate report and wiki context.
This report records assistant interpretation separately from unchanged model verdicts.
