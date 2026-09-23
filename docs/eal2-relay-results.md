# EAL/2 model-sequence execution record — 23 September 2026

The **92 earlier trials were recovered and pushed** with their original prompts, failures, usage and frozen inputs. Every archived trial matched its recorded SHA-256. The [earlier report](eal2-model-results.md) retains its findings and the stateless-host interface confounds.

The new campaign remains **incomplete**. Ten endpoints finished on one task before network approval cancellation interrupted execution. A separately frozen serial attempt was then rejected by automatic approval review despite the user's confirmation. No further API route or paid retry was attempted. These records do not support a comparison across the six-task suite.

## Design and preserved cohorts

The [design](model-relay-experiments.md) defines **27 conditions**, **six pinned model snapshots**, **six exposed tasks** and **two repetitions**, scheduling **324 endpoints**. It covers small→full, full→small, same-model controls, reasoning/non-reasoning combinations, different tool placements, small→mini→full and two three-stage return sequences. Answer-only, evidence, transcript and no-handoff conditions specify exactly what the next model receives. Small/mini/full denote product tiers; parameter-defined open SLM performance remains unmeasured.

| Cohort | Frozen protocol / package | Saved evidence | Disposition |
| --- | --- | --- | --- |
| Initial | 1.0.0 / 2.2.0 | No stage response; three orphan markers | Automatic review rejected private-task disclosure |
| Confirmed concurrent | 1.0.2 / 2.2.0 | 14 stage records; 10 finished endpoints | Network approval cancelled before a decision returned |
| Serial replacement | 1.0.3 / 2.2.1 | No stage response; one orphan marker | Automatic review did not recognise the prior confirmation |

Raw archives and indexes: [initial](../benchmarks/results/2026-09-23-relays/index.json), [confirmed concurrent](../benchmarks/results/2026-09-23-relays-authorised/index.json), [serial](../benchmarks/results/2026-09-23-relays-serial/index.json). Their frozen bytes are unchanged. Derived [concurrent](../benchmarks/results/2026-09-23-relays-authorised/checkpoint-audit.json) and [serial](../benchmarks/results/2026-09-23-relays-serial/checkpoint-audit.json) audits verify freeze/checkpoint digests, schedule identity, endpoint scores, hand-off identity, original source anchors and known charges against individual request records.

The concurrent cohort contains 324 scheduling records: **10 finished endpoints, six transport-failed endpoints, eight partial sequences and 300 conditions with no executed stage**. The 308 scheduling stops are excluded from model-outcome denominators. Three residual in-flight markers have matching completed stage records; they are stale markers, not three additional unknown requests. Four failed stage records have unavailable usage. Shared stages account for six failed endpoint records, so these counts are not independent trials.

## What the saved responses show

All finished endpoints concern `sampled-negative-finding`, repetition 0, and return its expected supported claim. The completed tool producers also pass the strict source/evidence checks. Their subsequent model-only recipients satisfy the common answer criterion; they do not thereby acquire independent tool verification.

| Finished condition | Correct on this one task | Standalone sequence cost estimate, USD |
| --- | --- | ---: |
| GPT-4.1 nano solo | Yes | 0.00025520 |
| GPT-5 nano solo | Yes | 0.00046155 |
| GPT-4.1 solo | Yes | 0.01412800 |
| GPT-4.1 nano with tools | Yes | 0.00130010 |
| GPT-4.1 with tools | Yes | 0.02599000 |
| GPT-4.1 with tools → nano, answer | Yes | 0.02671450 |
| GPT-4.1 with tools → nano, evidence | Yes | 0.02751290 |
| GPT-4.1 with tools → nano, no hand-off | Yes | 0.02624520 |
| GPT-4.1 nano with tools → GPT-5, evidence | Yes | 0.02971635 |
| GPT-5 nano with tools → GPT-5, evidence | Yes | 0.02844644 |

The primary answer-versus-evidence comparison has only **one matched task/repetition**. Both recipients are correct; evidence adds **$0.0007984** to this sequence. That observation neither establishes equivalence nor answers the suite-level hypothesis. Nano solo is also correct on this task. No superiority, generalisation or population interval is reported.

