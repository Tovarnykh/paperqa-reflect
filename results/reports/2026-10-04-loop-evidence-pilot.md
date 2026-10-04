# One versus three controller summaries: diagnostic pilot

4 October 2026. Four scheduled attempts finished; none was replaced or retried.
N=3 used one fewer evidence-gathering call on each selected question. It answered
both correctly; N=1 answered RfaH correctly but ended COSA-1 with `ABSTAIN` and
status `unsure`. This is a promising diagnostic observation, not an established
causal improvement: both pairs diverged before the first changed observation.

The most concrete additional finding is that a useful new summary can reach the
controller yet be excluded from the answer generator's five-record context.
That exclusion was reproduced offline with the pinned upstream serializer.

## Fixed comparison

[Protocol frozen before inference](../../docs/loop-evidence-v1.md). Runs used clean
commit `c717ddd64c832195e5f422c71057ba049e083f01`, seed42, the frozen local corpus,
Qwen3.8 27B Q4_K_M / BGE-M3, PaperQA2026.8.12 and Ollama0.35.0 on the UiA V10032GiB.
Model digests, source files, packages and corpus/input hashes matched across runs.
Effective settings matched after accounting for run-directory paths, the computed
checksum and `agent_evidence_n`. The actual observations were checked against the
stored summaries and upstream filtering/ranking: they displayed one or three.

Only controller visibility changed. Retrieval/RCS, answer cap5, prompts, model
sampling and timeouts stayed fixed; citation/verifier treatments were absent.
Order was RfaH N1→N3, then COSA-1 N3→N1. Each job had a fresh index and unloaded
models at start; filesystem cache state was not controlled. No paid API judge,
holdout, additional seed, adaptive retry or stage-B comparison was run.

## Outcomes and cost

Times are seconds. Question time includes model loading/switching but excludes
the separately measured index. Counts refer to actual tools, not papers.

| Case | N | Result | Controller turns | Search / gather / answer | Question | Index | Chat calls | Chat input / output tokens |
|---|---:|---|---:|---|---:|---:|---:|---:|
| RfaH | 1 | B, correct; success | 6 | 1 / 2 / 2 | 589.014 | 93.378 | 48 | 108583 / 3348 |
| RfaH | 3 | B, correct; success | 4 | 1 / 1 / 1 | 294.492 | 77.969 | 25 | 56055 / 2514 |
| COSA-1 | 3 | B, correct; success | 5 | 3 / 2 / 1 | 492.975 | 99.609 | 46 | 103598 / 4597 |
| COSA-1 | 1 | ABSTAIN; unsure | 7 | 3 / 3 / 2 | 882.116 | 84.313 | 69 | 173191 / 9628 |

All trajectories called `complete` once. COSA-1 includes parallel tool batches;
their duration cannot be counted separately for each contained tool. The last
CLI returned1 because the answer was `unsure`, not because of a transport crash.
All312 recorded local requests completed successfully, including188 chat calls.
Token totals are sums over a trajectory, not a single context-window size.

Do not interpret the time ratios as isolated speedups. For example, the first
RfaH chat request took150.505s in N1 and22.642s in N3, despite identical token
counts1125/95 and matching first search arguments. Startup/cache variation is
material. A startup GPU-discovery warning was preserved; subsequent logs showed
full GPU offload. No context truncation, out-of-memory failure or length-limited
chat completion was found. Maxima across chat requests were5764 input and2688
output tokens; all chat finish reasons were `stop`.

## What happened in RfaH

N1's first visible summary emphasized35.8% without the domain distinction. Another
stored summary already gave43.6% for full length and35.8% for KOW. The first answer
therefore already selected B correctly. The repeat added two original chunks and
five new summaries, then produced another B answer. Unlike the older inspected
baseline trace, this repeat did find new chunks; it cannot be described simply
as retrieving the same three passages again.

The longer second answer propagated a source-fidelity error already in RCS: it
described the disulfide bridge as joining KOW to NGN, whereas the original chunk2
describes an alpha3* helix tethered to the NGN core. N3 showed the full-length
percentage in its third summary, answered once and stopped. Its final text avoided
that particular location claim, but described35.8% vaguely rather than explicitly
identifying the KOW-domain comparison. Correct options do not settle answer quality.

