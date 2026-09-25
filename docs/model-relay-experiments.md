# Model sequence and evidence-transfer experiments

`eal-relay` runs one to four explicitly configured model stages. Each stage starts a fresh host and receives the original task plus a selected record from its predecessor. It supports the existing HTTP and trusted-command provider adapters, so a separately installed open-weight SLM can use the same protocol. Actual external-model claims require saved live responses.

The current plan, [eal2-model-relays.json](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-model-relays.json), defines 27 conditions on six exposed synthetic EAL/2 regression cases, with two repetitions: 324 sequence outcomes. The [scientific protocol](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/protocols/INV-EAL-RELAY-001.json) specifies hypotheses, estimand, controls, sampling limitations, analysis, decision rules and stop conditions. It was validated with the design-scientific-investigations skill before task execution. A local pre-execution freeze is retained; this is not an external preregistration.

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

All upstream and final-stage failures remain in the archive. Reports retain correction and damage transitions, incorrect positive answers, tokens, repairs, requests, returned model identities, cost and latency. Transition counts describe changes in stage correctness; causal interpretation requires the controlled contrast. A sequence's cost sums every recorded stage charge, including failed producers and repaired calls, at realised cache rates. Independent deployment may have different cache availability. Actual campaign cost counts a reused stage once. Sequence latency sums stage durations; elapsed scheduling time includes cache reuse and concurrency and is a different measure. Provider pricing estimates exclude host hardware, labour and tax. Zero marginal MCP fixture charge is an explicit assumption.

Two repetitions of six tasks provide six task clusters. Paired descriptive intervals resample whole tasks and retain both repetitions. The fixed suite is deliberately selected and was already exposed during development. Intervals and accuracy apply to these cases; they do not establish population-wide model performance. All-success bootstrap intervals cannot rule out unseen failures. A pre-execution [sensitivity simulation](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/protocols/relay-precision-simulation.json) found only 73.8–88.9% coverage for nominal 95% percentile intervals with six task clusters under its three specified distributions. These descriptive intervals therefore carry no calibrated 95% population-coverage claim. The single declared primary comparison remains a pilot estimate; the other pairwise comparisons are exploratory.

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

The user confirmed a $12 model-charge threshold. The historical serial replacement used $10, with $0.20 and 180 seconds per stage, ten requests and 120,000 tokens. Later continuations refreshed cumulative charges and conservative reservations before calls. The final recovery used a $2 phase threshold, a $4.75 historical unknown-usage reservation and $2.12792 single-response headroom; planned exposure was $11.47004583. Unknown prior charges remain unknown. Cost and token checks occur around responses; a response may exceed a threshold. These are recorded spending controls, not provider-enforced invoice caps. Tool fixture operations have separate zero marginal API pricing. An oversized hand-off fails explicitly rather than dropping qualifications or diagnostics.

## Next discriminating study

Use new, independently authored tasks after this pilot identifies interface and ceiling effects. Include a parameter-defined open SLM through the command provider and a token-matched evidence ablation. Estimate the required independent task count from observed discordance before making confirmatory superiority or cost-effectiveness claims. Conditional small-to-large escalation requires its own frozen routing rule and evaluation; this fixed-sequence study does not estimate that deployment strategy.

Official model documentation, accessed 23 September 2026: [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1), [mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano), [GPT-5](https://developers.openai.com/api/docs/models/gpt-5), [mini](https://developers.openai.com/api/docs/models/gpt-5-mini), [nano](https://developers.openai.com/api/docs/models/gpt-5-nano). Availability and capabilities were also probed directly; probes are retained outside the task-accuracy denominator.

Current execution status: **the planned comparison is complete**; see the [results and validation report](eal2-relay-results.md). Twelve complete blocks supply 324 attempted endpoints and 323 finished answers. Four contributing cohorts retain 358 attempts and 354 finished answers, with 34 incomplete-block attempts kept separately. Evidence transfer is correct in 12/12 versus 8/12 for answer-only transfer; the primary descriptive interval includes zero. Protocol 1.0.12 records the complete comparison and its bounded interpretation. Package 2.2.2 retains partial known charges and uses `EAL/relay-report/2`: recorded, attempted, completed, partial, unexecuted and unrecorded endpoint counts are distinct. Scheduling stops are excluded from model-outcome aggregates. The aggregate helper's `completed_trials` counts attempted records, including failed attempts; the report's top-level `completed_trials` counts finished answers. No further paid requests are needed for this pilot.


## Offline evidence audit

For any completed or interrupted archive, run:

```bash
PYTHONPATH=src python scripts/audit_relay_checkpoints.py --run /absolute/run-directory --output /absolute/audit-directory
```

This performs no provider calls and writes a checkpoint audit plus endpoint and stage CSV tables. It verifies frozen inputs, recorded identities, scores, transfers and per-request charges without modifying raw evidence. Missing endpoints remain missing; stale markers with matching completed records are distinguished from unknown orphan requests. `scripts/analyse_relays.py` is the stricter full-cohort exporter and requires every stage and scheduled endpoint.

For the final comparison, extract the four contributing archives into separate directories and compare only blocks in which all conditions were attempted:

```bash
PYTHONPATH=src python scripts/analyse_relay_blocks.py \
  --run /absolute/relay-explicit \
  --run /absolute/relay-continuation-numerical \
  --run /absolute/relay-funded-remaining \
  --run /absolute/relay-final-recovery \
  --canonical-freeze /absolute/relay-explicit/freeze.json \
  --output /absolute/block-analysis
```

The analysis retains failed attempted outcomes, lists missing blocks and withholds the declared six-task estimand while coverage is incomplete. Repeated `--run` arguments can combine separately frozen cohorts only if their implementation, suite, providers, stage budgets and conditions match. Duplicate complete blocks cause an error; the script never chooses the better result. The final [block analysis](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/block-analysis.json) has no missing blocks. Run `scripts/aggregate_relay_blocks.py` with the same `--run` and `--canonical-freeze` arguments and `--output /absolute/complete-aggregate.json` to reproduce all 351 pairwise contrasts. The [retained aggregate](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-relays-recovery/complete-aggregate.json) distinguishes the primary comparison from exploratory contrasts and checks its counts, charges and primary estimate against the audited blocks.

The historical [numerical](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-model-relays-completion-numerical.json) and [repair](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-model-relays-completion-repair.json) plans describe interrupted work. Later continuations used `scripts/run_relay_remaining.py`, an external serial scheduling adapter whose source hash and selection manifest are embedded in the frozen protocol. It preserves original task/repetition identities, condition order and sampling labels while selecting exactly the missing canonical blocks. The [funded manifest](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-model-relays-remaining.json) selected four blocks; after its transport interruption, the [recovery manifest](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-model-relays-recovery-blocks.json) selected the final three. Their raw freezes retain protocols 1.0.10 and 1.0.11 respectively. Current protocol 1.0.12 is the completion record, so historical executions must be reproduced from their archived definitions and recorded commits, not silently resumed against the amended protocol.
