# Server model selection: source-fidelity review (in progress)

Review by the assistant after inference, with model identities and keys visible.
This is a qualitative diagnostic, not an independent or exhaustive claim-level
annotation. Model inputs, questions, keys and corpus remain unchanged. Examine
answer-bearing claims and cited original passages, then record any uncertain
or unsupported statements separately from MCQ correctness.

## Gemma26 seed42 — 20261002T171555Z-43641a

- `22306bd7`: D, correct completion. Compared all three cited raw passages with
  their RCS summaries and final answer. Isotype list and IgG3 decline at week14
  agree with the source. Answer carefully says IgE is **not listed**, preserving
  the distinction between missing-from-list inference and proof of nonproduction.
  No material unsupported claim found in this answer. This does not remove the
  underlying ambiguity of this negative MCQ.
- `b105af85`: B (43.6%), correct completion and supported answer-bearing
  Ec/VcRfaH claim. The extra assertion that `pqac-5b160b77` "incorrectly
  attributes" the values to EcNusG/EcRfaH is not established by the evidence:
  that RCS faithfully repeats its source paragraph, which explicitly uses the
  same values for that other pair. `pqac-c5ff7b45` directly supports Ec/VcRfaH.
  Both raw passages were checked. Record **one unsupported correction claim in
  the final answer**, not a wrong MCQ option or an RCS hallucination. No attempt
  was made to decide whether the scientific article itself contains a typo.
- `ae02d0e9`: D (second longest), correct completion. Both cited RCS summaries
  retain the correct ranking and values. Final answer nonetheless adds
  "45.89 Mb is incorrect", then gives 45.89 Mb again correctly. The source
  table supports that value. Record **one unsupported correction/internal
  inconsistency** in the final answer; answer-bearing ranking remains correct.
- `487539f9`: abstention after two evidence/answer passes, 559.349 s. Correct
  source was retrieved. RCS emphasized point mutations at aa43–53 but omitted
  the deletion-boundary evidence (1–30 retained interaction; 1–40 impaired it)
  from the relevant source paragraph. The final answer then wrongly treated
  aa43–53 as excluding every offered interval. This is a diagnostic combination
  of lost answer-relevant evidence during compression and an overstrong
  exclusivity inference, not a transport failure. Repeating gather did not
  recover the deletion evidence. The refusal itself is not scored as hallucination.
- `658f7050`: A (300 Å), correct completion. Final answer and cited RCS
  distinguish stalk length (~300 Å) from crown width (~250 Å), agreeing with
  the source's electron-microscopy paragraph. No material error found in the answer-bearing
  dimension claim. The extra remark "other sources" refers to another chunk
  of the same article, so this is not evidence of independent corroboration.
- `7a88e6f7`: C (80), correct completion. Answer retains "putative" and
  attributes the count and >2.0 score to G4 hunter, matching the source. It
  does not claim all80 were experimentally confirmed in living cells. No
  material unsupported answer claim found.
- `77a41274`: A (enlarged granular cells), correct completion. Morphology,
  expanded ER and relocalization to puncta match the source. Proposed misfolding
  mechanism and effect on signaling remain qualified rather than established
  causation. No material unsupported claim found in this answer.
- `983f1ef5`: D (flocculation), correct completion after two gather passes.
  The listed enriched categories and FLO genes match the source. However,
  "specifically excludes enrichment" strengthens an RCS statement of **not
  mentioned** into an unsupported negative conclusion about other options.
  Record **one overstrong exclusion claim**. The odd gene string `YPL06°C-A`
  is already present in the fixed TXT source, so it is not attributed to model
  invention here. Seven correct answers therefore include three answers with
  identified extra unsupported/corrective claims; this is qualitative review,
  not a calibrated citation-accuracy metric.

## Qwen3.8 seed42 — 20261002T175947Z-2dc0f1

- `22306bd7`: D, correct completion. List and IgG3 timing match the source.
  However, the final answer calls an RCS observation of nonmention an explicit
  statement of the article, then concludes IgE is "not produced" without the
  missing-from-list qualification. Record **overstatement of the negative
  inference/source attribution** in one answer. The MCQ key stays unchanged;
  this is the known ambiguity of the first question, not a newly excluded item.
- `b105af85`: B (43.6%), correct completion after two gather passes. Correctly
  distinguishes full protein from35.8% KOW-domain identity and avoids Gemma's
  unsupported correction of the other excerpt. However, extra structural prose
  introduces the longer α3* helix/disulfide bridge as differences of the isolated
  KOW domain. The source explicitly places the C34/C102 bridge at VcRfaH-NGN,
  and separately discusses isolated KOW stability (TXT lines35/407). Flag this
  as **misleading domain attribution in an unnecessary extra explanation**;
  the answer-bearing sequence-identity claim remains supported. The RCS also
  strengthens the source's tentative stability explanation into "leading to".
