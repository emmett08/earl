# Masked architecture review, v4

Each independent reviewer gets one masked candidate directory, the system's
A baseline and the current B/C/D brief. Do not open arm packets, transcript,
assessor outcome, model usage or allocation key. Record `reviewer_id`,
`candidate_mask`, `system`, `stage`, `review_started_utc`, `review_sealed_utc`,
and whether a candidate file exposed the arm. For each item below, record
`status` (`absent`, `possible`, `present`, `not_assessable`), `severity`
(`none`, `minor`, `major`, `critical`), exact source locations, rationale,
counterevidence and confidence. A passing hidden probe is not a substitute
for architecture inspection. Compare with A and the required B→C→D design
pressure, not with a preferred pattern.

| Item | Question |
| --- | --- |
| Shared transition | Is one cross-cutting obligation implemented through a coherent state transition, including rejection and replay? |
| Effect boundaries | Do money, stock, issuer or calendar effects use the relevant boundary, with no bypass or duplicate irreversible call? |
| Event path | Do completion events follow the same commit/retry model and avoid publication on unresolved state? |
| Duplicate maintenance | Are two reachable paths now required to be changed for the same invariant? Identify both. |
| Obsolete reachable code | Does an old branch remain callable with semantics that conflict with the current rule? |
| Propagation surface | Does a local change require avoidable revisions across unrelated modules or public contracts? Anchor the path. |

System anchors: fulfilment has payment/refund, stock, carrier, order and
outbox ports; entitlement has account command history and external issuer
tokens; reservation has current booking index, customer-scoped command
history and events. In all three, a historical receipt is not automatically
the current state. A source-backed alternative design can pass review even
when it differs from the positive control.

Seal two reviewers' original forms before disclosing arm mapping or either
reviewer's findings. A third reviewer receives both originals and a masked
source, records agreement or disagreement and a reasoned final status. A
missing second review or unresolved critical disagreement remains `pending`;
no agent-generated imitation of a human review fills that endpoint.
