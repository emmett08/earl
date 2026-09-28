# EAL/2 argument model

EAL/2 evaluates an authored argument graph against recorded observations, a selected method registry, an environment and an assessment time. It determines whether the *declared* routes to a claim have usable support under the rules below. The result does not establish that the author chose the right physical model, collected an authentic measurement or translated the engineering question faithfully.

## Contents

- [Argument structure](#argument-structure)
- [Local support and formal propositions](#local-support-and-formal-propositions)
- [Compositional objections and defences](#compositional-objections-and-defences)
- [Result interpretation](#result-interpretation)
- [Scope, assumptions and evidence time](#scope-assumptions-and-evidence-time)
- [Formal relatives and extensions](#formal-relatives-and-extensions)

## Argument structure

An `argument` declares a conclusion, a reasoning step and at least one source: evidence, an assumption or a premise claim. Every declared source is required for that particular derivation. Several arguments can support one claim; a premise claim may itself have several derivations. Premise dependencies must be acyclic, and reusing the same evidence in several arguments does not make independent observations. A `pattern` expands one argument with closed, typed parameters; each `apply` becomes an ordinary named argument without copying its evidence identity. See [language syntax](language.md) for the grammar and [vocabulary](vocabulary.md) for construct contracts.

Toulmin's distinction among claim, grounds, warrant, backing, qualifier and rebuttal informs this design; EAL/2 defines executable relations rather than adopting Toulmin as a formal calculus. See the [primary source](sources.md#argument-and-reasoning-models).

| Toulmin function | EAL/2 relation |
| --- | --- |
| Claim | A `claim` statement, environment and optional typed proposition |
| Grounds | The argument's evidence, assumptions and premise claims |
| Warrant | A `reasoning` declaration selecting an exact method and stating its rationale |
| Backing | Evidence named by the reasoning declaration |
| Qualifier | Environment match, temporal validity, evidence freshness and formal result criterion |
| Rebuttal | An `objection` targeting a claim, application, method use, assumption use or objection |

The author supplies the rationale connecting the sources to the conclusion. `structured/1` checks its declared dependencies without independently proving that rationale. Computational methods check specific finite questions about typed inputs: for example, a propositional entailment, Wilson interval, finite hypothesis update, two-group contrast, affine intervention, feature comparison or bounded trace predicate. A method label alone does not grant support. [Reasoning modes](reasoning-modes.md) specifies each operation and its input/output limits.

[Enthymeme reconstruction](argument-reconstruction.md) makes proposed implicit content explicit before assessment. A recovered proposition can become a premise claim with its own support obligation; a claim without a derivation remains unsupported. Textual grounds for attributing an assumption to an author do not validate its empirical applicability. Likewise, a suspected gap is an authoring finding until evidence or premise claims support an EAL objection. The evaluator checks the declared dependencies and cannot establish that every material dependency was included.

## Local support and formal propositions

For each application, the evaluator checks its declared environment; the availability of direct evidence, assumption validation and reasoning backing; and the selected computation and result predicates. A computational method receives the deduplicated union of those evidence declarations and requires exactly one item of its designated input kind. Its `reasoning_result` records both computed details and predicate outcomes. A successful computation can return a negative finding; an explicitly negative result criterion may use it as support. A failed or incomplete computation supplies no such finding.

A typed `proposition` adds subject, quantity, unit, scope, validity interval, query and result criterion. Its `binding` checks that a designated observation addresses the registered method query and that the output addresses the proposition criterion. This is correspondence within the represented contract, not verification of the claim's natural-language statement; assessed claims expose `prose_verified: false`. Without a typed proposition, author-supplied text and selected output predicates still constrain support, but the evaluator cannot infer a formal meaning from the text.

Local usability precedes dialectical acceptance. A source-usable derivation has usable local sources and a source-usable path through its required premise claims. The composed solver then decides whether that derivation survives attacks. Keeping these stages separate prevents a locally successful calculation from pre-accepting a contested premise or objection.

## Compositional objections and defences

An `objection` names one target and at least one source, either evidence or premise claims. Its premises can themselves have alternative supporting arguments. An objection to another objection is a defence; that defence can be challenged in turn. Its sources and scope-bearing targets share one declared environment; a reasoning target applies only to uses of that declaration in the objection's environment. An objection to a `claim` attacks *every* argument deriving it; an objection to an `argument` attacks that application only. An objection to `reasoning` or `assumption` attacks their directly dependent applications within the objection's environment. Attacks on premise claims propagate through the dependencies of arguments that require them.

```eal
objection sampling_problem {
  target argument lifetime_estimate;
  premises samples_are_dependent;
}
objection independence_defence {
  target objection sampling_problem;
  evidence measured_independence;
  premises independence_measurement_applies;
}
```

The solver constructs one node for each argument application and objection, plus a claim node for each declared claim. Let $U(n)$ mean local source and computation usability for node $n$, $P(n)$ its required premise claims, $A(n)$ its attacking nodes and $D(c)$ the argument nodes deriving claim $c$. Starting with every label undecided, it repeatedly applies the following implications until no label changes:

$$
\begin{aligned}
\mathrm{Accepted}(n) &\Leftarrow U(n)\land
 \bigwedge_{c\in P(n)}\mathrm{Accepted}(c)\land
 \bigwedge_{a\in A(n)}\mathrm{Rejected}(a),\\
\mathrm{Rejected}(n) &\Leftarrow \neg U(n)\lor
 \bigvee_{c\in P(n)}\mathrm{Rejected}(c)\lor
 \bigvee_{a\in A(n)}\mathrm{Accepted}(a),\\
\mathrm{Accepted}(c) &\Leftarrow
 \bigvee_{n\in D(c)}\mathrm{Accepted}(n),\\
\mathrm{Rejected}(c) &\Leftarrow
 \bigwedge_{n\in D(c)}\mathrm{Rejected}(n).
\end{aligned}
$$

The last conjunction is true for an empty derivation set, so a claim with no derivation is labelled rejected in this *acceptance* calculus; its engineering status is `unsupported`, and its negation is not established. A node becomes rejected if a required premise is rejected or an accepted attacker defeats it. A circular defence depending solely on the claim it should restore has no initial support and can remain undecided. An independent accepted defence can reject an objection and reinstate the original route. Alternative accepted derivations can keep a claim supported when one route is defeated.

The trace identifies each newly settled node and the previous labels responsible. The composed graph permits attack and objection-support cycles; the ordinary argument-to-premise graph remains acyclic. The implementation bounds the graph to 4,096 nodes, 4,096 claims and 131,072 total attack, premise and derivation relationships. See [grounded reasoning](grounded-reasoning.md) for the separate abstract Dung operation, its API and verification.

## Result interpretation

| Claim status | Meaning under these source, observation, environment, time and registry inputs |
| --- | --- |
| `supported` | At least one source-usable argument application is accepted |
| `contested` | A source-usable application exists, but every such application is rejected or undecided |
| `unsupported` | No source-usable application establishes support; this does not assert falsity |
| `out_of_scope` | The claim's declared environment does not match the supplied context |

An objection with source-usable support is `active`, `defeated` or `undecided` according to its acceptance label; one without such support is `inactive`. These statuses, accepted/rejected/undecided graph labels, evidence availability and static source validity answer different questions. Static diagnostics prevent a usable assessment until source or registry errors are corrected. `supported` is neither a probability nor a certificate of physical truth; `rejected` in the graph is not the negation of its claim.

## Scope, assumptions and evidence time

An assumption has a stated environment, validation evidence and optional interval $[\mathtt{valid\_from},\mathtt{valid\_until})$. Its validation observation must match the requested tool, version, binding identity, inputs and environment; meet the evidence predicates and integrity checks; and satisfy freshness at assessment time. An observation is still fresh at exactly `max_age`. The original collection time differs from ingestion time. A fresh observation cannot by itself establish uninterrupted validity between collection and assessment.

Every scope-bearing dependency of an argument shares its conclusion's declared environment. Transferring support to another environment requires a separate claim and argument in that target environment. Missing, stale, failed or mismatched evidence leaves its declared route without support. An authored objection supported by an observed, scope-matched counterexample can defeat a universal claim over that scope. A matched negative result can support a negative *typed* proposition only when its method and result criterion actually express the negative question. Absence of a record does not establish the absence of an event without a validated completeness relation; a partial search with no match remains unresolved. See [MCP and tools](mcp-and-tools.md) for observation acquisition and trust boundaries.

An assessment identifies its source, observation set, context, evaluation time and registry fingerprint. Reassessment after an observation, context or method change recomputes dependent statuses; a recorded context fingerprint cannot detect omitted physical conditions, and a digest cannot authenticate an untrusted producer. A deterministic tool can miss a defect; a nondeterministic search can discover a derivation that an independent deterministic checker verifies. Tool repeatability and inferential validity are separate properties.

## Formal relatives and extensions

The attack-only fragment of the composed solver, when all nodes are locally usable, agrees with Dung grounded labelling. The separate `eal_grounded` operation directly solves an explicitly supplied finite argument-and-attack graph. A complementary Dung-node construction has been used as an independent check of the composed equations; that construction and the finite tests are described in [grounded reasoning](grounded-reasoning.md).

ASPIC+ distinguishes strict and defeasible rules, premise categories, contrariness and preference-sensitive attack/defeat. EAL/2's core targeted objections remain authored attacks under the equations above. The optional [`argumentation/aspic/1` method](aspic-method.md) separately constructs a bounded formal theory, its undermining, rebutting and undercutting defeats and grounded labels. The opt-in compiler obtains a theory from checked EAL routes and observations; reviewed top-level EAL directives declare strict inference, preference rank and directed claim contrariness. Each target kind follows from its unique declaration name. The authored EAL evaluator validates these directives without applying their inference effects. This instantiation does not implement all ASPIC+ variants or replace EAL evidence checks. The abstract `solve_grounded` operation still accepts only an already specified graph and cannot check how it was obtained. See [Modgil and Prakken](sources.md#argument-and-reasoning-models) for the framework.

A richer deductive language, preference-sensitive defeat or probabilistic argument calculus would need a declared input model and inference rules, not simply another keyword or confidence score. In particular, multiplying support probabilities across reused evidence requires justified dependence assumptions: $P(A\cap B)=P(A)P(B\mid A)$. The present methods give method-specific numerical outputs without converting them into a probability that an engineering claim is true.
