# Engineering language design contract

## Purpose and demonstrated completeness

Define a versioned set of engineering tasks before declaring a language complete. Include diagnosis, prediction, explanation, design comparison, requirements reasoning, model applicability, numerical calculation, simulation/test interpretation, causal and counterfactual questions, temporal behaviour and revision after new evidence where these belong to the intended domain. Add domain-specific examples when they expose genuinely new relations; keep the domain wider than the current implementation’s convenient examples.

For each task, record the engineering question, expected conclusion form, scope, required subarguments, reasoning methods, admissible evidence, assumptions, contradictions, relevant tools, expected result or justified unresolved outcome, and what changes the conclusion. Provide both a worked instance and counterexamples that distinguish correct semantics from plausible prose.

| Property | Demonstration required |
|---|---|
| Representational coverage | Encode the necessary engineering distinctions without leaving essential meaning in untyped prose or an opaque payload |
| Compositional coverage | Combine subarguments, methods and evidence with explicit dependencies, qualifications and treatment of conflict |
| Algorithmic guarantee | Specify the exact decision or calculation procedure, domain, termination/resource limits and meaning of incomplete results |
| Verification strength | State which property is established: well-formed syntax, typing, checked derivation, model-conditional result, statistical statement or empirical observation |
| Operational coverage | Collect actual inputs, run the intended method, return inspectable results and revise conclusions in the supported host workflow |
| Human and model usability | Show that engineers can interpret the source and selected models can produce/revise faithful requests on held-out tasks |

Keep unsolved task families visible. An explicit unknown result is correct for genuinely insufficient evidence or exceeded resources; returning unknown for every case does not demonstrate useful completeness. Require correct resolution on a declared set of tasks with independently known answers. Separate algorithmic completeness for a formal fragment from empirical adequacy for an engineering domain. Avoid claims of a terminating complete decision procedure for unrestricted mathematics or arbitrary programmes.

## Vocabulary and minimality

For each proposed keyword or operator, specify its exact referent, syntactic positions, operand/result types, binding rules, semantic effect, error behaviour, scope/time effects and examples that distinguish it from its nearest alternative. Use familiar engineering words when their precise meaning fits. Avoid synonyms for the same construct and unexplained abbreviations. A shared spelling is acceptable only when it denotes the same concept in the permitted contexts; distinguish unrelated notions such as tool execution variability and reasoning method.

Keep propositions, observations, evidence roles and arguments distinct. A proposition can be a conclusion in one argument and a premise in another. An observation becomes evidence for a question through an explicit relevance relation and method. An argument connects grounds to a conclusion through a specified reasoning step. An assumption supplies a qualified premise whose applicability can change. An objection identifies which proposition, assumption or reasoning step it challenges.

Apply a removal test: identify a required task and a semantic distinction that would be lost if the construct were removed. If existing constructs preserve that meaning with comparable readability and checkability, prefer them. Apply the same test to implicit defaults, syntax sugar and fixed method enumerations. Keep algorithms and data formats behind typed method interfaces; add syntax for an engineering distinction, not merely for a new solver or numerical formula.

Provide a compact normative vocabulary alongside the grammar. Make diagnostics use the same terms. Document proposed terminology separately from executable syntax; declare actual grammar changes explicitly. This project does not require backwards compatibility or migration machinery.

## Human-readable source and formal meaning

Maintain one semantic representation across source text, API requests, stored arguments and explanations. A readable surface can include explicit named clauses and concise domain expressions. Structured interchange serves automation and must preserve the same meaning. Require a canonical printer and round-trip tests when both forms are supported. Do not count an opaque JSON payload as a readable reasoning expression merely because its container parses.

Represent typed propositions and their bindings where verification depends on them. State variables, entities, units/dimensions, quantifier domains, model/environment identity, uncertainty interpretation and temporal scope when relevant to the task. Allow a narrower formal fragment initially, but identify the tasks it cannot yet express. Check that subargument results and method inputs refer to the same propositions and qualifications. Keep explanatory prose attached to those representations without interpreting free text as a proof.

Test comprehension by asking an engineer to identify the claim, method, dependencies, observations, assumptions, counterarguments and possible outcome changes from source alone. Test a model on the same distinctions. Prefer demonstrable reduction in semantic errors to mere reduction in token count.

## Delegation and low-cost models

Use the model for articulation, selection and revision of requests. Use the host for protocol interaction and state. Use the interpreter and method implementations for the specified reasoning, derivations, calculations and argument checks. Preserve the ability to use deterministic solvers, stochastic search, simulation, statistical software and external model services through distinct typed contracts.

Implement a closed interaction loop when autonomous agency is required: discover operations and schemas; obtain a structured request or source; validate it; return precise diagnostics; permit a bounded revision; execute the checked operation; return a compact result with retrievable derivations; decide whether to request more evidence, revise an argument, report an unresolved question or stop. Supply explicit time, token, iteration and execution budgets. A one-request dispatcher is a useful component but does not implement the whole loop.

Treat lower cost as a measured design objective. Compare at least the selected model alone and the same model with delegation on held-out tasks. Record model/version, sampling settings, task inputs, correct and unjustified conclusions, unresolved cases, repair attempts, tokens, solver/tool expense, latency and total cost per correctly resolved task. Count failed attempts. Keep reported low-cost capability limited to models and tasks actually evaluated.

## Elegance and expressive power

Apply [expert-language-design.md](expert-language-design.md) when choosing core constructs, reusable abstractions, notation or extension rules. Compare conceptual rules and exceptions, local composition, semantic preservation, comprehension and task coverage. Show a library or derived-form alternative before adding a primitive. Require fixed-input extension compatibility and controlled model comparisons; distinguish syntax-only prompting from host-mediated execution.

## Development order

Start with the task suite and vocabulary, then formal representation and method contracts. Implement parsing, binding, type checks, interpretation and explanation. Add concrete tool adapters and the host loop. Test formal meaning and empirical/model assumptions separately. Run human comprehension and model/cost experiments. Use uncovered tasks and redundant constructs to drive expansion or removal. Preserve this distinction in reporting: design requirement, implemented feature, tested behaviour and measured capability.

## Versioned extension boundary

Require an immutable registry of host-installed method contracts with explicit versioned identifiers, evidence kinds, input and query schemas, typed outputs, supported quantities and units, implementation identity, and resource bounds. Validate query identity before execution and output types before a result can support a proposition. Distinguish the measured input quantity from the computed output quantity or unit. A new method should be demonstrable through the unchanged parser and an actual CLI/MCP invocation. Source may select a registered contract; it must not import executable code. A callback version or source digest alone does not identify all of its software dependencies; preserve the host packaging needed for reproducibility.
