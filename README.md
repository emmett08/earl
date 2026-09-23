# Engineering Argument Language (EAL)

EAL represents engineering reasoning as claims, subordinate arguments, typed evidence, reasoning methods, conditional assumptions and objections. A claim can have several alternative arguments. Each argument can depend on claims established by further subarguments, using different reasoning methods at different levels.

The language is **EAL/2**, with `.eal` source files. EAL/2 is the only supported source language; backwards compatibility is never a project requirement. Python 3.11 or later is required. Configured command adapters currently require a POSIX host.

Package **2.1.0** enforces the current method contracts across built-in and installed procedures, rejects statically incompatible result predicates, and checks imported observations against their original acquisition requests. Current examples and references use these contracts. File imports require `request` metadata; obsolete envelopes have no compatibility adapter. The source language remains EAL/2.

## What is implemented

- ANTLR4 grammar and generated Python lexer, parser and visitor, with a typed intermediate representation, source-located diagnostics and separate semantic checks.
- Claim/subargument dependency graphs, alternative derivations, conjunctive premises, reusable subarguments and objections supported by evidence or subarguments. Objections may challenge claims, assumptions, reasoning methods, particular arguments or other objections.
- Distinct computational methods for finite propositional deduction, binomial induction, Bayesian hypothesis comparison, a randomised-group contrast, affine-model counterfactuals, feature-based analogy and finite sampled temporal reasoning. Each has a typed evidence contract and predicates over its computed result. Host-registered, versioned methods extend this catalogue without changing the grammar. Author-supplied structured support is also available.
- Environment conditions, explicit evaluation time, observation freshness and assumption applicability intervals. Expiry withdraws current support without asserting falsity.
- Actual configured commands and imported JSON observations, with preserved measurement time, bounded execution, deterministic/nondeterministic tool metadata and SQLite persistence.
- Composed support/attack evaluation with defence chains and undecided cycles, plus the finite Dung grounded solver for explicit attack graphs.
- Reusable argument patterns with typed parameters, closed lexical scope and identity-preserving applications.
- Typed scalar propositions with declared formal queries, subject/quantity/unit/scope/time correspondence, and explicit method-result bindings. Canonical formatting preserves the parsed meaning.
- An official-SDK MCP stdio server, a shared CLI, and a bounded interaction loop with plain-text and native-function interfaces, host-managed state, explicit draft revision, diagnostic feedback and usage accounting.
- Versioned engineering task corpora and a repeated, paired experiment runner with frozen references, balanced scheduling, structural source equivalence, evidence-trace scoring and retained failures. Provider trials measure outcomes and cost; scripted protocol tests do not establish model capability or savings.

The interpreter computes the declared reasoning operations. Natural-language statements, relevance, modelling assumptions and empirical truth still require justified interpretation. The precise computational limits are documented for each method; this implementation does not claim the complete ASPIC+ framework.

