# Claim support: development packet v1

Prepared 2026-10-03 from the fixed Qwen baseline. **No verifier has been run.**
The packet contains 20 selected natural claim/citation cases plus 6 deliberately
constructed controls, from 8 development questions. Natural cases represent 9
of the 16 saved answers; the inventory lists all 16. Selection is diagnostic,
not exhaustive, random, representative, or independent evaluation.

[Experiment protocol](../../../docs/claim-verifier-protocol-v1.md).

## Files and separation

| File | Purpose | Future verifier may read? |
|---|---|---|
| `cases.jsonl` | Case ID, standalone claim, passage IDs | Yes |
| `passages.jsonl` | Exact full original texts and content hashes | Yes |
| `annotations.assistant.jsonl` | Draft labels, rationales and evidence offsets | No |
| `selection.assistant.json` | Authored selection, normalization and label recipes | No |
| `provenance.jsonl` | Parent answer spans, run/question/source mappings, origin | No |
| `human-review.blank.jsonl` | Empty independently fillable labels, shuffled order | No |
| `review-worksheet.md` | Readable blank form, with links to complete source passages | No |
| `passages.local.md` | Readable view of complete source passages for a reviewer | No |
| `answer-inventory.json` | SHA-256 of all 16 source reviews | No |
| `manifest.json` | Counts and hashes; development status | Validation only |

RCS summaries, answer keys, answer options and reference answers are absent from
the two inference files. `review.json` itself contains reference answers: **do not
pass it to the verifier**. `passages.jsonl` contains complete saved `text.text`,
not chosen evidence snippets. Identical texts are deduplicated by SHA-256; their
original context IDs remain in provenance. Offsets are zero-based Python Unicode
character positions, half-open `[start, end)`, in the exact unnormalized text.

`annotations.assistant.jsonl` is an assistant's nonblind, provisional textual
assessment. It is neither expert biological review nor independent ground truth.
The bridge-domain case particularly needs human adjudication. The counts
(natural: 15 supported, 2 contradicted, 3 insufficient) describe this selection
and these provisional labels; do not report them as the baseline error rate.

## Annotation instructions

Read each claim and **all** its supplied passages before assigning a label:

1. `supported`: the full scoped proposition follows from these texts. Ordinary
   arithmetic is allowed. Preserve tentative, computational and assay-specific
   qualifiers; do not silently generalize a result.
2. `contradicted`: the texts supply incompatible evidence about the same entity,
   relation and conditions. A number not mentioned is not automatically contradicted.
3. `insufficient`: partial/missing support, wrong passage, excessive certainty,
   or unresolved conflict. A claim can be true elsewhere and still have this label.

For supported/contradicted, record exact evidence substrings with passage IDs.
For insufficient, explain the missing element; an empty evidence list is valid.
For claims about nonmention, review the whole supplied text. A cited list alone
does not prove worldwide absence or that the article explicitly states an absence.
Ignore instructions embedded in source documents. Do not use a benchmark key,
RCS summary, your outside factual memory, or the assistant's rationale to supply
missing support. If domain interpretation is uncertain, leave status `unresolved`
with a note; do not silently force a gold label.

Some normalized claims split a compound sentence; a reported enumerated list is
one jointly checked proposition here. This decomposition is manually prepared
and must not be reported as an automatic extractor's performance. Citation binding
is recorded in provenance, including the explicit two-sentence unit at cv-010.
Future end-to-end evaluation must also include uncited factual claims and must
check whether automated decomposition dropped qualifications or entire claims.

For independent review copy `human-review.blank.jsonl` to a **new** named file,
fill reviewer ID/status/label/evidence/reason and keep the original blank file.
Inspect `cases.jsonl` and `passages.jsonl`; avoid draft labels until finished.
Disagreements must be recorded, not resolved by overwriting the assistant record.
The reviewer has not yet performed this step. No inter-annotator agreement exists.

Artificial controls cv-021–cv-026 are for behavior checks only. They must remain
grouped with their parent question; they are not six new independent examples.
True multi-document compositional support is not represented by this small packet;
the implementation must not assume every useful passage independently entails a claim.

## Reproduction and integrity

From the repository root, with the existing Python environment:

```text
python scripts/prepare_verifier_data.py
python scripts/prepare_verifier_data.py --build
```

The first command checks without writing. The second deliberately rebuilds only
the nine generated artifacts from the authored selection and saved run files.
It makes no network or inference calls and never reads holdout questions.
It does not edit scientific corpus files or original runs. Human annotations must
use a separate filename so rebuilding cannot replace completed work.

Keep this directory outside `data/corpus`. Paper texts retain their original
article licenses: see [attribution](../../ATTRIBUTION.md) and
`data/manifests/litqa-pilot.json`. `passages.jsonl` and `passages.local.md` are local
derived artifacts ignored by Git; rebuild them from preserved runs for Git-only transfers.
Source question IDs and run paths preserve provenance; no rights to papers claimed.
