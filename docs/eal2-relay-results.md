# EAL/2 model-sequence results — 23 September 2026

The planned comparison is complete: **27 conditions × six tasks × two repetitions = 324 attempted endpoints**, of which **323 produced finished answers**. Full GPT-4.1 tool evidence → GPT-4.1 nano is correct in **12/12**, versus **8/12 for the same producer's answer alone**. The paired task-weighted difference is **33.3 percentage points**, with a descriptive task-cluster interval of **0.0 to 66.7 percentage points**. The frozen decision is **inconclusive under DM-003 because the interval includes zero**. This exposed synthetic pilot supports no calibrated population-superiority claim.

The four contributing cohorts retain **358 attempted records and 354 finished answers**. These include **34 additional attempts in incomplete blocks**, kept separately from the 324-slot comparison. The [92 earlier trials](eal2-model-results.md) also remain recovered, with original failures and interface confounds. All evidence is retained on the branch for [PR #3](https://github.com/emmett08/earl/pull/3).

## Coverage and primary comparison

The [frozen design](model-relay-experiments.md) compares six pinned model snapshots in small→full, full→small, same-model, reasoning/non-reasoning and three-stage sequences, with alternative tool placement and transferred content. Product tiers identify the small, mini and full models; parameter-defined open SLM performance remains unmeasured.

| Task | Repetitions | Evidence recipient correct | Answer recipient correct |
| --- | ---: | ---: | ---: |
| Sampled negative finding | 0, 1 | 2/2 | 2/2 |
| Defence cannot ground itself | 0, 1 | 2/2 | 0/2 |
| Defence with independent subargument | 0, 1 | 2/2 | 2/2 |
| Cold-room calibration reference repair | 0, 1 | 2/2 | 2/2 |
| Registered RMS velocity | 0, 1 | 2/2 | 2/2 |
| Registered RMS with wrong observation origin | 0, 1 | 2/2 | 0/2 |

The primary conditions share the **exact saved producer output** within each block, with the same recipient, original task and stage budget. Tool-evidence packets contain actual public tool results and failures; private reference labels and scores are excluded. Correctness assesses the final requested claim statuses. A model-only recipient does not independently verify the source or evidence merely by preserving a correct producer answer.

The four discordant pairs comprise both repetitions of circular defence and both repetitions of the wrong-origin observation. The answer-only recipient changes the producer's correct `contested` or `unsupported` status to `supported`; the evidence recipient preserves the correct status. The observed benefit is avoidance of recipient damage to an already correct producer answer.

Evidence adds **$0.01442620** across the twelve sequences, or **$0.00120218 per sequence**. Its recorded cost per correct endpoint is **$0.021847**, versus **$0.030968** for answer-only transfer. The full tool producer alone is correct in **12/12** at **$0.020296 per correct endpoint**. The added recipient supplies no accuracy improvement over the already correct producer on this suite. These descriptive ratios use realised cache rates and six exposed task types; they do not estimate population cost-effectiveness.

Block eligibility depends on **attempted coverage, never correctness**: all 27 conditions must have an attempted endpoint. Failed attempted outcomes remain in the denominator. This rule was declared after the first interruption and is a post-data analysis amendment. The [complete analysis](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/block-analysis.json) selects exactly one cohort per canonical task/repetition block. It retains all 34 incomplete-block attempts separately, including transport and quota failures. Earlier [seven-block](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-explicit/block-analysis.json), [eight-block](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-continuation/block-analysis.json) and [nine-block](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-funded/block-analysis.json) analyses remain unchanged.

## All conditions on the same twelve blocks

Symbols: `n` = GPT-4.1 nano; `m` = GPT-4.1 mini; `l` = GPT-4.1; `rn` = GPT-5 nano; `rm` = GPT-5 mini; `r` = GPT-5. GPT-5 configurations use low reasoning effort. `tool` gives that stage native EAL tools; final suffixes identify transferred content. Snapshot names and configurations appear in the [design](model-relay-experiments.md).

Costs sum each sequence's recorded stage charges, allocating its shared producer in full to that condition at realised cache rates. The final column counts endpoints whose **final stage itself** passed the strict source, evidence and workflow checks.

| Condition | Correct endpoints | Sum of sequence charges, USD | Per correct endpoint, USD | Verified tool endpoints |
| --- | ---: | ---: | ---: | ---: |
| `n_solo` | 6/12 | 0.004852 | 0.000809 | 0 |
| `m_solo` | 8/12 | 0.018493 | 0.002312 | 0 |
| `l_solo` | 8/12 | 0.085136 | 0.010642 | 0 |
| `rn_solo` | 8/12 | 0.002448 | 0.000306 | 0 |
| `rm_solo` | 10/12 | 0.010061 | 0.001006 | 0 |
| `r_solo` | 10/12 | 0.128371 | 0.012837 | 0 |
| `n_tool_solo` | 10/12 | 0.018857 | 0.001886 | 10 |
| `l_tool_solo` | 12/12 | 0.243558 | 0.020296 | 12 |
| `r_tool_solo` | 12/12 | 0.143744 | 0.011979 | 12 |
| `n_l_answer` | 6/12 | 0.078060 | 0.013010 | 0 |
| `l_n_answer` | 8/12 | 0.088967 | 0.011121 | 0 |
| `n_n_answer` | 6/12 | 0.008234 | 0.001372 | 0 |
| `l_l_answer` | 8/12 | 0.149272 | 0.018659 | 0 |
| `n_tool_l_evidence` | 11/12 | 0.416311 | 0.037846 | 0 |
| `l_tool_n_evidence` | 12/12 | 0.262169 | 0.021847 | 0 |
| `l_tool_n_answer` | 8/12 | 0.247742 | 0.030968 | 0 |
| `l_tool_n_transcript` | 10/12 | 0.276624 | 0.027662 | 0 |
| `l_tool_n_none` | 6/12 | 0.248410 | 0.041402 | 0 |
| `r_tool_n_evidence` | 12/12 | 0.163247 | 0.013604 | 0 |
| `n_tool_r_evidence` | 12/12 | 0.273681 | 0.022807 | 0 |
| `n_l_tool_n` | 12/12 | 0.249034 | 0.020753 | 0 |
| `l_n_tool_l` | 12/12 | 0.472870 | 0.039406 | 0 |
| `rm_tool_l_evidence` | 12/12 | 0.452776 | 0.037731 | 0 |
| `l_tool_rm_evidence` | 12/12 | 0.293966 | 0.024497 | 0 |
| `n_m_l` | 6/12 | 0.093609 | 0.015601 | 0 |
| `rn_tool_r_evidence` | 12/12 | 0.275683 | 0.022974 | 0 |
| `r_tool_rn_evidence` | 12/12 | 0.156130 | 0.013011 | 0 |

The [endpoint table](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/complete-block-endpoints.csv) retains every correction/damage transition, latency, token count, cached input and uncached-rate projection. The [stage table](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/complete-block-stages.csv) identifies response models and tool events. The nano→mini→full answer chain is correct in 6/12; the two three-stage return sequences reach 12/12 and 12/12. The full-tool→nano transcript condition reaches 10/12, failing both calibration-repair repetitions after correct producer answers. The [complete aggregate](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/complete-aggregate.json) retains all 351 pairwise contrasts. Apart from the single declared primary comparison, these are exploratory whole-sequence comparisons; they do not isolate chain length or model size.

## Interruptions, recovery and charges

The explicit cohort retained 194 attempts and 192 finished answers. Two original nano tool stages exhaust the calibration repair allowance; one is a failed tool-solo endpoint, while the other's later recipient returns a correct answer. Correct later status labels do not establish source repair. The original [failure summary](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-explicit/failure-summary.json) retains validator diagnostics and unsuccessful revisions. In the final calibration repetition, nano tool solo, GPT-5 mini solo and the full-tool→nano transcript recipient all finish with the wrong `unsupported` status. They remain incorrect completed answers, distinct from the original repair-limit failure.

The first continuation retained 49 attempts and 48 finished answers before HTTP 429. A separate diagnostic returned `insufficient_quota` / `credit_balance_exhausted`; execution stopped. The [diagnostic](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-continuation/provider-diagnostic.json) remains unchanged. After the user added credit, a minimal generation probe succeeded and recorded **$0.0000072**.

The restored-credit cohort then retained **34 attempts and 33 finished, correct answers**, with **38 stages** and **$0.26885568** in known charges. It stopped at a GPT-4.1 transport failure with unavailable usage. The execution tool reported network approval cancellation before a decision returned; this was not a new provider quota diagnosis. A read-only model lookup succeeded afterwards and performed no generation. The [interrupted archive index](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-funded/interrupted-index.json) and [metadata](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-funded/execution-metadata.json) preserve the failure and all scheduling records.

A separately frozen recovery selected only the remaining three canonical blocks. It added **81 attempted endpoints, 81 finished answers and 66 correct answers**, using **93 stages and 138 task requests**. Its known task charges are **$0.76613265**. The unchanged EAL runtime, task inputs, provider settings, scoring, stage budgets, canonical trial identities and condition order were checked before calls. Incomplete earlier blocks were preserved; completed blocks were not repeated.

The selected twelve blocks use **372 unique stages and 514 model requests**, with **6,216,051 input tokens**, **43,217 output tokens** and **3,220,992 cached input tokens**. Their unique recorded model charges total **$3.03964318**. Repricing those tokens at configured uncached rates gives **$5.05590430**, a projection rather than another deployment measurement. Shared stages count once in campaign charges.

Since the user restored credit, recorded additional charges are **at least $1.03499553**, including the generation probe and both funded cohorts. Across all new cohorts and successful probes, known charges are **at least $3.35825848**. Historical requests with unavailable usage remain unpriced, so actual cumulative charges remain unknown. Configured token-rate estimates exclude host hardware, labour and tax.

The final [budget reconciliation](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/budget-reconciliation.json) reserves **$4.75** for historical unknown usage, lowers the phase threshold to **$2.00**, and retains **$2.12792** single-response headroom. Its pre-call exposure was **$11.47004583**, below the original **$12** stop threshold. The reservation includes the newly failed request; it is a conservative planning allowance, not recovered billing or a provider-enforced invoice cap. Each interrupted phase stopped at its first new unknown charge.

## Preserved runs and publication

| Cohort | Frozen protocol / package | Retained record |
| --- | --- | --- |
| Initial | 1.0.0 / 2.2.0 | No stage response; three orphan markers; disclosure review block |
| Confirmed concurrent | 1.0.2 / 2.2.0 | 14 stages, ten finished endpoints; network approval cancellation |
| Serial replacement | 1.0.3 / 2.2.1 | No response; one orphan marker; review did not recognise confirmation |
| Explicit authorisation | 1.0.5 / 2.2.2 | 222 stages, 194 attempts, 192 finished answers; unpriced transport failure |
| Blocked numerical completion | 1.0.6 / 2.2.2 | No response; one orphan marker; additional-spending review block |
| Renewed authorisation | 1.0.8 / 2.2.2 | 52 stages, 49 attempts, 48 finished answers; exhausted prepaid credit |
| Restored credit | 1.0.10 / 2.2.2 | 38 stages, 34 attempts, 33 finished answers; unpriced transport failure |
| Final recovery | 1.0.11 / 2.2.2 | 93 stages, 81 attempts, 81 finished answers; all three selected blocks attempted |

Archive indexes: [initial](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays/index.json), [confirmed](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-authorised/index.json), [serial](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-serial/index.json), [explicit](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-explicit/index.json), [blocked completion](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-completion/index.json), [continuation](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-continuation/numerical-interrupted-index.json), [restored credit](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-funded/interrupted-index.json), and [final recovery](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/campaign-index.json). Intermediate checkpoints overlap the final archives and must not be counted as additional cohorts. Frozen raw bytes remain unchanged; markers matching priced completion records are not additional unknown requests.

The user authorised private EAL sources, observations and model hand-offs to `api.openai.com`, retained the $12 limit, and requested continuation and remote push. Automatic review initially rejected a new GitHub push as an unverified sensitive-data destination. Read-only repository checks confirmed private `emmett08/earl`, ownership by the authenticated user, push permission and the matching existing remote/PR. The subsequent push succeeded. Publication continues to the same branch, `feat/eal2-forward-contracts`, in PR #3.

## Capability probes

The eleven original text/native probes succeeded with the requested pinned snapshots; their [archive](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays/provider-probes.json) retains outputs and the **$0.0015704** configured-rate estimate. The additional [post-funding probe](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-funded/recovery-probe.json) succeeded at **$0.0000072**. These twelve successful probes are capability evidence outside task-accuracy denominators. Read-only credential/model checks performed no generation. The failed quota diagnostic is retained separately with unavailable usage.

## Statistical calibration

The pre-execution sensitivity simulation generated 1,000 synthetic datasets per scenario, with two perfectly correlated repetitions within each task. Each task's paired correctness difference was sampled from a declared distribution on −1, 0 and +1. This examines the finite-task interval procedure, not language-model performance.

| Independent tasks | True difference 0 | True difference +0.10 | True difference +0.25 |
| --- | --- | --- | --- |
| 6 | 88.9% coverage | 73.8% coverage | 80.1% coverage |
| 12 | 94.4% | 88.8% | 93.5% |
| 24 | 95.0% | 93.0% | 95.9% |
| 48 | 95.0% | 93.2% | 95.3% |

These are simulated coverage fractions for nominal 95% percentile intervals under the specified distributions, using 500 bootstrap draws per dataset. Monte Carlo standard errors, interval width, zero-width frequency and zero-exclusion frequency are retained in the [simulation record](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/protocols/relay-precision-simulation.json). Coverage with six clusters is inadequate for a calibrated 95% population claim. The protocol consequently treats actual model comparisons as descriptive pilot estimates and requires new independent tasks for confirmatory work. The larger simulated task counts improve coverage in these scenarios; they do not establish universal sample-size requirements.

## Validation and remaining research

Package **2.2.2** and language **EAL/2** are unchanged. The continuation's **15 targeted tests** passed, including missing-block selection, schedule identity, adapter restoration, cumulative spending and block analysis. The frozen recovery preflight reproduced all 81 selected canonical slots with unchanged source, suite, provider and scoring identities. Protocol 1.0.12 records the complete comparison and validates with no errors or warnings. GitHub CI passed the implementation's repository checks and package build.

Archive/member hashes, frozen/checkpoint hashes, schedule identities, scores, original source anchors, hand-off identities and per-request charges pass the offline audits. Complete-block analysis retains exact shared-producer and no-handoff invariants. The full aggregate reproduces all 27 condition counts and costs and the primary estimate; its coverage guard rejects the earlier nine-block dataset. All four model-facing runtime/reference drift flags are false. No further paid requests are needed for this planned campaign.

Fresh independent tasks, a token-matched evidence ablation and a parameter-defined open SLM remain necessary for broader claims. Correct status answers on exposed synthetic fixtures do not establish physical engineering validity, independent recipient verification or general model-class superiority.
