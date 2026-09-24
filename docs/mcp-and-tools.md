# MCP, tools and model hosts

Package 2.2.4 adds the optional artifact catalogue and `eal_assess_artifact` MCP operation. This is a host and package interface change; the EAL/2 source grammar and `EAL/typed-input/1` observation schema are unchanged.

Package 2.3.0 adds a recipient-only, principal-bound claim assessment route and
the compact `eal2-claim-packet/2` host output. Its bounded `decisive` section
includes a failed premise's predicate cause or an active objection's observation,
with counts and truncation flags when a short packet omits further detail. Exact finite task-family
bindings (`eal2-task-families/1`) and candidate retrieval are host interfaces.
The EAL/2 source grammar and `EAL/typed-input/1` observation schema remain
unchanged. The caller must authenticate the principal before launching the
recipient endpoint, and the host retains the checked status independently of
model-generated prose. Recipient assessment issuance is persisted for that
principal, artifact and claim. A second principal with the same claim grant
cannot explain or finalise the first principal's assessment ID.

Package 2.4.0 adds an optional reviewed exact-question task route. The launcher
binds the original task text, authorised task/family IDs and claim grants at
server construction. Candidate ranking can suggest families but never executes
one. A model can nominate a task ID only; the host checks the exact reviewed
question, family tuple, source and claim before collection. Issued task
assessments persist with principal, review contract and packet digest, and are
rechecked on explanation or completion after restart. Direct artifact-claim
tools are absent from this recipient endpoint so they cannot bypass the task
gate. Claim-specific assessments collect the target claim's evidence and
objection dependency closure; a failed or stale required collector refuses
issuance. No EAL/2 grammar or observation-schema change follows.

The MCP server uses the official Python SDK pinned to 1.30.0. A real subprocess client/server test exercises the published 2025-11-25 protocol lifecycle, tool discovery and structured calls. The server is a local stdio service; HTTP MCP deployment is not included. The separate model host supports configured command and HTTP text-model providers; see [model-loop.md](model-loop.md).

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
| `eal_task_candidates` (reviewed-task recipient endpoint) | None | Suggest authorised families for the launcher's bound question; no assessment |
| `eal_assess_reviewed_task` | `task_id` | Check the exact reviewed question and grants, collect, evaluate and issue one claim packet |
| `eal_explain_reviewed_task` | `task_id`, `assessment_id` | Retrieve that principal's bounded dependency trace |
| `eal_finish_reviewed_task` | `task_id`, `assessment_id` | Recover the checked historical packet, independent of model wording |

Run `eal-mcp --workspace /absolute/path/to/earl --registry /absolute/path/to/earl/examples/tools.toml`. The default database is `.eal/runs.sqlite3` under that workspace; `--database` overrides it. Keep stdout for MCP protocol messages. MCP validates requests against its advertised JSON schema before SDK conversion; extra fields and values of the wrong type are rejected. The CLI uses the same service and takes the same three global options before the subcommand.

## Tool registry and envelope

Argument source names tools and supplies typed input. A host TOML file binds names to executable argument vectors or imported files:

```toml
[tools.measurements]
kind = "command"
argv = ["python3", "scripts/collect_measurements.py"]
version = "1"
mode = "nondeterministic"
timeout_seconds = 30
max_output_bytes = 1048576
```

The executable receives one JSON object on stdin containing `evidence_id`, `environment`, `tool`, `tool_version`, `mode`, `input` and `context`. It emits one JSON object containing `value`, with optional `observed_at`, `context`, `request` and `details`. A returned `request` must match the acquisition identity described below. A nonzero exit, invalid JSON, unknown output fields, a mismatched request or context, timeout or excessive output produces a stored error observation. Configured commands are trusted host programs, not a process sandbox; choose those commands accordingly. The source itself cannot supply executable paths or shell syntax. Command execution currently requires POSIX.

