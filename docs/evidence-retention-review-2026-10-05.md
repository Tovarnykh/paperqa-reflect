# Evidence retention after the controller-visibility experiments

5 October 2026. Status: completed offline diagnosis and primary-source review;
the answer-context experiment below is a proposal, not an implemented treatment.
No local model generation or paid API calls were made for this investigation.

## Finding

The next useful question is whether direct access to original evidence improves
answer fidelity. Increasing controller visibility did not establish an improvement
in [Stage C](../results/reports/2026-10-05-loop-evidence-stage-c.md). However, the
saved traces show several different failure mechanisms. They must not all be
described as retrieval failure or RCS omission:

1. A decisive fact can be omitted or distorted by RCS.
2. A useful summary can be excluded by the answer's independent top-five cap.
3. A faithful summary can reach generation, but the answer strengthens its claim.
4. The answer can attach a claim to the wrong source despite having supporting
   evidence elsewhere in its context.

Literal source spans target the first mechanism most directly. They cannot
guarantee that generation or citation assignment will be correct.

## Offline replay and limits

Input: the preserved Stage C archives and completed 60-assessment evaluation,
as recorded at repository commit `f72025f3443393b31d6bc2674422aad34ec362b4`.
The [exact audit helper](repro/evidence-retention-v1/audit-evidence-paths.py)
replays the pinned PaperQA context serializer without inference. Its
[public output](../results/reports/2026-10-05-evidence-routing-audit.json)
contains source identifiers and hashes, not passages or API responses.

- All 47 answer-generation contexts in 46 successful runs were reproduced
  byte-for-byte, with saved state hashes checked. The final answer context and
  raw answer were also matched to each final generation state.
- Seven final answer contexts contain repeated original chunks among the selected
  records. Thirteen exclude at least one available context record. These are
  structural counts, not counts of harmful duplicates or lost decisive facts.
- The judge produced 93 issue records: 42 citation and 51 factual. All 93 cited
  source IDs belong to the assessed run, occur in its selected answer context,
  and have an exact matching quoted passage in that run's original text.
- These records are duplicated by mirrored orders and by N8 appearing in two
  contrasts. They are **not 93 independent errors**, nor an error-rate estimate.
  They also cover only the judge's cited-source issues; they do not rule out
  omissions elsewhere. Eight dev questions remain eight unique questions.

Original passages were inspected in saved step states; response exports can
omit the original `text.text`. Finding a source ID in the answer context proves
routing, not that the summary retained the relevant statement.

## Reviewed examples

These are assistant diagnoses from source/summary/answer inspection, informed by
the existing external judgments. They are not new independent expert annotations.

| Saved case | What happened | Likely location of error |
|---|---|---|
| RfaH, seed43 N8, `20261005T001554Z-cf62f5`, `pqac-489d13a0` | The original describes a bridge involving the alpha3* helix and NGN core; the RCS summary changes the linked component to the KOW domain, and the answer repeats it. | Distortion already present in RCS; the selected source was available. |
| Isotype question, seed43 N3, `20261004T235836Z-e56376`, `pqac-d08b2add` | A list of observed types becomes an assertion that all other types were not produced. The summary introduces the exclusion and the answer treats it as explicit source evidence. | Unsupported inference in RCS, propagated into the answer. |
| COSA-1, seed43 N3, `20261005T004723Z-68b592`, `pqac-cf5cd9f4` | Original and RCS distinguish a strong decrease from abolition. The answer upgrades the decrease to abolition and overstates the inferred interface. | Generation, despite a faithful selected summary. |
| Numerical answer, seed42 N1, `20261004T231039Z-dd8913`, `pqac-ab166aa7` | The cited summary explicitly lacks the requested total. Two other selected summaries contain it, but the numerical claim cites the wrong record. | Citation assignment, not lack of retrieved support. |

Historical diagnostics are complementary, not pooled observations:

- [Stage A](../results/reports/2026-10-04-loop-evidence-pilot.md): a useful new
  COSA-1 summary ranked sixth and did not enter the answer context. Previously
  replayed serialization showed the answer context stayed unchanged. Including
  that record has not been shown to repair the answer.
- [Stage B](../results/reports/2026-10-04-loop-evidence-stage-b.md): two selected
  summaries omitted a decisive comparison from the original passage. A different
  saved trajectory recovered it through another gather. Repetition can therefore
  be useful; banning repeated gathers is not justified by these observations.

Naive deduplication is not the first treatment: summaries of one chunk can retain
different useful details. Removing one can reduce evidence coverage.

## Relevant research and implementations

Primary sources checked on 5 October 2026; external models were not downloaded,
executed or benchmarked on our corpus. Published gains are not our results.

