# Text-model reasoning loop

`eal-agent` supplies the application loop around the EAL MCP server. Its default text interface works with a model that can only generate text. Optional configured native function calling, structured output and model reasoning controls use the same checked operation contracts. The host starts one MCP session, discovers its tools and input schemas, retrieves the language description when available, and gives those contracts to the model.

The model sees the exact flat host operation names and complete request schemas, such as `validate` with an `operation: "validate"` field. Raw MCP names remain in the discovery trace. The prompt supplies task-independent request templates for validation, collection, reasoning, explanation and completion, and tells the model to repair its own malformed request when diagnostics arrive. If the caller already supplied a language reference identical to the server's description, the host verifies that equality and reports its digest instead of repeating the reference in the prompt. The actual discovery call and full result remain recorded.

Each text response is one flat JSON request. The host checks its fields, the discovered input schema and the fixed task inputs before calling MCP. It automatically validates a source before collection or reasoning, returns diagnostics, and permits bounded repairs. Collection, assessment and explanation use persistent server identifiers retained by the host. Revised source must acquire applicable observations: the interpreter checks the exact source digest, input identity, environment and observation time.

## Active state

The default `--host-mode stateful` keeps the exact source bytes, context, assessment time, current matching collection and current assessment. A model does not have to recopy source or generate database identifiers. With `initial_data.source` or `draft_source`, `context`, and the task's required claims already supplied, the complete ordinary workflow is:

```json
{"operation":"assess"}
```

```json
{"operation":"finish"}
```

`assess` is a host operation that explicitly validates the active source, collects fresh observations, reasons using the new collection and retrieves its explanation. Each of the four actual MCP calls is recorded and counted against the tool-call and elapsed-time budgets. Invalid source stops before collection; failure or budget exhaustion cannot expose a previous assessment as the new result. The host never repairs a proposition automatically. Observation failure remains visible and can correctly yield an unsupported claim.

The individual operations remain available for investigations that need finer control:

```json
{"operation":"validate"}
```

```json
{"operation":"collect"}
```

```json
{"operation":"reason"}
```

```json
{"operation":"explain"}
```

```json
{"operation":"finish"}
```

These are five successive requests, each followed by host feedback. `reason` reuses a matching collection; `assess` always collects again. Host feedback supplies a concrete `next_request` when the next workflow step follows from retained state; it does not invent a source repair. Omitted fields resolve as follows.

| Omitted field | Meaning |
|---|---|
| `source` | Exact active source, including whitespace and terminal newline |
| `context` | Active context; absence of an active context produces a diagnostic |
| `now` | Active assessment time; server wall time only if no active time was supplied |
| `collection_id` in `reason` | Latest collection matching the active source and context; no observations if none exists |
| `assessment_id` in `explain` or `finish` | Current successful assessment; absence produces a diagnostic |
| `claims` in `finish` | Caller-supplied required claims; otherwise identifiers must be supplied explicitly |

Stateful `collect`, `reason` and `format` do not accept a `source` field: they operate on the retained source. Initial fixed context/time fields and current assessment identifiers are likewise absent from the relevant request schemas. Hashes are metadata, not source references or source text. A model that sends a digest or the string `initial_data` as source receives a diagnostic; it cannot overwrite the draft this way. An unanchored whole-source replacement is proposed through `validate` only and adopted only after successful validation. Invalid candidates leave the prior source, collection and assessment unchanged. An unanchored context or assessment time can be explicitly supplied where its schema offers that field; invalid timestamps are rejected before adoption.

An explicit `collection_id: null` requests reasoning without observations for that call. It differs from omission when a matching collection exists; string collection identifiers are host-owned in stateful mode. New source or context clears the current collection and assessment; a new assessment time clears the current assessment. A new collection attempt also clears the old assessment. A failed operation cannot silently become a successful assessment. Full resolved MCP arguments, actual results, source revisions and a compact state summary remain in the report.

Stateful feedback preserves every claim's status, proposition and reasons, every assumption and objection outcome, scope checks, argument dependencies, bound computed values and units, and method interpretation. Collection feedback retains observation values, timestamps, statuses and failures while removing duplicated process output and execution metadata. Reasoning summaries omit repeated method schemas, formal-input copies and solver iterations; large individual computation-detail fields are explicitly listed for retrieval. Nothing is removed from the persisted tool results. Request the full derivation when needed:

```json
{"operation":"explain","detail":"full"}
```

Ordinary `explain` returns the same concise outcome view. Stateless mode returns full feedback, allowing source-reference and feedback-volume changes to be evaluated together as an explicit host condition.

An unanchored draft can be repaired without reproducing the entire document:

```json
{"operation":"revise","replacements":[{"old":"conclusion misspelled_claim;","new":"conclusion actual_claim;"}]}
```

