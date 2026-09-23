# Engineering argument and reasoning model

EAL represents engineering claims, the evidence offered for them, the reasoning steps connecting their premises to their conclusions, and objections to those steps. It computes which conclusions currently have usable support under the declared environment and time. The result includes the dependencies responsible for each conclusion, so an engineer or an application can inspect the reasoning and determine what needs to be measured next.

The executable profile combines a finite, acyclic hierarchy of arguments with explicit reasoning modes. A mode performs a bounded computation over a specified kind of evidence; declared predicates then test its outputs. The text of a claim or reasoning rationale explains the engineering interpretation. The computation establishes its defined mathematical result, while the applicability of that result to the physical system depends on the stated model and assumptions.

## Choice of argument model

Toulmin provides a useful decomposition of an argument into a claim, grounds, a warrant, backing, a qualifier and possible rebuttal. EAL expresses those functions through terms that identify the engineering operation or dependency. The mapping below is a design choice, not a claim that Toulmin specified a programming language. See [Toulmin in the sources](sources.md#argument-and-reasoning-models).

| Argument function | EAL representation |
| --- | --- |
| Claim | `claim` with a statement and environment |
| Grounds | Evidence, assumptions and premise claims listed by an `argument` |
| Warrant | `reasoning` with a mode, rationale and result criteria |
| Backing | Evidence referenced by the reasoning step |
| Qualifier | Environment predicates, evidence freshness and assumption intervals |
| Rebuttal | An `objection` with a declared target and supporting evidence |

ASPIC+ distinguishes uncertainty in premises from defeasible inference, and distinguishes attacks on premises, conclusions and rule applicability. Those distinctions motivate EAL's targeted objections. EAL does not automatically construct all arguments from a logical theory, infer contrary propositions or compare preferences. An EAL objection to a claim resembles a rebuttal operationally; it is not automatically an ASPIC+ rebuttal. The formal framework and its required choices are described in [Modgil and Prakken](sources.md#argument-and-reasoning-models).

## Reasoning modes and evidence

A reasoning mode determines what operation is performed. An evidence kind identifies the input contract for that operation. The distinction allows the same engineering claim to depend on several subarguments using different methods, instead of treating every source as interchangeable support.

| Mode | Evidence kind | Bounded operation | Interpretation of the result |
| --- | --- | --- | --- |
| `structured` | Author-selected evidence | Apply explicit premise, assumption and backing dependencies | Support under the author-supplied conditional rule |
| `deductive` | `logical_case` | Check finite propositional entailment | A conclusion follows within the supplied propositional case |
| `inductive` | `sample` | Compute a Bernoulli estimate and Wilson interval | A sampling-based estimate under the declared sampling assumptions |
| `abductive` | `hypotheses` | Condition finite hypothesis priors on supplied likelihoods | Relative posterior support within the supplied hypothesis set |
| `causal` | `experiment` | Compute a randomised two-group mean contrast | An effect estimate conditional on the experiment design assumptions |
| `counterfactual` | `causal_model` | Evaluate an acyclic affine structural model under an intervention | A model-conditional outcome for the supplied exogenous values |
| `analogical` | `analogy` | Compare declared source and target features | Correspondence over the specified features, with mismatches exposed |
| `temporal` | `trace` | Check a predicate at every sample, with endpoint and gap checks | A result about the supplied observation sequence and horizon |

The computational modes require output predicates such as a Boolean entailment result or a specified interval bound. Selecting a mode is therefore a request for a particular calculation, not a descriptive label that grants support by itself. The [method documentation](reasoning-modes.md) defines accepted inputs, outputs and computational limits.

For each argument, the method receives the deduplicated union of its direct evidence, reasoning backing and assumption-validation evidence. A computational mode requires exactly one item of its designated kind. The argument's `reasoning_result` records the computed details and the outcome of the declared result predicates, allowing one reusable method to produce different results for different arguments.

These methods answer different questions. An abductive result ranks explanations of observations; a causal result estimates an effect of intervention. An analogical match identifies correspondence; a deductive result checks implication within a formal case. Combining them requires an argument that states how their separate conclusions bear on the parent claim.

## What the evaluator derives

An argument names a conclusion, a reasoning step, and its sources. Sources can include evidence, assumptions and previously supported claims. Every listed source is required within that argument. Operationally, each argument declaration is an author-supplied conditional support rule: satisfying its premises and reasoning criteria derives support for its conclusion. Alternative arguments for the same claim provide distinct possible derivations; the evaluator preserves an uncontested alternative when another derivation is challenged.

For an argument with evidence set $E$, assumption set $A$, premise-claim set $P$, reasoning step $r$ and conclusion $c$, the uncontested-support calculation has the form

$$
\operatorname{Support}(c) \Leftarrow
\operatorname{Applicable}(c)
\land \bigwedge_{e\in E}\operatorname{Usable}(e)
\land \bigwedge_{a\in A}\operatorname{Usable}(a)
\land \bigwedge_{p\in P}\operatorname{Support}(p)
\land \operatorname{Usable}(r)
\land \operatorname{Uncontested}(r,A,P,c).
$$

Here usability of a computational reasoning step includes successful evaluation and satisfaction of its output predicates. The equation derives `supported` from explicit dependencies. The author supplies the engineering interpretation of the rule; the implementation checks the selected computation and dependencies. Deductive validity is checked for the formal content supplied to the deductive mode, while prose statements retain their explanatory role.

The claim-premise graph must be acyclic. Rejecting cycles prevents a claim from acquiring support solely through circular declarations. Every argument must identify at least one source. Input size and dependency-depth limits make the supported evaluation domain explicit.

## Complex claims and subarguments

A premise claim can itself be the conclusion of one or more arguments. Referencing it through `premises` creates a subargument dependency. This produces a directed acyclic graph: several parent claims may reuse one subclaim, and a subclaim may have alternative supporting arguments. The parent uses the subclaim's evaluated result, so missing evidence, an expired assumption or a relevant objection propagates through every dependent argument.

For example, a controller claim can depend on an inductive argument about sampled failure frequency, a temporal argument about a bounded execution trace, and a causal argument comparing an intervention with a control condition. Each subargument retains its own evidence type, method, scope and assumptions. A parent structured argument explains why those particular results support the stated controller claim. Adding three positive results does not produce a numerical confidence score; their conjunction has the meaning declared by that parent argument.

Likewise, a passing test observation can support the claim that a specified test passed for a specified configuration. A second argument may use that claim as a premise for a broader engineering conclusion, while also requiring representative workloads and applicable configuration assumptions. The second conclusion becomes unusable when a required premise loses support. Passing the test alone does not establish that the broader conclusion follows; the rationale must state the additional engineering relation.

| Claim result | Interpretation |
| --- | --- |
| `supported` | At least one usable, uncontested derivation exists and no active objection targets the claim |
| `contested` | A relevant objection affects the available derivation or its premises, with no uncontested alternative |
| `unsupported` | The supplied programme and observations provide no usable derivation |
| `out_of_scope` | The claim's environment requirements are not met |

`unsupported` does not establish the claim's negation. `supported` expresses the outcome of this calculus for these inputs, not a probability of truth. An assessment with static diagnostics is invalid and must be corrected before its claim results are used.

## Objections and alternative derivations

An objection activates when all of its referenced evidence is usable and satisfies the declared predicates. An objection targeting a claim contests every argument for that claim. An objection targeting `reasoning` contests arguments using that reasoning step. An objection targeting an assumption contests arguments depending on that assumption. The effect of a contested premise propagates to dependent arguments.

An independently supported argument can preserve a conclusion when an objection affects only another reasoning step or assumption. Conversely, a claim-level objection cannot be bypassed by adding another argument with the same conclusion. These rules make the target of an objection semantically significant.

The authored-support calculation has no preference ordering or automatic counterargument generation. It reports the remaining contest so that the engineer can inspect the conflicting evidence. Explicit counterargument and defence relationships can be evaluated with the separate grounded operation below.

## Counterarguments and grounded reasoning

`eal_grounded` implements grounded semantics for an explicit finite argument-and-attack graph. It returns accepted, rejected and undecided arguments, together with a reproducible defence trace. Cyclic attack graphs are valid input; unresolved mutual attacks can remain undecided. See [grounded reasoning](grounded-reasoning.md) for the formal definition, API, examples and verification.

This operation and the EAL argument hierarchy solve different parts of the reasoning task. EAL derives scoped support from evidence and subarguments. The grounded operation calculates acceptance under a supplied attack relation. The host supplies that relation explicitly; the implementation does not infer it from statement text or automatically translate EAL objections into a full ASPIC+ theory.

## Assumptions, environments and time

An assumption has a statement, environment, validation-evidence reference and optional validity interval. Its current usability depends on the environment, the interval and the referenced observation. The observation must match the requested source, tool, inputs and environment, pass its integrity checks, satisfy its predicates and remain within its freshness bound. Evidence is usable at exactly its `max_age` and unavailable when older.

Every dependency of an argument must use the same declared environment as its conclusion. A transfer between environments therefore needs an explicit new observation and argument in the target environment; merely reusing a source-environment claim is rejected. This makes scope transfer visible for the engineer to justify.

An interval is a declared condition for using an assumption. Its start is inclusive and its end exclusive: $[\mathtt{valid\_from},\mathtt{valid\_until})$. A successful check is evidence at a particular observation time. A freshness bound defines how old that evidence may be for an assessment. These are different relations: a recent observation alone does not establish that the environment stayed unchanged throughout an interval.

An expired observation supplies no current support. A validator failure likewise supplies no support; its failure does not establish that the proposition is false. A predicate mismatch can establish that the recorded value fails the stated criterion, while its meaning for the wider assumption still depends on the validation method. Environment mismatch prevents reuse in a different context.

Assessments take an explicit time and context. Supplying the same programme, observations, time and context makes evaluation reproducible. Changing a required observation or context requires reevaluation, which propagates the change through premise dependencies. Persistent observation records allow an earlier assessment to be reconstructed without pretending that earlier evidence remains current.

The engineer remains responsible for choosing fields that adequately describe the relevant environment. A fingerprint identifies the supplied context; it does not discover omitted operating conditions. Similarly, a digest binds supplied data to a recorded value but does not authenticate an untrusted producer.

## Tools and inference validity

`deterministic` and `nondeterministic` describe how a tool is expected to behave under its declared inputs and operating conditions. They do not classify an argument as deductively valid or probabilistically reliable. A deterministic test can miss a defect; a stochastic search can find a proof which a separate checker verifies.

Each tool run produces an observation. The evaluator applies declared predicates and reasoning dependencies to that observation. Process success, a returned Boolean and an accepted conclusion are distinct stages. A tool error, malformed result or stale record cannot become supporting evidence merely because an invocation occurred.

An LLM may propose a claim, reasoning step or next measurement. A host application can parse and validate a text-only model's structured request before dispatching it to the MCP server. The model's request supplies input to the reasoning process; the server performs the implemented checks and returns explicit results. A model without native tool calling still requires that host adapter.

## Extensions and alternatives

**Richer deduction.** The bounded propositional checker can be extended with a separately specified first-order logic, arithmetic solver or proof assistant integration. Each extension needs a formal input representation, a result contract and computational limits. An arbitrary natural-language rationale does not become a mechanically checked derivation merely by selecting a deductive mode.

**Full structured defeasible reasoning.** An ASPIC+ instantiation can specify strict and defeasible rules, contrariness, argument construction and preferences, then derive the corresponding defeat graph. Acceptance would become a formally selected semantics over the constructed arguments. Such a change requires explicit treatment of inconsistent premises and inherited attacks, rather than adding a `strict` keyword to the present rationale field.

**Richer probabilistic reasoning.** Models beyond the implemented binomial interval and finite hypothesis update must identify the target quantity, sampling process and dependencies between observations. In general, $P(A\cap B)=P(A)P(B\mid A)$; multiplying marginal probabilities requires independence. Repeated model outputs, overlapping test datasets and shared measurement pipelines can supply dependent evidence. EAL computes numerical outputs under each method's declared model; it does not invent confidence by counting agreeing arguments or multiplying arbitrary confidence scores.

For the current profile, state each claim at the scope justified by its measurements and model, explain the reasoning relation, identify every required assumption, and add a specific objection or missing observation when the relation is challenged. The resulting assessment makes both available support and unresolved reasoning work explicit.