| Work | Mechanism and relevance | Practical boundary for this project |
|---|---|---|
| [Provence, ICLR 2025](https://arxiv.org/abs/2501.16214), [implementation](https://github.com/naver/bergen/tree/main/scripts/provence) | Query-conditioned sentence selection combined with reranking; retains selected sentences instead of generating a new prose summary. A direct candidate for reducing paraphrase-induced distortion. | The original checkpoint has a 512-token window. Its near-zero incremental cost claim assumes an existing reranker; our pipeline would incur an added model pass. |
| [XProvence, ECIR 2026](https://arxiv.org/abs/2601.18886), [v2 checkpoint](https://huggingface.co/naver/xprovence-reranker-bgem3-v2) | A later extractive pruning model, 568M parameters, 8192-token window, initialized from `bge-reranker-v2-m3`. It is a different model from our BGE-M3 embedder. | The card says training used paragraph-sized examples. Our scientific passages and V100 runtime remain unqualified. Initially preserve order with `reorder=False`; do not combine pruning with reranking. |
| [RECOMP](https://arxiv.org/abs/2310.04408), [code](https://github.com/carriex/recomp) | Explicitly compares extractive sentence selection with abstractive compression, trained for downstream use. It can omit unhelpful retrieved material entirely. | Supports the proposed comparison of evidence representations. Training a new compressor is unnecessary at this stage; compression quality is not automatically citation faithfulness. |
| [LongRefiner, ACL 2025](https://arxiv.org/abs/2505.10413), [code](https://github.com/ignorejjj/LongRefiner) | Query analysis, hierarchical document structure and coarse/fine context selection. Its structured treatment of long documents may help retain related pieces of evidence. | The repository uses several specialized adapters and a reranker. The paper limits its evidence largely to general/Wikipedia domains. A full integration would introduce too many changes now. |
| [LlamaIndex sentence-window pattern](https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/node_postprocessors/) | Retrieve a small unit, then restore nearby original text before generation. Neighbours can preserve pronoun referents and qualifications. | Useful engineering pattern, not proof of improved PaperQA quality. It can be implemented without migrating frameworks. |
| [JevDeepResearch](https://github.com/sunyasheng/JevDeepResearch) | The README describes model-based region selection followed by code returning original passages with document IDs and line ranges. Selection and text copying are separate responsibilities. | Its 20-question, single-attempt pilot changes depth and concurrency together, with no same-depth no-Jev control. Reuse the provenance principle; it does not establish a need for Jev in our local agent. |
| [The Attribution–Compression Frontier, September 2026](https://arxiv.org/abs/2609.14245) | Directly examines the difference between support measured against compressed text and against original source spans. | A narrow study: one generator and a primary NLI model reused in parts of recovery/evaluation, without human calibration. Motivation for checking originals, not a transferable numerical guarantee. |

Implementation detail from the [XProvence source](https://huggingface.co/naver/xprovence-reranker-bgem3-v2/blob/main/modeling_xprovence_hf.py):
its output is assembled by decoding selected token IDs and does not expose original
character offsets. An adapter should retain original sentence boundaries/offsets
and copy from the source, rather than assume the returned string is byte-exact.
Exact copying establishes provenance, not entailment or completeness.

## What our pinned PaperQA already provides

Inspected upstream commit `57e89f7223b0960d5ee5ea048c69e3c47e088572` in the
installed dependency; site-packages were not changed:

- `paperqa/settings.py`: the normal serializer sorts by score/name, takes up to
  `answer_max_sources=5`, applies its score cutoff, and renders `Context.context`
  (the summary) with source IDs. A custom serializer hook exists.
- `paperqa/docs.py` and `paperqa/core.py`: `evidence_skip_summary` already allows
  source-text contexts. With summary generation bypassed, this path assigns the
  default score 5. Thus a global switch also changes ranking and what the
  controller sees. It does not isolate the answer's representation of evidence.

Turning off summarization is an existing-settings ablation, not a new algorithm.
The initial proposal below instead holds the upstream saved state fixed.

## Proposed bounded next investigation

**Question:** With identical selected sources, does original wording improve
answer fidelity compared with RCS summaries, at an acceptable context/time cost?

1. Freeze a diagnostic panel from all 14 successful **N1** final answer states
   in Stage C. Preserve the two technical missing cells in reporting; do not
   substitute N3/N8 or choose only favourable/error cases. This remains previously
   inspected dev material, not independent validation.
2. Perform an offline prompt/token preflight. Compare the existing selected
   records as RCS summaries with their full original chunks, using identical
   source IDs/order and generation conditions. Preserve repeated records for
   this first comparison. Do not silently truncate oversized contexts; document
   feasibility and freeze any size-handling rule before generation.
3. If feasible, generate both a fresh RCS control and original-text treatment
   from those fixed states. The old sampled answer alone is not a matched fresh
   control. Keep the generator, seeds, prompts, corpus, retrieval, scores and
   controller policy fixed. No B3 rewrite is added.
4. Judge answers against the original cited passages with the frozen external
   evaluator and mirrored order, retaining ambiguity. Measure answer correctness,
   claim qualification/citation fidelity, omissions, tokens and observed answer
   generation time. More source tokens are a treatment cost; improvement would
   not isolate wording from context length. A later token-matched control is
   needed for that narrower causal claim.
5. Only if the diagnosis warrants a compressed local candidate, test one fixed
   extractive selector (XProvence is the strongest practical lead from this
   review), with deterministic original-span recovery and contextual neighbours.
   No threshold search or simultaneous reranking/deduplication/rewrite changes.

The external judge's error quotes and answer keys must never select the evidence
for a treatment. Sentence selection can use only the actual question and original
retrieved passages. Copies and offsets must remain auditable; negations, hedging,
comparisons and units require particular attention during diagnosis.

Stop this line if a bounded comparison gives no useful signal. Full source text
may still be ignored or misinterpreted. A working extractive candidate would then
need fresh end-to-end comparison before claims about loop behaviour or total
latency; fixed-state answer replay cannot establish those effects.

## Scope and separation

This is now an **answer-evidence construction** hypothesis, not an established
improvement to the controller's choice of actions. The N experiment remains a
separate completed result. Any future treatment should be isolated from the
frozen baseline and citation B3, with its own recorded configuration/branch; this
report in `exp/loop` records the diagnosis that motivated it, not merged code.
Holdout stays reserved until configurations are fixed. No new treatment, model
installation, server job or API assessment was launched by this investigation.
