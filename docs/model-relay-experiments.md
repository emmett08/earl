# Model sequence and evidence-transfer experiments

`eal-relay` runs one to four explicitly configured model stages. Each stage starts a fresh host and receives the original task plus a selected record from its predecessor. It supports the existing HTTP and trusted-command provider adapters, so a separately installed open-weight SLM can use the same protocol. Actual external-model claims require saved live responses.

The current plan, [eal2-model-relays.json](../benchmarks/experiments/eal2-model-relays.json), defines 27 conditions on six exposed synthetic EAL/2 regression cases, with two repetitions: 324 sequence outcomes. The [scientific protocol](../benchmarks/protocols/INV-EAL-RELAY-001.json) specifies hypotheses, estimand, controls, sampling limitations, analysis, decision rules and stop conditions. It was validated with the design-scientific-investigations skill before task execution. A local pre-execution freeze is retained; this is not an external preregistration.

## Models and sequences

| Symbol | Pinned model | Configured reasoning | Tool interface when enabled |
| --- | --- | --- | --- |
| n | GPT-4.1 nano, 2025-04-14 | None | Native functions |
| m | GPT-4.1 mini, 2025-04-14 | None | Text only in this plan |
| l | GPT-4.1, 2025-04-14 | None | Native functions |
| rn | GPT-5 nano, 2025-08-07 | Low | Native functions |
| rm | GPT-5 mini, 2025-08-07 | Low | Native functions |
| r | GPT-5, 2025-08-07 | Low | Native functions |

Small, mini and full describe product tiers. Parameter counts are not established by these records. The nano models represent the small-model tier in this campaign; they do not establish results for parameter-defined open SLMs. Pinned models were selected for continuity with the recovered experiments and verified endpoint access, not as a claim about the latest models.

The plan includes every solo model; nano/full non-reasoning and full reasoning models with native EAL tools; small-to-full and full-to-small answer transfer; same-model two-stage controls; tool producer to different-size recipient; full-model evidence to reasoning mini; reasoning-mini evidence to full non-reasoning; reasoning small-to-full and full-to-small; small→full with tools→small; full→small with tools→full; and small→mini→full.

The primary contrast is `l_tool_n_evidence` minus `l_tool_n_answer`. Both conditions use the **same saved producer output** for each task/repetition. Their final model, stage limits and original task are equal. This estimates the difference produced by the additional transferred record, including its extra prompt tokens. It does not isolate a token-independent mechanism.

## What moves between stages

| Mode | Content |
| --- | --- |
| none | Original task only; no prior output |
| answer | Prior claim-status map, producer identity and completion status |
| evidence | Answer plus actual tool events, source revisions, final source and earlier evidence packets |
| transcript | Evidence plus the externally visible conversation |

Packets preserve failed operations. A digest identifies their contents. The producer's scores, reference labels and explanatory oracle never enter a packet. Transcript transfer covers visible messages, tool requests and tool feedback; it does not obtain private provider reasoning. Every recipient treats prior output as fallible data. Earlier session identifiers cannot refer to a recipient's new local store.

Identical stage inputs within a task/repetition are executed once. This shares first stages across conditions and gives content ablations a fixed producer. The no-handoff recipient is the exact solo-model input, so its reuse is an implementation control rather than independent statistical evidence. There is no reuse across repetitions or tasks. Model temperature zero is not treated as deterministic.

## Outcomes and accounting

Every endpoint uses `common-endpoint-status/1`: the completed answer must contain exactly the requested claims with their reference statuses. Tool and no-tool endpoints have the same primary criterion. Separately, a tool stage retains the existing source-correspondence, evidence-trace and requested-workflow checks. A correct model-only recipient answer is not reclassified as independently verified because its producer used tools.

All upstream and final-stage failures remain in the archive. Reports retain correction and damage transitions, incorrect positive answers, tokens, repairs, requests, returned model identities, cost and latency. A chain's standalone cost sums every stage, including failed producers and repaired calls. Actual campaign cost counts a reused stage once. Standalone chain latency sums stage durations; elapsed scheduling time includes cache reuse and concurrency and is a different measure. Provider pricing estimates exclude host hardware, labour and tax. Zero marginal MCP fixture charge is an explicit assumption.

Two repetitions of six tasks provide six task clusters. Paired descriptive intervals resample whole tasks and retain both repetitions. The fixed suite is deliberately selected and was already exposed during development. Intervals and accuracy apply to these cases; they do not establish population-wide model performance. All-success bootstrap intervals cannot rule out unseen failures. A pre-execution [sensitivity simulation](../benchmarks/protocols/relay-precision-simulation.json) found only 73.8–88.9% coverage for nominal 95% percentile intervals with six task clusters under its three specified distributions. These descriptive intervals therefore carry no calibrated 95% population-coverage claim. The single declared primary comparison remains a pilot estimate; the other pairwise comparisons are exploratory.

## Execution and recovery

Supply `OPENAI_API_KEY` through the runtime environment. Do not put credentials in TOML, source, shell history or retained output.

```bash
eal-relay --plan benchmarks/experiments/eal2-model-relays.json --output /absolute/new/run-directory
```

The equivalent source-tree entry point is `python -m eal.relay`. `--freeze-only` validates reference cases and saves the plan, protocol, task data, answers, provider identities/configuration, code digests and seeded schedule without model requests. `--resume` requires the exact same frozen definition and never overwrites completed stages or trial records. Each saved record has an integrity digest and is atomically replaced after a complete write.

```bash
eal-relay --plan benchmarks/experiments/eal2-model-relays.json --output /absolute/existing/run-directory --resume
```

A marker records each in-flight stage. If interruption leaves a possibly billed request without a completion record, resuming treats its usage as unknown and stops further paid generation. Resolve provider billing externally or start a separately identified, authorised study; the runner never silently replays that request. Failed model completions with known usage may feed subsequent stages, so the study can observe recovery.

The user confirmed a $12 model-charge threshold. The serial replacement uses $10, leaving an allowance for the interrupted attempts, with $0.20 and 180 seconds per stage, ten requests and 120,000 tokens. Unknown prior charges remain unknown. Cost and token checks occur around responses; a response may exceed a threshold. These are recorded spending controls, not provider-enforced invoice caps. Tool fixture operations have separate zero marginal API pricing. An oversized hand-off fails explicitly rather than dropping qualifications or diagnostics.

## Next discriminating study

Use new, independently authored tasks after this pilot identifies interface and ceiling effects. Include a parameter-defined open SLM through the command provider and a token-matched evidence ablation. Estimate the required independent task count from observed discordance before making confirmatory superiority or cost-effectiveness claims. Conditional small-to-large escalation requires its own frozen routing rule and evaluation; this fixed-sequence study does not estimate that deployment strategy.

Official model documentation, accessed 23 September 2026: [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1), [mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano), [GPT-5](https://developers.openai.com/api/docs/models/gpt-5), [mini](https://developers.openai.com/api/docs/models/gpt-5-mini), [nano](https://developers.openai.com/api/docs/models/gpt-5-nano). Availability and capabilities were also probed directly; probes are retained outside the task-accuracy denominator.

Current execution status: see the [execution and validation report](eal2-relay-results.md). The user explicitly confirmed private-task disclosure and spending. After network approval cancellation interrupted the authorised concurrent campaign, protocol 1.0.3 schedules one serial replacement. Earlier raw records and unknown usage remain preserved separately. Package 2.2.1 retains known charges from completed requests even if a later request in the same stage has unknown usage.
