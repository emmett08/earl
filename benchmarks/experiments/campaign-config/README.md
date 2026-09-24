# Cross-model recipient campaign

`cross-model-developmental.json` freezes the existing four-root synthetic pilot
as a **developmental** comparison. It has three successive evidence states per
root and five delivery routes crossed with three declared model classes:

| Route | Input to recipient | Final status source | Calls per case |
| --- | --- | --- | ---: |
| `raw` | EAL/2 source and acquired records | Recipient | 1 |
| `skill` | Same source/records plus short instructions | Recipient | 1 |
| `skill_route` | Task, skill and candidate artefacts; then a checked packet if the model requests the permitted assessment | Host after valid request | 1 or 2 |
| `eal_host` | Compact claim-scoped EAL assessment | EAL host | 1 |
| `equal_checker` | Independent generic graph checker result in the same output contract | Generic checker host | 1 |

The strong reasoning comparison is the `raw` route on the reasoning-class
model, not a purported extra skill or delivery route. The `skill` condition
measures instruction following only. The `skill_route` condition records an
actual model-originated **text JSON request**, validates its artefact and
claim against the authorised task, runs a fresh host assessment, and exposes
the result in a second model call. It does not measure native function calling
or remote MCP access. It selects among a bounded set of known artefact IDs;
this is **not a test of family retrieval or parameter binding**. A bad request
is retained as a completed failure to route. Host packets are the final status
even if the recipient contradicts them; recipient explanations still require
independent adjudication.

The source files, tool acquisitions, comparator graphs, provider configurations,
method fingerprints, oracle statuses, host traces, messages, ordering and
parity checks and implementation hashes are frozen before the first generation
call. The comparator graphs were authored separately from EAL. The 60 generated
envelope mutations check the generic checker alone; authored challenge states
run through *both* implementations. These are bounded fixture checks, not proof
of general semantic equivalence.

The separate `cross-model-cohort-developmental.json` freezes the new three-root
cohort as a **developmental** schedule of 135 requests, with no paid execution
yet. `cross-model-confirmatory.json` points at the same new corpus and is
blocked. Its
independent oracle and comparator review is pending. Offline preflight checks
its current 9 scored states, 5 authored challenge states and 45 generated
checker-only tamper cases without permitting model calls. A paid confirmatory freeze also
requires an attestation tied to the exact corpus hash, two reviewers per state,
review of the independent comparator implementation hash, and measured
authoring/review effort. The runner rejects a missing or changed attestation.
These metadata are an audit record; software cannot verify human independence.
`independent-review.template.json` and `cost-measurement.template.json` leave
unknown reviewer identities and hours null. Record genuine measurements in the
corpus before producing the final signed-off review; changing the corpus
changes its hash and invalidates earlier attestations.

## Reproduce the offline gates

From the repository root:

```sh
PYTHONPATH=src:. python -m pytest -q tests/test_cross_model_campaign.py
PYTHONPATH=src:. python scripts/run_cross_model_campaign.py \
  benchmarks/experiments/cross-model-confirmatory.json /tmp/cross-model-confirmatory-check --preflight
PYTHONPATH=src:. python scripts/run_cross_model_campaign.py \
  benchmarks/experiments/cross-model-developmental.json /tmp/cross-model-developmental --freeze-only
```

The last command freezes **180 scenario requests**, each bounded to 20,000
UTF-8 prompt bytes, with at most 36 additional second model calls when all
route requests succeed. It does not contact a model. With an authorised
`OPENAI_API_KEY` in the process environment, the same command with `--resume`
executes the frozen schedule. The planning stop is US$4 at the configured
rates. A routed case reserves a full bounded second prompt before its first
call, and checks the actual second prompt and remaining budget again before
transmission. Byte-based reservation is not an invoice guarantee. Each request is
written as pending *before* transmission. A crash, failed request or unknown
usage blocks automatic resume so a potentially billed call is never silently
repeated. Inspect and reconcile the ledger before starting a new study.

```sh
PYTHONPATH=src:. python scripts/run_cross_model_campaign.py \
  benchmarks/experiments/cross-model-developmental.json /tmp/cross-model-developmental --resume
PYTHONPATH=src:. python scripts/analyse_cross_model_campaign.py \
  /tmp/cross-model-developmental --output /tmp/cross-model-analysis.json
```

The ledger retains raw responses, returned model identity, provider usage,
estimated price, each subcall, malformed outputs, host contradictions,
model request failures and elapsed time. No credentials appear in config or
ledger. Prices are configured rate estimates; confirm prevailing rates before
paid execution. The main metric is the rate of false `supported` answers
among completed adverse states, alongside exact status, malformed output,
route invocation, contradictions, token usage, failures and latency.

`analyse_cross_model_campaign.py` pairs cases within root/state/repetition and
resamples whole roots for descriptive contrasts. Four selected roots cannot
support broad population inference. Explanation faithfulness remains
`unavailable` until a separate file provides two reasoned judgements and
final adjudication for every completed response, linked to the ledger hash.
Root-level human authoring and review time is unmeasured in the developmental
fixtures, so cost per correct accepted decision is also `unavailable`. To
compute it, record per-root `effort` entries for common and route-specific
author/review hours, hourly rate and direct spending; per-state `costs` for
acquisition and both checker computation rates; and
`adjudication_cost_usd` for every independently reviewed recipient response.
Then the stand-alone route estimate is

`(model charges + root author/review + acquisitions + host/checker compute + explanation adjudication) / correctly accepted, faithful decisions`.

The report preserves each component and leaves the total unavailable until
every component and explanation judgement is measured. It reports model API
latency separately from offline frozen preassessment and fresh routed host
assessment; precomputed fixtures do not establish deployment latency. Missing
expenditure is never treated as zero.
