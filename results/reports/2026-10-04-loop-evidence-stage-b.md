# Controller visibility N1/N3: completed development comparison

4 October 2026. All 32 fixed attempts completed without technical failure. N3 used
19 evidence-gathering calls versus 25 for N1, but it did not establish a dependable
quality-preserving improvement: N1 answered 16/16 correctly; N3 answered 15/16 and
abstained once. The independent mirrored judge returned **N1: 2, N3: 3, order_unstable: 1, tie: 10**.
Keep the frozen N1 baseline and record N3 as an efficiency/quality trade-off.
This closes the bounded N1/N3 development experiment, not final held-out evaluation.

## Fixed design and provenance

[Preregistered Stage B protocol](../../docs/loop-evidence-stage-b-v1.md): eight
development questions, two seeds 42/43, two arms, 32 fresh attempts. Question order
was fixed; arm order alternated and reversed for seed 43. Stage A was not pooled.
All runs used clean commit `3b72d87d9084733a5dcd0c5150985195f3535de8`, the same frozen
corpus and Qwen3.8 27B Q4_K_M/BGE-M3 on UiA V100 32 GiB / Ollama 0.35.0. Only
`agent_evidence_n` differed. Answer cap 5, prompts, tools, sampling and timeouts
were unchanged; citation treatments and holdout were not used. No retries.

Actual config/model/package/input/source hashes matched for 32 runs. The audit
verified 145 intermediate state hashes, 384 source-snapshot files and 44 gather
observations. All 32 statuses are `success`, but that label is technical: the
COSA-1 N3 seed 42 final selection is `ABSTAIN` and is scored incorrect. Earlier
progress wording describing an erroneous option is superseded by this distinction.

## Aggregate results

Each arm has 16 attempts on the same eight questions. Times include model loading
and switching; indexing is separate. Counts are actual calls, including calls
sharing a controller batch. Both answer correctness and quality matter.

| Measure | N1 | N3 |
|---|---:|---:|
| Technically successful attempts |16/16|16/16|
| Correct completed answers |16/16|15/16|
| Final abstentions |0|1|
| Gather calls | 25 | 19 |
| Search calls | 27 | 24 |
| Answer generations | 16 | 18 |
| Controller turns | 73 | 72 |
| Question seconds | 6,117.601 | 5,209.942 |
| Indexing seconds | 1,301.830 | 1,282.049 |
| Chat calls | 589 | 470 |
| Chat input tokens | 1,277,429 | 1,042,316 |
| Chat output tokens | 40,852 | 43,786 |

Gather calls fell 24%; input tokens fell 18.40%; observed question time fell 14.84%.
Output tokens rose 7.18%, and answer generation increased 16 to 18. These are total
observations, not guaranteed speedups or evidence that every repeat is wasteful.

## All paired outcomes

Entries show N1 / N3. Q1–Q8 follow the frozen dev-file order; full question IDs,
run IDs, source hashes, per-question seed averages and all metrics are in the
[machine-readable report](2026-10-04-loop-evidence-stage-b.json). Q2 is RfaH; Q4 is COSA-1.
Judge outcomes require agreement across both presentation orders; `order_unstable`
is retained, never converted into a win. These are 16 pairs on 8 unique questions.

| Question | Seed | Final option N1 / N3 | Gathers N1 / N3 | Question seconds N1 / N3 | Mirrored judge |
|---|---:|---|---|---|---|
| Q1 | 42 | D / D | 2 / 1 | 656.2 / 222.2 | N3 |
| Q2 | 42 | B / B | 1 / 1 | 282.9 / 234.8 | tie |
| Q3 | 42 | D / D | 1 / 1 | 243.8 / 235.1 | N3 |
| Q4 | 42 | B / ABSTAIN | 4 / 2 | 952.6 / 652.2 | N1 |
| Q5 | 42 | A / A | 1 / 1 | 227.5 / 232.7 | tie |
| Q6 | 42 | C / C | 1 / 1 | 250.5 / 243.1 | tie |
| Q7 | 42 | A / A | 1 / 1 | 232.0 / 231.6 | N1 |
| Q8 | 42 | D / D | 1 / 1 | 224.6 / 223.2 | tie |
| Q1 | 43 | D / D | 1 / 1 | 237.8 / 250.1 | N3 |
| Q2 | 43 | B / B | 2 / 1 | 449.2 / 303.0 | tie |
| Q3 | 43 | D / D | 1 / 1 | 251.9 / 260.3 | tie |
| Q4 | 43 | B / B | 2 / 3 | 561.3 / 1045.5 | tie |
| Q5 | 43 | A / A | 1 / 1 | 235.4 / 238.5 | tie |
| Q6 | 43 | C / C | 1 / 1 | 251.7 / 249.0 | tie |
| Q7 | 43 | A / A | 1 / 1 | 249.9 / 333.6 | tie |
| Q8 | 43 | D / D | 4 / 1 | 810.3 / 255.1 | order_unstable |