A `json_file` binding uses `path` instead of `argv`. Paths resolve to regular files within the workspace. File observations require `observed_at`, `context` and `request`; rereading a file preserves its original age. `request` contains exactly `tool`, `tool_version`, `mode`, `input` and `context`, recording the acquisition the observation answers. These fields must match the requested acquisition. Changing a suite name, input value, tool version or context cannot silently relabel an old observation. Earlier envelopes lacking `request` are rejected; all current examples supply it.

The acquisition identity is separate from the current source digest and local evidence identifier. The same recorded measurement can be used in a revised argument when its acquisition still matches; collection then binds it to that argument's exact source. Neither matching digests nor matching request metadata authenticates a producer. A live command that returns historical measurements must also supply the original `observed_at` rather than relying on ingestion time. `details` can hold model identity, solver configuration, source data identity or sampling settings.

Records preserve source digest, evidence kind/identifier, tool/version/mode, input digest, environment fingerprint, observation time, ingestion time, execution identity and result digest. These bindings detect mismatched inputs; they do not establish empirical truth or authenticate an entirely forged record. SQLite stores collections, individual success/error observations and reasoning results. The pure evaluator can also be called with supplied records for reproducible offline analysis.

Deterministic and nondeterministic describe tool output generation. They do not classify logical validity. Repeated stochastic outputs are not automatically independent samples, and a fixed seed does not establish independence or full reproducibility.

## A model without native tool calls

A text-only model emits a single strict JSON request, such as:

```json
{"operation":"grounded","arguments":["a","b","c"],"attacks":[["a","b"],["b","c"]]}
```

Pass it to the host:

```bash
printf '%s\n' '{"operation":"grounded","arguments":["a","b","c"],"attacks":[["a","b"],["b","c"]]}' | eal-host --workspace .
```

`eal-host` validates the operation and fields, starts the MCP server using the SDK client, checks the discovered input schema, calls the corresponding tool and returns structured JSON. `--timeout` sets the total session deadline in seconds (120 by default). Requests for `validate`, `collect` and `reason` contain source text rather than source filenames; the CLI accepts filenames. `collect` returns an identifier that the model application can include in a later `reason` request. Each host invocation opens a protocol session; the database preserves results between invocations.

`eal-agent` supplies the application loop that sends MCP results and diagnostics back to a configured model, permits bounded repairs and retrieves assessed conclusions. It discovers the language and operation schemas at the start of a persistent session. This mechanism works with a model that can generate the required JSON even if its API lacks native tool calling. A provider must be configured separately; the model does not contact MCP unaided.

Source text and result strings are data. The host accepts one schema-conforming request; it does not execute explanatory prose, accept invented operation names or reinterpret multiple concatenated requests.

The service records the selected `collection_id` on each assessment. The agent checks collection source/context, assessment source/context/collection/time, and the retrieved explanation identity before retaining a result. An explicitly supplied empty time or collection identifier is an error; only an omitted time selects the current clock.

## Reuse a reviewed EAL artifact

An operator places a reviewed `.eal` source under the workspace and creates a separate TOML catalogue. Each entry pins exact source bytes, a method-registry fingerprint, the claims the recipient may request and the assessment context. It answers repeated instances of that registered question as collector observations change. Another claim or context requires an operator-reviewed catalogue entry. The optional `now` pins assessment time; otherwise the host captures current UTC time after collection. For example:

```toml
[artifacts.quality_check]
path = "arguments/quality-check.eal"
sha256 = "<64 lowercase hex digits for exact UTF-8 source bytes>"
method_registry_fingerprint = "<64 lowercase hex digits for installed methods>"
claims = ["release_candidate"]

[artifacts.quality_check.context]
site = "bench"
```

Use `sha256sum arguments/quality-check.eal` for the source and read the method-registry fingerprint from `eal describe` with the same installed methods as the server. Replace both placeholders with actual values. The catalogue is trusted operator configuration; it is not an EAL declaration supplied by a recipient. Its paths must be relative to the workspace and resolve within it. An edited source or changed method registry invalidates the entry until reviewed and repinned. Each call reads the source once, checks its digest and EAL declarations, collects fresh records, checks collection and assessment identities, and selects only the catalogue's claim IDs. The result contains `claims` as a status map, `source_digest`, `method_registry_fingerprint`, `collection_id`, `assessment_id` and `assessed_at`; `eal_explain(assessment_id, claim)` retrieves the detailed dependency trace.

