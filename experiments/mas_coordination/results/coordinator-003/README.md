# Reusable MCP coordinator validation

The prototype is now a packaged single-host service with the `eal-coordinate`
CLI and Python `Coordinator` API. It accepts trusted registered tasks, supports
multiple claims and two profiles, reserves worker execution before launch, and
atomically stores exact output bytes, admission and reply outbox before send or
ACK. Assessment acquisition now happens through actual registered MCP rather
than a preceding Python assessment call.

## Actual communicating agents

The [frozen plan](plan.json), [implementation hashes](manifest.json) and
[complete report](report.json) retain four independent case/arm workspaces.
Eight fresh native contexts executed: one assessor and one reviewer per unit,
with zero repairs and no supplied answer templates. All first outputs,
addressed contexts, canonical receipts and authoritative exports are retained
under `native/`. Exact response bytes are also saved as `*-attempt.bin`.

| Task profile | Durable JSON | Lab |
| --- | --- | --- |
| API-load criteria, two selected claims | Correct supported / unsupported results | Correct supported / unsupported results |
| General registered claims with an outage objection | Correct contested / supported results | Correct contested / supported results |

All **4/4 units** completed correctly: **2/2 per transport**. Every review
preserved claim status, assessment ID, individual assessment time, complete
requested scope and the conditional-on-argument qualification. Arm order was
counterbalanced by profile; each arm had its own freshly generated synthetic
workspace and observation store.

Across those units the gateway made **44 successful actual EAL MCP calls**,
including registered discovery and **8 registered assessments**. Those
assessments collected **8 evidence observations** and reused **2**. These are
logical EAL counts, not model tokens or dollars. Lab mailboxes reserved and
finished both actual worker calls and acknowledged consumed messages.

Lab uses its supplied local MCP adapter for create/send/receive/ACK/status and
the supplied CLI for reserve/finish, which have no MCP tools in this release.
The fixed Rust envelope remains version 1; message/task/finding contracts are
version 3. EAL/3 reasoning remains in the existing EAL host.

## Software, restart and installation checks

**171 focused coordinator checks passed**. They exercise both profiles,
multi-claim MCP acquisition, source/workload/criteria rejection, observation
reuse, exact response retention, role restrictions, enforced command limits,
concurrent reservations and cancellation. Process-interruption checks stop
after remote publication and after MCP assessment before its receipt commit.
Restart recovers committed delivery and leaves uncertain effects unresolved,
without another worker or assessment execution.

Two complete command-runner scenarios used the explicitly scripted
`software_test` client: API over JSON and general claims over Lab MCP. They
executed actual gateways in separate supervised processes, retained exact
stdout bytes, and resumed with no additional effects. These are software
verification, not additional native agents. An initial test assertion wrongly
reconstructed bytes from canonically ordered JSON; it was corrected to compare
the actual captured stdout. Frozen production code and native outcomes were
unchanged.

Twenty distribution-metadata checks also passed. `make check-distribution`
verified wheel and source archive metadata, independently installed both,
exercised CLI/stdio/HTTP plus the new coordinator outside the checkout, and
checked source-built runtime equality. The distribution guard was updated for
the new public CLI entry point.

## Reproduce and interpret

Use [the current service guide](../../../../docs/coordination.md). The
scripted fixture/client are development smoke helpers; neither launches a
model. Native execution requires actual separate host agents or an
operator-configured model worker program with external execution receipts.
No standalone provider command was executed in this study.

These results establish reusable workflow feasibility. Equal clean outcomes
do not demonstrate superior wire syntax, broader model accuracy, reduced total
cost or production performance. Tasks and records are synthetic. The operator
asserts question/source correspondence; registration does not certify prose or
measurements. Native model identities, token usage and billing are unavailable;
actual host task identities are retained. Native contexts share filesystem permissions; command
timeouts stop owned local process groups, not detached or remote work.

The [artifact hashes](artifact-hashes.json) cover machine-readable evidence.
Private EAL binding keys, environment values and workspace databases were not
exported. Earlier [/1](../paired-001/README.md) and [/2](../recovery-002/README.md)
results remain unchanged.
