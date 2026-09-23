# MCP, tools and model hosts

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
