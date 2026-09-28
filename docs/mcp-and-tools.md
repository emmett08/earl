# MCP, tools and model hosts

The MCP server exposes the EAL/2 interpreter through a local stdio service. It uses the official Python SDK pinned to 1.30.0; its subprocess test negotiates the 2025-11-25 protocol profile. The package also provides a CLI, a strict JSON host for text-only models, an interactive model host and optional operator-reviewed artefact and question routes. The [source grammar](../grammar/EAL.g4) declares a tool name and version; acquisition records identify its host binding. The source version `EAL/2`, package version `2.14.0`, persisted observation schema `EAL/observation-record/1`, formal method input envelope `EAL/typed-input/1` and compact projection `EAL/assessment-packet/1` identify separate contracts. The [API load-test example](../examples/api-load-test/README.md) exercises CLI and MCP paths over one synthetic request report; it reports no model-comparison result. The [live API experiment](../experiments/api_load_test/README.md) separately executes the configured collector against a real local HTTP service and compares model decisions, with JSON and prose using direct collection without MCP.

## Contents

1. [MCP operations](#mcp-operations)
2. [Tool registry and observation identity](#tool-registry-and-observation-identity)
3. [Text-model hosts and provider configuration](#text-model-hosts-and-provider-configuration)
4. [Reviewed artefacts and bounded recipients](#reviewed-artefacts-and-bounded-recipients)
5. [Reviewed question and retrieval](#reviewed-question-and-retrieval)
6. [Reusable argument procedures](#reusable-argument-procedures)
7. [Verification and sources](#verification-and-sources)

## MCP operations

| Tool | Input | Operation |
|---|---|---|
| `eal_describe` | None | Discover language versions, syntax, method schemas and typed binding contracts |
| `eal_format` | `source` | Return canonical checked source, its digest and whether changed bytes require a new collection |
| `eal_validate` | `source` | Parse and check language structure, references and method contracts |
| `eal_plan` | `source`, `claim` | Return the claim's complete support, alternative, objection and defence evidence plan without collection |
| `eal_collect` | `source`, `context`, optional `evidence_ids` | Run collectors explicitly granted for general model access; persist observations and return `collection_id` |
| `eal_collect_claim` | `source`, `context`, `claim` | Plan and collect every evidence declaration capable of affecting that claim; return the plan and collection |
| `eal_reason` | `source`, `context`, optional `collection_id`, `now` | Compute method results and argument conclusions; persist and return `assessment_id` |
| `eal_compile_aspic` | `source`, `context`, `collection_id`, `goal`, optional `now` | Derive and solve an opt-in bounded ASPIC+ snapshot from authored EAL routes and a matching stored collection; return both formal and authored statuses with a source map |
| `eal_explain` | `assessment_id`, optional `claim` | Retrieve the reasoning result and dependencies |
| `eal_packet` | `assessment_id`, optional `claim` | Return a bounded claim-focused result with method, binding and objection statuses; full explanation remains retrievable |
| `eal_grounded` | `arguments`, `attacks` | Calculate grounded labels for an explicit attack graph |
| `eal_sources` (with `--known-entry`) | optional `limit`, `offset` | List the host-selected registered EAL files and claims |
| `eal_find_claims` (with `--known-entry`) | optional `query`, `claim`, `limit` | Search metadata of the host-selected entries |
| `eal_assess_known` (with `--known-entry`) | `entry_id`, `claim` | Reuse compatible observations, collect missing ones, assess and return one bounded packet for a selected registered claim |
| `eal_assess_artifact` (only with `--artifacts`) | `artifact_id` | Read one host-pinned EAL file, collect, evaluate and return its configured claim statuses with assessment ID |
| `eal_assess_artifact_claim` (with `--artifacts`, outside reviewed-task route) | `artifact_id`, `claim` | Issue one bounded checked claim packet, subject to recipient grants |
| `eal_explain_artifact_claim` | `artifact_id`, `assessment_id`, `claim` | Retrieve that packet's direct dependency trace |
| `eal_finish_artifact_claim` | `artifact_id`, `assessment_id`, `claim` | Recover the checked packet independently of recipient prose |
| `eal_task_candidates` (reviewed-task recipient endpoint) | None | Suggest authorised families for the launcher's bound question; no assessment |
| `eal_bound_task` | None | Resolve the exact reviewed question and grants; return the route and question digest without collection |
| `eal_assess_bound_task` | None | Collect, evaluate and issue one claim packet for that route |
| `eal_explain_bound_task` | `assessment_id` | Retrieve that principal's bounded dependency trace |
| `eal_finish_bound_task` | `assessment_id` | Recover the checked historical packet under the same question and grant |
| `eal_resolve_prose` (with `--schemes`) | `prose`, optional `context`, `proposal`, `routing_candidate` | Select a reviewed argument form and typed bindings without running collectors |
| `eal_assess_prose` (with `--schemes`) | `prose`, optional `context`, `proposal`, `routing_candidate` | Collect and assess the selected form with explicit correspondence and adequacy obligations |
| `eal_resolve_bound_prose` (recipient schemes) | None | Resolve the launcher's bound original prose without collection |
| `eal_assess_bound_prose` (recipient schemes) | None | Run the checked assessment for the launcher's bound original prose |
| `eal_finish_prose` (with `--schemes`) | `assessment_id` | Recover the checked result for the bound principal and session |

Run `eal-mcp --workspace /absolute/path/to/earl --registry /absolute/path/to/earl/examples/api-load-test/tools.toml --methods eal.api_load_methods:registry` for the maintained load-test source. The default database is `.eal/runs.sqlite3` under that workspace; `--database` overrides it. Keep stdout for MCP protocol messages. The server checks advertised JSON schemas before SDK conversion, rejecting extra fields and incorrect types. The CLI uses the same service and accepts `--workspace`, `--registry`, `--database` and an optional host-registered `--methods` factory before its subcommand. The server uses stdio; HTTP MCP deployment is not included.

`eal plan SOURCE.eal --claim CLAIM` reports required evidence IDs in declaration order, including alternative derivations, transitive premises, backing, assumption validation and objections to objections. `eal collect SOURCE.eal --context JSON --claim CLAIM` executes that plan. `eal packet ASSESSMENT_ID --claim CLAIM` gives a compact projection; `eal explain` retains the full persisted result. These operations use the same static validator, method registry and authored argument graph. `eal reason` and `eal compile-aspic` refuse a collection whose exact source bytes or context differ from the assessment request.

A developer can register a source once using `eal register SOURCE.eal --context JSON`, then use `eal sources`, `eal find QUERY` and `eal assess-known ENTRY_ID --claim CLAIM` in later processes. The Python `EALKnowledgeBase` exposes the same catalogue, one-call assessment and indexed history. `ModelContextAdapter.prepare(question, entry_id, claim)` sends a bounded checked packet to a text-only model while the host performs collection and reasoning. A model-facing MCP server exposes only the three registered-source operations when its trusted launcher selects entries with repeated `--known-entry ENTRY_ID` options. `eal-host --known-entry ENTRY_ID` forwards the same selection for strict JSON text requests. Requests cannot register new files, change the default context, retrieve raw explanations or select an unexposed entry. Its caller still selects the exact claim; metadata search is only advisory. Use a separate operator server for raw source operations.

For a hand-authored formal theory, install the [finite ASPIC+ method](aspic-method.md) with `--methods eal.aspic:aspic_registry`; discovery then advertises its exact versioned input and output contract. For a source containing ordinary EAL arguments and objections, call `eal_compile_aspic` after `eal_collect`, using the returned `collection_id` and a declared goal claim. The CLI equivalent is `eal --workspace . --registry TOOLS.toml compile-aspic SOURCE.eal --context '{"site":"bench"}' --collection COLLECTION_ID --goal CLAIM --now 2026-09-25T10:00:30Z`. Reviewed top-level EAL `strict`, `rank` and `contrary` relations are optional; the target kind follows from the named declaration. Compilation checks the collection's source and context, current collector bindings and evidence eligibility; it does not collect again or replace an ordinary EAL assessment. Its returned `formal` result and `authored_claim_status` should be read together with `source_map`. The [synthetic companion](aspic-method.md#compile-authored-eal-routes) gives commands with a matching source, registry and context.

To inspect the returned argument structure, save the complete compilation JSON and run `eal --workspace . export-aspic RESULT.json --output VIEW.json`. Load the exported `aspic-view/2` file in the separate [visualisation app](https://github.com/emmett08/aspic_visualisation). Export recomputes the formal theory and checks the supplied result; the app shows direct derivations, defeats and their witnesses, grounded labels, typed availability issues and supplied declaration/observation origins in one interactive graph. Snapshot import events make changes inspectable. Neither operation collects observations or changes the default evaluator.

## Tool registry and observation identity

Argument source names tools and supplies typed input. A host TOML file binds names to executable argument vectors or imported files:

```toml
[tools.load_test_report]
kind = "command"
argv = ["python3", "examples/api-load-test/collect_results.py"]
version = "1"
model_access = "general"
timeout_seconds = 10
max_output_bytes = 16384
pinned_files = [{path = "examples/api-load-test/collect_results.py", sha256 = "d7978f0c4dbd6577b24e33035a7ec021aa4886cf7a8c390a970084f0179876e2"}]
```

The executable receives one JSON object on stdin containing `evidence_id`, `environment`, `tool`, `tool_version`, `input` and `context`. It emits one JSON object containing `value`, with optional `observed_at`, `context`, `request` and `details`. A returned `request` must match the acquisition identity described below. A nonzero exit, invalid JSON, unknown output fields, a mismatched request or context, timeout or excessive output produces a stored error observation. Collection preflight limits context JSON to 16 KiB, the selected set to 128 evidence IDs, each request to 1 MiB and the sum of configured output allowances to 128 MiB. Final collection JSON is limited to 32 MiB; an over-limit result leaves individual durable observations but issues no collection ID. Configured commands run as trusted host programs with host access; the command adapter requires POSIX and does not sandbox the command. EAL source cannot supply executable paths, shell syntax or credentials.

`model_access` is an operator-owned TOML grant: its default, `"reviewed"`, excludes a binding from generic model-authored `eal_collect` and `eal_collect_claim`; `"general"` explicitly permits those calls. The entire selected set is checked before any collector executes. A developer-selected registered file and claim can use the host's configured tools through the Python/CLI path; a model-facing MCP server requires a trusted `--known-entry` allowlist and registered context. Reviewed artefact and recipient routes retain their separately bound source and principal checks. `parallel_safe = true` is an operator assertion that the collector is read-only and independent of other such calls. The default is serial. The bounded scheduler overlaps only consecutive approved calls, retains each `evidence_id` in the command request and returns records in selected order. A claim plan selects IDs in declaration order; an explicit ID list keeps its requested order. Neither access nor scheduling policy appears in EAL source or contributes to keyed acquisition identity.

Command bindings can set `inherit_env = ["PATH", "KUBECONFIG"]` to select the inherited environment variables needed by the collector; explicit `env` entries are added. The effective values contribute to a keyed process-environment digest used for reuse. By default, the full inherited process environment is passed and hashed, so any change conservatively prevents reuse. Include all credentials and execution dependencies when narrowing inheritance. File imports do not spawn a process.

A `json_file` binding uses `path` instead of `argv`. Paths resolve to regular files within the workspace. File observations require `observed_at`, `context` and `request`; rereading a file preserves its original age. `request` contains exactly `tool`, `tool_version`, `input` and `context`, recording the acquisition the observation answers. These fields must match the requested acquisition. Changing a suite name, input value, tool version or context cannot silently relabel an observation.

The acquisition identity is separate from the source digest. `eal rebind SOURCE.eal --context JSON --from-collection COLLECTION_ID` explicitly binds successful `EAL/observation-record/1` measurements to revised source only when evidence ID, environment, input, request, context, evidence kind, current tool binding and command process-environment identity match. It creates new observation and collection IDs, records origin IDs and preserves original observation time. It never runs a collector or refreshes an observation's age; reasoning checks freshness and predicates under the revised source. An indexed candidate lookup supports this explicit operation, without automatically coalescing same-looking tool calls. A collector can depend on the `evidence_id` sent to it, so cross-ID reuse is excluded. Matching metadata checks correspondence and does not authenticate a producer. A live command returning historical measurements supplies original `observed_at`. `details` can hold non-secret source and execution metadata.

The operator CLI `eal invalidate --kind event|gap --reason TEXT` marks stored measurements ineligible for later rebinding. `--origin-run-id ID` targets an observation lineage; `--binding-digest DIGEST` targets a configured collector, with optional `--request-digest DIGEST` for one acquisition request. `--all` records a reconnect gap across bindings. Origin events continue to exclude their lineage. Scoped events and gaps exclude previously recorded or in-flight observations, while a fresh authoritative acquisition begun and observed afterwards remains eligible. This operation neither collects evidence nor rewrites historical assessments. It has no model-facing MCP equivalent.

`EAL/observation-record/1` records preserve source digest, evidence kind/identifier, tool/version, `tool_binding_digest`, input digest, environment fingerprint, original observation time, ingestion time, execution identity and result digest. Success and failure records retain output digests and byte counts but do not expose raw stdout or stderr. Older unversioned records may still be supplied for evaluation where their other checks pass, but are ineligible for new rebinding. The trusted host computes a store-local, keyed HMAC identity from the selected TOML configuration and checks it again when reasoning over a stored collection. A command binding may list up to 32 `pinned_files` with workspace-relative or absolute paths and reviewed SHA-256 values. It checks each regular file (at most 16 MiB) before and after collection, and again on reasoning and finalisation. A missing or changed pin refuses collection or invalidates reuse. The operator pins the executable, scripts and dependencies relevant to the deployment; pins do not discover imported code or prevent replacement between checks and execution. The example pins its collector script. The command adapter also records a keyed `process_environment_digest`; neither field exposes an unkeyed hash of configured environment values. The private `<database>.binding-key` sidecar remains private and travels with SQLite if stored collections must remain assessable after moving it. A database copied without that key receives a new identity and its old collections lose current-binding support. The pure evaluator requires a well-formed identity field; given only a record, it cannot independently select or authenticate the registry binding. Digests neither establish empirical truth nor authenticate an entirely forged record. SQLite stores collections, individual success/error observations and reasoning results. The pure evaluator can also be called with supplied records for reproducible offline analysis.

Tool output variability depends on the algorithm, actual input bytes, external state, sampling procedure and execution environment. An authored binary label cannot certify repeatability: a deterministic algorithm can read changing data, while a stochastic algorithm may replay a recorded seed and input. If a conclusion requires reproducibility or independent samples, put the exact data, seed, execution dependencies and sampling obligations in a reviewed tool/evidence contract and check them through appropriate observations. Neither a matching tool binding digest nor repeated equal outputs establishes those properties.

## Text-model hosts and provider configuration

A text-only model emits a single strict JSON request, such as:

```json
{"operation":"grounded","arguments":["a","b","c"],"attacks":[["a","b"],["b","c"]]}
```

Pass it to the host:

```bash
printf '%s\n' '{"operation":"grounded","arguments":["a","b","c"],"attacks":[["a","b"],["b","c"]]}' | eal-host --workspace .
```

`eal-host` validates the operation and fields, starts the MCP server using the SDK client, checks the discovered input schema, calls the corresponding tool and returns structured JSON. `--timeout` sets the total session deadline in seconds (120 by default). Requests for `validate`, `plan`, `collect`, `collect_claim` and `reason` contain source text rather than source filenames; the CLI accepts filenames. `collect` and `collect_claim` return identifiers for later `reason`; `packet` retrieves a bounded projection of a stored assessment. Each host invocation opens a protocol session; the database preserves results between invocations.

`eal-agent` starts one MCP session, discovers the tools and language description, gives the operation schemas to a configured model, validates each request, and returns diagnostics for bounded repairs. Its default stateful mode retains exact source bytes, context, collection and assessment identifiers. Once the caller supplies `initial_data.source` (immutable) or `draft_source` (revisable) with context, `{"operation":"assess"}` validates, collects a fresh complete closure for the required claim, reasons and retrieves an `EAL/assessment-packet/1`; `{"operation":"finish"}` returns the latest checked statuses. For several required claims, the host collects the union of their plans and returns individual packets under `EAL/assessment-packet-set/1`. With no required claim it collects every declared evidence ID. An invalid source stops before acquisition, and a source/context revision invalidates prior collection and assessment defaults. `--host-mode stateless` requires explicit source and identifiers on successive requests. `--interaction-mode native` uses a configured provider's native function calls, but all calls pass through the same host checks; model size or native calling does not imply reasoning quality.

For a configured command or HTTP text provider, run `eal-agent --provider PROVIDER.toml --task TASK.txt --initial-data INPUTS.json --claim performance_criteria_met --workspace . --registry examples/api-load-test/tools.toml --output REPORT.json`. Provider identity, sampling and model capabilities must be explicit; credentials stay in the host environment. `--unaided` invokes the same provider without MCP and labels the answer unverified. `AgentBudget` bounds attempts, repairs, tool calls, time and reported token/cost use. A provider may exceed a requested token or cost allowance before reporting it; unknown use is retained as unknown, and exceeding or unknown use prevents a budget-verified completion. A command adapter runs a trusted operator-selected argv, without a shell, using the host's access. The HTTP adapter implements configured Chat Completions style text, native calls and optional JSON output; only explicitly configured model capabilities are used. A caller must check the actual provider endpoint's parameter support.

Source text and result strings are data. The host accepts one schema-conforming request; it does not execute explanatory prose, accept invented operation names or reinterpret multiple concatenated requests.

For a closed operation schema, the HTTP and Responses adapters advertise the provider's strict function or structured-output form. They mark every property required and represent a host-optional field as nullable, then remove that transport-only null before applying the original host schema. Bounds and other constraints unsupported by the provider schema remain host checks. An open or ambiguously nullable host schema uses explicit non-strict provider mode and the same host validation. The provider response must still contain one complete operation; multiple assistant messages and truncated output cannot supply evidence. The API load-test experiment advertises report inspection before acquisition and the completion operation only after a successful inspection.

The service records the selected `collection_id` on each assessment. The agent checks the claim plan and collection source/context, assessment source/context/collection/time, and packet identities and claim statuses before retaining a result. An explicitly supplied empty time or collection identifier is an error; only an omitted time selects the current clock. `initial_data.source`, context and time anchor the engineering question; a `draft_source` can be revised, but preserving its intended meaning remains unverified until an independent task check. Automatic assessment sends bounded packets and collection metadata to the model. Explicit `reason` or `explain` calls in this agent also project model feedback to bounded packets; the operator's stored full explanation remains available through `eal_explain`. The final host result derives checked statuses from the latest successful server assessment, including `unsupported`, `contested` and `out_of_scope`; model prose cannot revise those statuses. Reports retain failed model attempts, actual tool calls and observed use. A completed tool loop is evidence of operation, not proof that the argument's authored warrant or collector is adequate.

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

Candidate retrieval is advisory. `--aliases` loads reviewed synonyms tied by `alias_review_digest` to a family contract. Alternatively, `--rag-catalogue RAG.toml` loads `eal2-rag-candidates/1` snippets tied to local UTF-8 source bytes, family case, claim and review digest. The two CLI options are mutually exclusive. The RAG catalogue limits each source to 64 KiB, each snippet to 2 KiB/256 searchable words and the corpus to 128 documents; it verifies local file identity and ranks with BM25. A Python host may inject compatible, reviewed document/query vectors and an explicit query embedder; positive cosine signal is fused with lexical ranks, not interpreted as probability. The optional `OpenAIEmbeddingAdapter` implements the [embedding request contract](https://developers.openai.com/api/reference/resources/embeddings/methods/create) and records attempts and provider usage if configured; the CLI invokes no embedding API. Retrieval never supplies a binding or authorises collection. Under this exact-question route, new wording, even a close paraphrase, needs its own reviewed question entry. The [argument-form route](#reusable-argument-procedures) covers reviewed parameterised phrasings with separate correspondence checks. Neither a matching digest nor a high retrieval score establishes evidence truth or the relevance of an omitted family.

The host checks input identity and local consistency; it does not authenticate a physical evidence producer, prove the author included every required observation, or validate the causal warrant. A live deployment needs trusted collection, coherent object identities and reassessment at the decision time. The [API load-test example](../examples/api-load-test/README.md) shows the current executable path with synthetic data and explains how to substitute an identified measurement report. Comparative benefits over a similarly capable JSON checker remain a hypothesis.

## Reusable argument procedures

The optional [argument host](executable-argument-host.md) uses a host-reviewed form catalogue to bind a later prose claim, decision or proposed action to EAL/2 source and a claim. Its TOML catalogue and the separate evidence-adequacy contract are operator-controlled; the model cannot supply an executable command, method implementation or lowered source. A form match or a model-proposed candidate alone does not establish that the prose means the same thing as the reviewed claim. The host records unresolved correspondence explicitly. A resolved request causes new tool collection and assessment. It delivers the scoped EAL status only after complete collection and `adequate` evidence checks; otherwise its checked answer remains `unresolved`. Principal and session identity bind the issued result across calls. Finalisation reevaluates current time and host binding identity, refusing a stale or changed assessment; the checked status remains separate from model-generated explanation.

An operator MCP process may expose `eal_resolve_prose(prose, context?, proposal?, routing_candidate?)`, `eal_assess_prose(...)` and `eal_finish_prose(assessment_id)`. To give a recipient model the reusable procedure without letting it substitute the user's original request, launch a separate process with `--schemes SCHEMES.toml --registry TOOLS.toml --recipient-only --recipient-principal USER --session-id SESSION --scheme-grant SCHEME --bound-prose-file REQUEST.txt`. It exposes only `eal_resolve_bound_prose()` and `eal_assess_bound_prose()` alongside session-bound `eal_finish_prose(assessment_id)`. A new request can use the same reviewed argument form and tools under the same principal/session, but needs a new binding and evidence assessment. The source, observation and adequacy identities are retained in the checked packet. The [CLI and contract](executable-argument-host.md#integration-contracts) explain the limits of recognition and guarded edits.

## Verification and sources

The subprocess MCP, host and extension regressions exercise protocol initialisation, tool discovery, schema rejection, observation binding, principal/assessment identity and checked status recovery. The interface's official [MCP, SDK and provider sources](sources.md#model-host-and-provider-interfaces) describe protocol behaviour; those specifications do not measure an EAL/2 advantage. The [argument model](argument-model.md) and [reasoning methods](reasoning-modes.md) define the meanings of results delivered through this interface.