## Uncertainty and runtime limitations

The preregistered bootstrap resampled eight question clusters, retaining both
seed pairs, 10000 times with seed 20261004. Differences are N3 minus N1 per attempt.
These exploratory intervals on selected dev questions do not establish general
efficacy or source-fidelity equivalence. The time interval includes zero.

| Metric | Mean paired difference | Exploratory 95% cluster interval |
|---|---:|---|
| gather_calls | -0.375 | [-0.750, -0.062] |
| question_seconds | -56.729 | [-144.569, 19.969] |
| chat_input_tokens | -14694.562 | [-31121.558, -2622.562] |
| chat_output_tokens | 183.375 | [-532.319, 1246.266] |

Five of 16 pairs already differ in first gather arguments/evidence before changed
visibility takes effect. Even matching context sets need not preserve array/tie
order. These fresh trajectories are not identical-state counterfactuals. Random
tool IDs and uncontrolled filesystem/model-loading conditions remain limitations.
The first job has GPU-discovery/startup warnings; none of the failed-discovery
messages establishes a failed inference. All 2031 requests succeeded, all 1059 chat
completions ended `stop`; maximum prompt 6663 and completion 2033 tokens. No context
truncation/OOM was found. Seven telemetry polling errors are monitoring gaps,
not inference failures. Models were fully resident in all recorded loaded-model
samples. The series ran 13:09:08–17:07:31UTC; raw telemetry/logs are preserved.

## What COSA-1 demonstrates

Assistant source/trajectory diagnosis, separate from blinded external judging:
the decisive source distinguishes cumulative deletions through 30 and through 40.
N3 seed 42 retrieved the original passage, but its summaries omitted that contrast.
Both relevant summaries entered the answer's top 5, yet the answer abstained.
This failure does **not** reproduce Stage A's rank 6 exclusion and does not prove
that showing three summaries caused the information loss.

N3 seed 43 first generated two abstentions from byte-identical answer contexts.
The intervening search added no new summaries. A later gather recovered the
decisive contrast in an already retrieved chunk; its summary ranked 4, reached
the generator and produced B. This was useful refinement, costing 208.055s.
N1 recovered the distinction and answered B in both seeds. Six actual upstream
serializer replays reproduced the stored contexts. Correct B answers can still
overstate which deletions were directly tested, so letters alone remain insufficient.

## External evaluation and decision

The frozen v2.1 evaluator from citation commit 201b3fb received each pair's exact
answers and the union of their full original cited passages, with no answer key,
arm labels or earlier diagnoses. Citations resolved without conflicts. Both
presentation orders used identical sources. It completed 32 planned requests;
32 passed strict structured-verdict and quotation checks.
Outcome counts: **N1: 2, N3: 3, order_unstable: 1, tie: 10**. This is a stronger-model proxy, not expert truth.
Position disagreements and issues observed in both mirrors are not independent
samples. Raw judge responses, key and budget ledger remain laptop-only.

Model `gpt-6.1-sol`, fixed medium reasoning / 4096 output cap. Full token-count
preflight reserved at most USD2.040182 within remaining group USD2.066048.
Conservatively accounted cost was USD0.863252; cumulative
ledger USD3.797204/321 calls. Pricing and token-count behavior were
rechecked against [official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [token-count documentation](https://developers.openai.com/api/docs/guides/token-counting).

Do not adopt N3 as an unconditional improvement or sweep more N values until a
positive result appears. Preserve this mixed result and the N1 comparator. The
next separately proposed experiment concerns preserving useful evidence in the
answer input; Stage A's selection loss and Stage B's summarization loss must be
distinguished. No new evidence-selection mechanism or combined treatment was run.

## Artifacts

- Local/server generation group: `20261004T130908Z-af58f8`; 2259 transferred files,
  archive SHA256 `6dc8cbde079b4a9441251d7a83546979a4091893eb2dff12728fa4af6e0746b5`.
- Laptop judge plan: `20261004T201206Z-87cdb8`, 32 requests; recipe/packet hashes and
  mirrored outcomes in the JSON. Raw source text and API outputs are not in Git.
- Pre-inference 68 tests/Ruff passed on both hosts; post-run validation checked
  artifact hashes, actual settings, observation reconstruction, source routing,
  request limits and mirrored evaluation. No new model run was used for repairs.
- [Exact analysis/preparation supplements](../../docs/repro/loop-stage-b-v1/README.md)
  preserve helper source hashes. Baseline tag and citation experiment stay unchanged.
