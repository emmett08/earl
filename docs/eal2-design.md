# EAL/2 design decisions

EAL/2 has one source language, one versioned reasoning-method selector and one set of support/attack semantics. Backwards compatibility is never a project requirement. The design favours a small set of explicit, composable rules; prior source versions, reasoning aliases and version-dependent objection behaviour are removed. Historical measurements retain their original labels and results.

The intended gain is easier faithful expression and revision of engineering arguments. This remains a design hypothesis. The [23 September 2026 regression report](eal2-model-results.md) measures selected model/host systems using EAL/2 package 2.1.0 on previously exposed tasks. Human comprehension, generalisation to unseen tasks and the effect of EAL notation remain unmeasured; passing interpreter tests cannot establish those gains.

## Expert recommendations and EAL adaptations

These are primary-source recommendations followed by project decisions. The authors did not assess or endorse EAL.

| Primary source and inspected location | Source recommendation | EAL/2 adaptation |
|---|---|---|
| C. A. R. Hoare, *Hints on Programming Language Design* (1973), reprint §§13.2–13.3, [text](https://flint.cs.yale.edu/cs428/doc/HintsPL.pdf) | Simplicity, readable programmes and early error detection help programmers understand consequences. Modularity and orthogonality serve simplicity. | Use one exact method selector, common argument checks and local diagnostics; permit combinations only when their meaning is defined. |
| Niklaus Wirth, *Good Ideas, Through the Looking Glass* (2005 author manuscript), §§4.8, 5.1–5.2, [text](https://people.inf.ethz.ch/wirth/Articles/GoodIdeas_origFig.pdf) | Type loopholes undermine checking; parser power cannot compensate for obscure, privately invented notation. | Keep a shared grammar and checked input/query/output contracts. New numerical algorithms add typed vocabulary through the registry. |
| Guy L. Steele Jr., *Growing a Language* (1998 talk; published 1999), preliminary manuscript pp. 3–6, [text](https://homepages.inf.ed.ac.uk/wadler/gj/Documents/steele-oopsla98.pdf) | A language should support growth and let user-defined vocabulary compose naturally with built-in vocabulary. | Built-in and installed methods have the same invocation and binding rules. Typed argument patterns factor repeated dependency structures. |
| Matthias Felleisen, *On the Expressive Power of Programming Languages* (1991), introduction and formal framework, [text](https://www2.ccs.neu.edu/racket/pubs/scp91-felleisen.pdf) | Computability alone is a weak comparison; constrained translation and eliminability distinguish expressive facilities. | Show a local, meaning-preserving expansion before adding an inference primitive. Argument patterns are derived forms, not a claimed increase in formal expressive power. |
| Terence Parr, *Language Implementation Patterns* (2009), [publisher overview](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf), [typing excerpt](https://media.pragprog.com/titles/tpdsl/static.pdf) | Recognition, intermediate representation, symbol handling, checking and interpretation have separate responsibilities. | ANTLR recognises source; lowering resolves typed patterns into arguments; static analysis and evaluation operate independently. Locations survive lowering for diagnostics. |

The language's defeasible reasoning meaning comes from the explicitly defined [argument model](argument-model.md). The recommendations above guide its expression and implementation, not its logical soundness or empirical adequacy.

## One typed method boundary

```eal
reasoning contrast {
  method "causal/1";
  rationale "Compare group means under the declared experiment assumptions.";
}
reasoning vibration {
  method "engineering/rms/1";
  rationale "Calculate RMS deviation from the specified origin.";
}
```

Both declarations use the same grammar and typed contract lookup. The second works when the host installs its contract. Source cannot import code. There is no reasoning `mode` alternative; tool `mode` still denotes collection variability.

The decisive case is two successful numerical procedures with different formal questions or units. A pressure contrast cannot support a flow-rate claim merely because its scalar exceeds a threshold. A bound query about RMS deviation from zero cannot be answered by a calculation about another origin. Uniform schemas, result interpretation and explicit `binding` check those distinctions for built-in and installed methods alike. A method's implementation still needs independent mathematical verification.

Each declared query field must also be a required input field with the identical schema. This ensures that every admissible declared question has the same type when supplied to the method. Schema enumerations distinguish booleans from numbers at every nesting level. A result predicate must select an output declared by its method contract. Unit conversion that overflows or would round a nonzero value to zero leaves the binding unsupported, with the conversion failure retained in the explanation.

Adding a keyword per algorithm was rejected: it changes the parser while duplicating the same application rules. An untyped payload escape hatch was rejected: it hides correspondence checks precisely where a new algorithm needs them. New inference relations remain possible core changes when a task demonstrates that the existing relations cannot preserve its meaning.

## Closed, reusable argument patterns

The complete [reusable measurement example](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/examples/reusable-measurements.eal) applies one causal observation to two typed claims. Both claims preserve their own output criteria and refer to the same measured trial.

```eal
pattern estimate_from_trial(c: claim, r: reasoning, e: evidence) {
  conclusion c;
  reasoning r;
  evidence e;
  binding e;
}
apply pressure_argument = estimate_from_trial(c=pressure_increase, r=pressure_difference, e=pressure_trial);
apply upper_argument = estimate_from_trial(c=pressure_bounded, r=pressure_difference, e=pressure_trial);
```

This is a fragment; names must resolve to corresponding global declarations. A pattern has typed `claim`, `reasoning`, `evidence` or `assumption` parameters. Every body reference must be a parameter; a same-spelled global declaration is not silently captured. Named bindings make changed inputs visible. The body contains exactly one ordinary argument and expansion yields an argument under the application's name, so an objection can target one application without attacking all uses of the pattern.

For a single application, the meaning is the directly written argument:

```eal
argument pressure_argument {
  conclusion pressure_increase;
  reasoning pressure_difference;
  evidence pressure_trial;
  binding pressure_trial;
}
```

Substitution preserves identity. Two applications using `pressure_trial` do not create independent measurements or duplicate its evidential weight. Assumption bindings preserve validation evidence and time/environment qualifications. Patterns cannot discharge assumptions, introduce global declarations, invoke patterns recursively or collect evidence. Invalid unused patterns are diagnosed. Expanded arguments undergo ordinary scope, reference, method and proposition checks. At most 1,000 applications and 100,000 total expanded references are allowed.

This bounded derived form addresses actual repeated argument structure. A general macro system would require additional capture, recursion and effect rules without improving this case. Text substitution would move type errors and accidental capture into user code. A claim parameter checks declaration kind; it is not a general quantified proposition type. Task-dependent unit, scope and query checks remain obligations of each expanded argument.

## Alternatives considered

| Design | Strongest advantage | Decision and distinguishing case |
|---|---|---|
| Typed JSON only | One structured representation can suit constrained generation and machine transport. | Retain JSON for observations, formal queries and host requests; retain readable EAL for authored argument structure. Human/model comparisons are still needed to determine which surface performs best. |
| Host library only | Numerical methods and reusable builders can be ordinary library functions. | Keep numerical methods in typed host libraries. Put argument pattern application in source so its dependencies, names and objection targets remain reviewable without executing a generator. |
| Smaller core plus derived patterns | Expansion preserves ordinary argument meaning without a new inference calculus. | Selected: closed typed parameter substitution, common checks and identity-preserving expansion. |
| General macros or new inference primitives | Could express recursive or rule-generating abstractions beyond one argument. | Defer until a required task needs the extra semantics. The present reuse case is locally expressible with ordinary arguments. |

No formal Felleisen-style expressiveness theorem is claimed: the observation model and translation restrictions required for one have not been formalised. The expansion is an engineering design and regression obligation.

## Diagnostics and evidence of improvement

Static diagnostics carry a stable code and message, a declaration and source span when available, and expected/actual descriptions where applicable. Spans use one-based positions and an exclusive end. Pattern-origin metadata identifies how an application became an argument. A repair should identify the mismatched reference or contract without silently weakening a claim. Canonical formatting preserves the checked representation, while changed source bytes still invalidate old observation identity.

The typed representation is checked before pattern expansion and name resolution, including when a Python caller constructs it directly. Declaration identities, field types, actual reference counts and JSON values must satisfy the same structural contract as parsed source. Strings must contain Unicode scalar values; JSON objects require string keys. Predicate paths and operand types are checked against declared method outputs where their schema determines the type. Paths through open JSON fields retain runtime checks.

Current verification covers interpreter behaviour: parsing, typed references, expansion, method contracts, units/query correspondence, source locations, canonical round trips and support/attack consequences. The larger design aim remains task-bounded; there is no general dimensional algebra, recursive argument definition system or hypothetical assumption-discharge calculus.

Fresh evaluation should compare the same tasks through readable source and typed structured requests, with equal observations, methods and budgets. Include model alone, source in the prompt, host-mediated EAL and an equivalent structured-tool baseline. Measure semantic correctness, unjustified claims, justified unresolved answers, repairs, comprehension, tokens, latency and total cost per correct task. Count failures. Earlier public benchmark instances are development knowledge for EAL/2. The [current regression measurements](eal2-model-results.md) cover those exposed cases; new held-out cases and controlled notation comparisons are required to assess generalisation and notation-specific gains.

## Package 2.1.0 contract corrections

The EAL/2 grammar is unchanged. Built-in computations now enforce the same registered input/output schemas and byte bounds as installed methods. Method output remains separate from execution metadata. Causal contrasts preserve small differences between large represented numbers; integer affine models preserve exact integer sums. These repairs enforce the declared meanings and bounds, without adding inference constructs.

Imported observations identify their acquisition through tool, version, mode, input and context. Reusing an observation in another argument is possible when that acquisition still matches; the new collection separately identifies the exact argument source. Old import envelopes lacking that identity are rejected. The strongest alternative was binding imported files permanently to source bytes, which would prevent justified reuse after an internal identifier rename without improving acquisition correspondence.

MCP requests are checked against their advertised schemas before SDK conversion. Host results retain and check source, context, collection and assessment time. This prevents a correct calculation for another request from being reported as the requested conclusion. Implementation verification consists of executable regressions, CLI examples, subprocess MCP/host calls and package inspection. The [live model measurements](eal2-model-results.md) separately assess selected model/host systems on previously exposed tasks.
