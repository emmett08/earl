# Design aim: precise, usable engineering reasoning

EAL/2 aims to let an engineer or a language-model host state a bounded engineering question, obtain observations, evaluate explicit reasoning methods, revise an argument after a challenge and report the checked conclusion with its scope. The source should remain readable to a person and parsable by a small or large model. The interpreter supplies only its defined checks; the author and evidence collector remain responsible for the question's relevance and the observation's origin.

## Contents

- [Purpose and acceptance criteria](#purpose-and-acceptance-criteria)
- [Language and implementation choices](#language-and-implementation-choices)
- [Developer use and evaluation](#developer-use-and-evaluation)
- [Present coverage and open obligations](#present-coverage-and-open-obligations)

## Purpose and acceptance criteria

“Complete for engineering purposes” requires a named set of tasks and a demonstrated result for each one. Specify the engineering decision, represented system, quantities and units, observation sources, temporal and physical scope, required reasoning relations, expected revisions and computation budget. For every task, test a correct case and an adverse variant against an independently established reference. Report separately whether the language can *represent* the question, the method can *compute* the defined result, the argument evaluator can *compose* it, the evidence can justify its use for the physical question, and a model-assisted host can *communicate* the checked outcome.

Useful coverage cases include a model property with measured applicability, competing fault explanations after a new measurement, a causal contrast distinct from a model-based counterfactual, an expiring calibration assumption, an objection to an intermediate argument with an independent defence, and a text-only model completing the full host interaction. Boundary cases include unit and quantity mismatch, relevant and irrelevant observations, partial negative searches, ambiguous briefs, missing evidence and changed source versions. Each added domain may demand new method contracts. The finite built-ins do not imply a complete procedure for arbitrary mathematics.

The human test is whether an engineer can recover a claim, formal question, supporting sources, author-supplied warrant, assumptions, objections and the effect of changed evidence from the source and result. The model test is whether the whole system reaches the justified qualified decision within measured resource limits. Parse success and shorter text are intermediate measures; neither alone establishes semantic fidelity or a better decision.

## Language and implementation choices

A keyword must denote one necessary concept with defined operands, types, scope, evaluation effect and failure behaviour. Source syntax, the typed representation and structured host interchange must agree about those concepts. The grammar and contract tables are in [language](language.md) and [vocabulary](vocabulary.md); the exact support and attack construction is in the [argument model](argument-model.md). Add algorithms through typed, versioned method contracts when the existing argument relations express the task. Add a new core relation only after a task shows that existing constructs cannot preserve its meaning. [EAL/2 design decisions](eal2-design.md) records the alternatives and the primary language-design recommendations.

The implementation applies selected patterns from Parr's *Language Implementation Patterns*: ANTLR4 recognition, external visitor lowering to typed declarations, closed name resolution and checks, and interpretation of the checked representation. A formatter emits source from the representation and is tested for semantic round trips. This division exposes syntax and type failures before method execution. It does not supply general expression inference, proof of correspondence between a prose statement and its typed proposition, or a general solver translation architecture. The [publisher's contents and typing extract](sources.md#language-implementation) anchor the pattern descriptions; Parr's book presents implementation choices, not EAL/2 semantics.

For a typed proposition, correspond the queried method input and output to the proposition's subject, quantity, unit, scope and interval. For instance, a successful calculation of pressure about one origin cannot justify a flow-rate claim or a different origin. The runtime checks represented correspondence; an independently reviewed brief and source are still needed to establish that this is the physical question the user asked. An observation's matching digest and environment fingerprint identify supplied data but cannot authenticate a measurement or detect an omitted operating condition.

## Developer use and evaluation

A developer registers a validated EAL/2 source and its claim once. Later sessions can select the same entry and claim, assess at the decision time, reuse compatible unexpired observations, collect only missing evidence and provide a compact checked result to a small or large model. The host performs collection and reasoning for a model without tool access or reliable reasoning capabilities. An application keeps the host's exact claim status separate from the model's prose. [The argument service](argument-service.md) specifies registration, assessment and reuse; [MCP and tools](mcp-and-tools.md) specifies the interfaces.

The [API load-test example](../examples/api-load-test/README.md) demonstrates source, collection of an identified report and assessment through CLI and MCP. It computes sample latency and error statistics from synthetic request results. Its bounded claim concerns those records; it supplies no production measurements or model-comparison outcomes.

Evaluate developer benefit on independently selected tasks with an equivalent question, observation access and answer contract: record time to first correct scoped answer, calls to collectors and models, prompt tokens, cost, and incorrect or unjustified claims. Test fresh and later sessions, small and large models, and models using native tools versus the host adapter. Keep authoring effort and catalogue selection errors visible. The executable example establishes behaviour but cannot establish a comparative benefit.

## Present coverage and open obligations

The grammar currently declares environments, tools, evidence, assumptions, reasoning, claims with optional typed propositions, arguments, closed patterns and applications, and objections. The runtime supports bounded method contracts, source and type checking, formal query/result bindings, finite support/attack evaluation, CLI and MCP calls, a one-request JSON host adapter and model-context preparation. Provider conversation loops belong to the calling application. Those are implementation properties exercised by repository tests and one worked path. They do not verify the engineering warrant in a source, authenticate an external observation, or demonstrate a performance advantage over equally capable prose or JSON systems.

Claims about authoring reliability, human comprehension, transfer to new task families, overall cost and model-class superiority remain open empirical questions. A comparison needs independently reviewed cases, specified model versions, a prespecified protocol and retained outcomes, including failures.
