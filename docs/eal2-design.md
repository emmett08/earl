# EAL/2 design decisions

This is the rationale and alternative-design record for the current EAL/2 source language. It does not specify syntax, the argument solver or the MCP wire protocol; those belong respectively to [language](language.md), [argument model](argument-model.md) and [MCP and tools](mcp-and-tools.md). [Design aim](design-aim.md) gives the broader research target.

## Contents

- [Research status and decision rule](#research-status-and-decision-rule)
- [Primary recommendations and adaptations](#primary-recommendations-and-adaptations)
- [One typed method boundary](#one-typed-method-boundary)
- [Derived argument patterns](#derived-argument-patterns)
- [Bounded support and attack](#bounded-support-and-attack)
- [Alternatives and empirical tests](#alternatives-and-empirical-tests)

## Research status and decision rule

The current source contract is EAL/2 and the installed Python package declares version 2.5.0. Source version, package version, observation envelope and method identifiers name different contracts. Historical assessments are tied to their actual code and data, not retrospectively relabelled as evidence for this version. Backwards compatibility with prior language versions is not a design requirement.

The intended gain is faithful formulation, challenge and revision of bounded engineering arguments with checked evidence identity and method results. That gain over prose or another notation is a **hypothesis**. The maintained [API load-test example](../examples/api-load-test/README.md) establishes an execution path for one task using synthetic data. A comparative study would need independent cases and measurements; no task count, parser test or earlier exposed-case result establishes superiority for every model class.

A grammar addition requires a task whose necessary distinction cannot be represented and checked using existing claims, propositions, versioned methods, premises and targeted objections. For example, an explicit negative-finding keyword would not improve the currently represented finite sampled counterexample unless it adds a distinct meaning or demonstrably reduces authoring failures. The exact [historical counterexample source](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/arguments/negative-revision/counterexample.eal) records the earlier bounded case. A richer causal or temporal task might justify an additional typed method or formal expression; it should first show which existing operation fails and why.

## Primary recommendations and adaptations

The cited authors supplied language-design ideas; they did not evaluate or endorse EAL/2. The source-to-design relation is recorded here so their recommendations are not mistaken for evidence of model performance or for the language's inference semantics.

| Primary source and inspected location | Source recommendation | EAL/2 adaptation |
|---|---|---|
| C. A. R. Hoare, *Hints on Programming Language Design* (1973), reprint §§13.2–13.3, [text](https://flint.cs.yale.edu/cs428/doc/HintsPL.pdf) | Simplicity, readable programmes and early error detection help programmers understand consequences; modularity and orthogonality can serve simplicity. | Keep one exact method selector, common argument checks and local diagnostics; combine features only where their meaning is specified. |
| Niklaus Wirth, *Good Ideas, Through the Looking Glass* (2005 author manuscript), §§4.8, 5.1–5.2, [text](https://people.inf.ethz.ch/wirth/Articles/GoodIdeas_origFig.pdf) | Type loopholes undermine checking; parser power does not cure obscure notation. | Use a shared grammar and checked input/query/output contracts rather than a free-form algorithm payload. |
| Guy L. Steele Jr., *Growing a Language* (1998 talk; published 1999), preliminary manuscript pp. 3–6, [text](https://homepages.inf.ed.ac.uk/wadler/gj/Documents/steele-oopsla98.pdf) | Built-in and user-defined vocabulary should compose as a language grows. | Give registered methods the same selector and binding checks as built-ins; factor repeated dependency structures through typed argument patterns. |
| Matthias Felleisen, *On the Expressive Power of Programming Languages* (1991), introduction and formal framework, [text](https://www2.ccs.neu.edu/racket/pubs/scp91-felleisen.pdf) | Computability alone is a weak expressiveness comparison; constrained translation and eliminability distinguish facilities. | Expand each argument pattern locally into an ordinary argument before adding a new inference primitive. This expansion is not a formal expressiveness theorem. |
| Terence Parr, *Language Implementation Patterns* (2009), [publisher overview](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf), [typing excerpt](https://media.pragprog.com/titles/tpdsl/static.pdf) | Recognition, intermediate representation, symbol handling, checking and interpretation have distinct responsibilities. | Generate an ANTLR recogniser, lower to typed IR, resolve declarations and check contracts before evaluation. Retain locations for diagnostics. |

The [sources catalogue](sources.md) holds the other reasoning, statistical and protocol references. These recommendations guide expression and implementation; the [argument model](argument-model.md) defines the executable inferential profile.

## One typed method boundary

Every reasoning declaration uses one exact versioned method contract. The host installs the implementation; source selects it. A new statistic such as the trusted example `engineering/rms/1` belongs in a registered typed contract rather than another parser keyword. The same input, query, output and proposition checks apply to built-ins and extensions. The [language reference](language.md#method-selection-and-static-checks) specifies source selection and static binding; [reasoning methods](reasoning-modes.md#host-registered-methods) specifies runtime contracts and computations.

The decisive error case is a calculation with a correct-looking scalar but the wrong question or engineering quantity. A pressure contrast cannot verify a flow-rate claim solely because it exceeds a number; RMS about a different origin cannot answer the declared RMS question. The bound proposition checks quantity, input unit, subject, scope, interval, formal query and the output's unit interpretation. Its metadata still does not establish that a producer measured the asserted physical variable or that the prose and statistical assumptions are valid.

An untyped payload escape hatch would bypass these correspondence checks. A new algorithm keyword would change the grammar without changing how the operation is selected or bound. A genuinely new inference relation can justify a language change once a case demonstrates that a typed library solution loses its required meaning. The [repository skill](../skills/engineer-argumentation-languages/SKILL.md) records this removal test.

## Derived argument patterns

The archived [reusable measurement source](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/examples/reusable-measurements.eal) demonstrated two typed conclusions from one identified trial. Its pattern expansions substitute declaration identities. Reuse therefore remains visible without duplicating the measurement, its validation time or its independent evidential weight. The two expanded arguments retain different names and may receive different objections. The [language reference](language.md#reusable-argument-patterns) contains current syntax and bounds.

Closed typed parameters and named bindings prevent accidental global capture and check each application. A general macro system would need recursion, capture and effect rules; those extra rules are not required for the existing reuse case. Neither the pattern nor its expansion adds a strict or defeasible inference law. The engineering equivalence is testable by comparing the expanded application and a directly authored argument under fixed observations.

## Bounded support and attack

The source identifies supports and attacks explicitly. Its evaluator checks finite method outputs and dependencies, then calculates acceptance with a least-information support/attack fixed point. It preserves alternative arguments and permits objections supported by further claim arguments and objections to objections. These decisions address a specific challenge-and-revision task. Their equations and limitations are given once in the [argument model](argument-model.md), with an independent construction in [grounded reasoning](grounded-reasoning.md).

ASPIC+ would require additional choices about a logical language, strict and defeasible rules, generated arguments, contrariness, preferences and defeat. This profile does not infer those relations from prose or implement full ASPIC+. Source authoring remains responsible for selecting relevant arguments and objections. An unsupported or unresolved status cannot by itself establish the opposite proposition.

## Alternatives and empirical tests

| Alternative | Useful property | Decision for the current task |
|---|---|---|
| Typed JSON as the authored format | Constrained structure and transport without a separate textual grammar | Retain JSON for method input and host requests; compare a semantically equivalent JSON authored arm in a future study before claiming EAL notation is easier. |
| Host library without source patterns | Reusable ordinary programming abstractions | Keep computation in trusted host libraries; represent argument dependency identities and objection targets in reviewable source. |
| General macros or a rule-generating syntax | Wider forms of reusable argument generation | Defer until a required case cannot preserve meaning under bounded, closed pattern expansion. |
| Full ASPIC+ | Explicit strict/defeasible distinctions and preferences | Specify and implement only if a task and independent verification require those distinctions; the current declared attack profile makes no such conformance claim. |

A future comparison must give every arm an equally specified task, evidence access, checker authority and cost accounting. It must measure source authoring and argument-family selection as well as checked communication: a correct computation can still concern the wrong build or test run, use a missing observation, or be misreported by a model. Compare paired outcomes within predeclared model strata and retain every attempt. A single working example or a result on exposed cases cannot establish a model-class-wide effect, much less universal superiority.
