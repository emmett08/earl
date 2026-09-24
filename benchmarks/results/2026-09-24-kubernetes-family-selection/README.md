# Developmental family selection, 24 September 2026

This **36-call synthetic** study exercised `CandidateIndex` nomination,
model choice of a listed family and typed bindings, and `TaskFamilyHost` exact
resolution. The user authorised paid comparison. The provider calls used
GPT-4.1 nano, GPT-6 Luna without reasoning effort and GPT-6 Sol with high
reasoning effort. Twelve authored task cases were crossed with the three
models. The archive `family-selection-36.tar.gz` retains the frozen prompts,
source/runtime hashes, candidate list, ordered raw responses, returned model
identities, usage, host packets or denial reasons, and summary. The pinned
freeze SHA-256 is
`b5ef86e16f16d539d75d0632497b73862a6f6ed4c1ea9cd42d6fdb313244c7cc`.
An independently audited earlier freeze had no calls; its runner defects were
fixed and its zero-attempt ledger is retained in
`superseded-zero-call-freeze.tar.gz`.

| Model | Correct task selection or appropriate abstention | Accepted family assessments | Safe abstentions, including the retrieval miss | Task-level false supported acceptances | Configured-rate model cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-4.1 nano | 9/12 | 9 | 2 | 2 | US$0.0006402 |
| GPT-6 Luna | 10/12 | 6 | 4 | 0 | US$0.0006322 |
| GPT-6 Sol, high reasoning | 10/12 | 6 | 4 | 0 | US$0.0183140 |

All **36/36 calls completed**, with zero failures and retries, 10,938 input
and 2,326 output tokens (including 482 reported reasoning tokens), zero cached
input tokens, and US$0.0195864 configured-rate model cost. The
per-call API median/p95 seconds were 7.339/8.395 for nano, 8.316/17.172 for
Luna, and 8.899/16.606 for Sol. The local host assessment/rejection path
totalled 1,495, 1,067 and 1,042 ms by model, respectively, for cases that
entered it. These timings do not include a live cluster or authenticated MCP
network transport.

The identical latency task under three evidence revisions resolved to the
same family and exact tuple for all three models. Its host statuses were
`supported`, `contested` and `unsupported`. All three model selections of the
unreviewed `prod_west` tuple were refused by exact resolution. The lexical
candidate index returned no family for `traffic switch backup`, so all three
models abstained safely but failed to complete that legitimate task. Luna and
Sol also abstained on the authored ambiguous and generic queries. Nano chose
the authorised `checkout_latency` family for both, and the host returned a
checked `supported` status for that family: **two task-level false supports**.
This is an applicability error, not a bypass of the reviewed tuple grant.
Luna and Sol also abstained on one serviceable rollout synonym, accounting
for their remaining selection errors.

All reference relevance and statuses were authored by the fixture designer;
there was no independent masked task review. The Kubernetes records were
synthetic JSON, not authenticated cluster measurements. The model saw task
text, trusted scope and lexical candidates, but not the EAL source, evidence
revision or checked status. It selected a family/claim or abstained in one
text-only call; no native MCP function-call ability or faithful explanation
was measured. Exact resolution guards listed tuples and claims but cannot
prove that a family is relevant to an underspecified natural-language task.
Initial authoring and human review effort, acquisition cost and explanation
fidelity are unavailable, so total cost per faithful correctly accepted
decision is unavailable. This small, single-author case set does not support
a field-accuracy or model-class population claim.

Re-run the no-call freeze preparation with:

```bash
PYTHONPATH=src:. python benchmarks/experiments/kubernetes-family-selection/run.py \
  /tmp/new-empty-family-run --freeze-only
```

The retained archive allows per-case inspection without another provider
call. A changed source, catalogue, prompt, runtime or provider identity
requires a new freeze.
