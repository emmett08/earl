# Reasoning semantics

## Model selection

Toulmin describes a claim’s grounds, warrant, backing, qualifier and rebuttal. Use this to expose the inferential work hidden in prose. It does not by itself specify an executable conflict-resolution algorithm.

ASPIC+ defines a family of structured argumentation systems. Select a logical language, contrariness relation, strict and defeasible rules, premise categories and preferences. Distinguish undermining a fallible premise, rebutting a defeasible conclusion and undercutting a defeasible inference. Implement the selected construction and defeat rules before claiming an ASPIC+ instantiation. An explicit objection table is not sufficient.

A finite Dung framework abstracts arguments as nodes and attacks as directed edges. For grounded semantics, use the least fixed point of the characteristic defence operator. Accepted, rejected and undecided labels concern the chosen graph; the solver does not establish that its premises or attack relations describe the world correctly. Mutual unresolved attacks must not be settled by declaration order.

A bounded authored-argument profile can evaluate specified acyclic premise dependencies, input predicates and evidence-supported objections without constructing all possible arguments. Give that profile its own name. Distinguish eligible support, contested derivation, absent support and inapplicable scope. Preserve independent arguments when an objection affects only one inference or assumption. Explain that arbitrary rationale text is recorded rather than logically proved.

Use a deductive kernel when the task requires proof. Specify propositions, introduction/elimination rules or a solver encoding, assumptions, checked derivation and trusted components. Keep execution repeatability distinct from entailment. Use statistical/Bayesian methods when the task requires quantified uncertainty, with explicit models and evidence dependence; do not multiply arbitrary confidence scores.

## Temporal and conditional assumptions

An assumption is a proposition used provisionally in a derivation. Identify its subject and relevant environment variables. Provide a validation operation that can supply evidence for or against its continued use. Keep `observed_at`, `evaluated_at`, maximum observation age and asserted applicability interval separate.

At a fixed evaluation time, distinguish: conditions unmet; usable validation; failed validation predicate; expired observation; missing observation; and validator execution error. Expiration removes the declared basis for current support without establishing falsity. Collection time does not replace original measurement time. A file reread must not refresh an old measurement. New observations require reevaluation of dependent derivations. Distinguish present applicability from a historical assessment at its recorded time. A later expiry does not falsify historical observations, while retrospective withdrawal of an assumption for that episode can invalidate dependent historical derivations. If an exposure permanently invalidates a calibration episode, model that state and its monitoring evidence rather than accepting a later normal snapshot as restoration.

Environment equality must include the variables material to the inference. A hash of selected variables identifies that representation, not the complete physical world. Record omitted factors as modelling limitations. Evidence reused by several arguments remains the same evidence; graph multiplicity does not create independent observations.

## Reasoning example

Question: does a measured latency support a claim about response time under a specified load? The observation contains measured latency, load and sampling details. An assumption states that instrumentation is accurate within a specified error bound during the observation. An inference explains the relationship between the measurement and the scoped response-time claim. A counter-observation can challenge the claim; a calibration fault can challenge the assumption; an unrepresentative sampling procedure can challenge the inference. The output should identify which of these relations changed, and what conclusion remains supportable.

A finite smoke test can support “these cases returned the specified outputs in this environment”. It cannot establish “all inputs always produce the specified outputs” without an additional justified inference. Syntax validity, semantic well-formedness, derivation under rules and empirical truth are different properties.
