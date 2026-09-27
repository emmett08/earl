# Split fulfilment and partial returns: frozen experimental protocol

Status: **specified exploratory experiment**. Freeze hashes and execution IDs appear in `materials/freeze.json` before the first coding session. The results and deviations are appended in `paper.md` after execution. This protocol is a bounded prose record because a single deliberately selected fixture and one paired B contrast cannot satisfy the sampling and identification requirements of a preregisterable population-level causal study. It nevertheless fixes the hypotheses, instruments, analysis and decision rules before outcomes are examined.

## Question and inferential scope

The target claim is that providing a situated EAL/2 architecture argument to an AI coding agent changes its implementation of a cross-cutting feature so that independent functionality and architecture checks improve, conditional on an identical starting source tree and feature brief. This case observes feature B (partial returns across shipments) after feature A (split fulfilment). Engineer 2 implements A after a real pre-A EARL MCP argument round trip; Engineer 3 is represented by two fresh B coding sessions, one with argument access and one without it. These are roles in a scripted scenario, not recruited human engineers.

The local estimand is the ordered difference of B outcome vectors, `Y(B, A*, EAL) - Y(B, A*, no-EAL)`, where `A*` is the single frozen A output. The target is descriptive for this pair; the two outputs come from different stochastic sessions, so the difference cannot identify a causal effect for one agent or a population. The A stage has no no-EAL control; no EAL effect on A is estimated. Model class is held the same across the primary B pair. Different-model runs, if executed, are separate sensitivity cases crossed with both B conditions and never pooled with the primary pair as if model variation were treatment.

## Rival hypothesis packages and predictions

**H1, architecture-guidance mechanism.** An agent that receives and uses the EAL argument will reuse or coherently revise the shared fulfilment boundaries when B affects order state, payment, stock and events. Under that auxiliary assumption, it may pass more fixed architecture and behaviour findings than an otherwise similarly configured agent without the argument. H1 excludes a treatment-only architectural bypass with control conformance under the same local checks. An MCP call or accepted ASPIC+ claim establishes delivery and formal assessment, not agent comprehension.

**H2, visible-code mechanism.** The source, architecture documentation and existing tests already contain enough information; both B agents may make coherent changes. Passing outcomes in both conditions are shared predictions and cannot discriminate H1 from H2. Agent stochasticity and order of sessions can also produce a difference in either direction.

**H3, constraint cost.** Additional argument material may divert attention or constrain a legitimate shared-contract refactor; the treatment could fail a fixed outcome that the control passes. Exact preservation of an old method AST is therefore not an acceptance condition.

The long-horizon proposition that EAL reduces future technical debt is a separate prediction. The current B check occurs immediately after implementation. No later maintenance effort, rework, defect arrival or accumulated obligation is observed, so the proposition is not an outcome of this case.

## Materials, assignment and exposure

The source fixture is `materials/base/`; the direct engineer requests are exactly `materials/features/feature_a.md` and `feature_b.md`. They specify observable requirements without an architecture hint. The agent receives its assigned source tree and the feature brief as ordinary working material. Host setup, tool registry, EAL/MCP exposure and assessment instructions are recorded separately from the engineer brief.

The baseline includes quote, reserve, capture, dispatch, transactional order/outbox save and event publication, with rollback and request-ID idempotency. Feature A must split fulfilment across warehouses and compensate a later shipment failure. Its final source tree is copied byte for byte into two isolated B directories. The B sessions have the same feature brief, exposed model name/class/configuration, tool availability, wall-time limit and A snapshot. Both can inspect the code. The EAL condition receives the argument via the recorded MCP interaction; the control does not receive the argument. If tooling availability or hidden instructions differ, the discrepancy is a delivery confound and is reported.

Before A, the host invokes the EARL MCP with baseline-only evidence and records the request, returned argument, source digests, tool version and timestamp. Engineer 2's direct feature request remains A alone. The pre-A result is delivered to the A agent as environment context; an unobserved or failed delivery invalidates any claim that A used EAL. Before B, the host records a corresponding treatment delivery and control absence while keeping the source snapshot identical. The exact exposure route and any unavoidable wrapper text are retained verbatim. No assessor output or other candidate's files enter either B working directory. The source storage is shared at the outer workspace level; the runs are operationally isolated directories, not a security sandbox, so unnoticed cross-directory access remains a limitation.

