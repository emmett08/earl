# Stage A explanation review rubric for the developmental 96-call study

**Status:** written while paid calls were still running, before examining the
Stage A responses. The 48 one-shot Stage A attempts are the denominator. A
second agent reviews independently using the same frozen prompt and reference.
The model is requested to return one JSON object containing three claim labels
and a one-sentence explanation. Model identity, case order and internal view
labels are hidden from the reviewer; the exposed formal source may reveal
whether it is EAL or JSON and cannot be suppressed while retaining the exact
information the recipient saw. Keep the linkage file separate until all
judgements are recorded.

## Decision contract

Read the actual system/user messages, response, expected three-claim statuses,
and source/record dossier for **that same case**. Treat the brief and records
as synthetic assertions, not physically authenticated facts. A finite sampled
counterexample can support `violating_sample` without complete coverage. A
qualified absence needs complete endpoint/gap coverage and the stipulated
detector contract. An out-of-scope, stale, wrong-query or withdrawn adverse
record cannot maintain the same claim's attack. An independent positive route
or separately supported defence can leave the parent claim supported despite
one objection. A source's rationale remains authored rather than proved by
the checker. No supplied record establishes continuous-time or future truth.

For every response record `category`, a concise `rationale`, and structured
flags for: `label_match` (all three recipient statuses equal reference),
`scope_and_time`, `sampled_limit`, `attack_and_alternatives`,
`absence_contract`, `source_attribution`, and `unsupported_addition`. A flag
may be `not_applicable` when the root does not expose that relation. Judge the
explanation independently of the mechanical label-match measure while
recording material conflict between prose and either the reference or the
recipient's own labels.

| Category | Rule |
| --- | --- |
| `faithful` | The explanation accurately gives the decisive basis for the three named statuses, or one compact causal statement from which all three follow, retains the bounded sampled scope, and makes no unsupported addition. |
| `incomplete` | Every affirmative assertion in the explanation is consistent with the exposed evidence and authored graph, but a decisive scope, attack/alternative, sampled finding or absence condition is missing, or it does not explain a named claim. |
| `materially_false` | At least one material assertion conflicts with a supplied record, its eligibility, the authored target/defence relation, the finite sampled contract, or a named output label; it claims unsupported physical, continuous-time or future truth. Include the shortest decisive correction. |
| `unreviewable` | The call failed, or the output/explanation is absent, empty, non-string, or cannot be recovered unambiguously from the retained response. Malformed schema and a readable explanatory sentence are recorded separately; do not automatically mark a readable sentence unreviewable. |

If a sentence has both a true fragment and a false material claim, mark
`materially_false`. If it is vague but does not assert a false relation, mark
`incomplete`. An exactly correct label without a faithful explanation remains
incomplete or unreviewable. A wrong claim label is scored separately; any
explanation that supports that wrong label against the supplied record is
materially false. A one-sentence output can be faithful if it preserves the
decisive distinctions; length alone never decides the category.

## Review and limits

Keep every attempted slot, including provider errors and malformed responses.
Score in masked order before joining the output to root, state, notation and
call index. Record reviewer disagreement case by case and retain both original
ratings; later adjudication must be marked as such. Report counts over all 48
attempts and by notation only after unblinding. Do not interpret the 48 paired
responses as independent engineering tasks: eight selected roots share a
generated scaffold and one sampled-negative method. This is an exploratory
agent review against author-constructed references, not masked human
adjudication or validation of real sensor truth.
