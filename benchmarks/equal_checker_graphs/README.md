# Bounded generic argument graph comparator

Each JSON graph was written from the ordinary task brief and acquisition
records, separately from EAL source. `benchmarks.equal_checker` reads these
graphs and observation envelopes; it never imports or invokes the EAL parser,
interpreter, runtime or AST. `reference_oracle.py` and the manifest's expected
statuses are used only to score the output. The graph should receive separate,
masked source-fidelity review before a confirmatory experiment. The current
cohorts have not received that review.

The checker binds a typed, exact context and the acquisition request's tool,
version, mode and input; checks that observations are no older than each
record's declared limit and are not from the future; evaluates alternative
conjunctions of positive conditions; then evaluates applicable objections and
independent answers. A positive route with an unanswered objection is
`contested`; a positive route otherwise is `supported`; unavailable evidence
cannot satisfy its particular condition. Route evidence is required by that
route. A missing or stale objection record leaves the objection inactive;
a missing or stale answer cannot discharge an active objection. The trace
retains envelope failures. This optional-record distinction matters when
testing evidence revisions beyond the frozen states.

Predicates are exact typed equality, numeric upper and lower bounds, literal
`true`, required named positions and values for a bounded negative finding,
and a single-variable conditional affine calculation retaining supplied
noise. The graphs contain two source-specific judgments: that a separate
reference answers an offset alert, and that a separate packet trace answers
a switch-buffer alert. These are stipulated synthetic task rules, not verified
facts about physical systems.

The checker does not support arbitrary EAL/2 methods, quantification, causal
identification, long-lived trigger state, evidence acquisition, multi-claim
cycles, inference over unreviewed retrieved documents, or general source
authoring. Graph identity and status parity on the selected states are weaker
than full language equivalence. Treat a new task outside this predicate
fragment as unsupported until the comparator is extended and independently
validated. A matched host must account for graph authoring and review costs.

Run `python -m benchmarks.equal_checker --output parity.json` for the four
historical pilot roots. For the new cohort use
`python -m benchmarks.equal_checker --fixtures benchmarks/experiments/cross-model-delivery --output parity.json`.
The report includes per-state traces and SHA-256 digests for the graph, EAL
source, canonical observation mapping and checker implementation; it exercises
wrong-scope, wrong-tool, stale, future and missing-record mutations of a
positive-route record. The new cohort also includes five separately authored
tamper fixtures, including a stale optional challenge and stale optional
answer. None of these checks calls a provider.
