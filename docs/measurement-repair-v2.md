# Bounded extraction repair v2

Predeclared before inference, 3 October 2026. User authorized the repair and asked
to avoid indefinite polishing. One prompt change and one comparative run; no
model changes, search, answer generation, judge feedback to the agent, or holdout.

Change: meaning takes priority over forced atomic splitting. Preserve exhaustive
composition and qualified relationships together; split independent facts only.
Use the explicit `--extraction-version v2` option for subsequent bounded-revision
runs. V1 remains available and is the legacy default for reproducibility.

Audit v2 distinguishes entailment from coverage: a weaker entailed statement is
faithful; missing details are checked over the complete set. Ambiguous wording
stays unclear. No automated relabeling of original judgments. A fresh blind,
shuffled audit uses the same v2 rubric on both old and new extractions.

Fixed workload:

1. Sixteen authored controls: original twelve plus four balanced checks of weaker
   statements, joint coverage, inclusion and exclusivity. Expected labels stay outside
   requests. All sixteen must match before interpreting the comparative audit.
2. Local v2 extraction: twelve regression texts, two new logical texts, six saved
   project answers. Same frozen Qwen model/settings and six unchanged answers.
3. Audit all eighteen old extractions plus all twenty technically completed new
   extractions. Record technical failures instead of retrying or omitting them.
4. Check that the known composition defect disappears in synthetic-01 and real
   dev-02 B2, and that no clear new meaning change or material omission appears in
   the six real answers and two new texts. Review ambiguous flags transparently.

Stop after this pass. If the targeted defect is removed and the real-answer check
has no material blocker, use v2 as a working measurement with documented limits
and resume the main development experiment. Do not require universal perfect
extraction. If significant problems persist, use original-answer/source assessment
as the primary next experiment measure and keep claim scores exploratory; do not
start an open-ended extraction optimization project. Citation scope and answer-to-
question completeness are separate concerns, not proved by this extraction audit.

API is an external evaluator only. Existing gpt-6.1-sol/medium profile, shared USD 5
pilot and USD 100 project ledger, output 4096. Source packets contain only authored
logical examples and model answers about public scientific facts, with no personal
data, credentials or user documents. API raw data/ledger remain laptop-only.

This practical boundary is our project decision. Clear criteria and task-specific
tests are consistent with [official evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
Our authored labels are not independent expert scientific annotations.

## Recorded calibration limitation before the comparative audit

Calibration `20261003T170321Z-83dc40` matched 15/16 exact labels and 16/16 coverage
decisions. Control-02 was `unclear` rather than expected `distorted`: the judge
considered a non-exhaustive reading of `consists of a battery`. It still rejected
faithful acceptance and detected missing information. The original exact-match
gate is **failed**, not silently relaxed or reported as passed.

Under the user's explicit request to avoid polishing, do not tune again. Complete
the planned comparison once as **diagnostic model judgments**, with direct review
of the saved real-answer/extraction pairs. The binary faithful/not-faithful decisions
match 16/16 controls (a post-hoc diagnostic, not the predeclared gate). Do not infer
validated error rates or general accuracy. If the practical targeted repair works,
use it provisionally and return to the main experiment; preserve the ambiguous
judgment as a limitation. This deviation was recorded before observing comparison
verdicts and does not alter any original expected label or verdict.
