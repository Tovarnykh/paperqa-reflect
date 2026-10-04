# UiA baseline selection v1 — 2 October 2026

User request: select a stronger baseline from the discussed local model families,
now using the available V100 32 GiB / 96 GiB RAM / 6 CPU quota. This is practical
model selection, not a new reflection mechanism. No hosted API or holdout tuning.

## Candidates and rationale

| Profile | Checkpoint / quantization | Why test |
|---|---|---|
| gemma26 | Gemma 4 26B-A4B IT QAT (~16 GB download) | Larger evidence-capable family than laptop E4B, sparse compute with all expert weights resident |
| qwen38 | Qwen3.8 27B, Q4_K_M (~18 GB) | Recent dense agent-oriented model; revisit Qwen beyond the 9B laptop failures |
| deepseek32 | DeepSeek-R1-Distill-Qwen-32B, Q4_K_M (~20 GB) | Explicitly discussed reasoning candidate; evaluate real tool/schema compatibility |
| gptoss20 | gpt-oss 20B, MXFP4 (~14 GB) | Separate agent-oriented open-weight family; actual V100/runtime compatibility must pass |
| gemmae4 | Existing Gemma 4 E4B IT QAT | Same-hardware compact anchor; previous laptop timings are not server controls |

Kimi Linear 48B-A3B remains a reserve: the publisher's documented deployment uses
a different stack; a suitable build, GPU placement and tool integration in our
pinned Ollama have not been qualified. Its 3B active parameters do not mean 3B
stored weights. Full Kimi/DeepSeek flagships are not ordinary single-V100 models.
Gemma 12B/31B and smaller distillations remain possible follow-ups, not an exhaustive
grid. This bounded selection cannot establish a global best model.

Sources checked on 2 October:
[Qwen card](https://huggingface.co/Qwen/Qwen3.8-27B),
[Qwen build](https://ollama.com/library/qwen3.8:27b),
[Gemma card](https://huggingface.co/google/gemma-4-26B-A4B-it),
[Gemma QAT](https://ollama.com/library/gemma4:26b-a4b-it-qat),
[DeepSeek card](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B),
[DeepSeek build](https://ollama.com/library/deepseek-r1:32b),
[gpt-oss Ollama guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama),
[gpt-oss build](https://ollama.com/library/gpt-oss:20b),
[Kimi card](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct).

## Fixed conditions before inference

Pinned PaperQA/high_quality prompts, tools, retrieval, BGE-M3, 7000/250 chunks,
20 evidence candidates, five answer sources, JSON-schema-v1 tool transport,
16K context, 4096 output tokens, 600/1800/2400 s request/agent/question limits.
Same 16 documents and eight dev questions; reserve untouched. One LLM supplies
controller/RCS/answer within each candidate. Local-only endpoint, same Ollama
0.35.0 at loopback port11436, one parallel request / one loaded model. Actual VRAM, context truncation,
reasoning/transport errors and backend behavior must be recorded.

Sampling is model-specific, so this compares practical configurations rather
than isolated weights. Gemma starts with its published 1/.95/top_k64 and thinking
off, matching the qualified transport configuration. Qwen uses .7/.8/top_k20,
presence_penalty1.5 for instruct roles and 1/.95/presence_penalty0 with controller
thinking. DeepSeek uses .6/.95 with default thinking; its recommendation against
system prompts is a known mismatch with unchanged PaperQA prompts, so failures
are not evidence against DeepSeek's general reasoning ability. gpt-oss uses
temperature1 and low reasoning in all roles. Seeds42/43.

Configuration support was extended only to pass presence_penalty and explicit
reasoning levels; test the actual LiteLLM-to-Ollama request mapping. Old config
values, upstream prompts and agent decisions remain unchanged.

## Evaluation and decision rule

1. Synthetic qualification: real tool definitions/structured controller call,
   source reading and observed GPU placement. Preserve every failure. Permit
   one narrowly justified compatibility/configuration adjustment, recorded before
   scoring; never use answer keys to steer the agent.
2. Complete eight dev questions for compatible candidates, seed42. Sequential
   scoring, cold model starts, no concurrent downloads/probes while timing.
   A candidate with two consecutive technical failures/timeouts may be stopped
   with a saved reason and partial status; unanswered questions are not scored
   as incorrect, and a partial series cannot win the baseline selection.
3. Inspect source fidelity for final answers/RCS, especially wrong, abstained
   or inconsistent cases. Correct MCQ letters are not verified citations.
4. Repeat the best two completed configurations with seed43 (ties broken by
   fewer unsupported source claims and then runtime). If another candidate is
   materially tied, include it or retain the uncertainty explicitly.
5. Recommend a working baseline by correct completed answers, completion,
   source fidelity and practical cost. Distinguish provisional selection from
   independent final evaluation. Repeated questions are not independent data;
   eight dev questions cannot demonstrate general superiority. Expanding dev
   without consuming the reserve may be necessary if differences remain unclear.

No automatic claim of improvement over PaperQA follows from selecting a larger
model. Future baseline/extension comparisons use the same selected configuration.

## Pre-scoring runtime correction

Ollama 0.30.10 returned HTTP412 when pulling Qwen3.8, requiring a newer version.
Install official 0.35.0 side by side, preserve old installation/diagnostics, and
score every candidate including the compact anchor on 0.35.0. No old-runtime
synthetic probe is a scored comparison. Existing old configs keep port11435.

## Pre-scoring gpt-oss transport correction

On 0.35.0, gpt-oss passed source reading on the V100 but failed the JSON-schema
controller adapter with `MalformedMessageError: Incomplete or multiple structured
tool responses`. A separate `uia-gptoss20-native-dev-s42` probe passed the real
PaperQA ToolSelector and source reading using the model's native function calling.
Use native transport for gpt-oss scoring and preserve the failed JSON profile.
The tools and upstream prompts remain the same, but wire transport differs;
compare practical configurations, not a causal effect of model weights alone.
