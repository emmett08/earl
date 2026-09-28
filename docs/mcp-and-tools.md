# MCP, tools and model adapters

The EAL/2 service connects an authored argument to configured collectors and versioned reasoning methods. A developer registers a validated `.eal` file and its claims once. Later prompt sessions and models can request a registered claim, reuse compatible observations and receive a checked packet without reconstructing the source. The same service has Python, CLI, MCP and strict JSON text-host interfaces. The [argument service](argument-service.md) defines claim planning and reuse; the [language reference](language.md) defines authored syntax.

## MCP operations

The operator server started without `--known-entry` exposes the explicit source operations:

| Tool | Input | Result |
|---|---|---|
| `eal_describe` | None | Language, method and binding contracts |
| `eal_format` / `eal_validate` | `source` | Canonical source or static checks |
| `eal_plan` | `source`, `claim` | Complete evidence plan for that claim |
| `eal_collect` | `source`, `context`, optional evidence IDs | Stored observations and `collection_id` |
| `eal_collect_claim` | `source`, `context`, `claim` | Plan and collect the claim's complete evidence closure |
| `eal_reason` | `source`, `context`, optional `collection_id`, `now` | Persisted method and argument assessment |
| `eal_packet` / `eal_explain` | `assessment_id`, optional `claim` | Compact model packet or full dependency trace |
| `eal_compile_aspic` | `source`, `context`, `collection_id`, `goal`, optional `now` | Optional compiled ASPIC+ snapshot |
| `eal_grounded` | Explicit argument and attack graph | Grounded labels |

For an exact registered source selected by the launcher, `eal-mcp --workspace . --registry TOOLS.toml --known-entry ENTRY_ID` exposes the following operations to the model. Repeat `--known-entry` for additional entries. The service uses the registered context and selected claims; clients cannot replace source or tool arguments through this route.

| Tool | Input | Result |
|---|---|---|
| `eal_sources` | Optional `limit`, `offset` | Registered file and claim metadata |
| `eal_find_claims` | Optional `query`, `claim`, `limit` | Advisory claim matches; the caller selects an exact entry and claim |
| `eal_assess_known` | `entry_id`, `claim` | Reuse eligible observations, collect missing ones, assess and return a bounded packet |

The default database is `.eal/runs.sqlite3` under `--workspace`; `--database` selects another path. The server uses stdio and keeps stdout for MCP protocol messages. Its advertised JSON schemas and host checks reject extra or incorrectly typed fields. The maintained [API load-test example](../examples/api-load-test/README.md) exercises CLI and MCP with synthetic records. It is a runnable example, not a model-performance measurement.

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

The Python `EALKnowledgeBase` provides the same operations. `ModelContextAdapter(kb).prepare(question, entry_id, claim)` assesses the selected claim and returns `EAL/model-context/1` with a checked assessment and bounded messages for a model without tools or reasoning. The application selects the exact entry and claim, sends the messages to the model, and retains the host's status and assessment ID. A free-form question does not itself select an argument.

The strict JSON `eal-host` accepts one schema-checked operation, calls the MCP server and returns structured JSON. Launch it with the same `--workspace`, `--registry` and `--known-entry` selection for a text-only model. For example, the model can emit `{"operation":"assess_known","entry_id":"load_test","claim":"performance_criteria_met"}`. The host executes that operation and returns the checked result; the model need not implement collection, freshness checks or a reasoning method. Each host invocation opens a new protocol session while the database retains registered entries and observations.

## Tool registry and observation identity

The EAL source declares `tool NAME { version "VERSION"; }` and an evidence declaration supplies an `input`, `kind`, environment and `max_age`. A sibling TOML registry chooses the collector:

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
