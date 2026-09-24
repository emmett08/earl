# Reviewed EAL/2 route and equal JSON comparator: developmental pilot

This executable study checks the current exact-question recipient route on the
three synthetic roots in `../cross-model-delivery/manifest.json`. It also
specifies a small OpenAI model pilot comparing raw EAL/2 source with a
separately authored JSON argument graph. The existing graph checker in
`../../equal_checker.py` is independent of the EAL parser. The JSON wrapper
in `json_checker.py` applies the same exact-question, grant, assessment-time
and complete-acquisition gate as the EAL recipient. Both receive the same
frozen JSON observation envelopes. All reviews in this corpus are pending;
the exercise is developmental and cannot confirm generalisation, human
comprehension, or an EAL/2 advantage.

## Frozen contrasts and measurements

| Contrast | Unit and outcome | What it can establish |
|---|---|---|
| Checked EAL versus checked JSON | Each root/state, status parity and match to the originally authored brief status | Interface and checker agreement on these submitted records; recipient refusals are reported separately from claim statuses. |
| Bound tool request | One model response per root/state, `assess_bound_task` adherence | Text request conformance; the launcher binds the original question and the model never supplies an ID or binding. |
| Checked delivery | Two model responses per root/state to byte-identical, normalised checked input, status agreement and fixture-author reason category | Repeat variation in copying a checked result and using the shared observations. It cannot estimate a format effect because parity makes the two prompts identical. |
| Real reviewed recipient | One actual `run_reviewed_recipient` invocation per root/state through the dedicated MCP subprocess; up to two model responses | End-to-end bound-question verification, candidate lookup, evidence collection, optional addressed explanation, model response and checked finalisation. A collection refusal occurs before a model call. |
| Raw EAL versus independently authored JSON graph | Paired model responses per root/state, exact status and fixture-author reason category | A bounded notation presentation diagnostic on exposed synthetic tasks. Prompt lengths differ and this alone cannot isolate notation from token exposure or prior training. |

Three roots, rather than repeated states of a single root, are the independent
task units. An optional two-state-per-root pilot has six paired task states:
`6 × (1 bound-tool request + 2 checked deliveries + 2 raw responses + up to
2 real recipient responses) = 42` provider calls per model. The complete
nine-base-state developmental schedule allows up to 63 calls per model.
Refused states require fewer calls because the real recipient cannot issue a
packet to the model. The tamper states are offline diagnostics and
are excluded from paid calls. Arm and state order is seeded; a seed cannot
guarantee deterministic model output.

The **system status** is issued by the host/checker, and remains distinct from
the **model's response status**. The `records_only` Boolean is a model
assertion, not an adjudication of free prose. `reason_code` has a fixed
fixture-author reference in `run.py`; no independent human evaluator has
adjudicated it. A model returning a status and reason code from a checked
packet has not demonstrated unaided reasoning. The raw arms are separate
responses with source/graph and observations, and their statuses are scored
against the existing original brief labels.

The original 14-state corpus includes four stale or future observations for
which the new complete-collection recipient contract refuses issuance. Those
are `thermal_soak/stale_qualifying`, `thermal_soak/future_timestamp`,
`network_failover/stale_alert` and `network_failover/stale_answer`. Their
original raw status labels remain in the report. A shared refusal is parity
of the recipient contract; it is **not** counted as a correct answer to the
brief-level question.

## Offline result

Run from the repository root after installing the package dependencies:

```sh
PYTHONPATH=src:. python benchmarks/experiments/eal2-reviewed-rag/run.py \
  preflight --output /tmp/eal2-reviewed-preflight.json
PYTHONPATH=src:. python -m pytest -q \
  benchmarks/experiments/eal2-reviewed-rag/test_run.py tests/test_json_comparator.py
```

On 24 September 2026, the offline preflight produced **14/14 EAL–JSON
recipient status agreements** and **10/14 agreements with the original raw
brief labels**. The four differences are the predeclared complete-collection
refusals above. The first nine states comprise 8/9 raw-label matches and the
five tamper states 2/5. No OpenAI provider call was made. This is a
regression and parity observation on synthetic records, not a model outcome.
The compact retained record is [`results.offline.json`](results.offline.json).

The separate `retrieval_preflight.py` checks advisory BM25 and lexical
suggestions against frozen queries. Run it with:

```sh
PYTHONPATH=src:. python benchmarks/experiments/eal2-reviewed-rag/retrieval_preflight.py \
  --output /tmp/eal2-retrieval-preflight.json
```
Those candidate outcomes do not authorise an assessment and are not pooled
with provider outcomes. The retained
[`results.retrieval.offline.json`](results.retrieval.offline.json) records 6/6
target recall at rank one for each method, with false suggestions on two of
three zero-target queries. Neither method improves on the other in this tiny
author-labelled sample.

## Bounded live command

Set the credential only in the execution environment; neither the command
nor reports contain its value. Select an explicit available model and enter
its applicable, verified per-million-token rates. The default Responses API
uses stateless requests; Chat Completions is an explicit alternative. The
cheap text-interface pilot configures `reasoning_effort=none`; treat another
effort as a separate condition with its own price and schedule.

```sh
PYTHONPATH=src:. python benchmarks/experiments/eal2-reviewed-rag/run.py run \
  --model "$MODEL_ID" --provider-api responses --reasoning-effort none \
  --max-calls 42 --max-output-tokens 256 --max-cost-usd 0.25 \
  --input-usd-per-million "$INPUT_RATE" \
  --output-usd-per-million "$OUTPUT_RATE" \
  --states-per-root 2 --seed 67453 \
  --output results.model-1.json
```

The command refuses to overwrite an earlier run. It writes
`results.model-1.json.freeze.json` before provider calls, recording hashes of
repository source, graph, observation, registry and executable study inputs,
plus runtime dependency versions, schedule and rates. Each attempted model
prompt and its SHA-256 is fsynced before the call, followed by its response,
in `results.model-1.json.attempts.jsonl`. It halts on provider error, absent
usage, model identity drift, input drift, call cap or local estimated cost cap;
a stopped run retains partial outcomes and the attempt ledger. Rates and
observed tokens give an *undiscounted estimated* charge. Cached-input
discounts and invoices are not inferred; the local reservation cannot
guarantee the provider bill, especially if a failed call omits usage.

There was no `OPENAI_API_KEY` or `OPENAI_API_TOKEN` in this runtime and a
connection to `api.openai.com` was unavailable. Accordingly no live result,
model success rate, latency comparison or API charge is reported here. The
96-, 960- and 800-call plans are separate protocols and remain unrun; this
developmental pilot does not replace their review and freeze requirements.

## Decision rule and next experiment

Any source/graph parity mismatch blocks the paid pilot. Report the complete
matrix of root, state, original brief label, recipient status, refusal reason,
model request, actual response, usage and version identity. Analyse raw
presentation correctness in paired root-level clusters and retain all
failures; three exposed roots offer calibration only. An EAL/2 advantage over
equal JSON requires new independently reviewed held-out tasks, equivalent
argument content and tools, matched model/effort and acquisition conditions,
predeclared success and cost thresholds, and enough independent task units
for a meaningful uncertainty interval. A retrieval index should be tested
separately with frozen unseen queries and relevant-task labels; its candidate
ranking cannot authorise a task assessment.
