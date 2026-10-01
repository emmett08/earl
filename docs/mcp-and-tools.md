# MCP, tools and model adapters

The EAL/3 service connects an authored argument to configured collectors and versioned reasoning methods. A developer registers a validated `.eal` file and its claims once. Later prompt sessions and models can request a registered claim, reuse compatible observations and receive a checked packet without reconstructing the source. The same service has Python, CLI, MCP and strict JSON text-host interfaces. The [argument service](argument-service.md) defines claim planning and reuse; the [language reference](language.md) defines authored syntax.

## MCP operations

Operator exposure provides the explicit source operations. It is the default when no registered entries are selected:

| Tool | Input | Result |
|---|---|---|
| `eal_describe` | None | Language, method and binding contracts |
| `eal_format` / `eal_validate` | `source` | Canonical source or static checks |
| `eal_plan` | `source`, `claim` | Complete evidence plan for that claim |
| `eal_collect` | `source`, `context`, optional evidence IDs | Stored observations and `collection_id` |
| `eal_collect_claim` | `source`, `context`, `claim` | Plan and collect the claim's complete evidence closure |
| `eal_reason` | `source`, `context`, optional `collection_id`, `now` | Persisted method and argument assessment |
| `eal_packet` / `eal_explain` | `assessment_id`, optional `claim` | Compact model packet or full dependency trace |
| `eal_compile_aspic` | `source`, `context`, `collection_id`, `goal`, optional `now`, `semantics`, `query_mode`, `preference` | Optional compiled ASPIC+ snapshot |
| `eal_grounded` | Explicit argument and attack graph | Grounded labels |

For an exact registered source selected by the launcher, `eal-mcp --workspace . --registry TOOLS.toml --known-entry ENTRY_ID` exposes the following operations to the model. Repeat `--known-entry` for additional entries. The service uses the registered context and selected claims; clients cannot replace source or tool arguments through this route.

| Tool | Input | Result |
|---|---|---|
| `eal_sources` | Optional `limit`, `offset` | Registered file and claim metadata |
| `eal_find_claims` | Optional `query`, `claim`, `limit` | Advisory claim matches; the caller selects an exact entry and claim |
| `eal_assess_known` | `entry_id`, `claim` | Reuse eligible observations, collect missing ones, assess and return a bounded packet |

The default database is `.eal/runs.sqlite3` under `--workspace`; `--database` selects another path. FastMCP 4 exposes the same application operations over stdio and Streamable HTTP. Advertised JSON schemas and adapter checks reject extra or incorrectly typed fields before handler invocation. The maintained [API load-test example](../examples/api-load-test/README.md) exercises CLI and MCP with synthetic records. These executions verify the interface and finite calculations; model-performance measurements require model trials.

## Configure and launch the server

`eal-mcp --config FILE` reads trusted TOML configuration. This configuration chooses the service and transport independently of EAL source and the tool-binding registry:

```toml
[service]
workspace = "."
registry = "tools.toml"
database = ".eal/runs.sqlite3"
# methods = "package.module:registry"
# limits = "limits.toml"
# known_entries = ["readiness"]

[server]
transport = "stdio"
max_in_flight = 1

[server.http]
host = "127.0.0.1"
port = 8000
path = "/mcp"
# token_env = "EAL_MCP_TOKEN"
```

The server accepts only the documented tables and settings. Paths supplied by the file resolve relative to its parent directory. CLI and environment paths resolve relative to the current working directory. Precedence is **CLI > environment > TOML > defaults**. `--config` selects the file, with `EAL_MCP_CONFIG` as its environment alternative. A selected entry list replaces the lower-precedence list in full.

