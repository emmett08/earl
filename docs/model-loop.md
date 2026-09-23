# Text-model reasoning loop

`eal-agent` supplies the application loop around the EAL MCP server. The selected model only has to generate text. The host starts one MCP session, discovers its tools and input schemas, retrieves the language description when available, and gives those contracts to the model. No native function calling or provider JSON-generation feature is required.

The model sees the exact flat host operation names and complete request schemas, such as `validate` with an `operation: "validate"` field. Raw MCP names remain in the discovery trace. The prompt supplies task-independent request templates for validation, collection, reasoning, explanation and completion, and tells the model to repair its own malformed request when diagnostics arrive. If the caller already supplied a language reference identical to the server's description, the host verifies that equality and reports its digest instead of repeating the reference in the prompt. The actual discovery call and full result remain recorded.

Each model response is one flat JSON request. The host checks its fields, the discovered input schema and the fixed task inputs before calling MCP. It automatically validates a source before collection or reasoning, returns diagnostics, and permits bounded repairs. Collection, assessment and explanation use persistent server identifiers. Revised source must acquire applicable observations: the interpreter checks the exact source digest, input identity, environment and observation time.

Example requests within one conversation are:

```json
{"operation":"validate","source":"language \"EAL/0.2\"; ..."}
```

```json
{"operation":"reason","source":"language \"EAL/0.2\"; ...","context":{"site":"bench"},"collection_id":"returned collection ID","now":"2026-09-23T12:00:00Z"}
```

The model ends with identifiers, not a self-certified conclusion:

```json
{"operation":"finish","assessment_id":"latest returned assessment ID","claims":["latency_requirement"]}
```

The host derives every final status and qualification from the latest successful server assessment in this run. A new collection or source revision invalidates that choice until reasoning runs again. Unknown IDs, omitted required claims, invented status fields and old assessment IDs produce diagnostics. `{"operation":"stop","reason":"Need a calibrated measurement"}` returns an explicitly incomplete report.

`completed` means the interaction finished with a checked server result. That result may be unsupported, contested or out of scope. It does not mean the engineering claim is true.

## Preserve the engineering question

The caller supplies optional `initial_data` JSON. Its `source`, `context` and `now` fields are immutable task anchors. Every corresponding request must preserve them; reasoning must supply a fixed `now` explicitly. Anchored source completion is reported as `task_correspondence: "source_anchored"`. The host also checks the returned assessment's source digest and context fingerprint.

For source construction or repair, supply `draft_source` instead of `source`. Source revision is then allowed, and `task_correspondence` is `unverified`. Required claim identifiers alone cannot establish that a model preserved the intended proposition. The final report includes the actual assessed source and context so an independent task checker can compare their meaning. The benchmark does that comparison separately; a renamed or weakened proposition must not receive success credit merely because its identifier remains unchanged.

## Configure a provider

Use `examples/agent-http.toml` as a configuration template. Set an explicit model name/version and endpoint, then select rates from the provider's applicable pricing schedule if cost estimates are needed. No model name, price or capability is silently assumed. Credentials are looked up by an environment variable name and are absent from the stored provider identity. The HTTP adapter sends ordinary `messages`, `model`, `n: 1`, `stream: false`, the selected output limit and configured sampling settings. It never adds `tools` or `response_format`.

Run an anchored task:

```sh
eal-agent --provider path/to/provider.toml --task path/to/task.txt \
  --initial-data path/to/task-inputs.json --claim latency_requirement \
  --workspace path/to/workspace --registry path/to/tools.toml \
  --output path/to/report.json
```

Use `--unaided` for the same provider without MCP. It receives the task inputs and returns claim statuses. Its answers are explicitly `unverified_model_answer`; the host does not use expected answers to repair them. `python -m eal.agent` exposes the same command when an editable installation has not refreshed entry points.

The command provider supports local models and other providers through a trusted operator-configured argv list. No shell is used, and model output cannot change the executable. Each invocation receives:

```json
{"model":"configured-model-version","messages":[{"role":"user","content":"task"}],"sampling":{"temperature":0.2},"max_output_tokens":4096}
```

It returns one UTF-8 JSON object:

```json
{"text":"one model-generated JSON request","input_tokens":100,"output_tokens":25,"model":"actual-model-version","metadata":{}}
```

Token counts may be null when unavailable; unknown usage is never recorded as zero. Command adapters run with the host's environment and access. They are trusted integrations, not a sandbox. Output, elapsed time and process groups are bounded; subprocess error bodies are not copied into reports. An `interface_only` measurement kind identifies scripted adapter fixtures. It must not be used as evidence of a real language model's ability.

## Budgets and measurement

`AgentBudget` bounds model iterations, repair attempts, MCP tool calls, elapsed wall time, prompt and response bytes, requested output tokens, reported total tokens and optional model cost. The host preserves each model attempt, each actual tool invocation, latency, diagnostics, discovered schemas and the final conversation. Failed responses and format repairs count. No implicit provider retry hides an attempt. The full initial prompt includes discovery and language-description tokens in provider-reported input usage.

Total token and model-cost bounds are checked before and after each provider response. A provider can consume more tokens or money than remain in the allowance because the host has no exact advance tokenizer or billing reservation. An observed overrun stops the run before executing that response or accepting its final answer; its actual reported usage remains in the report. These are stop conditions, not a provider-enforced spending cap. Unknown usage also stops further generation and cannot produce a budget-verified final answer. Byte, iteration and time limits still bound such failures.

Costs are estimates from explicit per-million token rates. Cached input requires its own configured rate when the provider reports cache usage. Missing rates, unknown failed-call usage or incomplete token metadata leave total model cost null while retaining known subtotals. No provider invoice or host/tool price is fabricated. The host's `tool_cost_usd` and `total_cost_usd` remain null; an evaluation runner can add declared tool execution rates and report whether the resulting total is complete. Budget and timing include MCP start-up and discovery; tool call counts include automatic validation and language-description calls.

The included tests use scripted text responses, real local subprocesses, actual MCP stdio sessions, and an HTTP protocol fixture. They verify integration contracts and budget accounting. They do not establish low-cost model reasoning performance. Run the paired benchmark with an actual configured model and held-out engineering tasks before making a capability or cost-saving claim. Model aliases, version identities, sampling settings and returned model identifiers are recorded; a seed is not a reproducibility guarantee.

## Adapter references

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk): client session initialisation, tool discovery, structured output and stdio transport.
- [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): text messages, completion limits, choices and usage fields. Compatible endpoints can have different parameter support; `max_tokens_field` explicitly selects `max_completion_tokens` or `max_tokens`.
- [OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting): returned completion usage includes non-visible generated tokens when present.

These references specify protocol behaviour. They are not evidence that an external provider was exercised in the local integration tests.
