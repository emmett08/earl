# Engineering Argument Language (EAL)

EAL represents engineering reasoning as claims, subordinate arguments, typed evidence, reasoning methods, conditional assumptions and objections. A claim can have several alternative arguments. Each argument can depend on claims established by further subarguments, using different reasoning methods at different levels.

The language is **EAL/2**, with `.eal` source files. EAL/2 is the only supported source language; backwards compatibility is never a project requirement. Python 3.11 or later is required. Configured command adapters currently require a POSIX host.

Package **2.4.0** adds reviewed exact-question applicability, durable family-route issuance, claim-scoped evidence collection and a bounded EAL/2 authoring helper. The source language remains **EAL/2**, the observation schema remains **`EAL/typed-input/1`**, and the compact claim packet remains `eal2-claim-packet/2`. Earlier experiments retain their measured package labels. File imports still require `request` metadata.

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
- An optional host-pinned artifact catalogue: a recipient requests a reviewed EAL file by ID while the host selects its source, method registry, context, time and claims, then returns a compact checked status packet.
- An optional reviewed-task recipient route: the trusted launcher binds the original question and grants; a model may nominate only a reviewed task ID. Exact task applicability, typed family bindings and claim grants are checked before collection. Task issuance is persisted for the principal and rechecked when finishing or explaining.
- An optional reviewed alias index for family suggestions and a validated authoring helper with bounded diagnostic repair. Neither ranking nor syntactic validity establishes that an argument expresses the intended question.
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

The operator MCP tools are `eal_describe`, `eal_format`, `eal_validate`, `eal_collect`, `eal_reason`, `eal_explain` and `eal_grounded`. With an operator-configured `--artifacts` catalogue, the server also offers `eal_assess_artifact(artifact_id)` and claim-specific assessment, explanation and finish tools. A separate reviewed-task recipient endpoint exposes only candidate, assess, explain and finish task tools; its exact-question gate checks applicability before collection. `eal describe` exposes syntax and contracts to a model without prior EAL knowledge. `eal format FILE` returns canonical source as JSON. Formatting changes exact source identity when its bytes change, so observations must then be recollected.

A text-only model can emit a JSON operation request for `eal-host`; the host performs one MCP call. `eal-agent` adds the configured model/request/result/repair loop over a persistent MCP session. Its stateful interface retains exact source, context and current result identifiers; a model can request `{"operation":"assess"}` to validate, collect, reason and explain, then `{"operation":"finish"}` to return the checked result without copying them. Plain-text and native-function interfaces use the same operation semantics. See [the model loop](docs/model-loop.md) and [model evaluation](docs/model-evaluation.md) for configuration, budgets and the distinction between a completed interaction and a correct engineering answer.

