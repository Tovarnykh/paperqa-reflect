# Controller visibility N1/N3/N8: completed local development comparison

5 October 2026. Local execution finished at **02:30:26 UTC / 04:30:26 Europe/Oslo**.
The 48-job schedule produced 46 technically successful answers, all with the correct
final option, one preserved model-startup failure and one infrastructure-interrupted
attempt. N8 did not reduce evidence-gathering calls relative to N3 and used more
observed time and tokens. **Independent evaluation is complete: N8 shows mixed preferences against both
comparators, with no established quality-preserving improvement. N1 remains the
frozen comparator; N8 is not adopted as an improved default.**

## Fixed design and recovery

[The frozen Stage C protocol](../../docs/loop-evidence-stage-c-v1.md) specifies
eight development questions, seeds 42/43, N1/N3/N8 and 48 fresh counterbalanced
attempts. Stage A/B results are not pooled. Only `agent_evidence_n` changes:
the controller sees up to N existing RCS summaries after each gather. The separate
answer evidence cap remains 5. Retrieval, RCS, answer selection, prompts, tools,
sampling and timeout limits remain fixed. Citation treatments and holdout are unused.

The original segment used clean commit `ad5b60ced2ae4b695c7f7119ddc7e49e5d0b5379`.
Coder autostop interrupted job 10 after jobs 1-9 had recorded outcomes. The
[explicit recovery amendment](../../docs/loop-stage-c-recovery-v1.md), clean commit
`50aee6411c44695ff96cffba50740d3a1cb11b16`, continued only never-started jobs 11-48.
Measured inference-source hashes remained unchanged across the recovery. No retry,
replacement seed, substituted Stage B result or additional N was used. The original
plan/progress and all failed/partial artifacts are preserved.

All runs used the frozen Qwen3.8 27B Q4_K_M/BGE-M3 models, UiA V100 32 GiB,
Ollama 0.35.0 and pinned PaperQA/packages. Context/output limits stayed 16384/4096.
Each job unloaded resident models and built a fresh index. Model loading, switching
and filesystem caches can affect observed times; indexing is reported separately.

## Availability and final options

| Measure | N1 | N3 | N8 |
|---|---:|---:|---:|
| Scheduled attempts |16|16|16|
| Recorded outcomes |15|16|16|
| Technically successful answers |14|16|16|
| Correct options among successful answers |14/14|16/16|16/16|
| Model-startup failure |1|0|0|
| Infrastructure-interrupted attempt |1|0|0|
| Wrong final options among successful answers |0|0|0|
| Final abstentions among successful answers |0|0|0|

Job 1 (N1, Q1, seed 42) failed when Ollama timed out starting its model server,
before any controller action. It retains 311.161 question seconds and 141.199 indexing
seconds, plus its failed chat request. Token usage for that request is unavailable,
not zero. Job 10 (N1, COSA-1, seed 42) was interrupted during a gather and has no
final response or grade. These two cells are technical availability failures, not
wrong answers or model abstentions, and do not establish an N8 correctness gain.

## Primary matched comparisons

N8/N1 uses 14 matched technically successful question/seed pairs. N8/N3 uses all 16.
Failed and interrupted costs are preserved separately, never imputed as zero or
included as apparently efficient trajectories. **No available matched pair crosses
the restart boundary**; recovery and uncontrolled runtime conditions still limit
timing generalization. Totals below therefore use different samples between contrasts.

| Measure | N1 (14 pairs) | N8 (same 14) | N3 (16 pairs) | N8 (same 16) |
|---|---:|---:|---:|---:|
| Gather calls | 17 | 15 | 18 | 18 |
| Search calls | 19 | 18 | 22 | 23 |
| Answer generations | 14 | 15 | 16 | 17 |
| Controller turns | 61 | 58 | 67 | 68 |
| Question seconds | 4,045.764 | 3,883.432 | 4,530.577 | 4,921.348 |
| Indexing seconds | 1,215.321 | 1,085.047 | 1,361.345 | 1,297.322 |
| Chat calls | 415 | 373 | 443 | 445 |
| Chat input tokens | 892,823 | 819,786 | 962,514 | 984,258 |
| Chat output tokens | 25,630 | 29,808 | 32,190 | 38,108 |
| New original chunks | 51 | 49 | 59 | 62 |
| New summary texts | 60 | 54 | 68 | 71 |

Against N1, N8 has 11.76% fewer gathers, 8.18% fewer input tokens and 4.01% lower
observed question time, but 16.30% more output tokens. The gather reduction occurs
only in Q3 seed 42 and Q8 seed 43, one call each. Against N3, gather counts match in
every pair; N8 has 8.63% higher observed question time, 2.26% more input tokens and
18.38% more output tokens. Call reductions are not automatically evidence of less
waste: repeated gathering can recover useful facts from previously retrieved text.

## All sixteen three-arm blocks

