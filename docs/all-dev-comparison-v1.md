# Eight-question development comparison (frozen before generation)

2026-10-03. B0: all eight seed-42 saved PaperQA answers from
`20261002T175947Z-2dc0f1`, byte-identical. B1: ordinary whole-answer review plus
one revision. B2: v2 extraction, local claim verification, one revision.
Model/runtime remain the qualified Qwen3.8 27B Q4_K_M / Ollama 0.35.0 on UiA V100.
The same original cited full passages are available to both interventions; no
new retrieval, gold answers, external judgments or repeat correction loops.

All dev questions are included in sorted ID order, alternating B1/B2 execution
order (four each). A technical failure retains B0 for that arm and is reported;
it does not prevent the other arm or later questions. No retries or answer
selection. Record every request, prompt, usage, load time, failure and source.
Extraction repair is closed provisionally; this run measures intervention value.

Primary assessment: blinded full-answer pairs B0/B1, B0/B2, B1/B2, independently
in both presentation orders, using the existing external OpenAI evaluation profile
and cumulative ledger. Judge source fidelity, citation attribution and substantive
coverage, not verbosity. Allow clear paragraph citation scope and supported repeated
conclusions. Quotes must match answer/source strings. Stable method wins/ties are
reported separately from order disagreement and unclear judgments. All 48 calls
are planned in advance; no majority-vote reruns. Expected model latency is descriptive,
including loading overhead, not a matched equal-compute comparison.

Before paid dev assessment, eight calls on four authored control pairs (both
orders) must all pass: number error, wrong attribution, missing requested fact,
equivalent concise/verbose answers. Control failure blocks primary scoring;
do not quietly relax the gate. This checks basic rubric behavior, not clinical or
scientific ground truth. Same-model-family external judging remains fallible.

Secondary: final option against dev gold only AFTER generation; baseline is
already 8/8 so correctness has a ceiling. Added requests/time and technical failures
remain outcomes. B2's per-sentence citation rule may overflag implied citations;
the independent whole-answer rubric does not assume those flags are errors.
No post-revision claim extraction is required for the primary measure.

These are eight previously seen development questions, with no independence claim
from the prior two-question engineering pilot, no held-out result, no significance
claim and no new model-selection study. Eight reserved questions remain untouched.
API is evaluation only and runs on the laptop; key/ledger/raw API outputs stay there.
Existing cumulative USD5 pilot / USD100 project caps apply. Stop if the plan does
not fit the cap. Report actual spend and failures, including unusable judgments.

## Recorded format correction before any paid dev assessment

Control plan `20261003T174955Z-d1846d`: 8 calls, 7 accepted; one rejected
coverage verdict correctly preferred the complete answer but invented an answer
quotation for absent content. Original strict gate failed and remains failed.
One versioned format repair is permitted before proceeding: require an empty
answer_quote for coverage omissions structurally in the JSON schema. Exact source
quotes and exact answer quotes for factual/citation issues remain required. Rubric,
control facts and expected winners stay unchanged. Run all eight controls again
once under v2; no further repair cycle in this stage. The local comparison runs
independently. Primary paid dev scoring remains blocked until the new gate passes.

Further diagnosis: v1 mistakenly reused a nonempty-string schema for answer_quote,
despite permitting empty omission quotes in the prompt. This is a harness defect,
not evidence that the evaluator cannot identify missing information. The first v2
plan `20261003T175406Z-df96b5` was rejected at free token preflight (HTTP400,
incompatible empty enum/minLength); zero paid requests. Final schema v2.1 replaces
that field entirely and leaves all other quote fields nonempty. Preserve both plans.
The single new paid calibration has not yet run at this recorded correction.

Final control plan `20261003T175619Z-cd8813`: 8/8 accepted, all four expected
outcomes reproduced in both orders (three substantive preferences and one tie).
The gate passed before primary dev evaluation. Format is frozen as
`source-grounded-answer-pairs-v2.1`; no further judge tuning in this stage.
The two paid calibrations cost USD0.039518 /16 calls; project ledger then
USD1.241156 /193 calls. The rejected preflight had zero paid calls. This is basic
engineering qualification, not a measured accuracy rate on scientific judgments.

## Main run and payload audit

Local run `20261003T174838Z-e451ff` completed all eight questions in2050.016 s.
B1 revised8/8 (16 calls); B2 revised7/8 and retained B0 once (82 calls).
Two claim-check failures in dev-04: one output-limit termination and one nonexact
evidence quote. No retries. All24 final options match dev keys; this does not establish
answer fidelity. All489 transferred local run/job files were hash-verified.

Automatic approval review initially rejected the proposed48 OpenAI requests because
it classified the source passages as private. Before retrying, an offline payload
audit proved all20 unique passages match eight public Europe PMC OA texts with
verified corpus hashes, and all eight questions match the public LitQA dev file.
The payload contains only anonymous IDs, public questions/options, these passages
and locally generated answers. Wiki, gold labels, personal identity and local paths
are excluded. Audit: `results/reports/2026-10-03-dev-api-payload-audit.json`.
After presenting this new evidence and the user's existing API-evaluation authorization,
automatic review approved the same purpose/destination. Frozen main plan:
`20261003T182504Z-125db8`, SHA256
`249ed4a5366c1f4838e306dc35d6392e198beae6caf68550e8e9a8572e520a88`.