## What happened in COSA-1

N3's first gather already contained the relevant original chunk4, but its summary
focused on point mutations and omitted the decisive truncation comparison. A
more specific second gather generated a useful new summary of the same original
chunk: deletion through30 retained interaction, through40 reduced it markedly,
and through53 made it undetectable. The final answer selected B and preserved
the distinction between reduced and undetectable interaction. This is a useful
repeat, not evidence that repeated gathering should be prohibited.

One qualification remains: the answer described separate internal intervals as
directly tested, while the source describes cumulative N-terminal truncations.
Inferring the most likely option is different from claiming each offered internal
deletion was experimentally tested. These observations are assistant trace/source
review, not blinded expert or external-judge ratings.

N1 gathered twice before answering. Its first answer was long and speculative,
then abstained. The controller made a third gather with the offered intervals
explicitly named. This produced a summary containing the decisive30/40 distinction
and showed it to the controller. Nevertheless, the next answer still abstained.

### Verified loss between evidence collection and answer generation

The third-gather summary `pqac-ecfc1320` had score9 and global rank6. The upstream
answer serializer sorts all stored records by descending score, then chunk name,
and takes five. Two earlier summaries of chunk4 scored10, another old record
scored10, and two chunk1 summaries scored9 and preceded chunk4 in the tie-break.
The useful new summary was thus outside the selected five records.

Saved answer-context strings before and after that gather are byte-identical
(SHA256 `ea09112b86e8d3b0c0239f2351c545910f9185e19556114e772cf30ef3fca7ef`).
Replaying `Settings.context_serializer` on the final stored contexts reproduced
the exact string and exclusion without any model calls. `Docs.aquery` does rebuild
the context; the repeated string follows from selection, not an assumed stale cache.
See pinned `paperqa/settings.py:1214–1224` and `paperqa/docs.py:643–647`.

This establishes that the new evidence was omitted from that answer's input.
It does not establish that including it would necessarily fix the answer; that
would be a separate intervention. Duplicate records, relevance-score calibration
and preservation of useful refinements are concrete candidates for later work.

## Interpretation and next boundary

Both pairs had matching initial search arguments but different first gather
questions **before** N1/N3 visibility took effect. RfaH initially gathered3 versus6
records; COSA-1 gathered5 versus4. Consequently these are fresh paired trajectories,
not identical-state counterfactuals. A fixed model seed does not freeze the whole
serialized interaction; the existing transport also creates random tool IDs.
Their presence is a variability factor, not a proven sole cause of divergence.

Keep N3 as a provisional candidate. Two selected questions and one seed cannot
establish general efficiency, source-fidelity equivalence or a reliable accuracy
gain. The new N1 abstention also shows why the historical8/8 dev runs must not be
treated as guaranteed repeatability. Preserve it rather than rerunning until success.

Stage A is closed. Stage B in the protocol (all8 dev questions, seeds42/43, same
independent evaluator and union of both answers' sources) remains planned and
unrun. An identical-state diagnostic could isolate the visibility effect; the
answer-context exclusion suggests a separate focused mechanism. Neither has been
implemented here, and neither should be mixed silently with N3 or citation B3.

## Artifacts and checks

- [Machine-readable metrics, provenance hashes and routing finding](2026-10-04-loop-evidence-pilot.json).
- Pilot `20261004T114111Z-aeb0a1`; all four run IDs are in the JSON.
- Full run states, sources, requests, telemetry and logs remain outside Git on
  both hosts. Export:289 files, archive SHA256
  `5f1deb7ceb8908d6fbbb4f0d4691ab16fbf1a80e2947de11f7d0892f3622b75c`.
- Pre-inference implementation checks:62 offline tests and Ruff on both hosts.
  Post-run checks: transfer hashes, immutable step hashes, actual setting/input/
  model parity, shown-summary reconstruction and offline upstream serializer replay.
- Frozen baseline tag remains unchanged; results belong to independent `exp/loop`.
  Source papers, credentials and raw API archives are excluded from publication.
