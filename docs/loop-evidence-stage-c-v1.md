# Controller visibility: Stage C observed-saturation comparison

Frozen before inference, following the user's explicit request to launch N8 after
the proposed N1/N3/N8 comparison. Stage A and Stage B remain completed historical
experiments; their outcomes are not substituted into or pooled with this series.

## Question and intervention

Does showing up to eight existing RCS summaries to the controller reduce evidence
gathering while preserving source-grounded answer quality, compared with N1 and N3?
The intervention is only `agent_evidence_n`. The controller still uses the same
upstream current-gather-question filter and descending relevance-score order.
Retrieval, RCS, prompts, tools, model sampling and answer selection are unchanged.
`answer_max_sources=5` is a separate setting and remains fixed. No citation B3,
verifier, adaptive selection, diversity rule or evidence-preservation fix is added.

N8 is the smallest cap covering all eligible pools observed in Stage B, not a
claim of optimality or a literal show-all policy for future trajectories. The
offline pools contained at most eight summaries. Caps3/5/6/8 would expose
116/152/160/164 summary presentations in those saved states, not independent
facts or predicted new trajectories. Two N1 gathers share a batch-end snapshot;
the observed maximum of eight also occurs in a single-gather batch. Pool length,
not the previous outcome key or judge score, motivates this endpoint. A negative
N8 result cannot rule out a beneficial intermediate setting.

## Fixed schedule and runtime

Run 48 fresh attempts: all eight frozen dev questions, seeds42/43 and N1/N3/N8.
Questions retain their frozen JSONL order within each seed. The order within
each question/seed block is fixed before inference:

| Question position | seed42 | seed43 |
|---|---|---|
|1|1,3,8|8,3,1|
|2|3,8,1|1,8,3|
|3|8,1,3|3,1,8|
|4|1,8,3|3,8,1|
|5|8,3,1|1,3,8|
|6|3,1,8|8,1,3|
|7|1,3,8|8,1,3|
|8|3,8,1|1,8,3|

Each of the six permutations occurs two or three times. Each arm appears in each
position five or six times overall. Balance is not exact within each seed: N3
occupies the third position four times in seed43. This reduces systematic overall
order imbalance; filesystem cache and random tool IDs remain uncontrolled. A
repeated seed is not identical-state replay.

Use the same UiA V10032GiB, Ollama0.35.0, frozen Qwen3.8 27B Q4_K_M/BGE-M3 digests,
16384 context/4096 output limits, pinned PaperQA/packages and frozen dev inputs.
Inference is sequential; unload resident models before each attempt and build a
fresh index. Report indexing separately. Share `.cache/loop-pilot.lock` with the
older drivers so they cannot overlap. The baseline tag remains immutable.

`python -X utf8 scripts/run_loop_stage_c.py` prepares a validated dry plan from a
clean commit. `--run` performs this schedule once. The saved plan freezes source,
configurations, models, packages, input hashes, runtime and the external evaluator.
Keep the loop Git HEAD and tracked tree unchanged throughout the running series.

All attempts retain the existing 4500-second wall bound and unchanged agent1800s/
question2400s limits. Preserve wrong answers, abstentions and structured model
failures. Stop on structural/infrastructure failures for inspection; no automatic
retries, resume, replacement seeds or outcome-driven additional runs. Do not
restart a completed series to seek a better result. The reserved split is unused.

## Context qualification

Before launching, inspect saved controller requests and the cumulative added
observation text for N8, using local artifacts only. Preserve that audit and its
method with the launch record. Word counts alone do not establish token fit.
An offline reconstruction of Stage B histories cannot guarantee the length of
new N8 trajectories. Keep existing context/time limits; retain and report any
truncation or overflow rather than silently increasing limits or retrying.

The completed local audit reconstructed44 saved gather observations. Request
logs contain token counts but omit messages/role labels; no exact Qwen tokenizer
was cached. A deliberately pessimistic screening proxy adds the cumulative
JSON-escaped UTF-8 bytes of added observation text to each run's maximum observed
question-chat prompt count, then reserves all4096 output tokens. This is not an
exact token count. All16 N3 histories fit this proxy (worst14919/16384);15/16 N1
histories fit, while the longest shared-batch N1 reconstruction reaches20523.
Thus the audit cannot certify fit for every reconstructed history, and it does
not establish actual overflow. The largest measured old prompt is6663 tokens.
Proceed as an exploratory run with unchanged limits; inspect actual runtime
truncation and preserve any failures. Scratch audit code/output are retained
in the parent workspace and their hashes are recorded in the launch readout.

## Outcomes and analysis

Primary comparisons are N8 versus N1 and N8 versus N3. Report answer correctness,
abstentions, source-grounded answer quality and gather calls together; a reduction
in calls with worsened quality is a trade-off, not an established improvement.
Also report search/answer calls, controller turns, new original chunks and summary
texts, question/index time, and chat input/output tokens. Repeated gathering can
recover useful facts from an already retrieved chunk and is not automatically
waste. Mixed tool batches do not establish separate tool durations.

Show all16 three-arm blocks and question-level averages across seeds. For each
primary contrast, use the Stage B descriptive method and an exploratory bootstrap
over eight question clusters, retaining both seed blocks (10000 resamples,
analysis seed20261004). Report both contrasts, all failures and missing measures;
do not select only the favorable comparison. Eight selected dev questions are not
16 independent questions and do not establish equivalence or generalization.
Historical Stage B comparisons may be described separately as repeatability
context, not merged as extra independent evidence.

Record observed eligible pool sizes, actual summaries shown and any pools above
eight. A positive result does not make eight optimal; a negative result does not
exclude a useful intermediate N. Select a future working treatment using answer
quality first and efficiency second. Any final improvement claim needs separately
frozen held-out evaluation, not tuning on that split.

## Independent evaluation after local runs

Reuse the unchanged mirrored pairwise evaluator/rubric v2.1 at citation commit
201b3fb, with exact hashes in [the existing evaluator freeze](loop-stage-b-evaluator-freeze.json).
The evaluator remains separate from the agent and its version is included in
the plan before inference. No API calls are part of the GPU driver.

Plan 32 answer pairs: N8/N1 and N8/N3 for each of16 question/seed blocks, each in
both orders (64 judgments). Use exact raw answers, the question/options and the
union of original passages cited by either answer. Resolve citation IDs, reject
conflicting mappings and record missing evidence explicitly. Exclude gold keys,
arm labels, performance metrics and prior diagnoses from the judge input.
Keep abstentions and mirrored disagreements; the judge is a stronger-model proxy,
not scientific expert ground truth. Do not tune the rubric to these outcomes.

Before paid evaluation, recheck the laptop-only cumulative ledger and reserve
the full packet-dependent maximum under the existing USD100 project ceiling.
Do not silently raise an existing budget group; establish and document any new
series allocation before requests. If the planned evaluation does not fit the
configured limits, preserve outputs and stop the paid phase for resolution.
Credentials, the API ledger and raw API data stay on the laptop.

After the fixed comparison, publish the code and curated results under the user's
existing authorization and retain a positive, negative or inconclusive finding.
Further N tuning, a different evidence mechanism and combined citation/loop work
require a separate explicit protocol; none is silently added to this series.