The assignment order of the B pair is drawn once using a recorded random bit before launching either session. There is one attempt in each arm; failures are retained, without substitution or optional stopping. Agent internal sampling seeds and exact model revisions may be unavailable; record the exposed identifier and this limitation.

The GitHub `workflow_dispatch` matrix is an operational replication path. Its B jobs may run concurrently; it is not the one-bit ordered primary local trial. Report its model label, timestamps, source digests and failures separately. Do not merge matrix outcomes with the primary pair unless a later protocol defines that analysis.

## Construct to measurement chain

| Construct | Observable and instrument | Permitted inference | Key error |
| --- | --- | --- | --- |
| Feature conformance | Independent assessor executes split-order, shortage, later-dispatch compensation, idempotency, cross-shipment return, exact unit-price-plus-tax refund, refund-failure and retry probes | Bounded behavioural result for the in-memory fixture | Probe coverage is finite; provider behaviour is simulated |
| Architecture coherence | Reviewer masked to arm inspects whether one causal state transition and shared contracts account for checkout, returns, compensation and outbox, and logs duplicate independent paths, adapter bypasses, unreachable production code and incompatible state writers; machine checks collect candidates | Local implementation structure and maintenance sites | Different correct architectures exist; reviewer judgement can disagree |
| Cognitive complexity | Frozen, declared algorithm and tool output at baseline, A and each B snapshot, per function and aggregate changed functions | Readability-related partial indicator | Language-dependent boundaries, generated code, trivial extractions and semantic behaviour affect score; not monetary debt |
| EAL exposure | MCP request/response transcript, argument digest and accessible source | Argument was delivered to the session host | Does not show reading, understanding or causal use by the agent |
| Future technical debt | No direct measurement in this two-feature horizon | No claim about accumulated or compounding debt | Maintenance cost and future changes are absent |

Behavioural checks are primary. Architecture findings are secondary and reported item by item, including legitimate boundary revisions. Cognitive complexity is tertiary. Scores are never added to form an unvalidated technical-debt index. Candidate-written tests are retained as diagnostics; independent probes set conformance. Structural inspection does not require exact AST identity. If the assessor or cognitive tool fails, report missing measurement instead of treating the candidate as passing.

## Analysis and decisions

For each B arm report the exact pass/fail/invalid vector, test command and exit, source digest, architecture findings, per-function complexity deltas from A, wall time and any available tool/session trace. The primary descriptive contrast is the componentwise B vector difference; a count of passes is a convenience only. A has its own baseline-to-A descriptive vector. Analyse failed implementation and failed measurement separately. A reviewer receives anonymised B snapshots in a shuffled order before knowing arm labels and records rationales for each architectural judgement. Disagreements and unassessed paths are preserved. No p-value or confidence interval is derived from one pair.

| Observation | Bounded conclusion | Follow-up |
| --- | --- | --- |
| Both B implementations conform and architecture review agrees | No observed EAL advantage on these checks; H1 and H2 both remain live | Repeat with independently selected tasks and later changes |
| Treatment conforms while control fails a fixed check | Local difference consistent with guidance, also with stochastic session variation | Repeat randomised same-model pairs; inspect exposure and failure mechanism |
| Control conforms while treatment fails | Local adverse association consistent with H3 or variation | Inspect failure and repeat without changing criteria |
| Both fail | Neither workflow succeeds on this fixture | Diagnose apparatus and task difficulty; retain both failures |
| Unequal B starts, absent exposure, invalid oracle or model mismatch | Planned contrast invalid or confounded | Preserve runs and correct setup in a new version |

Complexity differences cannot override a failed behavioural test. A lower score alongside more duplicate paths is reported as a divergent set of indicators. A valid shared-boundary refactor is assessed on behaviour and coherence even when source location or method AST changes. The paper must distinguish observed differences, explanatory interpretations and long-horizon forecasts.

## Provenance and stop rules

Before A, freeze SHA-256 for the baseline tree, two briefs, EAL source, trusted tool bindings, MCP harness, independent assessor, complexity implementation, protocol and any analysis code. Record Python/runtime, dependencies, model identifiers exposed by the runner, tool interface versions, random arm order and all source snapshots. Record each deviation at occurrence; do not silently alter an instrument after viewing results. A correction to a broken instrument requires a new version and remeasurement of all retained snapshots where possible, with the original failure retained. Stop after one A and the planned primary B pair, regardless of success. A factorial multiple-model replication or longitudinal follow-up is a separately frozen study.
