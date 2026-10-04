# Controller visibility: Stage B development comparison

Frozen before inference, 4 October 2026, after the four-attempt diagnostic pilot.
The user authorized the proposed expanded comparison with "Займись этим".
This extends [the original protocol](loop-evidence-v1.md); it does not change H1,
agent models, prompts, sampling, tools, answer selection, or citation treatments.

## Fixed schedule and boundaries

Run 32 fresh attempts: eight frozen dev questions x seeds42/43 x N1/N3. Order
questions as stored in the frozen dev JSONL. Within seed42, even zero-based
question positions run N1 then N3, odd positions N3 then N1. Seed43 reverses
each pair's arm order. Run all seed42 pairs followed by all seed43 pairs.
The Stage A attempts are not substituted into or pooled with this new series.

Use sequential inference on the UiA V10032GiB, Ollama0.35.0, the exact frozen
Qwen/BGE digests and four existing configs. Each attempt unloads resident models
and creates a fresh index. Indexing time remains separate. Filesystem cache and
random tool IDs remain uncontrolled: seed is not identical-state replay.
No concurrent GPU job, adaptive retry, tuning, holdout, B3 rewrite, or new evidence
selection mechanism. A new useful summary falling below answer top5 is a separate
later hypothesis. Do not change that behavior inside this comparison.

`python -X utf8 scripts/run_loop_stage_b.py` emits a validated dry plan.
`--run` executes it once from a clean commit. The plan freezes source/config/input
hashes, packages, runtime and evaluator. All attempts have the same4500s total
wall bound, with existing agent1800s/question2400s bounds unchanged. Structured
wrong answers, unsure/ABSTAIN and model failures remain results. An infrastructure
failure without a valid structured outcome stops the remaining schedule for
inspection, preserving the attempt; it is never silently retried. There is no
automatic resume or alternate-seed substitution.

## Outcomes and uncertainty

Primary practical question: does N3 reduce gathering while retaining answer
quality? Report paired differences in gather count, source-grounded answer quality
and correct completed answers together. Also report search/answer calls, turns,
abstentions/failures, new original chunks versus new summary texts, question time,
index time and chat input/output tokens. A repeated chunk is not a useless call.
Mixed tool batches do not provide individual tool durations.

Show all16 paired results and each question's average across the two seeds.
Summarize differences across eight unique questions; the two seeds are repeated
measurements, not sixteen independent questions. Use descriptive results plus a
question-cluster bootstrap (resample eight questions, retaining both seed pairs;
10000 resamples, analysis seed20261004) for mean paired gather/time/token
differences. With eight selected dev questions, intervals are exploratory and
cannot establish source-fidelity equivalence, causal isolation or generalization.
Report missing metrics and denominators explicitly; never convert failure to
zero cost or exclude a bad result from quality totals. Report timings both with
status and as paired observations, not a guaranteed hardware-independent speedup.

## Independent answer evaluation

Use the unchanged mirrored pairwise evaluator/rubric v2.1 at citation commit
201b3fb. Exact source/config and recipe hashes are frozen in
[the evaluator manifest](loop-stage-b-evaluator-freeze.json) and copied into the
run plan before inference. The evaluator lives in exp/citation; no citation
intervention is imported into the agent. API access/ledger remain laptop-only.

After local attempts finish, build16 packets from each pair's exact raw answers,
with the question, options and union of original passages cited by
either answer. Resolve citations against the respective saved states, reject
conflicting mappings of one citation ID to different original text, and record
unresolved citations rather than silently omitting them. Both mirrored requests
see identical evidence, with answer order swapped and neutral labels. Gold keys,
arm names, performance metrics and prior diagnoses remain outside judge inputs. Keep
ABSTAIN answers in the comparison; classify missing/unusable technical outputs
separately and do not invent a judge preference for them.

Run32 planned judgments (two orders per pair), using the existing budget ledger
and its cumulative limits. Before sending anything, inspect actual remaining
headroom and the packet-dependent conservative estimate. Stop before requests
if the complete evaluation does not fit; never silently raise the budget group.
The judge is a stronger-model proxy, not scientific expert ground truth. Report
mirrored disagreements, source fidelity, critical omissions, question coverage
and option correctness separately. Do not tune the rubric on Stage B outcomes.

After this fixed comparison and report, close the N1/N3 dev experiment with a
positive, negative or inconclusive finding before considering another mechanism.
