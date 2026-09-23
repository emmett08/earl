# EAL/2 model-sequence execution record — 23 September 2026

The unfinished earlier work was recovered in commit `a48a57f`. Its two archives retain all **92 completed trials**, original prompts, failures, usage and frozen inputs. Every archived trial matched its recorded SHA-256. The [earlier report](eal2-model-results.md) retains its original findings and host-interface limitations.

The additional sequence runner and pre-task design were committed as `cabc998`, package **2.2.0**, source language **EAL/2**. The [design](model-relay-experiments.md) contains **27 conditions**, **six model snapshots**, **six exposed tasks** and **two repetitions**, scheduling **324 endpoint outcomes**. It covers small→full, full→small, same-model controls, reasoning/non-reasoning combinations, different tool placements, small→mini→full and two three-stage return sequences. Answer-only, evidence, transcript and no-handoff conditions specify exactly what the next model receives.

## Execution status

The user subsequently confirmed private-task disclosure and the $12 threshold. The authorised concurrent attempt used protocol 1.0.2 and was interrupted by the environment with `network approval was cancelled before a decision was returned`. Its [separate archive](../benchmarks/results/2026-09-23-relays-authorised/interrupted-campaign.tar.gz) retains 14 stage records, ten finished endpoints, six endpoints stopped by unavailable usage, 308 unexecuted scheduling records and three in-flight markers. Known charges are at least $0.11302619; total charges are unknown. This first-task-only cohort is incomplete. Protocol 1.0.3 specifies a serial replacement with a $10 threshold, unchanged prompts/scoring and package 2.2.1's partial-charge accounting fix. The following paragraph records the earlier, pre-confirmation attempt.

**No new task outcome was saved.** Automatic approval review stopped the campaign because it would send private repository-derived task sources, observations and model hand-offs to `api.openai.com`. The GitHub connector subsequently confirmed that `emmett08/earl` is private. The current instruction to run experiments with the supplied key was not recognised by that automatic review as explicit authorisation for this disclosure.

Three stages had in-flight checkpoint markers. Their response, token use and billing are **unknown**. They have not been rerun. The [interrupted archive](../benchmarks/results/2026-09-23-relays/interrupted-campaign.tar.gz) preserves the full pre-task freeze and markers; [execution metadata](../benchmarks/results/2026-09-23-relays/execution-metadata.json) records the block. Zero completed records supplies no evidence about model accuracy, sequence advantage or cost per correct answer.

A future authorised campaign must preserve these records and identify itself separately. The runner will refuse to silently replay an interrupted request with unknown usage. The original freeze used protocol version 1.0.0; the current protocol version 1.0.1 records the newly observed access blocker and has status `specified`.

## Capability probes

All eleven preliminary API probes succeeded and returned the requested pinned model identities. These probes sent only a short greeting instruction or a trivial `ping` function schema, without repository tasks. They test endpoint capability, not engineering reasoning.

| Snapshot | Text response | Native function response |
| --- | --- | --- |
| GPT-4.1 nano, 2025-04-14 | Passed | Passed |
| GPT-4.1 mini, 2025-04-14 | Passed | Not requested |
| GPT-4.1, 2025-04-14 | Passed | Passed |
| GPT-5 nano, 2025-08-07 | Passed | Passed |
| GPT-5 mini, 2025-08-07 | Passed | Passed |
| GPT-5, 2025-08-07 | Passed | Passed |

The complete configured token-rate estimate for these probes is **$0.0015704**, excluding the three unknown in-flight task requests. [Raw probe records](../benchmarks/results/2026-09-23-relays/provider-probes.json) retain messages, output, response models, tokens, latency and cost. No key is retained. The small/mini/full groups denote product tiers; the records do not establish parameter counts or performance of parameter-defined open SLMs.

## Statistical calibration

The pre-execution sensitivity simulation generated 1,000 synthetic datasets per scenario, with two perfectly correlated repetitions within each task. Each task's paired correctness difference was sampled from a declared distribution on −1, 0 and +1. This examines the finite-task interval procedure, not language-model performance.

| Independent tasks | True difference 0 | True difference +0.10 | True difference +0.25 |
| --- | --- | --- | --- |
| 6 | 88.9% coverage | 73.8% coverage | 80.1% coverage |
| 12 | 94.4% | 88.8% | 93.5% |
| 24 | 95.0% | 93.0% | 95.9% |
| 48 | 95.0% | 93.2% | 95.3% |

These are simulated coverage fractions for nominal 95% percentile intervals under the specified distributions, using 500 bootstrap draws per dataset. Monte Carlo standard errors, interval width, zero-width frequency and zero-exclusion frequency are retained in the [simulation record](../benchmarks/protocols/relay-precision-simulation.json). Coverage with six clusters is inadequate for a calibrated 95% population claim. The protocol consequently treats actual model comparisons as descriptive pilot estimates and requires new independent tasks for confirmatory work. The larger simulated task counts improve coverage in these scenarios; they do not establish universal sample-size requirements.

## Implementation validation

All **530 tests passed**, including an actual MCP subprocess stage receiving prior evidence while preserving its original task anchors. Adversarial tests check that private scoring fields stay out of hand-offs, failed tool records remain visible, identical prefixes execute once, chain costs include failed producers, common endpoint scoring stays separate from strict tool verification, changed checkpoints are rejected, and unknown interrupted usage blocks further calls.

The wheel and source distribution build successfully. Package validation checks the installed `eal-relay` entry point and freezes all 324 scheduled outcomes without generation. The scientific protocol validator accepted the pre-task 1.0.0 design with zero errors or warnings. Version 1.0.1 preserves that design while recording the observed authorisation blocker.

Private-task disclosure is now explicitly authorised. The serial replacement is pending; the interrupted cohorts do not establish comparative sequence effects.
