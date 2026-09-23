# Live model experiments: 23 September 2026

These are the preserved EAL/0.2 experiments. The subsequent [EAL/0.3 repeated experiments](eal03-model-results.md) evaluate the revised host, compositional objections and registered methods; their results are reported separately.

This is a small, single-run comparison using the actual OpenAI API and the actual local EAL MCP server. The task observations are synthetic fixtures. Both arms received the same EAL reference, source or repair draft, observations, context and assessment time. The delegated arm additionally received operation schemas, server results and bounded diagnostic feedback. No native function calling, structured-output API feature or reasoning parameter was used.

The model snapshots were `gpt-4.1-nano-2025-04-14` and `gpt-4.1-mini-2025-04-14`, with temperature zero. Their official [nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano) and [mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) pages describe models without a reasoning step. They support tool calling, but this experiment deliberately used ordinary text responses, with the host executing requests.

## Held-out comparison

The implementation and prompts were frozen after development experiments. GPT-4.1 mini was selected because it completed both delegated development cases. Fifteen reserved cases were then run once per arm, in two concurrent batches of eight and seven tasks. Arm order alternated within each batch. The source-file digests were unchanged throughout that run. Selection on development performance and one evaluation per case do not establish generalisation or repeatability.

| Arm | Correct tasks | Unjustified answers | Missing/incomplete outcomes | Repair turns | Model tokens | Model API cost estimate | Cost per correct task | Mean trial seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| unaided | 6/15 | 8 | 0 | 0 | 38655 | $0.009908 | $0.001651 | 7.81 |
| delegated | 10/15 | 1 | 4 | 19 | 344478 | $0.080734 | $0.008073 | 47.73 |

Delegated execution returned 10 correct task outcomes; the unaided arm returned 6. The table counts correct unsupported, contested and out-of-scope answers as correct: absence of usable support is not falsity. Workflow tasks also require the recorded validation, collection, reasoning and explanation sequence; unaided status answers do not demonstrate execution of that sequence.
Delegation had a higher API cost in this run. This experiment does not demonstrate a cost saving.

The scorer's one delegated unjustified flag is a conservative identity rejection: the calibration repair consistently renamed the internal assumption `calibrated` to `calibration_valid`. A separate parsed-structure comparison found no other change; the required outcome and workflow were correct. Counting that equivalent repair gives a secondary 11/15 result. The frozen primary score remains 10/15. The [adjudication](../benchmarks/results/2026-09-23/adjudications.json) records the check. Four other delegated tasks ended without a final answer after request errors or model stops. These are protocol failures, not successful engineering conclusions.

## Development failures and selection

Two development tasks tested argument repair/explanation and typed pressure conversion. The initial nano host prompt mixed underlying MCP tool names with host operation names. Nano used the wrong names or invented an operation and stopped. The general protocol was revised to expose exact host-operation schemas, neutral request templates and explicit repair instructions. Identical language references were verified without repeating their text.

| Model and phase | Unaided correct | Delegated correct | Delegated repair turns | Combined API cost estimate |
|---|---:|---:|---:|---:|
| nano-development-initial | 2/2 | 0/2 | 2 | $0.002109 |
| nano-development-revised | 2/2 | 0/2 | 9 | $0.003103 |
| mini-development | 1/2 | 2/2 | 1 | $0.016762 |

Nano still failed the delegated development cases after the protocol revision, including invented assessment identifiers and omitted operations. Its failures were retained. Mini completed both delegated development cases, including the required repair and explanation workflow. This supports use of the implemented interface with that model on those cases; it does not establish that every low-cost model can follow the protocol. No held-out nano trial was run after its development failures. The mathematical interpreter passed its independent known-answer checks regardless of the model's protocol performance.

## Cost scope and reproducibility

Rates were checked on the official model pages above on the experiment date. Per million input/cached-input/output tokens, the configured USD rates were nano 0.10/0.025/0.40 and mini 0.40/0.10/1.60. These are token-rate estimates using returned usage, not reconciled invoices. Cache usage is recorded; the retry received a different cache state, so the development runs are not controlled cold-cache timing or cost measurements.

All received responses, failed requests, repairs, operation calls, input data, returned model identities and usage remain in the compressed JSON transcripts. Marginal fixture-tool charges were explicitly set to zero. Host infrastructure, electricity, taxes and engineering labour were not priced. No claim of complete infrastructure-inclusive total cost is made. Trial latency includes the host workflow and server interaction; aggregate latency sums trials and is not the wall duration of the concurrent batches.

Across the archived development and held-out runs plus the connectivity probe, the model API estimate is **$0.112618**. The key was supplied only through the runtime environment and is absent from these files.

The held-out budget per arm/task was ten model attempts, four repairs, 120,000 reported total tokens, 120 seconds and a USD 0.025 observed model-cost threshold. The model-cost threshold is checked after a response and may be exceeded by one billable response; recorded charges are never truncated to the threshold. Detailed budgets for each earlier phase remain in its report.

Reproduce the held-out selection from the repository root, with `OPENAI_API_KEY` configured externally:

```sh
python -m eal.benchmark   --provider benchmarks/providers/openai-4.1-mini.toml   --split held_out --max-iterations 10 --max-total-tokens 120000   --max-elapsed-seconds 120 --max-model-cost-usd 0.025   --per-mcp-call-usd 0 --output .eal/mini-held-out.json
```

This command runs sequentially; the recorded run used the two batches described above. Install `.[socks]` if the HTTP connection uses a SOCKS proxy. Model sampling and provider state can change outputs even at temperature zero.

The [index](../benchmarks/results/2026-09-23/index.json) records transcript digests and aggregates. Full records are [initial nano development](../benchmarks/results/2026-09-23/nano-development-initial.json.gz), [revised nano development](../benchmarks/results/2026-09-23/nano-development-revised.json.gz), [mini development](../benchmarks/results/2026-09-23/mini-development.json.gz), and [mini held-out](../benchmarks/results/2026-09-23/mini-held-out.json.gz). Decompress with `gzip -dc FILE.json.gz`, or read with Python's `gzip.open`. The task suite digest covers the manifest, source, observations and repair drafts; transcripts retain the exact prompts and responses.

These cases exercise a bounded language profile. They do not establish unrestricted engineering completeness, natural-language-to-model fidelity for arbitrary questions, human comprehension, physical truth, or general performance on new engineering domains. See the [task coverage](engineering-tasks.md) and [evaluation contract](model-evaluation.md).
