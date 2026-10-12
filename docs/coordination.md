# Registered-task coordination through MCP

`eal.coordination.Coordinator` and `eal-coordinate` run a durable, single-host
assessor/reviewer workflow over registered EAL/3 arguments. An operator selects
the registered entry, claims, correspondence profile and finite budgets. The
assessor requests checked findings and authors a reference-bearing handoff; a
separate reviewer retrieves those findings and authors the scoped answer.
The coordinator admits the workers' responses without filling in their answers.

EAL's existing host owns observation acquisition, compatible reuse, reasoning,
freshness and claim statuses. The coordination gateway uses actual MCP stdio
operations for registered discovery, acquisition/assessment, persisted packets
and explanations. Local profile checks inspect trusted registration and source
identity before acquisition. This layer adds no grammar or reasoning method.

## Register and select a task

Use the ordinary [registered EAL workflow](argument-service.md) to register a
source, its default context and available claims. The trusted server
specification contains exactly `workspace`, `registry`, `database`, `methods`
and `limits`; optional values are `null`. Paths resolve on the local host.
Workers receive gateway arguments and cannot replace this server configuration.

A task contains exactly these fields:

| Field | Meaning |
| --- | --- |
| `task_id` | Stable operator-selected task identity. |
| `question` | Bounded question text; registration does not certify its correspondence to prose. |
| `entry_id` | Exact registered entry to inspect. |
| `claims` | One to sixteen unique selected claim IDs. |
| `profile` | `registered_claims/1` or `api_load/1`. |
| `requirements` | Closed requirements object for that profile. |

`registered_claims/1` requires exactly `{"context": {...}}`. It checks the
selected claims and exact registered context, source revision and method
registry. The operator asserts that those registered claims answer the question;
the profile does not independently formalise arbitrary prose.

`api_load/1` requires exactly `context`, `workload`, `criteria` and
`claim_outputs`:

```json
{
  "context": {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"},
  "workload": {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic", "run_id": "selected-run", "concurrent_clients": 10},
  "criteria": {"minimum_requests": 100, "maximum_sample_p95_ms": 200, "maximum_error_rate_percent": 1, "evidence_max_age_seconds": 86400},
  "claim_outputs": {"performance_criteria_met": "passes", "performance_criteria_failed": "fails"}
}
```

This finite profile checks all five workload fields against source evidence
inputs, the source freshness limit, the installed
`engineering/api-load-criteria/1` method and its implementation identity, and
the selected claims' passing/failing output predicates. The method's fixed
limits are 100 requests, sample p95 at most 200 ms and error rate at most 1%.
Other limits require an appropriate installed profile; changing task numbers
cannot change the method's semantics. These are sample criteria, with no
production guarantee or authentication of the report's measurements.

Starting a run freezes a digest over the task, registered context, source
revision, method-registry fingerprint and pin time. A subsequent source change
invalidates earlier correspondence. A new task pin requires a new run directory.

## Prepare fresh synthetic inputs

From a development checkout with its environment active:

```sh
python -m experiments.mas_coordination.coordinator_demo \
  --output .cache/mas-coordination/my-demo
eal-coordinate start \
  --demo .cache/mas-coordination/my-demo/demo.json \
  --task-id synthetic_api_sample \
  --run .cache/mas-coordination/my-api-run
```

The preparation command creates two registered sources: a synthetic API sample
for `api_load/1` and an independent synthetic availability snapshot with an
explicit objection for `registered_claims/1`. Each selects two claims. It
records the actual fixture creation time, pins the synthetic bytes and writes
server/task specifications. It performs no assessments or worker execution and
includes no answer key or binding credentials. Existing output is preserved;
choose an empty directory for each preparation.

Select `synthetic_availability_sample` in a separate run to exercise the generic
profile. The maintained [API example](../examples/api-load-test/README.md)
remains self-contained; demo preparation copies its collector and creates fresh
synthetic inputs in the separate workspace.

For an ordinary registered workspace, pass `--spec run-spec.json` instead of
`--demo`. The strict run-spec object requires `server` and `task` and permits
only the additional `budgets` and `transport` fields. In Python:

```python
from eal.coordination import Coordinator, ServerSpec, TaskSpec

server = ServerSpec("/absolute/workspace", "/absolute/workspace/tools.toml")
task = TaskSpec(
    task_id="review", question="What do these registered checks support?",
    entry_id="readiness", claims=("ready", "challenged"),
    profile="registered_claims/1", requirements={"context": {"cluster": "staging"}},
)
coordinator = Coordinator.start("/absolute/new-run", server, task)
```

## Execute and retain two separate workers

For a native host, reserve the assessor **before** launching its fresh context:

```sh
eal-coordinate reserve --run .cache/mas-coordination/my-api-run \
  --role assessor --execution-mode actual_host_agent \
  --context-out .cache/mas-coordination/my-assessor-context.json
```

The reservation returns `new`, `call_id`, state and context. Launch a worker
only when `new` is `true`. Its context includes the pinned task, actual addressed
messages, the response schema and a role-specific gateway argument vector.
The assessor executes that vector's `query` operation, inspects the finding and
authors `{"message": {...}, "consumed_message_ids": [...]}`. Record its exact
first output with the actual host execution identity:

```sh
eal-coordinate record --run .cache/mas-coordination/my-api-run \
  --call-id RESERVED_CALL_ID --response assessor-output.json \
  --execution-id ACTUAL_HOST_EXECUTION_ID --execution-mode actual_host_agent
```

Reserve a fresh reviewer context with `--role reviewer` after the accepted
handoff. It executes its supplied `lookup` vector with `--finding-id FINDING_ID`,
then authors `{"answer": {...}, "consumed_message_ids": [...]}`. Record that
first output with the reviewer's distinct execution identity. The native host
supplies actual execution and usage evidence when available; an ID string
alone does not prove that an agent ran or inspected a message.

For automated execution, configure a trusted command adapter and run:

```sh
eal-coordinate execute --run .cache/mas-coordination/my-api-run \
  --execution-mode provider \
  --worker-argv '["/absolute/path/provider-worker"]' \
  --worker-environment /private/path/worker-environment.json
```

The optional environment file is private JSON mapping names to values; those
values are not copied into execution evidence. `CommandWorker` invokes argv
without a shell, supplies one JSON context on stdin, and owns a fresh supervised
POSIX process group for each role. The operator-supplied program must implement
the model/provider interaction and use the gateway; no provider is selected by
the coordinator. Live stdout is one envelope:

```json
{
  "response": {"message": {}, "consumed_message_ids": ["request"]},
  "execution": {
    "execution_id": "actual-external-execution-id",
    "model": null,
    "usage": null
  }
}
```

`response` must satisfy the full role schema; the empty message above only
illustrates the envelope. `usage`, when provided, contains nonnegative integer
`input_tokens`, `output_tokens` and/or `total_tokens`. Live command receipts are
operator assertions, not independently authenticated provider receipts. A
scripted program must use `software_test` and return the direct role response
without a live receipt. Software executions do not count as model trials.

The development-only [`coordinator_worker.py`](../experiments/mas_coordination/coordinator_worker.py)
client exercises this command loop mechanically. Pass its absolute path and
the development Python interpreter as `--worker-argv`, with `software_test`.
It invokes actual MCP gateways and supplies no live execution receipt.

## Reference and answer contracts

The domain message, task-anchor and finding contracts are respectively
`EAL/MAS-coordination/3`, `EAL/MAS-coordination-task/3` and
`EAL/MAS-coordination-finding/3`. The JSON worker-response schema is
[`EAL/coordination-worker-response/1`](../src/eal/coordination/response-schema.json).
MAS Protocol Lab's independent envelope remains version `1`. EAL/3, package
3.2.4, `EAL/observation-record/1` and `EAL/assessment-packet/2` are unaffected.

The coordinator sends `request`; the assessor authors either `outcome`, which
contains a finding ID and every selected assessment reference, or `disposition`,
which contains a finding ID and a checked rejection/incomplete code. Common
fields bind the task digest, addressed roles, reply identity and attempt `0`.
Messages contain no inline measurement, packet or asserted host status.

The recipient retrieves the complete gateway-issued finding. Lookup checks its
content identity, current source correspondence, and actual persisted MCP
packets/explanations. Each answer contains exactly `task_digest`, `finding_id`,
`claims`, `scope`, `conclusion` and `qualification`. Each selected claim retains
its actual `assessment_id`, `status` and `assessed_at`. Scope contains the exact
requested `context` and complete profile `requirements`; qualification is
`conditional_on_registered_argument`.

| Conclusion | Meaning |
| --- | --- |
| `assessed` | Every selected claim has a matching persisted EAL assessment; supported, contested and unsupported are all genuine reasoning outcomes. |
| `out_of_scope` | Source, context, workload or criterion correspondence failed; selected claims retain `null` assessment IDs, statuses and times. |
| `unresolved` | Evidence is unavailable or execution is uncertain; unassessed fields remain `null`. |

The closed disposition codes are `context_mismatch`, `workload_mismatch`,
`criteria_mismatch`, `source_changed`, `evidence_unavailable` and
`effect_outcome_unknown`. The first four use `rejected`; the latter two use
`incomplete`. EAL `unsupported` does not mean false, and an unassessed `null`
cannot be replaced with `unsupported`.

## Acquisition, delivery and restart