Each `old` fragment must occur exactly once in the active source at that step. The replacement list applies atomically; ambiguous or absent fragments leave the source unchanged. The operation records explicit edits and digests, invalidates prior observation/assessment defaults and requires validation before execution. It does not infer a replacement, silently change a proposition or establish that the revised engineering question is faithful. Fixed `initial_data.source` cannot be revised.

`--host-mode stateless` requires the full source and result identifiers on each request and returns full feedback. It provides an explicit host condition for controlled comparisons. Historical reports retain their original protocol names and results. The standalone `eal-host` is a single-request stateless dispatcher; active state belongs to `eal-agent`.

Explicit requests, including those used in stateless mode, are:

```json
{"operation":"validate","source":"language \"EAL/2\"; ..."}
```

```json
{"operation":"reason","source":"language \"EAL/2\"; ...","context":{"site":"bench"},"collection_id":"returned collection ID","now":"2026-09-23T12:00:00Z"}
```

The model ends with identifiers, not a self-certified conclusion:

```json
{"operation":"finish","assessment_id":"latest returned assessment ID","claims":["latency_requirement"]}
```

The host derives every final status and qualification from the latest successful server assessment in this run. A new collection or source revision invalidates that choice until reasoning runs again. Unknown IDs, omitted required claims, invented status fields and old assessment IDs produce diagnostics. `{"operation":"stop","reason":"Need a calibrated measurement"}` returns an explicitly incomplete report.

`completed` means the interaction finished with a checked server result. That result may be unsupported, contested or out of scope. It does not mean the engineering claim is true.

## Preserve the engineering question

The caller supplies optional `initial_data` JSON. Its `source`, `context` and `now` fields are immutable task anchors. Every resolved request must preserve them; stateful omission retains their exact values, while stateless requests supply them explicitly. Anchored source completion is reported as `task_correspondence: "source_anchored"`. The host also checks the returned assessment's source digest and context fingerprint.

For source construction or repair, supply `draft_source` instead of `source`. Source revision is then allowed, and `task_correspondence` is `unverified`. Required claim identifiers alone cannot establish that a model preserved the intended proposition. The final report includes the actual assessed source and context so an independent task checker can compare their meaning. The benchmark does that comparison separately; a renamed or weakened proposition must not receive success credit merely because its identifier remains unchanged.

## Reviewed recipient route

