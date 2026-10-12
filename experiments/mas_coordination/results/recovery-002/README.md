# Corrected coordination and recovery study

The implementation now checks the complete requested task and retains results
before acknowledging delivery. The software comparisons show improvements in
scope admission and repeated effect invocations. Eight fresh native-agent
contexts verified the corrected handoff workflow; they do not isolate a benefit
from the Rust wire representation.

## What prevented the original pilot from improving

The [/1 trial](../paired-001/README.md) exposed equivalent packets and completed
handoff templates to both arms. The scope-mismatch reviewer contexts were
byte-identical. Changing the invisible transport could not change that input.
Both arms also lacked a normative rule choosing `out_of_scope` rather than
`unresolved` for an unassessed different target, causing the same strict
conclusion-label failure. Both reviewers preserved null unassessed statuses.
The original 3/4 scores remain unchanged.

The old admission gate checked service/build/dataset context but omitted the
requested run and client count. Delivery acknowledgement could precede durable
response admission. These implementation gaps motivated the versioned fix;
the original trial does not refute protocol-based coordination.

## Software measurements

The [full software report](software/report.json) retains all eighteen episodes,
their declared schedules, event traces and actual assessment receipts. Four
separate correspondence cases retain the old context-only admission and new
complete-task check. Nominal and different-build controls agree; the old gate
falsely admits both changed-run and changed-client requests, which /2 rejects.

| Arm | EAL calls for three duplicate deliveries | Effects across six episodes | Delivered | Safe unknown |
| --- | ---: | ---: | ---: | ---: |
| Plain retry | 3 | 11 | 6 | 0 |
| Durable JSON | 1 | 6 | 5 | 1 |
| Durable Lab | 1 | 6 | 5 | 1 |

Each duplicate episode acquired one observation in every arm. Plain retry
reused it twice; fewer assessments do not establish acquisition savings.
Other effect counters are explicitly synthetic software operations. The
unknown interrupted effect remains unresolved in each durable arm instead of
being automatically repeated. Thus completion counts are not interchangeable.
These tests made zero native-model calls and zero MCP calls.

Durable JSON matches Lab. Validation, immutable results and an outbox explain
the measured benefit; the data do not credit wire syntax. Faults are Python
interruptions at declared boundaries, not process-kill or power-loss tests.

## Actual communicating workers

The [frozen plan](native/plan.json), [implementation manifest](native/manifest.json)
and [combined report](report.json) retain the trial rules and all four units.
Each unit used a fresh assessor and fresh reviewer. Workers requested findings,
authored handoffs and retrieved the received finding before answering. Initial
contexts contained neither computed assessments nor completed answer templates.

| Fresh synthetic case | Plain MCP | Checked protocol |
| --- | --- | --- |
| Measured 3% sample failure | Correct `sample_fail` | Correct `sample_fail` |
| Different requested run and client count | Correct `out_of_scope` | Correct `out_of_scope` |

Both arms scored **2/2**; all **4/4** units were correct with **zero repairs**.
Arm order was counterbalanced by case. The first sample arm was plain and the
first workload arm was checked. Actual host task identities, prelaunch call
reservations, exact response bytes, consumed IDs, gateway calls and canonical
Lab receipts are retained under `native/`. Both Lab calls per unit were
reserved before launch and finished with actual host execution identities.

Both native arms use the corrected correspondence gate, explicit semantics and
answer checks. Their equal clean outcomes establish feasibility of that design,
not a causal old/new comparison. The two sample units performed four Python EAL
assessments in total, collected two observations and reused two. They made eight
actual MCP calls for packet verification and registered discovery. Workload
mismatches collected nothing. MCP lookup is actual; acquisition occurs through
the Python host at the trusted historical teaching time.

## Reuse and limits

Follow the [current workflow](../../README.md) and [payload schema](payload-schema.json).
The domain payload is EAL/MAS-coordination/2; the supplied Lab envelope remains
version 1 and EAL interpretation remains EAL/3. The checked ledger can also be
used over JSON; retain Lab when its addressed delivery and accounting are useful.

73 new contract/recovery checks and 67 original coordination checks passed.
The maintained CLI/MCP synthetic example was checked separately. These figures
are software verification, not additional native trials.

Native model identity, token receipts, billing and implementation costs are
unavailable. Gateway and Lab budgets are enforced; requested native time/token
ceilings are soft. Separate agent contexts share filesystem permissions, so
role restrictions are host instructions rather than operating-system isolation.
Raw response files are separate from the atomic identity/digest/outbox record.
No exactly-once external execution, representative engineering capability,
production-performance guarantee or lower total-cost claim follows.

The [artifact hashes](artifact-hashes.json) cover retained machine-readable
evidence. Workspace databases and private EAL bindings were not exported.
