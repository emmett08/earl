# EAL/3 design decisions

This explains the design of the EAL/3 source language. Syntax, the argument solver and the MCP interface are specified respectively in [language](language.md), [argument model](argument-model.md) and [MCP and tools](mcp-and-tools.md). [Design aim](design-aim.md) describes the intended engineering tasks and evaluation criteria.

## Contents

- [Purpose and extension criterion](#purpose-and-extension-criterion)
- [Primary recommendations and adaptations](#primary-recommendations-and-adaptations)
- [One typed method boundary](#one-typed-method-boundary)
- [Tool identity and acquisition](#tool-identity-and-acquisition)
- [Derived argument patterns](#derived-argument-patterns)
- [Bounded support and attack](#bounded-support-and-attack)
- [Evaluation](#evaluation)
- [EAL/3 experiment methodology](#eal3-experiment-methodology)

## Purpose and extension criterion

EAL/3 is the semantic source contract, `EAL/3` identifies the current newline-based notation, and the installed Python package declares version 3.2.0. Formal reasoning-method inputs use `EAL/typed-input/1`. Source version, package version, acquisition fields, typed-method input envelope and method identifiers name different contracts. Model summaries use `EAL/assessment-packet/2` and `EAL/model-context/2`; the observation-record schema remains `/1`.

The service keeps validated EAL/3 source, claim identity, compatible tool observations and checked reasoning results available across sessions and model providers. A developer can request a registered claim without sending the source, reconstructing its dependency graph or rerunning unexpired observations. A gain in correctness, time or cost remains a **hypothesis** to measure. The maintained [API load-test example](../examples/api-load-test/README.md) establishes an execution path using synthetic data.

A grammar addition requires a task whose necessary distinction cannot be represented and checked using existing claims, propositions, versioned methods, premises and targeted objections. For example, a new negative-finding keyword would need to express a semantic distinction that an explicit negative method result cannot express. A richer causal or temporal task should first identify which existing method or relation fails; an additional typed method may address it without changing the grammar.

The API load-test case shows the distinction. A measured p95 above the limit remains a usable observation; `engineering/api-load-criteria/1` computes a negative criterion result and supports the explicit failing claim. A stale or mismatched report makes the evidence unusable and supports neither the passing nor failing claim. The installed method expresses the calculation through existing EAL/3 claims and predicates. Tests establish those finite outcomes; comparative readability and maintenance benefits require separate human tasks.

## Primary recommendations and adaptations

The cited authors supplied language-design ideas; they did not evaluate or endorse EAL/3. The source-to-design relation is recorded here so their recommendations are not mistaken for evidence of model performance or for the language's inference semantics.

| Primary source and inspected location | Source recommendation | EAL/3 adaptation |
|---|---|---|
| C. A. R. Hoare, *Hints on Programming Language Design* (1973), reprint §§13.2–13.3, [text](https://flint.cs.yale.edu/cs428/doc/HintsPL.pdf) | Simplicity, readable programmes and early error detection help programmers understand consequences; modularity and orthogonality can serve simplicity. | Keep one exact method selector, common argument checks and local diagnostics; combine features only where their meaning is specified. |
| Niklaus Wirth, *Good Ideas, Through the Looking Glass* (2005 author manuscript), §§4.8, 5.1–5.2, [text](https://people.inf.ethz.ch/wirth/Articles/GoodIdeas_origFig.pdf) | Type loopholes undermine checking; parser power does not cure obscure notation. | Use a shared grammar and checked input/query/output contracts rather than a free-form algorithm payload. |
| Guy L. Steele Jr., *Growing a Language* (1998 talk; published 1999), preliminary manuscript pp. 3–6, [text](https://homepages.inf.ed.ac.uk/wadler/gj/Documents/steele-oopsla98.pdf) | Built-in and user-defined vocabulary should compose as a language grows. | Give registered methods the same selector and binding checks as built-ins; factor repeated dependency structures through typed argument patterns. |
| Matthias Felleisen, *On the Expressive Power of Programming Languages* (1991), introduction and formal framework, [text](https://www2.ccs.neu.edu/racket/pubs/scp91-felleisen.pdf) | Computability alone is a weak expressiveness comparison; constrained translation and eliminability distinguish facilities. | Expand compact or compound argument patterns into ordinary typed declarations before adding a new inference primitive. This expansion is not a formal expressiveness theorem. |
| Terence Parr, *Language Implementation Patterns* (2009), [publisher overview](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf), [typing excerpt](https://media.pragprog.com/titles/tpdsl/static.pdf) | Recognition, intermediate representation, symbol handling, checking and interpretation have distinct responsibilities. | Generate an ANTLR recogniser, lower to typed IR, resolve declarations and check contracts before evaluation. Retain locations for diagnostics. |

The [sources catalogue](sources.md) holds the other reasoning, statistical and protocol references. These recommendations guide expression and implementation; the [argument model](argument-model.md) defines the executable inferential profile.

## One typed method boundary

Every reasoning declaration uses one exact versioned method contract. The host installs the implementation; source selects it. A new statistic such as the trusted example `engineering/rms/1` belongs in a registered typed contract rather than another parser keyword. The same input, query, output and proposition checks apply to built-ins and extensions. The [language reference](language.md#method-selection-and-static-checks) specifies source selection and static binding; [reasoning methods](reasoning-modes.md#host-registered-methods) specifies runtime contracts and computations.

The decisive error case is a calculation with a correct-looking scalar but the wrong question or engineering quantity. A pressure contrast cannot verify a flow-rate claim solely because it exceeds a number; RMS about a different origin cannot answer the declared RMS question. The bound proposition checks quantity, input unit, subject, scope, interval, formal query and the output's unit interpretation. Its metadata still does not establish that a producer measured the asserted physical variable or that the prose and statistical assumptions are valid.

A new inference relation has its own specified semantics. Existing versioned methods share one typed boundary and retain the same correspondence checks.

## Tool identity and acquisition

The tool declaration is a `tool NAME` block containing `version "VERSION"`. A trusted TOML binding chooses the collector. The selected binding's digest is recorded in a collected observation and checked by the host before reasoning with stored collection records. Source describes the intended acquisition; the host owns execution configuration. Evidence obligations check the value and applicability of each acquired observation.

Repeatability needs specified replay inputs, algorithm version, environment and test procedure, possibly multiple acquisitions or a sampling obligation. A test runner with fixed code can read a changing remote service, while a stochastic simulation with a recorded seed and initial state can replay one run. A binary source label would not establish either property's relevance to a conclusion. Repeated outputs do not prove independence or measurement accuracy. A configuration digest identifies configured arguments and limits, not executable bytes, dependencies, external state or physical authenticity.

Whether this syntax improves model accuracy, tokens or end-to-end latency must be measured under comparable evidence access, methods and answer contracts, including failed attempts.

## Derived argument patterns

Pattern expansion substitutes declaration identities into a named argument. Several applications may refer to the same observation without duplicating that measurement or its evidential weight. The expanded arguments retain separate names and can receive distinct objections. The [language reference](language.md#reusable-argument-patterns) gives current syntax and bounds.

Closed typed parameters and named bindings prevent accidental global capture and check each application. Compound patterns use explicit typed closure, hygienic namespaces and guarded decreasing list recursion. These rules permit nested authoring while keeping expansion finite; templates cannot execute host effects. Neither the pattern nor its expansion adds a strict or defeasible inference law. The engineering equivalence is testable by comparing the expanded application and a directly authored argument under fixed observations.

## Bounded support and attack

The source identifies supports and attacks explicitly. Its evaluator checks finite method outputs and dependencies, then calculates acceptance with a least-information support/attack fixed point. It preserves alternative arguments and permits objections supported by further claim arguments and objections to objections. These decisions address a specific challenge-and-revision task. Their equations and limitations are given once in the [argument model](argument-model.md), with an independent construction in [grounded reasoning](grounded-reasoning.md).

The core authored profile does not infer rules, contraries or preferences from prose and does not implement full ASPIC+. The separately installed [`argumentation/aspic/2` method](aspic-method.md) constructs arguments and preference-sensitive defeat from a finite, explicit theory. The opt-in compiler derives a theory from EAL arguments and scoped observations; its reviewed `strict`, `rank`, `contrary` and `prefer` relations resolve names through EAL's unique symbol table after pattern expansion. Neither operation changes the core authored graph. Source authoring remains responsible for selecting relevant arguments and objections. An unsupported or unresolved status cannot by itself establish the opposite proposition.

The optional structured solver answers only the formal theory supplied to it. EAL binds that theory's exact query, subject, scope, interval and observation identity. The solver cannot establish the semantic relevance or truth of its premises, the choice of strict rules, contraries or ranks, or the physical provenance of the observations.

## Evaluation

The source format names dependencies and objection targets in a reviewable programme; JSON remains the format for method inputs and host requests. The optional ASPIC+ method implements its specified finite profile. The registered argument service retains source revisions, exact claim selection and eligible observations, and can hand a checked packet to a model that cannot call tools.

Evaluate the combined system on tasks with specified source authoring, catalogue selection, evidence access, method authority and answer contract. Record correctness of the scoped claim, unsupported assertions, collection and model calls, context size, latency and cost across first and later sessions. A correct computation can still concern the wrong build or test run, use a missing observation, or be misreported by a model. Retain failures and report results by model and task type; the synthetic example alone establishes no model-class-wide benefit.

## EAL/3 experiment methodology

The [experiment methodology](eal3-experiment-methodology.md) defines the fresh-session ordinary comparator, a joint correctness and cumulative-token decision at ten recipient sessions, pilot-informed precision allocation and separate component diagnostics. It specifies task provenance, repeated-session dependence, evidence changes, accounting and the limits of inference. The [run guide](../experiments/model_transfer/README.md) describes execution; the [versioned protocol](../experiments/model_transfer/protocol.json) records the prospective scientific contract.
