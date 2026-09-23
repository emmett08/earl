# MCP, tools and model hosts

The MCP server uses the official Python SDK pinned to 1.30.0. A real subprocess client/server test exercises the published 2025-11-25 protocol lifecycle, tool discovery and structured calls. The server is a local stdio service. HTTP deployment, authentication and external LLM-provider integration are not included.

| Tool | Input | Operation |
|---|---|---|
| `eal_validate` | `source` | Parse and check language structure, references and method contracts |
| `eal_collect` | `source`, `context`, optional `evidence_ids` | Run configured collectors and persist observations; return `collection_id` |
| `eal_reason` | `source`, `context`, optional `collection_id`, `now` | Compute method results and argument conclusions; persist and return `assessment_id` |
| `eal_explain` | `assessment_id`, optional `claim` | Retrieve the reasoning result and dependencies |
| `eal_grounded` | `arguments`, `attacks` | Calculate grounded labels for an explicit attack graph |

Run `eal-mcp --workspace /absolute/path/to/earl --registry /absolute/path/to/earl/examples/tools.toml`. The default database is `.eal/runs.sqlite3` under that workspace; `--database` overrides it. Keep stdout for MCP protocol messages. The CLI uses the same service and takes the same three global options before the subcommand.

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

The executable receives a single JSON object on stdin: `evidence_id`, `input`, `environment` and `context`. It emits one JSON object containing `value`, with optional `observed_at`, `context` and `details`. A nonzero exit, invalid JSON, unknown output fields, a mismatched context, timeout or excessive output produces a stored error observation. Configured commands are trusted host programs, not a process sandbox; choose those commands accordingly. The source itself cannot supply executable paths or shell syntax. Command execution currently requires POSIX.

A `json_file` binding uses `path` instead of `argv`. Paths resolve within the workspace. File observations require both `observed_at` and `context`; rereading a file preserves its original age. A live command that returns historical measurements must also supply the original `observed_at` rather than relying on ingestion time. `details` can hold model identity, solver configuration, source data identity or sampling settings.

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

`eal-host` validates the operation and fields, starts the MCP server using the SDK client, calls the corresponding tool and returns structured JSON. Requests for `validate`, `collect` and `reason` contain source text rather than source filenames; the CLI accepts filenames. `collect` returns an identifier that the model application can include in a later `reason` request. Each host invocation opens a protocol session; the database preserves results between invocations.

The application must provide the loop that sends the host’s output back to its model. This mechanism works with a model that can generate the required JSON even if its API lacks native tool calling. It does not assume that arbitrary model prose is a valid instruction or that the model can contact MCP unaided.

Source text and result strings are data. The host accepts one schema-conforming request; it does not execute explanatory prose, accept invented operation names or reinterpret multiple concatenated requests.
