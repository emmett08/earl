# MCP, tools and model hosts

The MCP server exposes the EAL/2 interpreter through a local stdio service. It uses the official Python SDK pinned to 1.30.0; its subprocess test negotiates the 2025-11-25 protocol profile. The newer SDK v2 and 2026 protocol have not been integrated or verified here. The package also provides a CLI, a strict JSON host for text-only models, an interactive model host and optional operator-reviewed artefact and question routes. These host interfaces do not alter the [source grammar](../grammar/EAL.g4) or the `EAL/typed-input/1` observation schema. The [API load-test example](../examples/api-load-test/README.md) exercises CLI and MCP paths over one synthetic request report; it reports no model-comparison result. The [live API experiment](../experiments/api_load_test/README.md) separately executes the configured collector against a real local HTTP service and compares model decisions, with JSON and prose using direct collection without MCP.

## Contents

1. [MCP operations](#mcp-operations)
2. [Tool registry and observation identity](#tool-registry-and-observation-identity)
3. [Text-model hosts and provider configuration](#text-model-hosts-and-provider-configuration)
4. [Reviewed artefacts and bounded recipients](#reviewed-artefacts-and-bounded-recipients)
5. [Reviewed question and retrieval](#reviewed-question-and-retrieval)
6. [Verification and sources](#verification-and-sources)

## MCP operations

| Tool | Input | Operation |
|---|---|---|
| `eal_describe` | None | Discover language versions, syntax, method schemas and typed binding contracts |
| `eal_format` | `source` | Return canonical checked source and its digest; changed bytes require new observation bindings |
| `eal_validate` | `source` | Parse and check language structure, references and method contracts |
| `eal_collect` | `source`, `context`, optional `evidence_ids` | Run configured collectors and persist observations; return `collection_id` |
| `eal_reason` | `source`, `context`, optional `collection_id`, `now` | Compute method results and argument conclusions; persist and return `assessment_id` |
| `eal_explain` | `assessment_id`, optional `claim` | Retrieve the reasoning result and dependencies |
| `eal_grounded` | `arguments`, `attacks` | Calculate grounded labels for an explicit attack graph |
| `eal_assess_artifact` (only with `--artifacts`) | `artifact_id` | Read one host-pinned EAL file, collect, evaluate and return its configured claim statuses with assessment ID |
| `eal_assess_artifact_claim` (with `--artifacts`, outside reviewed-task route) | `artifact_id`, `claim` | Issue one bounded checked claim packet, subject to recipient grants |
| `eal_explain_artifact_claim` | `artifact_id`, `assessment_id`, `claim` | Retrieve that packet's direct dependency trace |
| `eal_finish_artifact_claim` | `artifact_id`, `assessment_id`, `claim` | Recover the checked packet independently of recipient prose |
| `eal_task_candidates` (reviewed-task recipient endpoint) | None | Suggest authorised families for the launcher's bound question; no assessment |
| `eal_bound_task` | None | Resolve the exact reviewed question and grants; return the route and question digest without collection |
| `eal_assess_bound_task` | None | Collect, evaluate and issue one claim packet for that route |
| `eal_explain_bound_task` | `assessment_id` | Retrieve that principal's bounded dependency trace |
| `eal_finish_bound_task` | `assessment_id` | Recover the checked historical packet under the same question and grant |

Run `eal-mcp --workspace /absolute/path/to/earl --registry /absolute/path/to/earl/examples/api-load-test/tools.toml`. The default database is `.eal/runs.sqlite3` under that workspace; `--database` overrides it. Keep stdout for MCP protocol messages. The server checks advertised JSON schemas before SDK conversion, rejecting extra fields and incorrect types. The CLI uses the same service and accepts `--workspace`, `--registry`, `--database` and an optional host-registered `--methods` factory before its subcommand. The server uses stdio; HTTP MCP deployment is not included.

## Tool registry and observation identity

Argument source names tools and supplies typed input. A host TOML file binds names to executable argument vectors or imported files:

```toml
[tools.load_test_report]
kind = "command"
argv = ["python3", "examples/api-load-test/collect_results.py"]
version = "1"
mode = "deterministic"
timeout_seconds = 10
max_output_bytes = 16384
```

The executable receives one JSON object on stdin containing `evidence_id`, `environment`, `tool`, `tool_version`, `mode`, `input` and `context`. It emits one JSON object containing `value`, with optional `observed_at`, `context`, `request` and `details`. A returned `request` must match the acquisition identity described below. A nonzero exit, invalid JSON, unknown output fields, a mismatched request or context, timeout or excessive output produces a stored error observation. Configured commands run as trusted host programs with the host's access; the command adapter is not a sandbox and currently requires POSIX. Source cannot supply executable paths, shell syntax or provider credentials.

A `json_file` binding uses `path` instead of `argv`. Paths resolve to regular files within the workspace. File observations require `observed_at`, `context` and `request`; rereading a file preserves its original age. `request` contains exactly `tool`, `tool_version`, `mode`, `input` and `context`, recording the acquisition the observation answers. These fields must match the requested acquisition. Changing a suite name, input value, tool version or context cannot silently relabel an old observation. Earlier envelopes lacking `request` are rejected; all current examples supply it.

The acquisition identity is separate from the current source digest and local evidence identifier. The same recorded measurement can be used in a revised argument when its acquisition still matches; collection then binds it to that argument's exact source. Neither matching digests nor matching request metadata authenticates a producer. A live command that returns historical measurements must also supply the original `observed_at` rather than relying on ingestion time. `details` can hold model identity, solver configuration, source data identity or sampling settings.

Records preserve source digest, evidence kind/identifier, tool/version/mode, input digest, environment fingerprint, observation time, ingestion time, execution identity and result digest. These bindings detect mismatched inputs; they do not establish empirical truth or authenticate an entirely forged record. SQLite stores collections, individual success/error observations and reasoning results. The pure evaluator can also be called with supplied records for reproducible offline analysis.

Deterministic and nondeterministic describe tool output generation. They do not classify logical validity. Repeated stochastic outputs are not automatically independent samples, and a fixed seed does not establish independence or full reproducibility.

## Text-model hosts and provider configuration

A text-only model emits a single strict JSON request, such as:

```json
{"operation":"grounded","arguments":["a","b","c"],"attacks":[["a","b"],["b","c"]]}
```

Pass it to the host:

```bash
printf '%s\n' '{"operation":"grounded","arguments":["a","b","c"],"attacks":[["a","b"],["b","c"]]}' | eal-host --workspace .
```

`eal-host` validates the operation and fields, starts the MCP server using the SDK client, checks the discovered input schema, calls the corresponding tool and returns structured JSON. `--timeout` sets the total session deadline in seconds (120 by default). Requests for `validate`, `collect` and `reason` contain source text rather than source filenames; the CLI accepts filenames. `collect` returns an identifier that the model application can include in a later `reason` request. Each host invocation opens a protocol session; the database preserves results between invocations.

`eal-agent` starts one MCP session, discovers the tools and language description, gives the operation schemas to a configured model, validates each request, and returns diagnostics for bounded repairs. Its default stateful mode retains exact source bytes, context, collection and assessment identifiers. Once the caller supplies `initial_data.source` (immutable) or `draft_source` (revisable) with context, `{"operation":"assess"}` validates, collects, reasons and retrieves an explanation; `{"operation":"finish"}` returns the latest checked assessment. An invalid source stops before acquisition, and a source/context revision invalidates prior collection and assessment defaults. `--host-mode stateless` requires explicit source and identifiers on successive requests. `--interaction-mode native` uses a configured provider's native function calls, but all calls pass through the same host checks; model size or native calling does not imply reasoning quality.

For a configured command or HTTP text provider, run `eal-agent --provider PROVIDER.toml --task TASK.txt --initial-data INPUTS.json --claim performance_criteria_met --workspace . --registry examples/api-load-test/tools.toml --output REPORT.json`. Provider identity, sampling and model capabilities must be explicit; credentials stay in the host environment. `--unaided` invokes the same provider without MCP and labels the answer unverified. `AgentBudget` bounds attempts, repairs, tool calls, time and reported token/cost use. A provider may exceed a requested token or cost allowance before reporting it; unknown use is retained as unknown, and exceeding or unknown use prevents a budget-verified completion. A command adapter runs a trusted operator-selected argv, without a shell, using the host's access. The HTTP adapter implements configured Chat Completions style text, native calls and optional JSON output; only explicitly configured model capabilities are used. A caller must check the actual provider endpoint's parameter support.

Source text and result strings are data. The host accepts one schema-conforming request; it does not execute explanatory prose, accept invented operation names or reinterpret multiple concatenated requests.

The service records the selected `collection_id` on each assessment. The agent checks collection source/context, assessment source/context/collection/time, and the retrieved explanation identity before retaining a result. An explicitly supplied empty time or collection identifier is an error; only an omitted time selects the current clock. `initial_data.source`, context and time anchor the engineering question; a `draft_source` can be revised, but preserving its intended meaning remains unverified until an independent task check. The final host result derives checked statuses from the latest successful server assessment, including `unsupported`, `contested` and `out_of_scope`; model prose cannot revise those statuses. Reports retain failed model attempts, actual tool calls and observed use. A completed tool loop is evidence of operation, not proof that the argument's authored warrant or collector is adequate.

## Reviewed artefacts and bounded recipients

An operator places a reviewed `.eal` source under the workspace and creates a separate TOML catalogue. Each entry pins exact source bytes, a method-registry fingerprint, the claims the recipient may request and the assessment context. It answers repeated instances of that registered question as collector observations change. Another claim or context requires an operator-reviewed catalogue entry. The optional `now` pins assessment time; otherwise the host captures current UTC time after collection. For example:

```toml
[artifacts.performance_check]
path = "examples/api-load-test/source.eal"
sha256 = "<64 lowercase hex digits for exact UTF-8 source bytes>"
method_registry_fingerprint = "<64 lowercase hex digits for installed methods>"
claims = ["performance_criteria_met"]
now = "2026-09-25T10:00:00Z"

[artifacts.performance_check.context]
service = "orders-api"
build_id = "demo-build-42"
dataset = "synthetic"
```

Use `sha256sum examples/api-load-test/source.eal` for the source and read the method-registry fingerprint from `eal describe` with the same installed methods as the server. The pinned time reproduces the synthetic example; a current decision should assess genuine measurements at its actual time. Replace both digest placeholders with actual values; this block is a configuration template, not an installed reviewed catalogue. The catalogue is trusted operator configuration, separate from EAL source. Its paths must resolve within the workspace. Edited source or changed method registry invalidates the entry until reviewed and repinned. Each call reads source once, checks its digest and declarations, collects fresh records, checks collection and assessment identities, and selects only the catalogue's claims. The result contains `claims`, `source_digest`, `method_registry_fingerprint`, `collection_id`, `assessment_id` and `assessed_at`; `eal_explain(assessment_id, claim)` retrieves the full dependency trace.

Start MCP with `eal-mcp --workspace . --registry examples/api-load-test/tools.toml --artifacts ARTIFACTS.toml`. A client calls `eal_assess_artifact` with `{"artifact_id":"performance_check"}`. The advertised schema rejects a client-supplied `source`, `context`, `now` or claim substitute. An operator can assess before any model call:

```bash
python -m eal.artifacts --workspace . --registry examples/api-load-test/tools.toml \
  --artifacts ARTIFACTS.toml --id performance_check
```

A Python host can pass this compact packet to a text-only recipient for an explanation while retaining authority over the status:

```python
from eal.artifacts import ArtifactRegistry
from eal.runtime import ReasoningService

artifacts = ArtifactRegistry.load(ReasoningService(".", "examples/api-load-test/tools.toml"), "ARTIFACTS.toml")
packet = artifacts.assess("performance_check")
# Give packet to an optional text-only model for prose; its status labels are untrusted.
final = artifacts.finish("performance_check", packet["assessment_id"])
```

`finish` refuses an unrelated assessment ID or changed source/contract. `await artifacts.assist_text_only("performance_check", task, recipient)` passes `{"task": task, "checked_assessment": packet}` to an application callback and returns a checked answer separately from `recipient_output_unverified`. The application presents the checked claim status. The status is historical at its assessment time; another decision collects again. The recipient-only endpoint requires a principal authenticated by the launcher and explicit artefact/claim grants. It stores issuance for that principal, assessment and claim, so another principal cannot explain or finalise the packet merely by sharing a claim grant. `eal2-claim-packet/2` bounds the decisive reasons and marks omitted detail with counts and truncation flags. Full explanation may expose observations and dependencies. The compact status packet's cost and disclosure properties must be evaluated for the intended deployment. A native-tool model may call the endpoint directly; a text-only model needs its host. The source review, evidence acquisition and adequacy of the authored warrant remain separate obligations.

## Reviewed question and retrieval

This optional route requires operator-created artefact, family (`eal2-task-families/1`) and exact-question (`eal2-task-applicability/1`) catalogues. Each reviewed question binds its exact text, family, complete typed parameters, pinned source and one claim under a digest generated by `review_applicability_digest`. Duplicate questions and changed case contracts are rejected. The authenticated launcher supplies the original question in `TASK.txt` and grants for task, family and artefact/claim. No reviewed task catalogue ships with the load-test example; the following is a deployment template:

```sh
eal-mcp --workspace . --registry TOOLS.toml --artifacts ARTIFACTS.toml \
  --families FAMILIES.toml --tasks TASKS.toml \
  --recipient-task-file TASK.txt --recipient-only \
  --recipient-principal caller_a --recipient-task-grant pilot_task \
  --recipient-family-grant rig --recipient-grant rig_pilot:accepted
```

The endpoint accepts `eal_bound_task()` for a no-collection check,
`eal_assess_bound_task()` to collect and assess, and later
`eal_finish_bound_task({"assessment_id":"..."})` to recover the checked
packet. The model cannot submit a task ID, family bindings, source, context or question text. A trusted Python application holding an exact task ID may call the corresponding methods directly. The text host accepts `{"operation":"assess_bound_task"}` and finalises with the issued assessment ID; its response separates `checked_answer` from `recipient_output_unverified`. The route checks the question, case, source, principal and grants again at explanation/finalisation, including after restart. An absent, paraphrased, ambiguous or revoked question fails before collection. Claim-specific assessment collects evidence and objection dependencies; a failed or stale required collector refuses packet issuance. This conservative closure can block an otherwise usable alternative argument. A completed packet is historical; collect again when evidence changes.

`run_reviewed_recipient` in `eal.recipient` provides a bounded, model-facing loop for that endpoint. Before model generation it compares the host's original question digest with `eal_bound_task`, obtains the checked packet with `eal_assess_bound_task`, then permits only an `answer`, `explain` or `stop` JSON operation. `explain` retrieves the addressed trace; `answer` submits prose. The host calls `eal_finish_bound_task` after model output and reports the unverified prose separately from the checked status. A failed model response can leave a successfully issued checked packet available even when the loop reports incomplete. The loop checks that it connected to the dedicated recipient endpoint, not a general operator endpoint; principal authentication still belongs to the launcher. Native function calling, structured JSON and plain text use the same checked route when their exact provider capabilities are configured. Its `RecipientBudget` limits turns, repairs, tool calls, time, bytes, tokens and optional configured model cost; a token or cost limit is a post-use stop threshold, not a billing reservation. Failed attempts and actual use remain in the report.

Candidate retrieval is advisory. `--aliases` loads reviewed synonyms tied by `alias_review_digest` to a family contract. Alternatively, `--rag-catalogue RAG.toml` loads `eal2-rag-candidates/1` snippets tied to local UTF-8 source bytes, family case, claim and review digest. The two CLI options are mutually exclusive. The RAG catalogue limits each source to 64 KiB, each snippet to 2 KiB/256 searchable words and the corpus to 128 documents; it verifies local file identity and ranks with BM25. A Python host may inject compatible, reviewed document/query vectors and an explicit query embedder; positive cosine signal is fused with lexical ranks, not interpreted as probability. The optional `OpenAIEmbeddingAdapter` implements the [embedding request contract](https://developers.openai.com/api/reference/resources/embeddings/methods/create) and records attempts and provider usage if configured; the CLI invokes no embedding API. Retrieval never supplies a binding or authorises collection. New wording, even a close paraphrase, needs its own reviewed question entry. Neither a matching digest nor a high retrieval score establishes evidence truth or the relevance of an omitted family.

The host checks input identity and local consistency; it does not authenticate a physical evidence producer, prove the author included every required observation, or validate the causal warrant. A live deployment needs trusted collection, coherent object identities and reassessment at the decision time. The [API load-test example](../examples/api-load-test/README.md) shows the current executable path with synthetic data and explains how to substitute an identified measurement report. Comparative benefits over a similarly capable JSON checker remain a hypothesis.

## Verification and sources

The subprocess MCP, host and extension regressions exercise protocol initialisation, tool discovery, schema rejection, observation binding, principal/assessment identity and checked status recovery. The interface's official [MCP, SDK and provider sources](sources.md#model-host-and-provider-interfaces) describe protocol behaviour; those specifications do not measure an EAL/2 advantage. The [argument model](argument-model.md) and [reasoning methods](reasoning-modes.md) define the meanings of results delivered through this interface.
