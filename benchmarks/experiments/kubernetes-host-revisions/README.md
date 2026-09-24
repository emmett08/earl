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
run. Those frozen input and result files retain their original bytes and
describe the earlier host contract. The original design, source and result remain under
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
occurred. Hashes of all input files appear in the retained
`results.offline.json` from the earlier run.

Primary operational questions:

1. Does the raw evaluator still derive the author's predeclared status pairs
   for all seven revisions, while the current host issues checked packets
   only when the full selected-claim evidence closure is acquired and fresh?
2. Does a claim packet remain at most 3,072 UTF-8 JSON bytes and omit direct
   traces for unrelated claims, while an authorised explanation includes the
   prerequisite record claim and its evidence?
3. Does lexical retrieval nominate relevant families and abstain on
   underspecified or unrelated tasks, without turning a suggestion into
   an authorised binding?
4. Do changed source identity, an unreviewed cluster, a wrong family/claim
   pair and an unknown family fail closed?

The seven revisions are repeated 20 times in separate temporary workspaces
per revision, using the same local JSON observations and a fixed assessment
time. For each repeat the runner measures assessment, explanation, finish and
combined host wall time with `perf_counter_ns`. A refusal measures assessment
and combined time only; packet, explanation and finish fields are null. It
reports per-revision median and nearest-rank p95 where an operation occurred;
the first assessment is included. The ten
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

The interpretation separates the raw EAL/2 assessment from host delivery.
The evaluator's seven status pairs remain a regression against the authored
fixture. The host must refuse the two revisions with stale required evidence:
`bounded_load` in `stale_load_record`, and `batch_pressure`,
`monitor_complete` and `separate_reservation` in `stale_pressure_gap`.
The latter's raw `unsupported` result remains diagnostic; no recipient
packet is issued. A mismatch diagnoses a host or fixture defect. A packet
above its bound, trace leakage or accepted unreviewed tuple invalidates the
claimed interface property. Lower retrieval precision or synonym recall motivates
revised metadata or a separately evaluated retrieval system; it does not
alter the host-owned verdict. An unforeseen result is reported as a failure
requiring an amended fixture and a new developmental run.

## Retained result

Run with:

```bash
PYTHONPATH=src python benchmarks/experiments/kubernetes-host-revisions/run.py \
  --repetitions 20 \
  --output benchmarks/experiments/kubernetes-host-revisions/results.current.json
PYTHONPATH=src python -m pytest -q tests/test_kubernetes_host_revision_study.py
```

The retained `results.offline.json` is historical and should not be overwritten
by this command. Its Linux x86-64/Python 3.12.14 run observed 7/7 expected
operating-basis statuses and decisive causes and 7/7 separate record-content
statuses. The new batch contention was `contested` for the operating basis
while the record remained `supported`. The stale load, failed test, wrong
deployment and stale monitoring coverage were `unsupported` for the
operating basis. The earlier passing record remained `supported` when the
load result or coverage was stale for the operating inference. With stale
monitoring coverage, a stale pressure record cannot supply an active
challenge, but absence of a challenge does **not** restore an operating
basis: its mandatory fresh-coverage premise fails.

In that retained run, the mean compact packet was 1,553 bytes, versus 6,042
bytes for its then-direct explanation (mean ratio 0.257). Per-revision median end-to-end
assess/explain/finish times ranged from 161.0 to 174.4 ms locally.
Candidate retrieval obtained 8 true positives, 6 false positives and
1 false negative: micro precision@3 0.5714, recall@3 0.8889, top-one hit
rate 0.875 for eight target queries, and abstention 1/2 for zero-target
queries. The miss was `traffic switch backup`; the generic
`Kubernetes` query returned a spurious candidate. These ten authored
queries are insufficient to estimate field retrieval quality.

With the current complete-collection claim route, a one-repeat developmental
rerun recovered 7/7 raw status pairs, issued five checked claim packets and
refused two stale revisions. Valid observations that make an objection
predicate false remain usable negative findings. Failed acquisition, stale
records, invalid record identity or malformed predicates prevent delivery;
the failure and raw assessment remain in the local store. The host also
requires observations for alternative support branches, even when another
branch could independently support the claim. Which adverse monitors belong
in an argument remains an authored review obligation: the gate cannot detect
an omitted declaration.

The host rejected the unreviewed `prod_west` tuple, wrong family/claim
pair and unknown family. The test suite also verifies that source drift
invalidates the pinned artefact. Packet and trace byte sizes are not model
token counts. The retrieved evidence here is fixture JSON with
`consistency_checked_not_authenticated` integrity: it cannot authenticate
apiserver state, the collector or the engineer's intervention.
The current authorised explanation follows the prerequisite
`checkout_test_record` through `record_route` to `recorded_load`, including
the relevant objection and defence evidence. It omits the unrelated digest
and failover claims. The full trace remains bounded and accessible only for
the selected claim route.

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