Q1-Q8 follow frozen dev-file order; Q2 is RfaH and Q4 is COSA-1. Full IDs, run IDs,
hashes, all metrics and per-question means are in the
[machine-readable report](2026-10-05-loop-evidence-stage-c.json). Entries follow
N1 / N3 / N8. `startup failure` and `interrupted` are deliberately not answer options.

| Question | Seed | Final option or availability N1 / N3 / N8 | Gathers N1 / N3 / N8 | Question seconds N1 / N3 / N8 |
|---|---:|---|---|---|
| Q1 | 42 | startup failure / D / D | n/a / 1 / 1 | n/a / 258.3 / 286.4 |
| Q2 | 42 | B / B / B | 1 / 1 / 1 | 294.9 / 240.6 / 267.3 |
| Q3 | 42 | D / D / D | 2 / 1 / 1 | 441.2 / 234.4 / 231.5 |
| Q4 | 42 | interrupted / B / B | n/a / 2 / 2 | n/a / 527.4 / 751.5 |
| Q5 | 42 | A / A / A | 1 / 1 / 1 | 222.0 / 225.7 / 225.4 |
| Q6 | 42 | C / C / C | 1 / 1 / 1 | 245.2 / 245.8 / 247.4 |
| Q7 | 42 | A / A / A | 1 / 1 / 1 | 229.9 / 226.3 / 244.5 |
| Q8 | 42 | D / D / D | 1 / 1 / 1 | 219.3 / 219.8 / 223.2 |
| Q1 | 43 | D / D / D | 1 / 1 / 1 | 247.1 / 232.1 / 232.5 |
| Q2 | 43 | B / B / B | 1 / 1 / 1 | 234.8 / 343.1 / 287.9 |
| Q3 | 43 | D / D / D | 1 / 1 / 1 | 244.6 / 265.1 / 249.0 |
| Q4 | 43 | B / B / B | 2 / 2 / 2 | 501.9 / 541.3 / 711.8 |
| Q5 | 43 | A / A / A | 1 / 1 / 1 | 234.9 / 228.8 / 224.5 |
| Q6 | 43 | C / C / C | 1 / 1 / 1 | 248.6 / 251.7 / 248.0 |
| Q7 | 43 | A / A / A | 1 / 1 / 1 | 247.2 / 245.9 / 239.9 |
| Q8 | 43 | D / D / D | 2 / 1 / 1 | 434.3 / 244.5 / 250.5 |

## Uncertainty and trajectory differences

Eight selected dev questions are not 16 independent questions. The original Stage C
bootstrap specified eight question clusters retaining both seeds. Missing N1 cells
prevent applying that complete design unchanged. Main N8/N1 descriptives above use
all 14 available pairs; its separately labelled exploratory bootstrap uses only six
complete question clusters/twelve pairs, excluding Q1 and Q4 entirely. This smaller
bootstrap does not represent all 14 pairs or eliminate missingness bias. N8/N3 retains
the full eight-cluster/sixteen-pair design. Both use10,000 resamples, analysis seed
20261004, Python `random.Random` and linearly interpolated percentile intervals.

| Contrast and metric | Cluster mean N8 minus comparator per attempt | Exploratory95% interval | Clusters / pairs |
|---|---:|---|---:|
| n8_vs_n1: Gather calls | -0.167 | [-0.333, 0.000] | 6 / 12 |
| n8_vs_n1: Question seconds | -29.805 | [-66.760, 4.708] | 6 / 12 |
| n8_vs_n1: Chat input tokens | -7563.583 | [-16582.417, 1281.750] | 6 / 12 |
| n8_vs_n1: Chat output tokens | -28.167 | [-327.244, 248.917] | 6 / 12 |
| n8_vs_n3: Gather calls | 0.000 | [0.000, 0.000] | 8 / 16 |
| n8_vs_n3: Question seconds | 24.423 | [-4.989, 75.670] | 8 / 16 |
| n8_vs_n3: Chat input tokens | 1359.000 | [-176.425, 3922.812] | 8 / 16 |
| n8_vs_n3: Chat output tokens | 369.875 | [38.747, 871.812] | 8 / 16 |

The first search action matched in every comparable pair. However, first-gather
arguments and resulting context sets differed before the intervention in 7/14
N8/N1 pairs and 7/16 N8/N3 pairs. This is fresh execution, not identical-state replay.
Repeated seeds, random tool IDs and context ordering do not guarantee identical
trajectories. Intervals are exploratory descriptions, not equivalence tests or
proof of causal speedups. Historical Stage B remains a separate repeatability
observation and does not fill missing Stage C cells.

## Actual visibility and context limits

The audit reconstructed all 53 completed gather observations: 17 for N1, 18 for N3
and 18 for N8. No batch contained multiple gather calls. In N8 the actual shown
counts were 2 (5 calls), 3 (4), 4 (2), 5 (3), 6 (3), 8 (1); every observed N8 pool was at most 8.
N1 and N3 each encountered one eligible pool of 9. Thus 8 covered its own observed
trajectories but is neither a universal show-all rule nor a demonstrated optimum.