The [endpoint table](../benchmarks/results/2026-09-23-relays-authorised/endpoints.csv) includes all scheduling states; the [stage table](../benchmarks/results/2026-09-23-relays-authorised/stages.csv) includes all recorded failures. Raw archives retain actual prompts, visible model outputs, tool events and transferred packets. Sequence costs include every constituent stage as if run alone and must not be summed as campaign charges because prefixes are shared.

Known unique model charges in this cohort are **at least $0.11302619**. This includes **$0.01178125** for a completed request in a GPT-5 tool stage whose subsequent request failed. Total charges remain unknown. Orphan markers from the initial and serial cohorts have no saved usage. The spending settings are post-response stop thresholds, not provider-enforced invoice caps.

## Capability probes

All eleven preliminary API probes succeeded and returned the requested pinned model identities. They sent only a short greeting or a trivial `ping` function schema, without repository tasks, and test endpoint capability rather than engineering reasoning.

| Snapshot | Text response | Native function response |
| --- | --- | --- |
| GPT-4.1 nano, 2025-04-14 | Passed | Passed |
| GPT-4.1 mini, 2025-04-14 | Passed | Not requested |
| GPT-4.1, 2025-04-14 | Passed | Passed |
| GPT-5 nano, 2025-08-07 | Passed | Passed |
| GPT-5 mini, 2025-08-07 | Passed | Passed |
| GPT-5, 2025-08-07 | Passed | Passed |

The configured token-rate estimate for the probes is **$0.0015704**, additional to task charges. [Raw probe records](../benchmarks/results/2026-09-23-relays/provider-probes.json) retain messages, outputs, returned models, tokens, latency and cost. No credential is retained.

## Statistical calibration

The pre-execution sensitivity simulation generated 1,000 synthetic datasets per scenario, with two perfectly correlated repetitions within each task. Each task's paired correctness difference was sampled from a declared distribution on −1, 0 and +1. This examines the finite-task interval procedure, not language-model performance.

| Independent tasks | True difference 0 | True difference +0.10 | True difference +0.25 |
| --- | --- | --- | --- |
| 6 | 88.9% coverage | 73.8% coverage | 80.1% coverage |
| 12 | 94.4% | 88.8% | 93.5% |
| 24 | 95.0% | 93.0% | 95.9% |
| 48 | 95.0% | 93.2% | 95.3% |

These are simulated coverage fractions for nominal 95% percentile intervals under the specified distributions, using 500 bootstrap draws per dataset. Monte Carlo standard errors, interval width, zero-width frequency and zero-exclusion frequency are retained in the [simulation record](../benchmarks/protocols/relay-precision-simulation.json). Coverage with six clusters is inadequate for a calibrated 95% population claim. The protocol consequently treats actual model comparisons as descriptive pilot estimates and requires new independent tasks for confirmatory work. The larger simulated task counts improve coverage in these scenarios; they do not establish universal sample-size requirements.

## Implementation validation and current block

Package **2.2.2**, source language **EAL/2**, fixes two issues exposed by the interruption. Known charges from earlier requests survive a later usage failure. The **EAL/relay-report/2** schema separates recorded, attempted, completed, partially executed, unexecuted and unrecorded endpoints. Scheduling stops stay in the raw archive but are excluded from model-outcome aggregates; transport-failed attempted endpoints remain included. Earlier raw evidence retains its original versions.

All **532 tests pass**, including actual MCP subprocess operation, protected task anchors, score exclusion from hand-offs, preserved failed tool events, shared prefixes, partial charge retention, unknown-billing stops and correct classification of unexecuted recipients. Wheel and source distribution builds and the installed `eal-relay` 324-endpoint freeze are checked without further provider generation. Protocol **1.0.4** validates with zero errors or warnings and records the incomplete cohorts and approval block.

The environment's latest automatic-review reason was that the visible messages did not explicitly authorise disclosure of private repository task data and model hand-offs to OpenAI, or the spending threshold. The user's preceding confirmation is documented; it was not recognised by that review. Further live execution remains blocked, and no workaround was attempted. The $10 serial threshold leaves an allowance within the previously confirmed $12 threshold, but unresolved earlier usage prevents an exact total bill.