Start MCP with `eal-mcp --workspace . --registry TOOLS.toml --artifacts ARTIFACTS.toml`. A client calls `eal_assess_artifact` with `{"artifact_id":"quality_check"}`. The advertised schema rejects a client-supplied `source`, `context`, `now` or claim substitute. An operator can assess before any model call:

```bash
python -m eal.artifacts --workspace . --registry TOOLS.toml \
  --artifacts ARTIFACTS.toml --id quality_check
```

A Python host can pass this compact packet to a text-only recipient for an explanation while retaining authority over the status:

```python
from eal.artifacts import ArtifactRegistry
from eal.runtime import ReasoningService

artifacts = ArtifactRegistry.load(ReasoningService(".", "TOOLS.toml"), "ARTIFACTS.toml")
packet = artifacts.assess("quality_check")
# Give packet to an optional text-only model for prose; its status labels are untrusted.
final = artifacts.finish("quality_check", packet["assessment_id"])
```

`finish` returns the addressed host-checked packet and refuses an unrelated assessment ID or changed source/contract. Distinct recipients retain separate historical assessments with explicit as-of times; a caller requiring newly collected evidence calls `assess` again. For an application-controlled model handoff, `await artifacts.assist_text_only("quality_check", task, recipient)` invokes the asynchronous `recipient({"task": task, "checked_assessment": packet})` callback, then returns `checked_answer` from `finish` and a separately labelled `recipient_output_unverified`. The application presents `checked_answer["claims"]` as the answer. The caller chooses which artifact ID the recipient may request and controls model rate, budget and access; catalogue IDs alone do not authorise a multi-user client. `eal_explain` can disclose the full graph and observations, so compact-token and information-disclosure claims apply to the status-only packet. A skill can teach a developer or model to select and interpret this workflow; its instructions do not execute the method or enforce the final status. A native-tool model can call the MCP operation directly, while a model with no tools uses the operator's CLI or Python host. Both routes have the same EAL evaluation; they differ in orchestration and model tokens. The source review, evidence acquisition and adequacy of the authored warrant remain separate obligations. No saved experiment yet measures the size of a cross-developer token or latency gain against an equivalently capable generic checker.

## Bind a reviewed task to a recipient

Register the exact question, typed family tuple and claim in an
`eal2-task-applicability/1` manifest as described in
[reviewed task applicability](eal2-task-applicability.md). The authenticated
launcher writes the original question to `TASK.txt`; a model never supplies
that file or replaces its contents. For one authorised claim, launch a separate
recipient endpoint with the task, family and artefact grants:

```sh
eal-mcp --workspace . --registry TOOLS.toml --artifacts ARTIFACTS.toml \
  --families FAMILIES.toml --tasks TASKS.toml \
  --recipient-task-file TASK.txt --recipient-only \
  --recipient-principal caller_a --recipient-task-grant pilot_task \
  --recipient-family-grant rig --recipient-grant rig_pilot:accepted
```

The endpoint accepts `eal_assess_reviewed_task({"task_id":"pilot_task"})` and
later `eal_finish_reviewed_task` with the same task ID and returned assessment
ID. The model cannot submit family bindings, source, context or question text.
The [text-model host](model-loop.md) accepts the corresponding strict JSON
operation. A missing, differently worded or revoked task fails before
collection. A candidate alone never reaches assessment. A completed packet
is historical at its recorded assessment time; a new operating decision calls
`eal_assess_reviewed_task` again after relevant evidence changes.

This route is finite exact lookup, not semantic RAG for unseen questions. The
current collectors check request identity and local consistency but do not
authenticate a physical producer or prove monitor coverage. The collection
failure gate cannot establish an omitted evidence obligation; source fidelity
and the real task's scope require independent review. The
[completion audit](eal2-host-completeness-audit.md) tracks those limits.