| TOML setting | CLI option | Environment variable | Default |
| --- | --- | --- | --- |
| `service.workspace` | `--workspace` | `EAL_MCP_WORKSPACE` | Current working directory |
| `service.registry` | `--registry` | `EAL_MCP_REGISTRY` | Empty tool registry |
| `service.database` | `--database` | `EAL_MCP_DATABASE` | Workspace `.eal/runs.sqlite3` |
| `service.methods` | `--methods` | `EAL_MCP_METHODS` | Built-in method registry |
| `service.limits` | `--limits` | `EAL_MCP_LIMITS` | Default `ExecutionLimits` |
| `service.known_entries` | Repeated `--known-entry` | `EAL_MCP_KNOWN_ENTRIES` (JSON array) | Empty selection |
| `server.transport` | `--transport` | `EAL_MCP_TRANSPORT` | `stdio` |
| `server.exposure` | `--exposure` | `EAL_MCP_EXPOSURE` | Inferred from selected entries |
| `server.max_in_flight` | `--max-in-flight` | `EAL_MCP_MAX_IN_FLIGHT` | `1` |
| `server.http.host` | `--host` | `EAL_MCP_HOST` | `127.0.0.1` |
| `server.http.port` | `--port` | `EAL_MCP_PORT` | `8000` |
| `server.http.path` | `--path` | `EAL_MCP_PATH` | `/mcp` |
| `server.http.token_env` | `--token-env` | `EAL_MCP_TOKEN_ENV` | Unauthenticated loopback HTTP |

An empty entry selection chooses `operator` exposure; a non-empty selection chooses `registered` exposure. Explicit exposure must agree with that selection. A registered endpoint admits only its configured IDs and their registered claims, and uses their stored context. Transport changes preserve the selected exposure and operation contracts.

Launch either transport using the self-contained example configuration:

```sh
eal-mcp --config examples/api-load-test/mcp.toml --transport stdio
```

```sh
eal-mcp --config examples/api-load-test/mcp.toml --transport http
```

Stdio reserves stdout for MCP messages and writes framework logs to stderr. HTTP serves `/mcp` on port 8000 by default. Each process serves one transport. Separate launches can make both available against the same local workspace and database; acquisition locking coordinates their collection. A stdio proxy to a central HTTP endpoint is another deployment option when clients require stdio and the application needs one service process. FastMCP provides proxy facilities; EAL's launcher implements direct transport selection.

## HTTP access and execution limits

Loopback HTTP permits unauthenticated access by local clients. For a non-loopback bind, supply `token_env` and set the named environment variable before launch. For example, a process started with `--transport http --host 0.0.0.0 --token-env EAL_MCP_TOKEN` reads its bearer credential from `EAL_MCP_TOKEN`. Configuration stores the variable name, and the composition root reads its value. Requests must provide the corresponding `Authorization: Bearer …` header. Use HTTPS at the deployment boundary when the credential traverses a network; the launcher runs a plain HTTP listener.

The credential authorises the endpoint's fixed exposure. An operator endpoint grants source-level operations over its configured workspace and stored results; a registered endpoint grants its selected catalogue and assessment operations. Each endpoint serves one host trust domain. Deploy separate workspaces/endpoints where callers need different access scopes. A fixed bearer credential requires operator-managed distribution and rotation; OAuth login and per-user data separation require an additional deployment design.

`max_in_flight` bounds admitted tool calls per process, defaulting to one. The workspace acquisition lock coordinates MCP collection and the registered-assessment reuse/collection decision across participating threads and server processes. Eligible `parallel_safe` collectors can overlap inside an acquisition. The lock covers local filesystem deployments; replicas on independent hosts and network filesystems need a distributed coordinator. Raising admission concurrency does not imply a measured throughput gain. See [MCP architecture](mcp-architecture.md) for the responsibilities and verification scope.

## Registered developer workflow

```sh
eal --workspace . --registry examples/api-load-test/tools.toml \
  --methods eal.api_load_methods:registry register examples/api-load-test/source.eal \
  --entry-id load_test --claim performance_criteria_met \
  --context '{"service":"orders-api","build_id":"demo-build-42","dataset":"synthetic"}'

eal --workspace . --registry examples/api-load-test/tools.toml \
  --methods eal.api_load_methods:registry assess-known load_test \
  --claim performance_criteria_met --now 2026-09-25T10:00:00Z
```

`register-tree DIRECTORY` scans a bounded directory of `.eal` files. `sources` lists validated entries and `find QUERY` searches claim metadata. `history ENTRY_ID` lists previous assessment identities. The first `assess-known` call collects a complete claim closure. A later call reuses eligible observations at their original measurement times and acquires only missing or expired ones. Each call creates an assessment for its chosen time, even when all measurements are reused. `--reuse fresh` requests fresh collection. `--context` on the Python or CLI assessment overrides the registered default context explicitly.

