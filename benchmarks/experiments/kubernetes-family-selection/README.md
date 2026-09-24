# Developmental paid family-selection study

This is a **separate 36-call** study of the newly implemented
`CandidateIndex` and `TaskFamilyHost` path. It does not modify or extend the
180/135-case recipient campaigns. Twelve task cases are crossed with three
recipient classes: `gpt-4.1-nano` (non-reasoning), `gpt-6-luna` at
`reasoning_effort=none`, and `gpt-6-sol` at `reasoning_effort=high`.
The same synthetic Kubernetes source, finite family catalogue and seven
evidence revisions used by the separate offline study are pinned as inputs.
No live cluster observation or human-adjudicated reference is implied.

The caller supplies the query and trusted cluster/namespace scope. The host
returns lexical candidates, their descriptions, parameter types and allowed
value domains, and claim IDs. The model makes one text-only JSON selection or
abstains. The host checks that the family was retrieved, the typed bindings
equal the trusted task scope, the tuple was reviewed, and the selected claim
belongs to that case before assessing. The final status, if any, comes from
the host. The model never receives EAL source, evidence observations,
reference labels or the assessed status in the prompt. It has no native MCP
or function-call access. The catalogue's reviewer label is explicitly a
fixture-author assertion without independent review.

The 12 cases include exact latency, rollout and failover queries; three
synonymous phrasings; ambiguous `checkout service`; underspecified
`Kubernetes`; an unrelated tax query; the unreviewed but typed `prod_west`
tuple; and an *identical latency prompt* under baseline, batch-contention
and stale-monitor-coverage evidence revisions. The synonym `traffic switch
backup` is a predeclared retrieval miss: no candidate appears. Ambiguous
and no-target queries should abstain. A model may nominate the relevant
`prod_west` family, but exact resolution must reject the unseen tuple.
The same selection can produce supported, contested and unsupported
host statuses as the three evidence revisions change.

## Execution and retention

From the repository root:

```bash
PYTHONPATH=src python benchmarks/experiments/kubernetes-family-selection/run.py \
  /tmp/eal2-family-selection --preflight
PYTHONPATH=src python benchmarks/experiments/kubernetes-family-selection/run.py \
  /tmp/eal2-family-selection --freeze-only
# Audit /tmp/eal2-family-selection/freeze.json before execution.
PYTHONPATH=src OPENAI_API_KEY=... python \
  benchmarks/experiments/kubernetes-family-selection/run.py \
  /tmp/eal2-family-selection --execute
```

Supply the API key by a protected process environment mechanism; never
commit it or copy it into the ledger. The frozen directory contains
`freeze.json` with exact ordered prompts, candidate suggestions, references,
provider identities and hashes of the source, catalogue, plan, runner,
EAL grammar, generated parser and recursive `src/eal` implementation. It
also records the Python and installed ANTLR/MCP/JSON Schema/HTTPX versions.
`ledger.json` initially contains zero attempts. Execution regenerates the
entire candidate schedule and exact prompts from the pinned materials and
rejects a discrepancy even if someone recalculated the freeze's own hash.
The runner writes a pending row **before** each provider call, then retains
the raw response, model identity, usage (including reasoning tokens when
reported), model and host latency, parsed selection, host packet and direct
trace or rejection, and every failed call. `summary.json` aggregates the
completed attempts and records known spend separately from any attempt with
unknown cost. A response received before a host failure is retained with
its usage and configured cost. Completed-prefix model identity, token
counts and cost are checked against frozen configuration before budget
continuation. A failed, pending or uncertain-usage attempt blocks
automatic continuation because it may already have been billed. No silent
retry occurs. Changing any frozen material also blocks execution. A
continuation after a successfully completed prefix uses the same freeze and
only the remaining cases.

The provider configurations currently carry standard input/output prices
per million tokens of $0.10/$0.40 for nano, $0.10/$0.50 for Luna, and
$2.00/$10.00 for Sol. The [OpenAI nano model page](https://developers.openai.com/api/docs/models/gpt-4.1-nano)
and [pricing page](https://developers.openai.com/api/docs/pricing) provide
the source of these configurable estimates. The maximum prompt is 4,096
UTF-8 bytes, maximum completion 2,048 tokens, planned reserve uses twice
the prompt-byte count plus message overhead, and the $1.00 configured
planning cap stops further calls. The current offline preflight computes a
$0.363 reserve across 36 calls, with the longest prompt 1,980 bytes.
This reserve is deliberately conservative for these ASCII prompts, but it
is **not a billing guarantee**; provider accounting is authoritative.
Check current access and rates before paid execution.

## Analysis boundary

Report exact family/scope/claim selection for the seven serviceable target
cases per model, safe abstention for ambiguous and no-target tasks,
retrieval failure on `traffic switch backup`, exact rejection or abstention
on `prod_west`, and false supported **accepted** decisions for any adverse
or irrelevant task. Keep a retrieval miss separate from a model mistake:
abstaining on an empty list is safe but fails to complete that task.
Report host status across the repeated latency prompt, model input/output
tokens, provider model time, host time, failures and retries. Retrieval
occurs during frozen offline preparation; the paid runner does not claim
a live candidate-retrieval latency.
The packet and trace bytes are measured; they are not token counts.

The first zero-call freeze at
`/workspace/scratch/4d452efe689d/paid-family-selection-v1` is marked
`superseded_zero_call` after an audit found omitted parser identity,
weak prompt verification and charged post-provider result loss. It must
never be executed; make a fresh freeze after this runner is audited.

This small single-author set is a developmental implementation test and
cannot estimate field accuracy or model generalisation with useful
precision. It does not test whether recipient prose faithfully explains a
host packet, nor compare native tool calls or an independent checker.
Authoring and review hours, acquisition costs and independent answer
adjudication are unmeasured. Consequently **cost per correct accepted
decision including initial effort is unavailable**, even when API usage
has been recorded. A confirmatory extension needs independent masked
reference adjudication, representative tasks, authenticated cluster
evidence and actual effort accounting.