Completed-run request logs show maximum prompt 6093 tokens and completion 2120,
all 1303 successful chat responses finishing with `stop`, and no truncated steps.
These are observations from the captured artifacts, not an absolute proof that
context truncation can never occur in the service or in future trajectories.

## Integrity and runtime observations

All 47 recorded outcomes matched schedule/progress; their settings matched after
normalizing arm, seed and run paths. Frozen models, inputs, packages and measured
source snapshots matched. The audit verified 196 state hashes, 564 source files,
53 gather observations and all 47 recorded grades. Interrupted job 10 was checked
separately: one saved state, 12 source files, matching settings/model/config and
35 completed request logs, with an unfinished action and no final response/grade.

682 locally imported pre-recovery files match the continuation manifest hashes.
Three original runtime-cache files were not imported locally; the JSON names them
explicitly rather than claiming they were rechecked. The recovered driver also
recorded that original artifacts remained unchanged. The complete 3357-file
archive was independently hash-verified on import.

Recorded outcomes contain 2720 request logs: 2719 successful and the one known
startup failure. Including interrupted-job telemetry,1795 samples contain three
monitor errors. All 1512 loaded-model observations show full VRAM residency
(Qwen 1123, BGE 389) on the V100 32 GiB. No incomplete controller batches occur among
the completed trajectories; the preserved interruption is reported separately.

## Independent evaluation and current decision

All60 mirrored assessments are complete, covering14 N8/N1 pairs and16 N8/N3
pairs. The frozen v2.1 model, rubric, exact request bodies and arm mapping were
retained. Questions/options, exact final answers and full unioned original cited
passages entered the judge; gold keys, treatment labels and runtime metrics did not.
Missing N1 cells receive no invented preference. The judge is a model proxy, not
scientific expert ground truth, and these eight selected dev questions are not an
independent final evaluation.

| Contrast | N8 preferred in both orders | Comparator preferred in both orders | Tie in both orders | Order disagreement |
|---|---:|---:|---:|---:|
| N8 / N1,14 pairs |2|3|8|1|
| N8 / N3,16 pairs |3|4|9|0|

N8 does not show a clear quality advantage. Against N3 it also leaves gather
counts unchanged and increases observed question time and input/output tokens.
**Keep N1 as the frozen comparator; do not adopt N8 as an established improvement.**
This is a mixed development result, not proof of equivalence or a globally optimal N.
No further N tuning, evidence-selection change, citation combination or holdout run
has been added. Stage A/B remain separate and are not pooled to choose a winner.

### Credit interruption and explicit continuation

The original plan `20261005T103734Z-00aaee` completed53 valid assessments before
item054 returned HTTP429; items055–060 were never submitted. The user reported
exhausted API credits, then explicitly requested the remaining seven after topping
up. Error429 alone does not independently identify the billing reason.

The original failed run, all53 successful results and their raw responses remain
unchanged and hash-verified. A separate manual-continuation-v1 plan repeated only
the unsuccessful item054 and sent the six unstarted requests, in original order.
It finished5October15:18:28UTC with7/7 checked; combining source-verified results
produced60/60 checks and30 complete mirrored pairs. Original API attempts total61:
60 successful assessments plus the preserved429 failure. No successful answer was
rejudged, no model/rubric changed, and the 30-pair sample was not filtered by outcome.

Continuation maximum reservation was USD0.469142; its usage-based accounted cost
was **USD0.206432**. Stage C successful assessments totalUSD1.704848; cumulative
project accounted cost isUSD5.502052. The old429 reservationUSD0.071925 is retained
conservatively in the ledger as held_http429, after backup and documented inspection.
It is not asserted to be an actual charge or silently released. Budget consumption
including that unresolved hold isUSD5.573977. The sameUSD5 series group andUSD100
project cap apply. [Allocation provenance](../../docs/loop-stage-c-evaluation-allocation-v1.md)
and the exact continuation helper are retained; raw API data/key/ledger stay local.

## Reproducibility artifacts

- Group: `20261004T210539Z-3f1ab1`, continuation: `continuation-v1`.
- Local analysis helper: parent workspace `.tmp/analyze-loop-stage-c.py`.
- Helper SHA256: `fc1f128858f285b39c227836e969c597963ccc4dd88d6cd933eacf5124de1282`.
- Stats input SHA256: `ed2a939d6b2150d2ac716bccfc75fbfa51e57d3662be40d143db99b13f2f5ef4`.
- Complete raw archive: `loop-stage-c-completed-v1.zip`.
- Archive SHA256: `3b999f550cfb4521b14a4fca950fdaecd6e9c55778a86033607bfb4066a25340`.
- Exact plans, per-run artifact hashes, restricted bootstrap specification and limits
  are recorded in the machine-readable report. Source passages, raw answers, API
  responses, credentials and the API ledger are not published in this report.
