# Kubernetes host and finite-family revision study

This is an executable **developmental synthetic** study of the EAL/2 host
adapter, claim-scoped packet and finite reviewed-family selector. It exercises
the current source and host contracts without changing EAL/2 grammar. It
does not contact Kubernetes or a model provider.

Two claims separate an earlier observation from a forward decision. The
`checkout_test_record` claim says that a submitted record for
`checkout-api` in `prod_east/checkout` reports p99 at most 200 ms at at
least 400 requests per second with at least four replicas. Its observation
remains available for a day within this synthetic assessment. The selected
`checkout_latency` claim says that a recent qualifying result and fresh
monitoring coverage supply a *provisional basis to consider* five minutes of
operation under unchanged deployment, traffic and resource conditions. A
second engineer's batch job can challenge that forward inference without
changing the earlier record. A current separate reservation observation
answers the named contention challenge, subject to independent verification
of its physical meaning. A string value saying `cpu_reservation_effective`
does not prove isolation or future SLO compliance.

## Frozen design and analysis

The fixture author specified seven revised status pairs and ten query
relevance sets in `manifest.json` before the retained 20-repeat timing
run. The original design, source and result remain under
`docs/history/kubernetes-host-revisions-v1/` as superseded developmental
evidence: its contention attack targeted a literal record-reporting claim.
The same person
specified expected claim statuses, so the comparison is a regression and
feasibility check, not independent adjudication or confirmatory evidence.
The pinned `source.eal`, `artifacts.toml` and `families.toml` bind one
cluster/namespace tuple, one prerequisite record claim and three family
selected claims to an exact source,
assessment time, method fingerprint and context. The catalogue's
`reviewed_by` entry explicitly says that independent review has **not**
occurred. Hashes of all input files appear in `results.offline.json`.

Primary operational questions:

1. Does the host return the author's predeclared operating-basis status and
   decisive cause after a passing, challenged, stale, failed, answered or
   wrong-identity observation, while keeping the separate record-content
   status unchanged by a new contention alert?
2. Does a claim packet remain at most 3,072 UTF-8 JSON bytes and omit direct
   traces for unrelated claims, while an authorised explanation remains
   retrievable?
3. Does lexical retrieval nominate relevant families and abstain on
   underspecified or unrelated tasks, without turning a suggestion into
   an authorised binding?
4. Do changed source identity, an unreviewed cluster, a wrong family/claim
   pair and an unknown family fail closed?

The seven revisions are repeated 20 times in separate temporary workspaces
per revision, using the same local JSON observations and a fixed assessment
time. For each repeat the runner measures assessment, explanation, finish and
combined host wall time with `perf_counter_ns`. It reports per-revision
median and nearest-rank p95; the first assessment is included. The ten
fixed queries are run once because retrieval is deterministic; its times are
small local measurements, not network latency. JSON size uses compact UTF-8
serialisation. There is no token proxy, API charge or cost estimand in this
offline study.

Retrieval is scored against the author's candidate relevance sets at
`limit=3`: micro precision is `TP/(TP+FP)`, micro recall is
`TP/(TP+FN)`, top-one hit rate uses queries with at least one relevant
family, and abstention rate uses only zero-target queries. A candidate is
relevant to `prod_west` as a *family suggestion*, but no reviewed case exists
for that parameter tuple, so the exact resolver rejects execution. Generic
`Kubernetes` is marked as underspecified: it has no relevant exact family.
These are candidate labels, not evidence that a family is valid for the
requester's actual task.

The interpretation is: correct status pairs and cause across all revisions
establish that this implementation followed these authored records and
argument dependencies; a mismatch diagnoses a host/fixture defect. A packet above its
bound, trace leakage or accepted unreviewed tuple invalidates the claimed
interface property. Lower retrieval precision or synonym recall motivates
revised metadata or a separately evaluated retrieval system; it does not
alter the host-owned verdict. An unforeseen result is reported as a failure
requiring an amended fixture and a new developmental run.

## Retained result

Run with:

```bash
PYTHONPATH=src python benchmarks/experiments/kubernetes-host-revisions/run.py \
  --repetitions 20 \
  --output benchmarks/experiments/kubernetes-host-revisions/results.offline.json
PYTHONPATH=src python -m pytest -q tests/test_kubernetes_host_revision_study.py
```

The retained Linux x86-64/Python 3.12.14 run observed 7/7 expected
operating-basis statuses and decisive causes and 7/7 separate record-content
statuses. The new batch contention was `contested` for the operating basis
while the record remained `supported`. The stale load, failed test, wrong
deployment and stale monitoring coverage were `unsupported` for the
operating basis. The earlier passing record remained `supported` when the
load result or coverage was stale for the operating inference. With stale
monitoring coverage, a stale pressure record cannot supply an active
challenge, but absence of a challenge does **not** restore an operating
basis: its mandatory fresh-coverage premise fails.

The mean compact packet was 1,553 bytes, versus 6,042 bytes for its direct
explanation (mean ratio 0.257). Per-revision median end-to-end
assess/explain/finish times ranged from 161.0 to 174.4 ms locally.
Candidate retrieval obtained 8 true positives, 6 false positives and
1 false negative: micro precision@3 0.5714, recall@3 0.8889, top-one hit
rate 0.875 for eight target queries, and abstention 1/2 for zero-target
queries. The miss was `traffic switch backup`; the generic
`Kubernetes` query returned a spurious candidate. These ten authored
queries are insufficient to estimate field retrieval quality.

The host rejected the unreviewed `prod_west` tuple, wrong family/claim
pair and unknown family. The test suite also verifies that source drift
invalidates the pinned artefact. Packet and trace byte sizes are not model
token counts. The retrieved evidence here is fixture JSON with
`consistency_checked_not_authenticated` integrity: it cannot authenticate
apiserver state, the collector or the engineer's intervention.
The selected claim's direct explanation names the prerequisite record claim
and its acceptability label but does not include that premise's full evidence
trace. An independent reviewer needs an authorised, bounded transitive trace
or separate access to the prerequisite's assessment.

## What a cluster study would need

Use a scoped collector with recorded principal, cluster UID, namespace,
deployment UID/generation, pod UID, node UID, resourceVersion, collection
request and time. Correlate rollout and scheduler snapshots with observed
CPU throttling, allocatable and requested resources, HPA events, tail latency
under specified traffic, and independent service probes. Measure before and
after the competing workload under a declared load and observation window.
Keep an immutable provenance record and test collector failure, stale
records, identity mismatch and missing metrics. A live experiment then needs
independently reviewed task/claim fixtures and an independent adjudicator.
An event or TTL must trigger reassessment when deployment, resource quotas,
requests, limits, node allocatable capacity, HPA state or competing workloads
change. A previous status cannot be carried forward solely because a query
retrieves the same family.

The local timings describe a single synthetic host and cannot support
claims about MCP transport, paid model latency, token usage, cluster
correctness, proof sufficiency, continuous monitoring or production cost.
