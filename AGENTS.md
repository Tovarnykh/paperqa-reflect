# Research working context

This is Viktor's UiA IKT464 experiment repository. Read README.md and the latest
report under results/reports before substantive changes. The optional parent
workspace's LLM Wiki/advanced-ict-project stores broader course context.

Use Python 3.12 and `uv sync --frozen`. PaperQA is a pinned upstream dependency;
do not edit site-packages. Keep fhlmi's compatibility pin unless the real
ToolSelector integration has been rechecked. Models are configured by role.

The current config is an engineering smoke baseline using local Ollama. It is
not a published PaperQA2 reproduction or a finalized research protocol. Keep
paid providers out of this local config. Record prompt/config/model changes.

Only data/corpus/<set> is indexed. Keep questions, answer keys, wiki and run
outputs outside that directory. Preserve all attempted runs including failures.
The five smoke questions are development data; use separate questions for final
evaluation. Successful termination, answer correctness and citation support
are different outcomes.

Run pytest and Ruff for implementation changes. A passing doctor command checks
configuration and availability but does not perform inference. Record actual
integration results, tool traces, model digests and timing conditions. Do not
claim a run succeeded from a plausible answer if status is fail/truncated.

Explain results to the user in Russian using concrete examples. Future verifier
and stopping experiments remain exploratory; no detailed hour allocations.