- `ae02d0e9`: D, correct completion with recovery from an RCS error.
  `pqac-b5ed0dce` mislabeled Chromosome4 (33.59 Mb,2038 genes) as Chromosome1
  and claimed X exceeds every autosome, contradicting its own second-largest
  statement. Its original chunk2 starts explicitly with Chromosome4 and has no
 89.58 value, so this is a verified summarization error, not a faulty table.
  The other RCS (`pqac-0e5014ba`) retained the complete correct table. The final
  answer explicitly resolves the generated-context discrepancy correctly.
  Unlike Gemma's invented correction on this question, this correction has a
  real basis in the RCS output. Final answer-bearing ranking is supported.
- `487539f9`: B, correct completion after two search/gather/answer passes,
  555.259 s. **First draft already chose B**, but via speculative proximity to
  aa43/44 and a long uncertain discussion; it lacked the retained-interaction
  result for Δ1–30. Controller then reformulated gather to explicitly request
  deletion mapping across aa1–10/11–20/21–30/31–40. New RCS `pqac-cba74028`
  preserved the relevant deletion boundaries. Final answer uses the supported
  comparison Δ1–30 versus Δ1–40. The loop improved grounding, not the MCQ
  letter. This is an observed recovery by ordinary PaperQA with this model;
  no new verifier/stopping mechanism was added. The final answer's "does not"
  is less precise than "dramatically decreased", but it states the latter
  explicitly elsewhere and reaches the supported comparative conclusion.
- `658f7050`: A, correct completion. Accurately distinguishes the direct EM
  description of stalk length300 Å/crown width250 Å from the predicted model's
  overall length. Both cited raw paragraphs were checked. Extra discussion of
  axes/crown height is explicitly speculative ("might imply"), not a fact
  established by the paper; it is unnecessary for the MCQ. No material error
  in the answer-bearing dimension claim. Both excerpts are from one article.
- `7a88e6f7`: C (80), correct completion; main count and in-silico qualification
  supported by `pqac-72d451a6`/`pqac-6005b4b4`. However, the last sentence says
  `pqac-ab166aa7` explicitly confirms that number. Its entire raw chunk3 was
  checked: it discusses ligand/gene-expression experiments and does not give
  the count80. Record **a non-entailing citation for a true repeated claim**.
  Another RCS (`pqac-3fc32417`) mistakenly infers a total of4 from a supplement
  description of four displayed regions; the final answer correctly treats
  four as visualized regions rather than replacing the total80. Raw chunk8
  was checked. Identifier validity and claim support are distinct here.
- `77a41274`: A, correct completion. Enlarged granular cells, expanded ER,
  puncta and the72% signaling-population decrease match the source. The answer
  explicitly says direct cell death is not reported, rather than presenting
  measured mortality as evidence. No material issue in the answer-bearing
  phenotype claim; the speculative misfolding explanation remains secondary.
- `983f1ef5`: D, correct completion. Main citation `pqac-5798634e`
  supports the enrichment claim and listed genes. Extra citation `pqac-c0336695`
  supplies qualitative discussion of gene losses, without statistical enrichment
  in its raw chunk7. This is an indirect extra chunk citation, not an invented
  paper or a false answer-bearing claim; the main citation is sufficient.

## gpt-oss20 native seed42 — 20261002T183829Z-c104df

All eight final texts were inspected. The answer-bearing source passages for
the principal failures or inconsistencies below were checked directly. This
remains a bounded diagnostic review, not exhaustive claim annotation.

- `22306bd7`: D, correct. Accurately begins with non-reporting, then strengthens
  it into non-production. Same negative-inference ambiguity as Qwen; not evidence
  of a measured negative result.
- `b105af85`: B, correct. Preserves the full-length/domain distinction. Calls
  the pair "paralogs" while the source describes RfaH orthologs: a minor extra
  terminology error, with the requested percentage correctly supported.
- `ae02d0e9`: D, correct ranking. Incorrectly attaches the full autosomal range
  33.59–89.58 Mb to chromosomes2–4 alone. RCS correctly assigns89.58 to chromosome1;
  the final answer introduces this extra range error.
- `487539f9`: B, correct option but weak reasoning. RCS omits preserved interaction
  after deletion1–30. The final generalization that any deletion within1–40 should
  impair recruitment is unsupported and conflicts with the omitted source result.
  Thus correct option selection is not evidence of faithful reasoning.
- `658f7050`: A, correct. Distinguishes the directly described stalk length from
  the predicted overall structure; additional inference about most of the span
  is unnecessary. No material answer-bearing discrepancy identified.
- `7a88e6f7`: C, correct and explicitly putative; requested count matches source.
- `77a41274`: Final text A is correct and source-supported, but the controller
  calls `complete(has_successful_answer=false)`. Verified in `events.jsonl`
  at132.902 s. Upstream therefore returns `unsure`; the fixed metric correctly
  excludes it from successful answers. This is an agent completion decision,
  not a malformed answer, unavailable source or biological error.
- `983f1ef5`: D, correct. Qualifies alternatives as not reported in context;
  does not claim they were experimentally excluded.

## Gemma E4B seed42 — 20261002T190258Z-d34f30

All eight final texts inspected; two non-correct outcomes checked against raw
source and RCS. Six correct completions, one wrong option, one explicit abstention.

