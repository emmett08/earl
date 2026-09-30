# Expert-informed language design

Use this reference when designing or revising EAL's core, notation, abstraction mechanisms or extension system. The source summaries below report the authors' positions; the EAL recommendations and evaluation criteria are engineering adaptations. They do not establish expert endorsement of EAL or measured benefits for AI models.

## Primary-source recommendations

| Source and inspected location | Source position | EAL design application |
|---|---|---|
| C. A. R. Hoare, *Hints on Programming Language Design* (1973), reprint §§13.2–13.3, especially simplicity and orthogonality: [primary text](https://flint.cs.yale.edu/cs428/doc/HintsPL.pdf) | Simplicity, readability, error detection and efficient implementation support understanding. Modularity and orthogonality are means towards simplicity; unrestricted combinations are not an end in themselves. | Minimise concepts and exceptional rules together. Permit useful, well-typed combinations; reject combinations without a defined engineering meaning. Evaluate the reader's burden and implementation cost rather than counting keywords alone. |
| Niklaus Wirth, *Good Ideas, Through the Looking Glass* (2005 author manuscript), §§4.8, 5.1–5.2: [primary text](https://people.inf.ethz.ch/wirth/Articles/GoodIdeas_origFig.pdf) | Type-system loopholes weaken checking. Powerful parser machinery cannot repair poor notation. Locally invented grammar can obstruct communication and make semantics difficult to specify. | Preserve a shared syntax and checked extension boundary. Give every extension typed inputs, outputs and explicit semantic obligations. Treat repeated escape-hatch use as evidence of a missing abstraction; replace it with a typed facility. |
| Guy L. Steele Jr., *Growing a Language* (1998 OOPSLA talk; final publication 1999), preliminary manuscript pp. 3–6: [primary text](https://homepages.inf.ed.ac.uk/wadler/gj/Documents/steele-oopsla98.pdf) | Design for growth. User-defined vocabulary should compose naturally with built-in vocabulary. Adding vocabulary and changing the rules of meaning are distinct forms of growth. | Give built-in and installed methods the same invocation and result-binding rules. Support reusable argument definitions. Prefer extending vocabulary through typed libraries; version changes to the rules of meaning explicitly. |
| Matthias Felleisen, *On the Expressive Power of Programming Languages* (1991), introduction and formal framework: [primary text](https://www2.ccs.neu.edu/racket/pubs/scp91-felleisen.pdf) | Computability alone poorly distinguishes universal languages. Restricted translations and eliminability expose whether a construct can be removed without global programme reorganisation. | Attempt a local, meaning-preserving encoding before adding a primitive. Record when removal requires non-local changes or loses a required relation. Treat this as a design heuristic unless EAL's languages, observations and translation restrictions have been formalised sufficiently for a theorem. |
| Terence Parr, *Language Implementation Patterns* (2009), publisher overview, contents and typing excerpt: [overview](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf), [excerpt](https://media.pragprog.com/titles/tpdsl/static.pdf) | Recognition, intermediate representations, symbol handling, type checking and interpretation have distinct implementation responsibilities. | Give source and structured requests one typed representation. Keep syntax recognition, binding, static checks and execution independently testable. Preserve source locations through lowering so errors identify the author's expression. The book predates ANTLR4; use current official documentation for ANTLR4 details. |

Read these recommendations together. Steele's account supports extensibility; Wirth's criticism concerns private grammar and unclear meaning. EAL can support extensible typed vocabulary while retaining common syntax. Hoare's warning limits indiscriminate orthogonality. Felleisen's account helps distinguish convenience from additional expressive capability. None of these sources determines EAL's argumentation semantics; choose those through the existing reasoning-semantics reference.

## Operational meaning of elegant and powerful

Define **elegance** as a small set of coherent concepts with predictable composition, few exceptional rules and readable local explanations. Define **power** as faithful expression, execution and revision of the declared engineering tasks, including useful abstraction and method composition. These are design objectives to evaluate, not properties established by a slogan or universal computability.

For each substantial design decision, compare the current design, a library or derived-form solution, and a core-language change where plausible. State the task, observable semantics, smallest distinguishing example, counterexample, translation, implementation implications and measured or expected usability effects. Label estimates explicitly. Use the following criteria without collapsing them into an arbitrary weighted score.

| Criterion | Required evidence |
|---|---|
| Conceptual economy | List independent semantic rules and exceptions. Show what each retained construct contributes and where its removal relocates complexity. |
| Composition | Combine nested subarguments, scoped assumptions, method results and objections through common typing and binding rules. Reject mismatched scope, units, domains or inference strength with local explanations. |
| Abstraction | Factor repeated reasoning into named, parameterised definitions when repetition warrants it. Show expansion preserves claim meaning, assumption dependencies and evidence identity. |
| Readability | Ask readers to recover a conclusion's grounds, qualifications and objections and predict the effect of a change. Measure accuracy and effort; record token length separately. |
| Useful expressiveness | Solve representative and held-out tasks with independently assessed outcomes. Record awkward encodings and non-local edits as well as unsupported tasks. |
| Predictability | Test formatting invariance, capture-avoiding renaming, declared expansion equivalence, and extension compatibility under fixed inputs and versions. |
| Implementability | Provide executable semantics for the supported fragment, informative diagnostics and explicit resource behaviour; distinguish unknown, conflict and execution failure. |
| Evolution | Add a genuinely new method without editing the parser. Demonstrate that installing an unused extension leaves existing programmes' meaning unchanged. |

Set task-specific acceptance criteria before comparative evaluation. Prefer designs that preserve required meaning and improve comprehension or composition at acceptable implementation cost. Preserve a richer construct where a smaller core would merely force users into opaque payloads, repeated boilerplate or non-local rewrites.

## Core, derived forms and libraries

Keep identities, typed propositions, scope, dependency relations and the chosen inference/defeat semantics in the semantic design. Decide their exact surface spelling from examples and the existing grammar. Do not turn this conceptual list into a mandatory keyword list.

Place recurring domain definitions and reasoning patterns in libraries where typed parameters and explicit dependencies suffice. Place numerical algorithms and solver integrations behind installed, versioned method contracts. Classify syntax sugar by its expansion into the core; retain it when it measurably improves comprehension or faithful generation. Keep its expansion visible to explanations and preserve source mappings. Require a core change when a necessary semantic distinction cannot be preserved by the existing composition rules.

Introduce parameterised argument definitions only with a concrete reuse case. Specify lexical scope, capture-avoiding substitution, input and result types, assumption discharge and identity rules. Reusing a derivation must not turn one observation into several independent observations. Define whether recursive definitions are rejected or interpreted under an explicitly bounded or terminating semantics. Treat proposed syntax as a design sketch until implemented by the declared grammar.

Require extension contracts to state applicable assumptions, supported proposition forms, output interpretation, verification strength, failure states and resource bounds. Preserve explicit conversions between reasoning methods: a confidence interval cannot silently become a deductive proof, and a simulation outcome cannot silently become a universal claim. A stable grammar does not by itself guarantee stable semantics; pin contracts and test EAL/3 programmes against a fixed semantic baseline.

Adopt conservative extension as the default for existing constructs: under the same inputs, evaluation time and pinned method versions, adding unused names must preserve existing conclusions and qualifications. Scope imports explicitly, reject ambiguous names, and avoid replacing contracts in place. When an inference rule intentionally changes conclusions, document the current semantic contract and revise the reference cases. EAL/3 does not retain earlier language semantics or require migration examples; the extension invariant concerns unchanged EAL/3 programmes under the same pinned contracts.

Keep parsing, type checking and pure argument evaluation free of implicit evidence collection. Represent effectful requests explicitly and execute them through the host. Readability must survive deferred IO, time-dependent evidence and failed computation.

## Human and AI usability experiments

Test the same semantic tasks through readable EAL source and structured interchange. Explore compact and explicit surface variants when their trade-off is uncertain. A structured request may suit a constrained model; a concise source form may suit human review. Preserve one typed meaning across both forms, and measure their relative performance.

For each actually tested model class, record the exact model, tool access, reasoning settings, prompts, examples, budgets and sampling parameters. Use paired task instances and repeated trials where outputs vary. Include the model alone, the same model with EAL in the prompt only, and the same model with host-mediated execution; add an equivalently resourced plain structured-tool baseline when isolating the benefit of EAL's notation. Keep evidence and solver access comparable in comparisons intended to isolate notation. This separates language effects from extra computation and tool availability.

Measure semantic correctness, unsupported conclusions, justified unresolved outcomes, repair success, comprehension, total tokens, elapsed time and total cost per correct solution. Record all attempts and include uncertainty estimates appropriate to the sampling design. Keep prompt development tasks separate from held-out evaluation tasks. Examine results separately by task family and model class. A gain for a reasoning model or a tool-enabled model does not establish a gain for a text-only model, or vice versa.

Use diagnostics with a stable code, source span, expected type or relation, actual value/type and an actionable explanation. Offer repairs without silently changing the intended claim. Return concise results with retrievable derivations so brevity does not conceal assumptions or objections. Treat constrained decoding, examples and bounded repair as experimental factors; none guarantees faithful reasoning.

## Worked design decision and stress cases

Consider adding separate keywords for every statistical method, plus a generic untyped payload for future methods. Compare that proposal with a typed method registry using one invocation form. A confidence-interval method and a queueing method should expose different schemas through the same checked binding mechanism. Prefer the registry if it preserves quantities, domains, assumptions and conclusion interpretation while allowing a third method without parser changes. Introduce a new core relation only when an actual task demonstrates that those rules cannot express its meaning. This is a design example, not executable EAL syntax.

Exercise these cases before accepting the design:

- Substitute a result expressed in milliseconds for a claim requiring a rate per second; check dimensional incompatibility rather than trusting its numerical value.
- Reuse one observation through two subarguments; preserve shared dependence when combining support.
- Place a reusable argument under a narrower time or environment scope; reject an invalid binding or retain the resulting qualification.
- Add a method named like an existing imported method; require explicit disambiguation and preserve existing pinned meaning.
- Challenge an inference while retaining its premises; derive the outcome from the chosen defeat semantics.
- Exhaust a solver budget; return the specified incomplete outcome without manufacturing a negative proposition.
- Compare compact syntax with explicit clauses on a held-out repair task; retain the form that best preserves meaning under the declared cost and readability criteria.

Report the chosen design, the best alternative, the decisive example and remaining empirical uncertainty. Keep the skill's design advice separate from claims about what a particular EAL release already implements.