`eal-agent` constructs or revises a draft source and reports its task correspondence as unverified unless the caller pinned the source. A separate `eal-host` recipient route uses an operator-reviewed [exact task catalogue](task-families.md#reviewed-recipient-route). The authenticated launcher supplies the original question file, principal and task, family and artefact-claim grants. The recipient can nominate an authorised task ID in JSON; it cannot supply the question, EAL source, bindings or claim.

For the reviewed `field_inspection` example, the operator first saves the exact catalogue question bytes with no added newline, then invokes the host under an authenticated principal. The same database and grant must be available when finalising the returned assessment ID:

```bash
printf %s 'Does the field rig satisfy the reviewed inspection claim?' > question.txt
route=(--workspace . --registry tools.toml --database runs.sqlite3 \
  --artifacts artifacts.toml --families families.toml --tasks tasks.toml \
  --recipient-task-file question.txt --recipient-principal caller_a \
  --recipient-family-grant rig --recipient-task-grant field_inspection \
  --recipient-grant rig_field:accepted)
assessment_response=$(printf %s '{"operation":"assess_reviewed_task","task_id":"field_inspection"}' |
  eal-host "${route[@]}")
printf '%s\n' "$assessment_response"
assessment_id=$(printf %s "$assessment_response" |
  python -c 'import json,sys; print(json.load(sys.stdin)["result"]["assessment_id"])')
printf %s 'The model explanation, if any' |
  eal-host "${route[@]}" --task-id field_inspection --assessment-id "$assessment_id"
```

The first response contains the host-checked result packet. The final response separates `checked_answer` from `recipient_output_unverified`; generated prose cannot change the stored status. `{"operation":"task_candidates"}` can suggest accessible families, and `{"operation":"explain_reviewed_task","task_id":"field_inspection","assessment_id":"..."}` can retrieve the authorised trace. Candidate scores do not confer applicability. The task resolver requires an exact reviewed question and refuses unmatched, ambiguous or drifted contracts. The launcher must authenticate the principal independently of the CLI flag, and the operator must have reviewed the question, scope, source, methods and evidence obligations. A checked status remains conditional on the declared argument and actual observations; it does not certify the prose claim or remove the need to test adverse states.

## Configure a provider

Use `examples/agent-http.toml` as a configuration template. Set an explicit model name/version and endpoint, then select rates from the provider's applicable pricing schedule if cost estimates are needed. No model name, price or capability is silently assumed. Credentials are looked up by an environment variable name and are absent from the stored provider identity. Ordinary text mode sends `messages`, `model`, `n: 1`, `stream: false`, the selected output limit and configured sampling settings. Tool and response-format fields are added only through the explicit capabilities described below.

Run an anchored task:

```sh
eal-agent --provider path/to/provider.toml --task path/to/task.txt \
  --initial-data path/to/task-inputs.json --claim latency_requirement \
  --workspace path/to/workspace --registry path/to/tools.toml \
  --output path/to/report.json
```

Add `--methods module:factory` when the selected server needs a trusted configured method extension. Source text cannot select an import path.

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

## Optional provider capabilities

The HTTP adapter accepts an explicit `[provider.capabilities]` table. Defaults retain ordinary text generation. No feature is inferred from a model's name, size or marketing category.

```toml
[provider.capabilities]
native_tools = true
structured_output = "none"
# Configure only values supported by this exact model and endpoint:
# reasoning_effort = "low"
# tool_reasoning_compatible = true
```

`--interaction-mode native` requires `native_tools = true`. Each host operation becomes a function with the same arguments, excluding the constant `operation` field because the function name supplies it. The adapter requests one call with `parallel_tool_calls: false`, retains the assistant's actual `tool_calls`, and returns host feedback as a `tool` message with the matching `tool_call_id`. Text and native calls converge on the same expansion, validation, provenance and interpretation path. Unknown operations, malformed arguments or multiple calls are rejected and their usage is retained. Function schemas explicitly use `strict: false` so omission retains its precise meaning; the host validates all arguments itself.

For text interaction, `structured_output = "json_object"` requests JSON output. `"json_schema"` submits the operation schemas under a single `request` envelope and unwraps the result before the shared host checks. Its provider schema setting is explicitly non-strict: the language accepts arbitrary context data and distinguishes omitted fields from explicit null, which must not be rewritten to satisfy a provider's strict schema subset. Neither setting replaces host validation. In unaided runs, structured JSON requests constrain the response to an object and the host separately checks the claim-status schema.

`reasoning_effort` is forwarded only when explicitly configured. Supported values and interactions with tools vary by model and endpoint. Native tools with a non-`none` effort require `tool_reasoning_compatible = true`, asserting that the operator selected a documented compatible combination. Unsupported combinations still produce recorded provider errors; there is no silent fallback to a different model or effort. Models that reject temperature must have that sampling field omitted. This adapter implements Chat Completions; some newer models require a different API for combined reasoning and tools.

The provider identity records all capability and sampling settings. Reported completion tokens include the provider's reasoning-token usage; any separate reasoning-token count is preserved in attempt metadata. A configured capability is not a measured claim of improved performance.

## Budgets and measurement

`AgentBudget` bounds model iterations, repair attempts, MCP tool calls, elapsed wall time, prompt and response bytes, requested output tokens, reported total tokens and optional model cost. The host preserves each model attempt, each actual tool invocation, latency, diagnostics, discovered schemas and the final conversation. Failed responses and format repairs count. No implicit provider retry hides an attempt. The full initial prompt includes discovery and language-description tokens in provider-reported input usage.

Total token and model-cost bounds are checked before and after each provider response. A provider can consume more tokens or money than remain in the allowance because the host has no exact advance tokenizer or billing reservation. An observed overrun stops the run before executing that response or accepting its final answer; its actual reported usage remains in the report. These are stop conditions, not a provider-enforced spending cap. Unknown usage also stops further generation and cannot produce a budget-verified final answer. Byte, iteration and time limits still bound such failures.

Costs are estimates from explicit per-million token rates. Cached input requires its own configured rate when the provider reports cache usage. Missing rates, unknown failed-call usage or incomplete token metadata leave total model cost null while retaining known subtotals. No provider invoice or host/tool price is fabricated. The host's `tool_cost_usd` and `total_cost_usd` remain null; an evaluation runner can add declared tool execution rates and report whether the resulting total is complete. Budget and timing include MCP start-up and discovery; tool call counts include automatic validation and language-description calls.

The included tests use scripted text responses, real local subprocesses, actual MCP stdio sessions, and an HTTP protocol fixture. They verify integration contracts and budget accounting. They do not establish low-cost model reasoning performance. Run the paired benchmark with an actual configured model and held-out engineering tasks before making a capability or cost-saving claim. Model aliases, version identities, sampling settings and returned model identifiers are recorded; a seed is not a reproducibility guarantee.

## Adapter references

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk): client session initialisation, tool discovery, structured output and stdio transport.
- [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): text messages, completion limits, choices and usage fields. Compatible endpoints can have different parameter support; `max_tokens_field` explicitly selects `max_completion_tokens` or `max_tokens`.
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) and [structured output](https://developers.openai.com/api/docs/guides/structured-outputs): native call/result pairing, parallel-call control and provider schema restrictions.
- [OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting): returned completion usage includes non-visible generated tokens when present.

These references specify protocol behaviour. They are not evidence that an external provider was exercised in the local integration tests.