## Run it

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make test
make demo
make live-demo
make modes-demo
make tasks
```

`make demo` uses labelled synthetic observations at a fixed time. It shows support before a calibration assumption expires and loss of dependent support afterwards. `make live-demo` runs two local Python commands: deterministic inspection of the workload input and a duration measurement of a real SHA-256 workload. Timing is nondeterministic. No external model provider is needed for these demonstrations.

Java is needed only to regenerate the parser. Generated Python sources are included for normal installation.

```bash
make generate
make check-generated
make build
```

The generation script checks the ANTLR 4.13.2 distribution’s SHA-256 digest. The runtime is pinned to the same version.

## A subordinate argument

An argument’s `premises` are claims, each of which can be established by other arguments:

```eal
reasoning compose_observations {
  method "structured/1";
  rationale "The subordinate results jointly support the stated, qualified engineering explanation.";
}
argument engineering_explanation {
  conclusion explanation;
  reasoning compose_observations;
  premises measured_behaviour, model_applicability;
}
```

This is a fragment. [examples/latency.eal](examples/latency.eal) is a complete executable source. The two premise claims may use different methods; the final step preserves their qualifications. An unresolved objection to a required premise propagates to the dependent argument. An independent supporting argument can remain usable.

[The reusable measurement example](examples/reusable-measurements.eal) uses one typed argument pattern twice, preserving the same trial identity while checking two pressure bounds:

```bash
eal --workspace . --registry examples/reusable-tools.toml validate examples/reusable-measurements.eal
```

Reasoning declarations select one exact versioned method and a predicate on the method’s output, for example an inductive lower bound. See [the method contracts](docs/reasoning-modes.md) and [the mixed-method example](examples/mixed-reasoning.eal). A computational method without its required evidence or result predicate is rejected. [Method extensions](docs/method-extensions.md) show how to add a typed numerical procedure through host configuration.

## CLI and MCP

```bash
eal --workspace . --registry examples/tools.toml validate examples/latency.eal
eal --workspace . --registry examples/tools.toml collect examples/latency.eal --context @examples/context.json
```

Use the returned collection identifier with `reason`; retaining the same source and context ensures the observations apply to the intended question:

```bash
eal --workspace . reason examples/latency.eal --context @examples/context.json --collection COLLECTION_ID --now 2026-09-23T01:00:00Z
eal --workspace . explain ASSESSMENT_ID --claim sample_latency
eal grounded examples/grounded.json
eal-mcp --workspace . --registry examples/tools.toml
```

The MCP tools are `eal_describe`, `eal_format`, `eal_validate`, `eal_collect`, `eal_reason`, `eal_explain` and `eal_grounded`. `eal describe` exposes syntax and contracts to a model without prior EAL knowledge. `eal format FILE` returns canonical source as JSON. Formatting changes exact source identity when its bytes change, so observations must then be recollected.

A text-only model can emit a JSON operation request for `eal-host`; the host performs one MCP call. `eal-agent` adds the configured model/request/result/repair loop over a persistent MCP session. Its stateful interface retains exact source, context and current result identifiers; a model can request `{"operation":"assess"}` to validate, collect, reason and explain, then `{"operation":"finish"}` to return the checked result without copying them. Plain-text and native-function interfaces use the same operation semantics. See [the model loop](docs/model-loop.md) and [model evaluation](docs/model-evaluation.md) for configuration, budgets and the distinction between a completed interaction and a correct engineering answer.

## Read the design

[EAL/2 design decisions](docs/eal2-design.md) explains the expert-informed choices, alternatives and reusable patterns. [Design aim and remaining work](docs/design-aim.md) defines purpose completeness, precise vocabulary, human readability and low-cost model delegation, distinguishing requirements from current capabilities.

- [Argument model and subarguments](docs/argument-model.md): chosen semantics and relation to Toulmin and structured argumentation.
- [Language reference](docs/language.md): declarations, scope, time, predicates and diagnostics.
- [Precise vocabulary](docs/vocabulary.md) and [typed propositions](docs/typed-propositions.md): formal queries, unit checks and result correspondence.
- [Engineering tasks](docs/engineering-tasks.md): known-answer cases, adverse variants and remaining coverage gaps.
- [Historical live model experiments](docs/live-model-results.md): original API comparisons, retained failures, token usage and cost estimates from earlier EAL versions.
- [EAL/2 regression experiments](docs/eal2-model-results.md): live model/host measurements for package 2.1.0 on 23 September 2026, using previously exposed tasks.
- [Historical EAL/0.3 repeated experiments](docs/eal03-model-results.md): original model/interface conditions and development ablations.
- [Reasoning methods](docs/reasoning-modes.md): distinct evidence schemas, algorithms and interpretation limits.
- [Grounded argumentation](docs/grounded-reasoning.md): counterargument, defence and undecided cycles.
- [Implementation architecture](docs/implementation.md): Parr’s patterns, ANTLR4 and extension points.
- [MCP and tool execution](docs/mcp-and-tools.md): host configuration, protocol, persistence and text-model integration.
- [Primary sources](docs/sources.md).
- [Reusable skill](skills/engineer-argumentation-languages/SKILL.md): the maintained contributor guidance, including expert language-design references and the project’s EAL/2 rules.

`CONTRACT.md` records the implementation interface shared by the parser, interpreter and runtime. The interpreter evaluates authored finite support graphs and explicit argument graphs. It does not automatically discover causal structure, prove arbitrary prose, infer unlisted hypotheses, model continuous behaviour from isolated samples, or authenticate the physical provenance of observations from digests alone. Typed correspondence narrows what is checked; it does not establish general engineering completeness. The [EAL/2 regression report](docs/eal2-model-results.md) measures selected model/host systems on previously exposed tasks. Human comprehension, generalisation to unseen tasks and the effect of EAL notation remain unmeasured. Historical experiments retain their original versions and results.
