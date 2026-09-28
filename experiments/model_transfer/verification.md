# Model-session investigation verification

Recorded 2026-09-28 for protocol 2.0.0 and package 2.15.0. These are software
and measurement-instrument checks. No live API experiment has been run with
this revision.

| Check | Actual result |
| --- | --- |
| `make check` | 702 passed, 1 skipped; generated ANTLR sources verified; maintained synthetic API example exercised through CLI/MCP. |
| Real EAL calibration | All 24 case/session checks passed, with zero API requests. |
| Scripted pipeline | 48 sequences and 144 sessions completed across both donors, recipients, native-tool settings and all three arms. |
| Retained-result analysis | Append-only journal reconstructs the API records; the offline CLI reproduces all report measurements. |
| Protocol validator | VALID, specified status, zero errors and zero warnings. |
| `make build` | Source distribution and wheel built for 2.15.0. |
| Distribution inspection | New runtime and experiment modules included; generated run directories excluded. |
| Workflow parsing | Only `workflow_dispatch`; live execution defaults to false. |
| `git diff --check` | Clean. |

Assignment checks verify all 256 standard-plan sequences, matched arms, crossed
donor/case coverage, repetitions and fixed-seed replay. The scripted pipeline
checks fresh conversation histories, naturally produced notes, native-tool
masks and reasoning-item continuation within a session. In its recipient
sessions, compatible EAL reuse produces 24 reuses and eight collections;
forced collection produces 32 collections. These figures describe the scripted
fixtures, not observed model behaviour.

Scoring checks independently cover inclusive threshold/freshness boundaries,
exclusive assumption expiry, negative and missing measurements, incorrect
citations, appropriate abstention labels, no answers, ambiguous JSON and rejected
optional files. Analysis checks cover known zero and positive paired differences,
all planned units after a fatal failure, incomplete provider usage, interrupted
requests, lost session records and failed host assessments. Unknown resource
amounts remain distinguishable from measured zeroes.

Five maintained reasoning fixtures were also evaluated with the original and
revised evaluator. After removing only the added assumption-time fields and
predicate-failure diagnostics, complete results were identical and matched the
original digests. Snapshot updates reflect those new fields; existing formal
support semantics were retained. Packet/context checks verify bounded diagnostics,
observation times, omitted-data indicators and claim-to-evidence links.

## Implementation boundaries

The context strategies implement the Strategy pattern for ordinary, reuse and
forced-collection conditions. The injected provider Transport separates API
access from study orchestration. ModelContextBuilder owns the checked projection;
ReferenceScorer owns independent task arithmetic; ReportBuilder composes scores
and resource summaries. Existing collectors, repositories, method contracts and
formal evaluation remain in use.

Session execution, answer parsing, assignment, calibration, accounting and
journal persistence are separate modules with one responsibility each. Durable
attempt logging is extracted from the provider, avoiding full-log rewrites on
every call. The packet evidence projection remains together because its bounded
allowlist, omission count and state projection form one responsibility. No new
plugin framework or general-purpose workflow abstraction is introduced.

## Empirical status

The historical run is documented separately in
[run-36432530106.md](results/run-36432530106.md); its original scores are unchanged.
It does not validate the revised experiment. Credentialed manual execution is
required to observe actual model answers, provider compatibility, latency and
usage under the common structured-output contract.

The selected tasks are synthetic and the EAL sources are pre-authored. The revised
model experiment cannot establish human authoring savings, population model-class
effects, performance on general engineering tasks or isolated reasoning benefits.
Its additional cases are prospective additions, not independent confirmation.