The gateway first checks correspondence without collecting evidence. Registered
MCP exposure discovers the pinned entry with `eal_sources` and calls
`eal_assess_known` once for each selected claim using entry/claim arguments.
EAL collects missing observations or reuses compatible ones and assesses at its
actual current time. Separate operator exposure calls `eal_packet` and
`eal_explain` for persisted results. Workers gain no time, context, source or
reuse override. Assessment times belong to individual results; replaying one
cannot establish a new current decision or refresh an original observation.

`coordination.sqlite` is the authoritative run state. The ledger reserves worker
and assessment effects before execution. One SQLite transaction commits exact
response bytes (base64 plus digest), execution evidence, parsed response,
admission/diagnostics and immutable reply outbox. Publication and incoming ACK
follow that commit. JSON exports are views, and cannot issue a finding or replace
the first response.

Delivery is at least once. Identical stable message IDs deduplicate; changed
content under the same ID is rejected. After a lost send, ACK or completion
confirmation, `resume` reconciles committed delivery and accounting without
launching another worker or assessment. It never grants execution permission
for an existing uncertain reservation. An assessment whose effect has no
complete committed receipt produces `effect_outcome_unknown`, no assessment
references, and unknown acquisition/reuse counts. The missing receipt cannot be
treated as proof that no external effect happened.

Lifecycle commands are:

```sh
eal-coordinate status --run RUN
eal-coordinate resume --run RUN
eal-coordinate cancel --run RUN
eal-coordinate export --run RUN --output retained-evidence.json
```

`status` distinguishes ready roles, `awaiting_worker_result`, `delivery_pending`,
completed assessed/unassessed results, rejection, cancellation and expiry.
Cancellation blocks new effects; restart can still finish already committed
delivery. Rejected and interrupted first responses remain retained. The current
two-role profile provides no model repair turns, automatic uncertain-effect
retry or distributed replica execution.

## Transport and finite limits

The default `{"kind": "json"}` transport is a durable local SQLite mailbox with
the same stable-ID delivery and effect ledger. To use an installed and built
MAS Protocol Lab runtime, pass `--runtime /workspace/mas-protocol-lab` on `start`,
or select `{"kind": "lab", "runtime": "/absolute/runtime"}` in the run spec.
The current Lab bridge calls actual local MCP `mas_create_run`, `mas_send`,
`mas_receive`, `mas_ack` and `mas_status`; the supplied Rust codec encodes and
recognises its canonical wire envelope. Worker `reserve` and `finish` use the
supplied CLI because its MCP server exposes no such operations. No replacement
wire parser, remote account endpoint or persistent daemon is introduced.

Keep Lab's MCP 1.26.0 environment separate from EAL's MCP 2.2.0 environment.
The Lab runtime, its original licence and provenance remain outside the EAL
package. The JSON transport is also a mechanism control: equivalent validated
answers and recovery do not demonstrate an advantage from wire syntax.

| Frozen budget | Default |
| --- | ---: |
| `max_worker_calls` | 2 |
| `max_gateway_calls_per_role` | 4 |
| `max_mcp_calls_per_role` | 64 |
| `max_messages` | 8 |
| `max_bytes` | 65536 |
| `max_worker_output_bytes` | 65536 |
| `wall_seconds` | 900 |
| `worker_seconds` | 180 |

Gateway/MCP quotas are recorded before calls, including failed attempts. Message
and worker-call caps survive restart. Commands enforce output and per-worker
time limits, constrained by remaining run time; cancellation supervises their
process groups. For externally launched native agents the coordinator cannot
terminate the external host or enforce its token budget. Native runtime/token
limits remain host responsibilities, while gateway admission and first-response
locking remain enforced locally. There is no billing estimate when receipts are
unavailable.

## Evidence and scope of the result

[Service tests](../tests/test_coordination_service.py) exercise both profiles,
multi-claim MCP acquisition, reuse, source substitution, quotas, cancellation,
exact malformed-byte retention and abrupt process termination at declared
boundaries. [Transport tests](../tests/test_coordination_bus.py) distinguish
actual Lab checks from optional-runtime skips. Retained trials and their limits
belong in the [coordinator report](../experiments/mas_coordination/results/coordinator-003/README.md).

Reliable scope checking and recovery are implemented mechanisms. Broader model
accuracy, latency and total-cost improvements require comparative trials with
fresh separate contexts, equivalent durable-JSON controls and all failures
retained. Passing interpreter or software checks cannot establish those gains.

This is a trusted single-host workflow on a local filesystem. Workers use
separate execution contexts while sharing host filesystem permissions; role
restrictions are not operating-system isolation. Content digests detect
inconsistent views under that trust model, and do not authenticate measurements
or prevent a shared writer from changing databases. Claim/question prose,
physical continuity and production adequacy remain outside these checks.
