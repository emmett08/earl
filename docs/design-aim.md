# Design aim: a precise engineering reasoning language

The aim is a human-readable language that can express and execute the reasoning required for engineering arguments, using a small semantic core and explicit method contracts. Engineers and AI agents should use the same represented claims, subarguments, evidence, assumptions and conclusions. A small or large language model can delegate supported reasoning operations through an application host and a custom MCP server. Low cost is an objective to measure across that whole system.

This document specifies the wider aim and distinguishes it from implemented EAL/2 behaviour. EAL/2 is the only supported source language. See [EAL/2 design decisions](eal2-design.md), the [engineering task suite](engineering-tasks.md) and [model evaluation](model-evaluation.md).

## Applying Parr’s patterns

The skill requires working implementations of selected patterns from Terence Parr’s Language Implementation Patterns. The publisher’s [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf) and [typing excerpt shown in the supplied screenshot](https://media.pragprog.com/titles/tpdsl/static.pdf) support the pattern references below. The book presents alternative implementation choices; the language should select those needed for its semantics.

| Pattern family | Application | EAL/2 status |
|---|---|---|
| P.8 and P.10–11 | Recognition followed by typed intermediate representation | ANTLR4 parse tree lowered to typed declarations |
| P.13 | External visitor | `_ASTBuilder` converts generated contexts into semantic objects |
| P.16, bounded scope adaptation | Name resolution | Global declaration maps, closed pattern parameter scopes, typed references and uniqueness checks |
| P.20 and P.22, bounded adaptation | Expression types and compatible operations | Scalar predicate, quantity and contract checks; a closed unit catalogue, formal query correspondence and compatible method outputs. General expression type inference is not implemented |
| P.25 | Interpretation of checked intermediate objects | Dependency evaluation and bounded method computations |
| Chapter 11 translation architecture | Output translation from checked intermediate objects | Explicit IR-to-source emission with round-trip checks. Rule-based rewriting, target-specific generator classes, templates and general solver translation are possible later choices, not implemented patterns |

ANTLR4 supplies recognition; its visitor is adapted to the book’s separation of concerns. Current code does not implement every alternative parser, virtual machine or type system in the book. Nested scopes, richer expression checking or specialised translators should be introduced when a required engineering task needs them.

## Purpose completeness

“Complete for engineering purposes” requires a declared task domain and demonstrated coverage. A version should identify its engineering question classes, relevant system/model types, quantities, evidence forms, reasoning relations, argument composition and computational limits. Coverage must be assessed against those tasks, rather than inferred from the number of named reasoning modes.

For each required task, supply a readable representation, typed inputs, explicit assumptions, a known-answer instance, an adverse instance, the required result and an explanation of its scope. Distinguish representational coverage, implemented calculation, checked derivation, empirical assumptions and operational model use. Keep unsupported task families explicit. Correctly returning an unresolved result for insufficient evidence is necessary; resolving the cases with adequate evidence and known answers is also necessary.

A starting task suite should include:

1. A model-derived property combined with experimental observations and a model-applicability subargument.
2. Competing fault explanations revised by a new measurement, including shared evidence whose reuse does not imply independence.
3. Causal and counterfactual questions with distinct input requirements and assumptions.
4. A calibration assumption applicable only to part of an operating episode, including historical and current assessments.
5. An objection to an intermediate argument, a counterargument to that objection, and an independent route to the main conclusion.
6. A text-only model completing construction, collection, calculation, revision and explanation through the host within a specified cost/resource budget.

Add cases for incompatible units, mismatched physical quantities, unsupported generalisation, missing evidence and time-dependent validity. Expand the suite when another engineering domain reveals a new required relation. Mathematical decision guarantees must state their formal fragment; the general aim does not imply a terminating complete decision procedure for unrestricted mathematics.

## Precise vocabulary and minimal syntax

A keyword should denote one documented concept, with specified operand types, binding rules, semantic effect, scope/time behaviour and failure or unknown outcomes. Its tests should distinguish it from adjacent concepts. The canonical source, diagnostic messages, structured API and explanations should use the same meanings.

| Concept | Required distinction |
|---|---|
| Claim | The proposition being considered, including its formal identity where verification is intended |
| Argument | A stated conclusion connected to grounds by a specified reasoning method |
| Premise | A proposition used by a particular argument; it may itself have supporting subarguments |
| Observation | A recorded measurement or tool result with its original time and context |
| Evidence | An identified observation/result used for a claim through a specified evidential relation |
| Collection specification | The requested observation and the configured means of obtaining it |
| Assumption | A proposition used provisionally under explicit conditions; represent whether reasoning is hypothetical or claims current empirical support |
| Reasoning method | An operation with typed inputs, defined computation and a stated interpretation of its outputs |
| Objection | Reasoning against a premise, conclusion or applicability of a reasoning step |
| Verification | A named procedure establishing a specified property of an identified representation |

These are design distinctions, not a proposal to turn every row into a new reserved word. Retain a construct only when removing it loses a required distinction or makes a necessary task materially harder to express and check. Keep numerical procedures, tool-provider settings and transport mechanics behind appropriate interfaces. Method additions should usually extend typed contracts rather than force new core keywords.

The [executable vocabulary](vocabulary.md) defines the current constructs. `evidence` declares collection and eligibility criteria; observations live in runtime records. `method` selects an exact versioned reasoning contract, while `mode` describes tool variability. `valid` reports static well-formedness. `collected_at` denotes original observation time and `ingested_at` denotes storage time. Backwards compatibility is never a project requirement.

## Human readability and executable meaning

Source text and structured interchange should denote the same typed representation. Provide canonical formatting and parse–format–parse equivalence. Use readable domain expressions for quantities, relations, scope and assumptions where these are needed; retaining essential mathematical meaning only in an opaque payload does not meet the readability aim.

Bind method inputs and outputs to the intended propositions. For example, a pressure calculation cannot verify a flow-rate claim merely because a successful result is attached to that claim’s identifier. Verify quantity/unit, variable, model, environment and time correspondence where the method depends on them. Keep explanatory text attached to the formal proposition and expose any unformalised correspondence explicitly.

Human comprehension trials should ask engineers to recover the conclusion, method, premises, observations, assumptions, objections and expected effects of changed evidence from the source. Model trials should test the same semantic distinctions. Short source is useful when it preserves meaning and reduces errors; raw token count alone is insufficient.

## Delegating to ordinary text models

The model articulates a question, proposes an argument or requests an operation. The host validates the request and manages state. The interpreter and configured methods perform the represented reasoning and argument checks. An MCP interface makes those operations callable from the host. A model without native tool calls can still participate by producing text that satisfies the host’s request schema.

An autonomous application needs a complete interaction loop: operation/schema discovery, request construction, validation, diagnostic feedback, bounded repair, execution, result retrieval, argument revision and stopping conditions. Explanations should identify the checked proposition and its dependencies. Compact responses can refer to stored source/results and offer a separate detailed explanation, preserving essential qualifications.

Empirical capability and savings require actual model experiments. Compare selected named models with and without delegation on held-out engineering tasks. Record correct conclusions, unjustified conclusions, unresolved tasks, retries, token use, tool/solver costs and end-to-end latency. Include every failed attempt in total cost per correctly resolved task. Model size and a “non-reasoning” label do not predict those results sufficiently.

## Current implementation and remaining work

| Area | Implemented | Still required by the wider design aim |
|---|---|---|
| Argument composition | Typed closed-scope argument patterns, reusable subclaims, alternative arguments, scoped evidence and assumptions; typed scalar query/result bindings | Wider proposition forms, explicit binding from symbolic premise atoms to independently supported claim propositions |
| Reasoning methods | Seven bounded computations plus authored structured support; immutable host registries with versioned input/query/output contracts and bounded custom methods | Task-driven methods for further domains; broader units and proposition types |
| Counterarguments | Objection premises, attacks on particular arguments and objections, defence chains and an explicit least-information support/attack construction; standalone grounded graph solver | Preferences, contrariness and strict/defeasible rule systems would need further semantics if required by new tasks |
| Representation | Declaration syntax, source-located typed IR, canonical formatting and semantic round trips | Richer mathematical expressions beyond the bounded scalar/query fragment; engineer comprehension trials |
| Verification | Parsing, reference/type checks, computations, declared query identity, unit/quantity/scope/time bindings and dependencies | General dimensional algebra, quantified propositions and independently established physical/prose correspondence |
| Model access | Actual MCP server, source-preserving host state, targeted draft revision, plain-text and native-function interfaces, bounded feedback and a repeated paired experiment harness | Wider model/task coverage and infrastructure-inclusive costs; mechanisms usable across model classes do not guarantee equal effectiveness |
| Completeness | Versioned known-answer engineering tasks and adverse variants, composed-defence cases, runtime and protocol regressions | Wider domains, human comprehension trials, hypothetical assumption/discharge calculus and richer formal premise bindings |

The task suite, vocabulary, typed bindings, canonical representation, extensible methods, composed objections and model interaction loop provide a bounded implementation. Typed argument patterns now make recurring dependency structures reusable without copying evidence identity. The suite records its uncovered distinctions instead of claiming complete engineering coverage. [Historical EAL/0.3 experiments](eal03-model-results.md) retain their original measured outcomes. EAL/2 comprehension, model performance and cost gains remain unmeasured; regression results alone cannot establish them.