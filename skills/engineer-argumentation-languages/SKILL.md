---
name: engineer-argumentation-languages
description: Design, implement, extend and critically test domain-specific languages for engineering reasoning and argumentation using ANTLR4 and Terence Parr’s language-implementation patterns. Use for Toulmin or defeasible argument models, claims and evidence, deductive, inductive, abductive, causal, counterfactual, analogical and temporal reasoning, nested subarguments, conditional or time-dependent assumptions, deterministic and nondeterministic reasoning tools, and MCP interpreters usable through native tool calls or text-model host adapters.
---

# Engineer Argumentation Languages

Build languages that help engineers formulate, derive, challenge and revise conclusions from explicit grounds. Keep the object of the language reasoning and argumentation. Introduce organisational approvals, release controls or compliance workflows only when independently requested.

Read [reasoning-semantics.md](references/reasoning-semantics.md) before choosing a logic. Read [reasoning-modes.md](references/reasoning-modes.md) when a question combines methods or requires different evidence contracts. Read [implementation-patterns.md](references/implementation-patterns.md) when building a parser or interpreter. Read [mcp-execution.md](references/mcp-execution.md) when connecting tools or language models. Use [sources.md](references/sources.md) to verify intellectual and technical claims against primary sources. Verify current ANTLR and MCP documentation before changing their pinned versions.

## Establish the reasoning problem

Inspect the target repository, its local instructions, existing grammar and examples. Preserve the declared language version. Treat a new grammar as a distinct language/version rather than silently claiming compatibility. For the emmett08/earl repository, inspect its current EAL grammar and docs before editing; the repository name does not imply EARL 6.1 compatibility.

Identify a concrete engineering question, competing conclusions, available observations, intended inference, conditional assumptions and what would change the conclusion. Start with one worked reasoning problem and a counterexample. Separate the proposition to be considered, its executable representation, the observations relevant to it and the inferential relation. Resolve routine design choices directly; ask only when the answer changes the language’s purpose or semantics.

## Specify meaning before syntax

Map Toulmin’s claim, grounds, warrant, backing, qualifier and rebuttal to precise engineering vocabulary. Prefer `claim`, `evidence`, `inference`, `premise`, `assumption`, `environment` and `objection` when those meanings fit. Define every keyword through its denotation, allowed operands and semantic effect. Give reasoning methods explicit names and distinct typed evidence contracts; a generic `inference` declaration is insufficient to express a mixed-method reasoning programme. Implement method-specific computations and evaluate explicit predicates on their outputs; mode labels alone do not add reasoning behaviour. Use a predicate for a measured relation; use prose to state a proposition or rationale. Never silently evaluate arbitrary prose as logic.

Represent complex arguments as a graph of claims and their supporting subarguments. Permit multiple alternative derivations for one claim and mixed reasoning methods at different steps. Preserve reusable subarguments by identity; repeated use does not create independent evidence. Check each local reasoning step before propagating its conclusion, and retain the path explaining why a higher-level conclusion changed.

Choose and name the executable reasoning model. Distinguish an authored argument-dependency evaluator, a Dung graph solver, a specified ASPIC+ instantiation, a deductive kernel and probabilistic inference. Implement the chosen model’s actual semantics. State omitted features without claiming general conformance. When adopting a bounded profile, specify its inference and objection propagation rules, termination bound and treatment of alternatives.

Distinguish evidence against a premise, evidence against a conclusion and evidence against applying an inference. Define how an attack becomes a defeat, whether preferences apply and how unresolved conflict is represented. Preserve uncertainty and independent arguments; never equate absent support with falsity. Reject or interpret cycles explicitly. Separate supporting premises from challenged targets.

Define assumptions as propositions provisionally used within a stated scope. Represent applicability conditions, validation method, observations, observation time, evaluation time, freshness, and any asserted interval of applicability. Specify what happens after expiry, failed validation, changed environment, missing observation or collection error. Explain that freshness and environment fingerprints cannot establish physical continuity or truth.

Keep tool repeatability separate from inference validity. A deterministic test supplies limited observations; a stochastic search can discover a derivation checked by a deterministic kernel. Treat LLM assertions as fallible outputs. Introduce uncertainty measures only with a specified estimand, sampling model and dependence assumptions.

## Implement independent passes

Use ANTLR4 for lexical and syntactic recognition. Lower a generated parse tree through an external visitor into a typed intermediate representation. Perform declaration collection, name resolution, type/shape checking and dependency analysis before interpretation. Keep IO and tool execution outside the pure evaluator. Follow the implementation patterns reference; avoid embedding the application in grammar actions.

Pin compatible generator and runtime versions. Preserve generation commands and a verified generator digest. Check lexer and parser errors; reject recovery-produced trees after any syntax error. Preserve source locations for diagnostics. Check unknown names, duplicate symbols and fields, wrong reference kinds, predicate operand types, dates, invalid numbers, cycles and bounded resource use.

Use typed expressions or a closed predicate evaluator. Never use general-purpose `eval` on source text. Specify numerical comparison, missing field and type-mismatch behaviour. Reject NaN/infinity where ordering or canonical serialisation requires finite numbers.

Interpret a fixed source, observation set, environment and explicit evaluation time reproducibly. Return conclusions with usable and blocked derivations, assumptions, objections, dependency IDs and reasons. Preserve alternatives and state which parts of a rationale remain author-supplied. Define the effect of new evidence as recomputation over the dependency graph.

## Connect evidence and delegated reasoning

Implement adapters for actual tools and a durable observation store when required. Record request, tool/version/mode, environment, timing, result, execution errors and relevant digests. Bind observations to their intended evidence declarations and inputs. Preserve original observation timestamps for imported results. Test failure, stale data, wrong environment and wrong request as well as successful collection.

Expose small MCP operations for parsing/validation, evidence collection, reasoning, explanation and supported solver operations. Share interpreter functions with the CLI. Use the official SDK for protocol lifecycle and stdio transport. Keep host configuration for executable commands separate from argument source.

For a model without native tool calling, implement a host that parses a strictly defined JSON request, validates its schema, invokes MCP and feeds the structured result back. Explain the division of labour: the model proposes expressions or requests; the interpreter performs specified operations; the host executes the interaction. Do not claim MCP gives an unconnected model tool access or guarantees sound reasoning.

## Exercise the semantics and deliver

Test a positive derivation and cases for an expired assumption, false condition, missing observation, tool failure, changed environment, contested premise, challenged inference, contrary conclusion and an independent supporting argument. Add tests for cycles and undecided outcomes when the selected logic supports them. Compare a formal solver against hand-calculated small examples and the chosen definitions.

Run real parser regeneration, CLI execution and a subprocess MCP client/server round trip. Test the text-model host if provided. Distinguish a local tool-adapter demonstration from verification of an external service. Review the compiled artefact or installed package as well as the source tree when packaging is part of the task.

Document vocabulary, grammar, inference semantics, temporal behaviour, tool/result contract, complete executable examples, extension points and precise limitations. Use synthetic examples labelled as such. Explain the reasoning model and why it was chosen; include alternatives only where they change what can be inferred. Install or publish only the work the user requested, following the relevant skill or repository workflow.
