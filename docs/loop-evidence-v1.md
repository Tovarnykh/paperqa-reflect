# Controller evidence visibility: bounded pilot v1

Frozen before inference, 4 October 2026. User authorized beginning the candidate
described in the prior offline loop inspection. This tests an existing PaperQA
setting, not a newly invented controller or a demonstrated improvement.

## Hypothesis and one intervention

H1: showing the controller up to three already available, relevant RCS summaries
after gather_evidence, rather than one, may reduce collection caused by incomplete
observations while preserving useful follow-up questions and answer quality.
H0: there is no dependable benefit, or the larger observation increases cost or
hurts decisions. Previously RfaH repeated collection in seed42 but not seed43;
visibility has not been established as the cause.

L0 uses agent_evidence_n=1; L1 uses agent_evidence_n=3. The installed upstream tool
filters context records to the current gather question (or question=None), ranks
them by score and displays the top N. It may display fewer than N. These are RCS
summaries, not full passages or necessarily N different papers. Search, RCS,
answer evidence limits (20 candidates / up to5 answer records), prompts, available
tools, model settings and timeouts are identical. Repeated collection remains
allowed. B3 rewrite and all citation interventions are disabled in both arms.

Both arms run from the same exp/loop commit. Omitted setting preserves the tagged
baseline defaults; tests compare complete effective Settings for L0 versus the
original configs. The only L0/L1 settings difference is agent.agent_evidence_n
and the automatically computed settings checksum. The added per-step state
snapshots apply identically to both arms and do not enter any model prompt.
The frozen baseline tag remains unchanged; this instrumented branch deliberately
has different source hashes in reference.py and runner.py. verify_baseline.py is
a checker for the frozen tree and will report those two changes here.

Preflight found legacy Git newline normalization in the dev questions, dev key
and corpus manifest: parsed JSON was identical but archived byte hashes differed.
Before inference, exact archived bytes were restored in both experiment branches;
the historical baseline tag was retained. The runner checks all three input hashes.
This common storage repair is not a data/content change or a treatment difference.

## Stage A: diagnostic paired pilot, four fresh runs

Use the selected UiA V10032 GiB, Ollama0.35.0 on11436, exact Qwen3.8 27B Q4_K_M /
BGE-M3 digests, 16K context,4096 output tokens, seed42 and the frozen dev corpus.
No API judge call, holdout use, parameter search or retry based on a bad answer.

| Order | Case | Arm |
|---|---|---|
| 1 | RfaH, b105af85-833e-48bc-ac78-48f73c9673fd | L0, N=1 |
| 2 | RfaH, same question | L1, N=3 |
| 3 | COSA-1, 487539f9-2f17-4009-aa4a-c41322445f11 | L1, N=3 |
| 4 | COSA-1, same question | L0, N=1 |

These cases were deliberately selected from prior traces: one potentially wasted
repeat and one useful clarification. They cannot estimate an overall improvement.
Rerun both arms instead of comparing today's timings only to old runs. Keep
separate fresh indices and cold starts; record indexing separately from question
time, as well as wall time, GPU/runtime, model residency, tokens and failures.
No simultaneous inference/download jobs on this GPU. Preserve every attempt.

`python -X utf8 scripts/run_loop_pilot.py` checks the plan without inference.
Pass `--run` to execute the fixed four-job schedule. The script rejects a dirty
Git tree, mismatched model digests/settings, or another active pilot lock. It
records its source hash and each run's provenance. No adaptive retries.

## What to inspect

For each paired question report termination/status, final-option correctness,
controller turns, tool sequence, gather/search/answer counts, question time,
token usage and indexing time. From the per-step state snapshots record which
original chunks and summaries first appear at each gather. A repeated chunk
can still yield a useful new summary; "no new chunks" is not "useless call".
Mixed parallel tool batches are marked because their durations are not separately
attributable to one tool. Source fidelity, qualifications and final-answer
coverage require review; fewer calls or a correct option alone is not success.
Inspect all pilot results, including new errors, not only the motivating RfaH case.

Stage A ends after the four scheduled attempts and their diagnostic report.
Technical failures stay visible; do not repeatedly tune N or wording on these
two questions. The pilot may justify continuing or rejecting the candidate; it
cannot prove either causal generality or preserved answer quality.

## Stage B, planned after the diagnostic readout

If technically valid, freeze the same two settings and compare all eight dev
questions with seeds42/43, with paired/counterbalanced order and uncertainty at
the question level. Do not count16 repetitions as16 independent questions.
Use the fixed mirrored pairwise evaluator from exp/citation commit201b3fb and its
v2.1 rubric, retaining identical sources/inputs between mirrored evaluations and
original passages for both answers. Freeze its actual recipe hash before requests.
Judge evidence must cover the union of sources cited by both arms, not only old B0
sources. Separate source fidelity, omissions, correctness and extra compute.
Only then decide whether the effect deserves a held-out evaluation or a later
L+B3 combination. No promise of a positive result or a full new architecture.
