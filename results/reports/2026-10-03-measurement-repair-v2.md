# Bounded measurement repair v2 — 3 October 2026

**Decision: close this repair cycle and use extraction v2 provisionally for the
next development experiment.** One prompt change and one comparative pass removed
the observed composition split. This is preparation of a measurement tool, not a
demonstrated improvement of PaperQA or a separate research contribution.

The user explicitly asked to avoid indefinite polishing. That request is preserved
in the project wiki. Ambiguous judge wording remains a documented limitation;
no second prompt-tuning cycle or repeated attempts were used to get a perfect score.

## What changed

- `revision.extract(..., version="v2")` preserves related composition/conditions,
  splitting only when the meaning survives. Prompt v1 remains immutable/available.
- The bounded-revision CLI supports `--extraction-version v2`; use this explicit
  option in subsequent experiments. The legacy default is still v1 to avoid quietly
  changing historical commands. No baseline or PaperQA dependency change.
- Audit v2 separates entailment from coverage. A weaker but entailed claim is
  faithful; missing details are checked across the whole extraction. Ambiguity is
  retained rather than automatically classified as a factual distortion.
- Old and new extractions were judged blind under the **same** updated rubric.
  All 18 paired source texts are identical; the six model answers were not rewritten.

## One completed local pass

Run `results/measurement/20261003T170428Z-c10eda`: **20/20** technically completed,
zero technical failures, **290.276 seconds** including loading. Inputs: 12 known
logical regressions, two new logical texts and six saved project answers. There
were **99 extracted claims** (26 regression, 7 new logical, 66 real-answer).
Same Qwen3.8 27B/Ollama0.35.0/V100 profile, seed42, temperature0, thinking off,
context32768/output4096. No retries, model selection, new retrieval or holdout use.

The synthetic full composition is now retained verbatim as one assertion. In
dev-02 B2, the claim now says that the assembly consists of **four autosomes and
one X chromosome**, keeping the joint composition. Conditions, negation and
uncertainty were retained in the new texts. Direct assistant review of all six
real-answer/extraction pairs found no new material distortion or omission. That
review is not independent expert scientific annotation.

The erroneous chromosome-length comparison in original B0 is still present in
its extraction: the extractor correctly preserves what the answer said, including
its mistakes. The separate source-support evaluation should detect such errors.

## Evaluator calibration and explicitly recorded limit

Calibration `results/measurement-judge/20261003T170321Z-83dc40` completed 16/16
requests: **15/16 exact expected labels**, **16/16 coverage decisions**. Control-02
was classified `unclear` instead of expected `distorted`; the judge allowed an
alternative reading of “consists of a battery”, but identified the missing cable.
The predeclared exact-match gate **failed**. It is not renamed a perfect pass.

Faithful/not-faithful acceptance agreed on 16/16 controls, but this is explicitly
a **post-hoc diagnostic**, not the original gate. Before the comparative audit,
the deviation was recorded in [the protocol](../../docs/measurement-repair-v2.md):
finish the single planned pass as diagnostic judgments and inspect the real texts,
without another tuning cycle. The working decision below does not imply validated
error rates or universal judge reliability.

## Comparative diagnostic audit

Run `results/measurement-judge/20261003T171115Z-789ac6` evaluated both versions
in one shuffled plan. Metadata identifying the version and expected labels were
not sent. Input consists only of source answer text, neutral IDs and extracted
claims. The external judge did not generate or repair any agent answer.

| Inputs | Claims | Faithful | Distorted | Unclear | Complete coverage | Unclear coverage |
|---|---:|---:|---:|---:|---:|---:|
| V1, 12 regression texts | 33 | 31 | 0 | 2 | 11 | 1 |
| V2, 12 regression texts | 26 | 26 | 0 | 0 | 12 | 0 |
| V2, two new texts | 7 | 7 | 0 | 0 | 2 | 0 |
| V1, six saved answers | 92 | 88 | 0 | 4 | 4 | 2 |
| V2, six saved answers | 66 | 66 | 0 | 0 | 6 | 0 |

All 99 new claims were marked faithful, with complete coverage for all 20 new
inputs. The old extraction had 119 faithful / 6 unclear claims and complete
coverage for 15/18 inputs, unclear for three; no old claim was called distorted
under rubric v2. The previous rubric's nine distortion flags therefore must not
be described as nine independently established errors. The battery example was
previously characterized too categorically; the new judge calls its old wording
ambiguous. Identical `comprises` claim wording also received different fidelity
treatment in old dev-02 B0 versus B1. This reinforces the evaluator limitation.
The practical gain is clearer meaning-preserving extraction, not a validated
reduction in factual errors or proof that the agent improved.

These are judgments of one model, not independent accuracy. More coarse claims
change the denominator: do not interpret the reduction in claim count as increased
truth or compare raw support fractions across extraction versions. Historical
dev-02 B1 also benefits from the previously fixed sentence-boundary parser; its
comparison is not a pure prompt-only ablation. The synthetic regressions and
targeted dev-02 B2 composition repair do not depend on that list-boundary fix.

## Scope and next work

This repair is sufficient to resume development with a **working** extraction
version. It does not establish improved scientific answer quality. Keep old scores
historical, unclear cases visible and the original full answers available for review.
Citation scope and question-level completeness are still separate limitations;
an extracted-claim fraction alone must not decide which agent is better.

Return to the main B0/B1/B2 experiment: saved PaperQA answer, ordinary review and
one revision, local verifier and one revision. Expand across development questions
and assess actual corrections, regressions, source support, answer completeness,
time and calls. The eight reserved questions remain untouched until configurations
are frozen. Do not add another extraction-polishing stage or require student
scientific annotations before this work.

## Cost, checks and provenance

Calibration **USD 0.048365**, comparison **USD 0.209590**; this stage **USD 0.257955 / 54 calls**. Persistent ledger **USD 1.201638 / 177 calls**, all accounted, no pending reservations. Conservative usage-based accounting, not a provider invoice.

Windows **143 tests passed**; UiA **141 passed, 2 skipped**; Ruff clean. Both server
skips inspect laptop-only historical API archives. Frozen inputs/prompts match
their pre-inference hashes; all **170** local-run/job files transferred with verified
hashes. Old answers, extractions, expected labels and verdicts remain intact.

Code, local run, aggregate report and wiki context are available on both hosts.
API key, ledger, external request packets and raw responses remain laptop-only.
Protocol: [measurement-repair-v2](../../docs/measurement-repair-v2.md).
Separating task-specific checks from broad quality claims is consistent with
[official evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices);
the bounded stopping decision is our project choice, not an external standard.