- `b105af85`: Selects35.8% (C) instead of the full-length43.6% (B). Its cited
  discussion paragraph itself uses35.8% without an immediate domain qualifier,
  while the earlier Results paragraph clearly distinguishes both numbers.
  This is failed source disambiguation, not invention of the cited number.
- `487539f9`: ABSTAIN despite RCS preserving both relevant deletion boundaries.
  Unlike Gemma26, evidence survived compression. The answer refuses the requested
  comparative inference because individual internal deletions were not tested.
  This separates overly conservative answer selection from missing evidence.
- The other six answer-bearing conclusions match the fixed source facts.
  Extra citation in the final enrichment answer repeats qualitative discussion
  as corroboration; it is not an independent source or statistical confirmation.

## Interpretation limits

An unsupported extra sentence, a wrong chunk citation for a true claim, a wrong
MCQ option and an agent refusal are distinct outcomes. The diagnostic findings
above must not be collapsed into an uncalibrated "hallucination rate". Several
chunk-level mismatches still cite the correct article and coexist with a valid
main citation. No biomedical expertise or domain-wide scientific conclusion is
claimed by this literature-agent evaluation.

## Completed repeats, reviewed 3 October

### Qwen3.8 seed43 — 20261002T215145Z-f6be20

All eight final answers inspected. All eight choices and success statuses match
the fixed key. Repeated accuracy does not imply fully faithful explanations:

- `22306bd7`: repeats the source-attribution ambiguity: an RCS observation of
  nonmention is presented as an explicit statement in the paper. Negative
  evidence remains limited to what was listed or measured.
- `b105af85`: correct full-length percentage, but RCS `pqac-489d13a0` invents
  a cross-domain tether. The raw source says the helix is tethered to the NGN
  core. Final answer inherits that extra structural error. Speculation about
  different alignment methods is unnecessary; the source distinguishes domains.
- `ae02d0e9`: source table and RCS preserve47.28 and45.89 correctly, but RCS
  wrongly calls47.28 shorter than45.89. Final answer repeats that comparison
  before giving the correct sorted ranking and answer D. This is a verified
  internal inconsistency despite a correct final option.
- `487539f9`: main deletion-boundary inference is supported and retained in RCS.
  Extra phrase "mutations in this region" overlocalizes a point-mutation result
  to31–40; the source's conserved point mutations are43–53. Main MCQ conclusion
  is still supported by the deletion comparison.
- The other four main conclusions match the source facts. The count answer
  distinguishes all computational candidates from studied subsets; the phenotype
  answer states that death is not reported; enrichment answer limits alternatives
  to what the context identifies. These are not exhaustive clause-by-clause audits.

### Gemma26 seed43 — 20261002T225059Z-3d778e

All eight final texts inspected; all eight successful choices are correct. The
earlier full-length/domain and ranking errors are absent in this repeat. The
previously abstained deletion question now retains both relevant boundaries and
answers B. It still describes internal deletions as if each were directly tested,
an overstrong phrasing compared with cumulative N-terminal truncation evidence.
No independent citation-accuracy advantage over Qwen is established by this
nonblind inspection; Gemma remains a close quality alternative, with slower runs.

### gpt-oss20 native seed43 — 20261002T222802Z-c6fde3

Five correct successful answers, one wrong successful answer, two `fail` trajectories
whose final text nonetheless contains the correct option. Both failures lack a
successful `complete` event. Pinned upstream maps rollout exceptions to `FAIL`;
the saved response has no exception detail, so its exact type is unresolved.
One failure coincides with a failed API request for question `7a88e6f7`; the other
does not have a failed request in the ledger. Do not call both HTTP errors or OOM.

The wrong answer `22306bd7` claims absence of a listed antibody isotype. RCS
`pqac-1d74322a` explicitly admits the excerpt lacks the answer, then introduces
an unsupported "known from the published study" assertion; its raw chunk has no
isotype discussion. The answer elevates this into corroboration by multiple
studies, although the contexts are from the same paper. This is a concrete
source-faithfulness failure, beyond the known negative-question ambiguity.

### DeepSeek32 seed42 — 20261002T192224Z-2a879f

One correct success, two wrong successes and five `unsure` outcomes; all eight
questions attempted. All366 logged API requests succeeded. It is not a GPU crash.
The preserved final answers and selected RCS show ungrounded numerical additions,
conflicting generated summaries and refusals despite an answerable fixed corpus.
For example, one chromosome RCS supplies three incorrect lengths absent from
its cited chunk. Another summary supplies an unsupported length from a figure
caption; a second assigns a different estimate to an unrelated retrieved passage.
The final answer treats those generated discrepancies as source disagreement.
This describes the tested old R1-Distill-Qwen32B configuration with unchanged
PaperQA prompts, not the quality of all DeepSeek models.

## Final mechanical citation check

Across64 attempted question executions, every cited `pqac-*` identifier resolved
to a saved context. Three DeepSeek refusals had no cited identifiers. This check
validates identifier resolution only, not entailment, completeness or correctness.
All reviews here are assistant diagnostics after seeing the keys and model names.