For a reviewed source reused by another developer or a text-only model on the same registered question and context, configure an [artifact catalogue](docs/mcp-and-tools.md#reuse-a-reviewed-eal-artifact). The operator can call `python -m eal.artifacts --workspace . --registry TOOLS.toml --artifacts ARTIFACTS.toml --id NAME` before invoking a model. The result contains checked statuses and an explanation ID without transmitting the EAL source or language reference to the model. An application may call `ArtifactRegistry.assist_text_only` with a model adapter; it gives the model a compact packet and returns the host-owned status separately from unverified model prose. The present interface tests establish this status boundary; recipient token, latency and accuracy advantages require a prospective comparison.

For exact recurring questions, [reviewed task applicability](docs/eal2-task-applicability.md) binds the launcher's original question to a pinned family case and claim before the model can receive a checked answer. The [authoring helper](docs/eal2-authoring-helper.md) exposes current contracts and retains validation failures during bounded repair. These are host interfaces, not evidence of an EAL/2 advantage over an equal JSON checker. The [host completion audit](docs/eal2-host-completeness-audit.md) records remaining live-acquisition and relevance limits.

## Read the design

[EAL/2 design decisions](docs/eal2-design.md) explains the expert-informed choices, alternatives and reusable patterns. [Design aim and remaining work](docs/design-aim.md) defines purpose completeness, precise vocabulary, human readability and low-cost model delegation, distinguishing requirements from current capabilities.

- [Argument model and subarguments](docs/argument-model.md): chosen semantics and relation to Toulmin and structured argumentation.
- [Language reference](docs/language.md): declarations, scope, time, predicates and diagnostics.
- [Precise vocabulary](docs/vocabulary.md) and [typed propositions](docs/typed-propositions.md): formal queries, unit checks and result correspondence.
- [Engineering tasks](docs/engineering-tasks.md): known-answer cases, adverse variants and remaining coverage gaps.
- [Historical live model experiments](docs/live-model-results.md): original API comparisons, retained failures, token usage and cost estimates from earlier EAL versions.
- [EAL/2 regression experiments](docs/eal2-model-results.md): live model/host measurements for package 2.1.0 on 23 September 2026, using previously exposed tasks.
- [EAL/2 with a finite-state checker](docs/eal2-companion-investigation.md): a versioned argument, installed method, independent graph oracle and complete synthetic experiment, including an observation-authentication counterexample.
- [Why supplied arguments and evidence fail](docs/eal2-evidence-failure-analysis.md): a verified reanalysis of 180 retained model calls, five EAL/2 perturbation pairs, an executable bounded argument and a new discriminating investigation protocol.
- [Negative findings and revision](docs/eal2-negative-revision-results.md): a registered sampled-finding method, explicit EAL/2 objections, 20 deterministic status transitions, research synthesis and a staged prospective pilot.
- [Deployment research](docs/eal2-deployment-research.md): candidate EAL workflows, competing explanations and the evidence needed to choose a model, skill or tool route.
- [Artifact handoff live pilot](docs/eal2-artifact-live-pilot.md): four new synthetic roots, twelve checked states, a frozen 48-request model plan, offline preflight and the explicit limits of its EAL/JSON comparison.
- [Amortisation model](docs/eal2-amortisation.md): a bounded decision model for repeated use, source-review costs and compact recipient assessments.
- [Skill arm](docs/eal2-skill-arm.md): a scoped instruction experiment and its relationship to the checked artifact route.
- [Prospective deployment protocol](benchmarks/protocols/INV-EAL-DEPLOYMENT-001.json): the comparison needed to measure EAL-specific effects and cost on new tasks.
- [Historical EAL/0.3 repeated experiments](docs/eal03-model-results.md): original model/interface conditions and development ablations.
- [Reasoning methods](docs/reasoning-modes.md): distinct evidence schemas, algorithms and interpretation limits.
- [Grounded argumentation](docs/grounded-reasoning.md): counterargument, defence and undecided cycles.
- [Implementation architecture](docs/implementation.md): Parr’s patterns, ANTLR4 and extension points.
- [MCP and tool execution](docs/mcp-and-tools.md): host configuration, protocol, persistence and text-model integration.
- [Primary sources](docs/sources.md).
- [Reusable skill](skills/engineer-argumentation-languages/SKILL.md): the maintained contributor guidance, including expert language-design references and the project’s EAL/2 rules.

`CONTRACT.md` records the implementation interface shared by the parser, interpreter and runtime. The interpreter evaluates authored finite support graphs and explicit argument graphs. It does not automatically discover causal structure, prove arbitrary prose, infer unlisted hypotheses, model continuous behaviour from isolated samples, or authenticate the physical provenance of observations from digests alone. Typed correspondence narrows what is checked; it does not establish general engineering completeness. The [EAL/2 regression report](docs/eal2-model-results.md) measures selected model/host systems on previously exposed tasks. Human comprehension and generalisation to unseen tasks remain unmeasured. The exposed-task notation diagnostic below now measures a bounded EAL/JSON comparison. Historical experiments retain their original versions and results.

### Model sequences and evidence transfer

See [model sequence experiments](docs/model-relay-experiments.md) for reproducible small-to-full, full-to-small, reasoning/tool and three-stage comparisons, with saved evidence hand-offs, common endpoint scoring and resumable checkpoints.

The [sequence results](docs/eal2-relay-results.md) cover all 324 planned comparison endpoints across twelve complete blocks, with 323 finished answers. Evidence transfer is correct in 12/12 cases versus 8/12 for answer-only transfer; the descriptive task-cluster interval includes zero. The four contributing cohorts retain 358 attempted records and 354 finished answers, including 34 incomplete-block attempts kept separately. All failures, unknown charges and original raw records remain available. This is a six-task exposed synthetic pilot.

[What would establish an EAL reasoning advantage?](docs/general-reasoning-and-notation-argument.md) supplies an executable EAL/2 argument, an audit separating correction from preservation, and a runnable diagnostic comparing equivalent EAL/JSON inputs, raw observations and computed conclusions. It specifies the independent task study needed for broader engineering transfer. The historical primary contrast contains no initially wrong producer answers; its correction rate is unestimated. The [completed 180-call diagnostic](docs/notation-transfer-live-results.md) measured raw-only correctness of 4/10 for EAL and 5/10 for equivalent JSON. Incorrect proposals plus raw observations were corrected in 2/10 and 5/10 cases; adding interpreter conclusions yielded 7/10 and 8/10. All failures and raw records are retained. This supplies bounded correction observations but establishes neither an EAL notation advantage nor general engineering reasoning ability. Estimated model cost was USD 0.0660738; the EAL grammar and core runtime are unchanged.
