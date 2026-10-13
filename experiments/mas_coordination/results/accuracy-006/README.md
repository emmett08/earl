# First-attempt native-worker fidelity

The persistent Rust/MCP arm completed **6/6** scoped tasks correctly; durable
JSON completed **5/6**. These are actual fresh native-agent outcomes on six
synthetic task pairs, with no repairs. One JSON assessor confused completed
`unsupported` assessments with unavailable evidence. The coordinator rejected
that handoff, so its reviewer was not launched. This small result does not
establish a causal accuracy advantage for Rust or general model accuracy.

| First-attempt measure | Durable JSON | Persistent Rust/MCP |
| --- | ---: | ---: |
| Exact scoped tasks, including both roles | 5/6 (83.3%) | 6/6 (100%) |
| Selected claim status/null fidelity | 11/13 | 13/13 |
| Unsupported positive claims | 0 | 0 |
| Rejected assessor responses | 1 | 0 |
| Unlaunched downstream reviewers | 1 | 0 |
| Fresh native contexts actually executed | 11 | 12 |
| Repair/replacement turns | 0 | 0 |

The two missing JSON claim labels belong to the blocked reviewer in one task;
they are not two separate incorrect model assertions. Four labels per arm
correctly remain null in the scope-mismatch and unavailable-registration tasks.
An unassessed or rejected task remains in the fixed denominator. A valid EAL
`unsupported` or `contested` assessment is a completed assessment.

| Synthetic case | Reference result | JSON | Rust/MCP |
| --- | --- | --- | --- |
| Failed API sample limits | failed supported; met unsupported | correct | correct |
| Contested route, negative quorum, unobserved route | contested; unsupported; unsupported | correct | correct |
| Inclusive API boundary, 200 ms / 1% errors | met supported; failed unsupported | correct | correct |
| Stale positive snapshot | both claims unsupported | rejected assessor; no reviewer | correct |
| Requested workload differs from measured run | out_of_scope; both assessments null | correct | correct |
| Synthetic registration unavailable after pinning | unresolved; both assessments null | correct | correct |

## What ran

The [declared plan](frozen-plan.json), paired input bytes, task requirements,
role prompt, claim selection and tool budgets were frozen after separate
software preflight and before native outcomes. [The implementation freeze](implementation-freeze.json)
records 93 hashes, including EAL, the harness and native executable; all remained
unchanged through the final first-response record. Each unit had an independent
empty knowledge database and mailbox. Workers saw only an opaque reserved
role context, its response schema and actual gateway output. They received no
answer key, reference output, study plan, source fixture or scorer, and inherited
no parent conversation (`fork_turns=none`, no model override).

Twelve assessors and eleven reviewers independently executed in fresh host
contexts and authored their own responses. Each assessor used the actual
registered EAL MCP gateway; each launched reviewer looked up the finding from
its actual addressed handoff. EAL discovery, acquisition, assessments, packets
and explanations are retained in the unit findings and exports. Synthetic
registration removal affected only the selected entry in each case06 database
after pinning; it caused a real `evidence_unavailable` correspondence result.

The operator reserved each role before launching it and recorded its exact first
bytes with its actual distinct host identity. The coordinator enforced gateway
quotas and response admission. The requested 180-second/4000-token host worker
ceilings are soft; reservation-to-record elapsed includes scheduling and is not
inference latency. Native model identity, token usage and billing are unknown.
No paid provider invocation was used. The fixed run deadline was 900 seconds,
with at most two workers, four gateway calls per role and 64 EAL MCP calls per
role. No prompts, inputs or first responses were repaired after an outcome.

[Native call counts](actual-call-counts.json) retain 100 EAL MCP calls (55 Lab,
45 JSON), including 18 registered assessments. Equal quotas did not produce
equal realized tool use: one Lab reviewer looked up its finding twice, and the
rejected JSON assessor had no downstream reviewer. This study makes no call
efficiency claim.

After all twelve exports existed, separate empty-workspace reference runs
executed actual EAL MCP again. The scorer checks analytical reference labels,
each unit's own finding identity, assessment IDs and individual timestamps,
full requested scope, qualification, assessor frame, consumed handoff and both
first-response admissions. Admission alone is insufficient for a correct score.
Preflights, references and scorer tests are software checks excluded from the
native denominator.

## Failure and limits

[Unit08's exact assessor response](units/unit08/assessor-response.json) selected
`evidence_unavailable`/`incomplete` despite a complete finding containing two
`unsupported` assessments. Its missing assessment references caused rejection.
The raw response is retained byte-for-byte in the coordinator export; no
infrastructure failure, repair or downstream execution was substituted.
[The independent review](independent-review.json) checks this classification and
the final scores from raw artifacts.

There was one paired disagreement favouring Lab and none favouring JSON; the
exact two-sided paired sign-test p-value is **1.0**. Descriptive Wilson 95%
intervals are 43.6–97.0% for JSON and 61.0–100% for Lab. These do not support a
representative accuracy estimate. The tasks measure tool-assisted fidelity to
registered scoped results, rather than unaided reasoning or a comparison with
uncoordinated MCP. Both transports expose the same worker-visible JSON domain
contract, so the observed difference cannot be attributed to Rust wire syntax.

[A scheduling deviation](scheduling-deviations.json) retains the reversed
assessor launch order for case02 (JSON then Lab); no post-hoc resampling or
compensation occurred. Actual launch order was therefore not perfectly
counterbalanced. Shared filesystem permissions provide trusted local separation,
not operating-system isolation. Host execution records are operator attestations
accompanied by actual separate launches, not independently authenticated
provider receipts. Historical studies were left unchanged.
The isolated external Lab Python files were not included in this study's
prelaunch hash set; independent review found four of them still matched the
earlier transport benchmark's hashes. The current-study stability check covers
the 93 explicitly declared files.

## Retained evidence and reproduction

- [Machine scores](report.json), [manifest](manifest.json) and [implementation stability](implementation-stability.json).
- [Actual native launch order](native-launch-order.json) and [failure notes](native-execution-notes.json).
- `units/unitNN/`: reserved contexts, frozen prompts, exact responses, host execution records, admission records, first issued findings and coordinator exports.
- `references/caseNN/`: post-trial actual MCP oracle, packets and explanations; `preflight/` is separate software readiness evidence.
- [Operator dispatch helper](operator-dispatch.py): the executed reservation/record helper; it never authors model responses or launches a model.

Use the [current study harness](../../accuracy_study.py) and
[workflow](../../README.md#fresh-native-worker-accuracy) with a new empty output
directory and actual fresh workers. Existing results contain absolute paths and
timestamps for this execution; do not rerun them as fresh accuracy evidence.
Private SQLite state and `.eal` host bindings are excluded from Git. Portable
exports retain the data needed to review first-attempt scoring.
