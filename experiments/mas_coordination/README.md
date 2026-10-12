# Registered MCP coordination

The reusable [`eal.coordination` service](../../docs/coordination.md) coordinates
separate assessor/reviewer contexts over operator-registered EAL/3 arguments.
`eal-coordinate` pins task/source/method identities, enforces finite local
budgets, and commits exact worker bytes, admission and outbox before delivery or
ACK. Current acquisition, assessment, packet and explanation retrieval use
actual EAL MCP at current time. EAL remains responsible for reasoning and
compatible observation reuse.

Two correspondence profiles are supported: `registered_claims/1` checks selected
claims and registered context; `api_load/1` additionally checks complete report
workload, fixed method criteria, freshness and output bindings. A task selects
one to sixteen claims. The message/task/finding domain contracts are `/3`;
EAL/3 and MAS Protocol Lab's envelope version `1` retain their distinct contracts.
See the [service reference](../../docs/coordination.md) for closed requirements,
response schemas, Python integration, command workers and native-host use.

## Prepare a fresh fixture

From a development checkout with its virtual environment active:

```sh
python -m experiments.mas_coordination.coordinator_demo \
  --output .cache/mas-coordination/fresh-demo
eal-coordinate start \
  --demo .cache/mas-coordination/fresh-demo/demo.json \
  --task-id synthetic_api_sample \
  --run .cache/mas-coordination/fresh-api-run
```

[coordinator_demo.py](coordinator_demo.py) prepares current-time, explicitly
synthetic records and two registered sources. It does not assess claims or run
workers, and its manifest contains no answer key or binding credentials.
Select `synthetic_availability_sample` in another run to use the generic profile
with an explicit outage objection. Preparation requires an empty output
directory and preserves the maintained API example.

The default transport is durable JSON. Add
`--runtime /workspace/mas-protocol-lab` on `start` to use the installed Lab
runtime's isolated local MCP interpreter and the packaged persistent Rust
codec. Build `src/eal/coordination/rust_codec` with `cargo build --release --locked`
using its manifest, as described in the service reference. The adapter reuses
one MCP session and one codec process, combines canonical admission in Rust,
and exposes reservation/completion through the same MCP session and supplied
Store methods. Keep Lab's MCP 1.26.0 interpreter isolated from EAL's MCP 2.2.0
environment. Close Python transport/coordinator instances explicitly or use
their context managers; CLI subprocesses own their cleanup.

## Execute, recover and compare

Reserve each native worker before launching its fresh context, then record its
first exact response and actual external execution ID. Alternatively, `execute`
runs an operator-configured `CommandWorker` in fresh supervised processes;
the operator supplies the model/provider adapter. Scripted workers use
`software_test` and do not establish a model trial. The service reference
describes every lifecycle operation: `start`, `reserve`, `query`, `lookup`,
`record`, `execute`, `status`, `resume`, `cancel` and `export`.

`resume` drains committed delivery and reconciles transport accounting. It
cannot repeat an unknown worker or assessment effect. Identical stable message
IDs deduplicate, while changed content is rejected. Native-host execution time
and token limits require host enforcement; command workers have enforced
process/time/output limits. Shared filesystem access remains a trusted local
boundary, with no operating-system role isolation or certification of prose.

```sh
python -m pytest -q tests/test_coordination_*.py
```

Software tests cover two profiles, multiple claims, actual MCP acquisition and
reuse, source changes, quotas, cancellation, exact-byte retention, receipt loss
and abrupt process termination. Optional Lab tests report unavailable runtime
capability as a skip. Retained comparisons must separate software checks from
actual independently executed agents, preserve first attempts and failures,
and use an equivalently validated durable-JSON control.

The [coordinator report](results/coordinator-003/README.md) records the expanded
workflow's evidence and limits. Scope checking and durable recovery are useful
implemented mechanisms; broader accuracy, latency and total-cost gains require
comparative measurements. Equivalent JSON and Lab results do not establish a
benefit from wire syntax.

## Local transport performance

The [persistent transport benchmark](results/transport-005/README.md) retains
25 equivalent software workloads across five execution stages, raw samples,
actual launch logs, separate codec measurements and independent artifact
checking. The median useful cycle changed from 10,758.7 ms in the frozen
per-operation Lab bridge to 486.5 ms with persistent MCP and Rust admission;
actual process starts changed from 61 to two. Combined admission improved
post-create operations by a median paired 1.354× over persistent round trips;
that scope includes the codec's first lazy startup. JSON remained faster at
20.48 ms. These measurements establish local transport cost for the fixed
workload, not model accuracy, inference latency or wire-syntax superiority.

Use `python -m experiments.mas_coordination.transport_benchmark --help` and
the frozen [benchmark plan](transport-benchmark-plan.json) to reproduce in a
new output directory. The report distinguishes cold startup and measured
software workloads from native agent execution.

## Retained study records

- [Paired protocol pilot](results/paired-001/README.md).
- [Scope and recovery study](results/recovery-002/README.md).
- [Initial baseline report](results/baseline-001/report.json).

These records retain their original plans, outputs, scores and implementation
identities. They are evidence archives, not the current service execution
contract.
