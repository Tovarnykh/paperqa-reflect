# Bounded revision: engineering pilot v1

Recorded 2026-10-03 before inference. Follows external-judge pilot A and
[evaluation protocol v2](evaluation-judge-protocol-v2.md).

Two deliberately selected **known dev failures**, one per question: source-count
attribution (seed 42) and a numerical chromosome comparison (seed 43). This is an
integration test, not a representative estimate of improvement. The eight reserved
questions remain untouched. Baseline answers are reused byte-for-byte.

- B0: saved PaperQA answer.
- B1: one ordinary whole-answer review, then one revision.
- B2: atomic claim extraction, local citation checks, then one revision.

B1/B2 have the same pool of originally cited full passages and the same revision
prompt/model. No new retrieval, no answer keys, no external-judge feedback. This
pool is narrower than all retrieved contexts. B1 is not a compute-matched control.
Use Qwen3.8:27b at the frozen digest, Ollama 0.35.0, seed 42, temperature zero,
thinking off. Extraction uses 32768 context / 4096 output; review and revision
65536 / 4096. Verifier retains its frozen 32768 / 1024 profile. These are new
postprocessing contexts, not changes to the 16384-context baseline.

Deterministic sentence units retain exact answer offsets. Each sentence must be
represented in the model extraction (empty claims only for nonfactual filler); quotes must match the original sentence.
These checks do not prove atomicity, semantic faithfulness or exhaustive coverage.
The final option marker is scored separately. Claims inherit only explicit citations
on their own sentence; no paragraph-level inheritance. Uncited claims are recorded
as no_citation, not sent to a model, and stay in the later metric denominator.
This conservative policy can reward citation placement and must be disclosed.

Log every request/response, model identity, tokens, duration and runtime truncation
audit. No automatic inference retries. Technical corrections require a separate
versioned run, preserving prior attempts. Failed extraction/review/verification stops the pilot;
a failed revision retains B0 and records a fallback. Preserve all failed runs.
Judge all later variants using the same extraction procedure and external rubric,
including answer correctness and completeness, before claiming a quality gain.

Commands (repo root, local server):

```sh
python -m paperqa_reflect.revision prepare
python -m paperqa_reflect.revision run
```

Generated inputs and responses live outside the corpus and are ignored by Git.
The external API key, its cost ledger and API responses remain on the laptop.

Engineering v1b: the first attempt was deliberately interrupted after finding that
list numbering could become a separate unit. The splitter now preserves numbered
items and the extractor allows zero claims for nonfactual headings/filler. This is
a technical correction, not tuning to external labels. Preserve v1 outputs.

## External diagnostic evaluation

After the local run completes, `paperqa_reflect.revision_report export` exports
every extracted cited claim from all three variants using one procedure. Uncited
claims remain explicitly in `mapping.json` and in metric denominators, with no
empty-source API request. The existing judge anonymizes system/source IDs and
shuffles all cases together. It never receives original answers, variant names,
local feedback or answer keys. No local feedback prompt is changed using its results.

`configs/judge-openai-revision-dev-v1.json` retains the model, rubric and medium
reasoning profile of pilot A, with an output cap of 4096 for **all** B variants.
The previous 26-case run used 8192 and actually generated 3909 output tokens in
total. The smaller new cap bounds maximum reserved cost; a capped/incomplete
response is not_checked. Both runs share the same USD 5 group and USD 100 project
ledger on the laptop. Original pilot requests/results are immutable.

`revision_report report` verifies input hashes, joins external verdicts back to
variants, and reads source answer keys only for post-hoc option scoring. It reports
unchecked/uncited claims, lower/upper support bounds and key match. Empty claim
sets score zero, not perfect fidelity. This diagnostic does not score completeness;
whole-answer comparison and an independent cohort remain necessary before a quality
or mechanism-superiority claim. No statistical significance is inferred from two
deliberately selected dev failures.

## Observed outcome and measurement repairs

See [first-run report](../results/reports/2026-10-03-bounded-revision-pilot.md). All four revisions completed. The inline enumeration boundary fix affected five citation bindings in one B1 answer. A failed model re-extraction is archived; the accepted repair rebinds unchanged claims by exact containing answer spans, with no model call. Existing judgments are reused only for exact claim/evidence/profile matches. An additional five judgments cover the new bindings. Full-answer texts are immutable.

The resulting claim metrics are diagnostic only: decomposition distorted two exhaustive-composition assertions. Exact substring checks cannot establish faithfulness. Do not freeze a larger quality comparison until this extraction layer and citation/completeness rubric are qualified.
