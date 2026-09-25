# Design aim: precise, usable engineering reasoning

EAL/2 aims to let an engineer or a language-model host state a bounded engineering question, obtain observations, evaluate explicit reasoning methods, revise an argument after a challenge and report the checked conclusion with its scope. The source should remain readable to a person and parsable by a small or large model. The interpreter supplies only its defined checks; the author and evidence collector remain responsible for the question's relevance and the observation's origin.

## Contents

- [Purpose and acceptance criteria](#purpose-and-acceptance-criteria)
- [Language and implementation choices](#language-and-implementation-choices)
- [Delegation and end-to-end study](#delegation-and-end-to-end-study)
- [Present coverage and open obligations](#present-coverage-and-open-obligations)

## Purpose and acceptance criteria

“Complete for engineering purposes” requires a named set of tasks and a demonstrated result for each one. Specify the engineering decision, represented system, quantities and units, observation sources, temporal and physical scope, required reasoning relations, expected revisions and computation budget. For every task, test a correct case and an adverse variant against an independently established reference. Report separately whether the language can *represent* the question, the method can *compute* the defined result, the argument evaluator can *compose* it, the evidence can justify its use for the physical question, and a model-assisted host can *communicate* the checked outcome.

Useful coverage cases include a model property with measured applicability, competing fault explanations after a new measurement, a causal contrast distinct from a model-based counterfactual, an expiring calibration assumption, an objection to an intermediate argument with an independent defence, and a text-only model completing the full host interaction. Boundary cases include unit and quantity mismatch, relevant and irrelevant observations, partial negative searches, ambiguous briefs, missing evidence and changed source versions. Each added domain may demand new method contracts. The finite built-ins do not imply a complete procedure for arbitrary mathematics.

The human test is whether an engineer can recover a claim, formal question, supporting sources, author-supplied warrant, assumptions, objections and the effect of changed evidence from the source and result. The model test is whether the whole system reaches the justified qualified decision within measured resource limits. Parse success and shorter text are intermediate measures; neither alone establishes semantic fidelity or a better decision.

## Language and implementation choices

A keyword must denote one necessary concept with defined operands, types, scope, evaluation effect and failure behaviour. Source syntax, the typed representation and structured host interchange must agree about those concepts. The grammar and contract tables are in [language](language.md) and [vocabulary](vocabulary.md); the exact support and attack construction is in the [argument model](argument-model.md). Add algorithms through typed, versioned method contracts when the existing argument relations express the task. Add a new core relation only after a task shows that existing constructs cannot preserve its meaning. [EAL/2 design decisions](eal2-design.md) records the alternatives and the primary language-design recommendations.

The implementation applies selected patterns from Parr's *Language Implementation Patterns*: ANTLR4 recognition, external visitor lowering to typed declarations, closed name resolution and checks, and interpretation of the checked representation. A formatter emits source from the representation and is tested for semantic round trips. This division exposes syntax and type failures before method execution. It does not supply general expression inference, proof of correspondence between a prose statement and its typed proposition, or a general solver translation architecture. The [publisher's contents and typing extract](sources.md#language-implementation) anchor the pattern descriptions; Parr's book presents implementation choices, not EAL/2 semantics.

For a typed proposition, correspond the queried method input and output to the proposition's subject, quantity, unit, scope and interval. For instance, a successful calculation of pressure about one origin cannot justify a flow-rate claim or a different origin. The runtime checks represented correspondence; an independently reviewed brief and source are still needed to establish that this is the physical question the user asked. An observation's matching digest and environment fingerprint identify supplied data but cannot authenticate a measurement or detect an omitted operating condition.

## Delegation and end-to-end study

A text model can formulate the question, author or select a source and request further observations. A host validates its requests, calls the MCP server and configured collectors, returns diagnostics for bounded repair, obtains an assessment and preserves its exact statuses when composing the final answer. This loop is part of the tested *system route*: MCP availability by itself cannot make a model call tools, translate a brief faithfully or adopt a checked status. [MCP and tools](mcp-and-tools.md) specifies the current interface and trust boundaries.

The [API load-test example](../examples/api-load-test/README.md) demonstrates EAL/2 source, collection of a pinned report and assessment through CLI and MCP. It computes sample latency and error statistics from synthetic request results. Its bounded claim concerns those records; it supplies no production measurements or model-comparison outcomes.

The [live API experiment](../experiments/api_load_test/README.md) compares EAL/2 through MCP, a meaning-equivalent JSON prompt, three ordinary developer prompts and explicit prose with an ordinary deterministic checker across six pinned nano/mini/full model snapshots. Every arm selects from the same immutable case measurements. EAL receives an MCP assessment; the conventional-checker control receives direct deterministic checks. The remaining arms receive measurements without a verdict. A common text-mediated adapter supports models without native function calling. Its protocol therefore estimates a combined system difference, not a notation-only effect. The previous benchmark plans remain in Git history. Broader claims still require independently selected engineering cases.

Independent papers on program-assisted reasoning, symbolic-solver feedback, defeasible argumentation and prompt-format sensitivity motivate these alternatives; their reported effects concern their own systems and data. Their bibliographic entries and limits are in [sources](sources.md#model-assisted-reasoning-and-study-design). Earlier EAL/2 model trials and notation diagnostics used exposed development tasks; they are archived at the [pre-reset commit](sources.md#retired-repository-artefacts), and do not establish comparative benefits for the current implementation.

## Present coverage and open obligations

The grammar currently declares environments, tools, evidence, assumptions, reasoning, claims with optional typed propositions, arguments, closed patterns and applications, and objections. The runtime supports bounded method contracts, source and type checking, formal query/result bindings, finite support/attack evaluation, CLI and MCP calls and a host interaction loop. Those are implementation properties established by repository tests and one worked path. They do not verify the engineering warrant in a source, authenticate an external observation, or demonstrate a performance advantage over equally capable prose or JSON systems.

Claims about authoring reliability, human comprehension, transfer to new task families, overall cost and model-class superiority remain open empirical questions. A future study needs independently reviewed cases, frozen model snapshots, a prespecified comparison and retained outcomes, including failures.