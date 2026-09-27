# Condition-masked architecture review

Two reviewers independently inspect immutable candidate sources labelled only
by random candidate IDs. They see the current feature requirements and common
A source, but no arm mapping, EAL packet, other reviewer report, agent report
or automated assessment result until both forms are sealed. The host records
source digests before mask release. A third reviewer adjudicates disagreements
with both original judgements retained. This is source review, not evidence of
future maintenance effort.

For each episode, record a JSON object with candidate ID, family, stage,
source digest, reviewer identifier, timestamp, and findings below. Each
finding requires `status` (`present`, `absent`, `unresolved`), exact file/line
locations, mechanism, and a plausible alternative reading. Do not convert an
unexecuted function to dead code merely because finite tests missed it.

| Finding | Review question | Positive evidence | Defeater |
| --- | --- | --- | --- |
| Shared state transition | Does one coherent service/store history account for checkout and all added operations? | Enumerated writers and their call paths | A second writer to the same order/return/cancellation state with incompatible rules |
| Effect boundary | Do payment, stock and shipping mutations flow through the declared ports, with stable retry keys? | Call graph from public operation to effect adapter | Direct adapter state mutation or independent non-idempotent effect path |
| Outbox boundary | Does one order/event record and retry route handle every event kind? | Call paths and commit/ack sequence | A direct publish path that bypasses outbox/retry |
| Duplicate maintenance site | Would the same later rule need coordinated edits to independent implementations? | Specific duplicate predicates and callers | Mere repeated syntax with distinct business responsibility |
| Reachable obsolete code | Is an earlier implementation no longer called by any public or internal route? | Static calls, dynamic registration search and counterexample attempt | A reachable entry point, import, callback or purposeful compatibility path |
| Propagation surface | How many distinct production modules and call sites changed for the current requirement? | Source diff, affected test/rule map | Renames/generated code or a coherent shared-contract refactor miscounted as drift |

Record each possible problem separately. An alternative coherent refactor is
permitted, even if it edits an existing port. Report failures of behavioural
probes only after the source judgement is sealed. Reviewers do not grade on
the exact old AST, raw class count, SOLID labels or Cognitive Complexity alone.
Their forms are a secondary outcome; no composite architecture score is
assigned without validation and agreement. Disagreement and uncertainty
remain visible after adjudication.
