# Dataset attribution

The LitQA2 question/options and gold files are adapted from FutureHouse,
[LAB-Bench](https://huggingface.co/datasets/futurehouse/lab-bench), configuration
LitQA2, revision `5c77cec648430f30611808808861eb86f81d5eaa`.
The upstream dataset is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
These adapted question/gold files remain available under that license.
Changes: availability-based subset selection, development/reserved splits,
deterministic option permutation and A–Z labels, answer-letter keys, source
mapping and extraction diagnostics. Question wording and ideal answers are retained.
Canaries remain in the gold/source metadata outside the searchable paper corpus.

The paper corpus comes from Europe PMC open-access JATS article XML. Individual
article titles, authors, DOI, source URL, license text and source/derived SHA-256
hashes are in `manifests/litqa-pilot.json`. Article licenses are separate from
the question-set license. Source XML, extracted articles, figures and weights
are not included in this repository. No rights to third-party papers are claimed.

This subset is not an official LAB-Bench split or a full benchmark reproduction.
