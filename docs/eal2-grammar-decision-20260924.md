# EAL/2 grammar decision for the three proposed studies

**Decision, 24 September 2026:** retain the EAL/2 grammar for the proposed
96-, 960- and 800-call studies. This is a task-bounded design decision, not a
claim that EAL/2 can express every engineering inference. The source-language
contract stays `EAL/2`; no parser, method-envelope or observation-schema
version changes follow from this decision. The three original protocols remain
version `0.1.0`, specified and unrun. Freeze new executable schedules against
the current implementation before attributing calls to any of them.

## The distinguishing task

In the finite sampled negative-finding example, two independent tests
provisionally support a sampled property. A bound violating observation supports
a separate claim, which is a premise of objections to both test arguments.
An independently supported defence can challenge each objection. The tested
meaning is visible in
[`arguments/negative-revision/counterexample.eal`](../arguments/negative-revision/counterexample.eal):
the typed negative proposition fixes subject, unit, interval, finite query and
`finding == true` (lines 15–18); the alternative routes, bound method and
premise-backed attacks occur at lines 19–25. Existing grammar rules accept
typed queries and results, versioned reasoning methods, claim premises and
objection targets (`grammar/EAL.g4`, lines 10–33). The registered
`engineering/sampled-negative/1` method distinguishes a witnessed
counterexample from qualified sampled non-detection; the latter requires
endpoint and gap coverage plus documented detector limits
(`src/eal/sampled_negative.py`, lines 30–35, 67–96, 119–131). A missing
observation cannot become a finding through a negative spelling. The source
and result are conditional on the reviewed warrant and supplied observations;
calibration fields are acquisition assertions, not authenticated sensor facts.

The language-design removal test asks what necessary semantic distinction a
new `negative finding` or `attack` keyword would add. For these studies, none
has been demonstrated: the current claim, proposition, method, premise and
target already retain polarity, finite coverage contract, query identity and
attack target. A new surface form could reduce authoring errors, but that is
an **unmeasured usability hypothesis**, not a required extra semantic rule.
Test it separately on blinded ordinary-brief formalisation and revisions if
reviewed source failures identify that spelling as the cause. Require equal
typed semantics, parse–format–parse equivalence, a matched generic view and
measured fidelity/cost before adopting any change.

## Implementation gaps outside the grammar

The Kubernetes example can express the finite canary, the provisional
operating route and a contention objection to its reasoning
(`examples/kubernetes-resource-revision.eal`, lines 107–187). Its
`structured/1` rationales still record author-supplied engineering warrants;
the interpreter does not prove that these prose relations or a causal
explanation describe a live cluster. If a later task requires a formal causal
contrast, define a versioned typed method, its result interpretation and
explicit premises first. Add syntax only after a concrete task shows that
existing typed propositions and bindings cannot preserve the required
meaning locally.

Host completeness remains separate. The generic host has no mandatory
monitor gate and may collect evidence beyond a granted claim; acquisition
digests do not authenticate the producer, guarantee coverage or establish a
warrant. Its saved result is historical, family issuance is process-local,
and candidate retrieval can select an authorised but irrelevant family
([`docs/eal2-host-completeness-audit.md`](eal2-host-completeness-audit.md),
lines 9–25). Changing source syntax cannot fix those failures. An authored
negative claim with correct syntax can still be wrong if the intended
objection, scope or measurement is omitted.

## Consequences for the original counts

| Protocol | Grammar consequence | What a current schedule must preserve |
| --- | --- | --- |
| [`INV-EAL-NEGATIVE-REVISION-001`](../benchmarks/protocols/INV-EAL-NEGATIVE-REVISION-001.json) | Its 48 one-shot view calls and 48 linked author/revision calls can use the existing typed negative method and objection graph. | Eight genuinely new reviewed briefs, an independently implemented equal checker, adjudicated coverage and status reversals, and separate authoring-fidelity scores. Deterministic executions are additional to the 96 model calls. |
| [`INV-EAL-MECHANISMS-001`](../benchmarks/protocols/INV-EAL-MECHANISMS-001.json) | Its `24 × 10 × 2 × 2 = 960` one-shot factorial compares current EAL source with a semantically equal JSON view. | The ten content arms and paired checked references; 192 deterministic checker executions are additional. Substituting compact host delivery changes the exposure and requires a distinct schedule. |
| [`INV-EAL-DEPLOYMENT-001`](../benchmarks/protocols/INV-EAL-DEPLOYMENT-001.json) | Its **stated 800-call count excludes** the optional nested candidate-grammar factor, but the described full Stage 1 factorial is miscounted. The text says 384 fixed-source calls, followed by 96 author/revision and 320 recipient calls. | With all stated Stage 1 factors crossed, Stage 1 is 768 calls, so the full design totals 1,184. A versioned 800-call amendment must counterbalance half the format × instruction cells to obtain 384, and must label unestimable or aliased interactions. Mark `CLM-GRAMMAR`/`EST-GRAMMAR` untested; any future explicit-syntax factor needs separately priced calls. Current host/family contracts, reviewers, parity and provider freeze remain required. |

The canonical protocol's `sampling.sample_size_or_information_target` says
`8 × 3 × 2 × 2 × 3 × 2 = 288` tool-capable Stage 1 calls and
`8 × 3 × 2 × 2 × 2 = 96` non-tool calls. Their products are actually 576 and
192, respectively. Its `feasibility.resources` excludes grammar extension;
`interventions_or_exposures.INT-FORMAT` makes the grammar factor nested and
conditional. Thus removing that factor does not alter the base arithmetic,
but **the original full factorial does not schedule 800 calls**. A balanced
half-fraction over format × instruction can yield 384 Stage 1 calls and 800
total, provided the allocation, aliasing, estimands and model eligibility
are declared before execution. This amendment cannot be described as the
unmodified original factorial. Preserve the original protocols' bytes and
version labels; place executable current-contract allocation and budget
freezes under `benchmarks/experiments/` as distinct versioned schedules. The
three specified designs measure different effects and cannot be
retrospectively populated from other paid campaigns.

This decision follows the repository-maintained
[`engineer-argumentation-languages` skill](../skills/engineer-argumentation-languages/SKILL.md):
add a core construct only for a required distinction that existing typed
composition cannot preserve; keep versioned computation and acquisition at
their respective host boundaries. The expert-design reference distinguishes
evidence about a syntax usability effect from evidence that syntax changes
semantic coverage.