The Python `EALKnowledgeBase` provides the same operations. `ModelContextAdapter(kb).prepare(question, entry_id, claim)` assesses the selected claim and returns `EAL/model-context/2` with a checked assessment, a decision-focused context and bounded messages for a model without tools or reasoning. The context preserves bounded selected and premise claim statements, their `prose_verified` qualifications, computed negative results, bounded missing-field diagnostics and assumption applicability, while complete trace identities remain in the assessment. Authored statements identify propositions as task data; the formal evaluator does not verify their prose. Statement truncation records omitted bytes and makes the summary incomplete. The application selects the exact entry and claim, establishes their correspondence to the task, sends the messages to the model, and retains the host's status and assessment ID. A free-form question does not itself select an argument. The adapter does not require a structured model answer: output formatting belongs to the receiving application.

The strict JSON `eal-host` accepts one schema-checked operation, calls the MCP server and returns structured JSON. Its operation names omit the `eal_` prefix, including `compile_aspic` with the compiler's declared arguments. Launch it with the same `--config` or service options and `--known-entry` selection for a text-only model. For example, the model can emit `{"operation":"assess_known","entry_id":"load_test","claim":"performance_criteria_met"}`. The host executes that operation and returns the checked result; the model need not implement collection, freshness checks or a reasoning method. By default it launches a stdio subprocess. The workspace database retains registered entries and observations between requests.

With an HTTP server already running, the host connects to its configured URL:

```sh
eal-host --url http://127.0.0.1:8000/mcp <<'JSON'
{"operation":"describe"}
JSON
```

Add `--token-env EAL_MCP_TOKEN` for an authenticated endpoint. A configured `http` transport also connects to an existing server, using the configured host, port and path; a wildcard bind such as `0.0.0.0` requires an explicit client `--url`. An explicit URL overrides the configured transport. The server's launch configuration fixes its workspace, methods and tool exposure. The host validates the flat request and the discovered input schema before invoking the remote operation. The MCP client negotiates a supported protocol profile; EAL operation identities and persisted assessment bindings are independent of that profile.

## Tool registry and observation identity

The EAL source declares a `tool NAME` block containing `version "VERSION"` and an evidence declaration supplies an `input`, `kind`, environment and `max_age`. A sibling TOML registry chooses the collector:

```toml
[tools.load_test_report]
kind = "command"
argv = ["python3", "examples/api-load-test/collect_results.py"]
version = "1"
timeout_seconds = 10
max_output_bytes = 16384
```

The command receives a JSON object with `evidence_id`, `environment`, `tool`, `tool_version`, `input` and `context` on stdin. It emits one JSON object with `value` and optional `observed_at`, `context`, `request` and `details`. The collector may authenticate, query external systems, execute tests or aggregate data. Secrets and executable paths remain in the host configuration. A `json_file` binding uses a workspace path instead of a command and must supply its original observation time, request and context. Reading an old file again does not make its measurement new.

Collection accepts at most 128 selected evidence IDs, 16 KiB of context, 1 MiB per request and 128 MiB total configured output allowance. Final collection JSON is limited to 32 MiB. A command's own timeout and output limit are set in TOML. Configured commands run with host access and are not an operating-system sandbox. A tool failure, malformed output or mismatched identity is stored as an error observation; it does not support the opposite claim.

`parallel_safe = true` asserts that a command is independent and read-only; the default is serial. The scheduler overlaps eligible calls within bounded concurrency and preserves evidence IDs and result order. `inherit_env = ["PATH", "KUBECONFIG"]` limits which host environment variables enter a command; otherwise the command inherits the full process environment. Explicit `env` values are added. The effective process environment participates in reuse identity. Scheduling policy does not.

An acquired `EAL/observation-record/1` stores the exact evidence ID, source, request and context identity, evidence kind, environment, selected binding, original observation time, ingestion time and outcome. The host checks this record before reasoning or reusing it. A matching record cannot certify that the physical measurement is authentic or that the author included every necessary dependency. Compatible reuse checks the selected tool, command environment, input, context, kind and evidence ID; `max_age` is calculated from the original time. An assumption's `valid_from` and `valid_until` dates govern its applicability at assessment time. Expiring an assumption does not make its previous tool observation newer; recollecting cannot extend the declaration's date window. A registered assessment binds compatible older observations to its current exact source without changing their measured time.

The [reasoning modes](reasoning-modes.md) specify what each method accepts as evidence. The interpreter reports method output and authored argument status separately; the model packet conveys their scoped result. The full persisted explanation remains available through `eal_explain` or the CLI `explain` operation.
