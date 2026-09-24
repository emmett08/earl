# EAL/2 integration contract

EAL/2 is an engineering reasoning language with explicit claims, evidence, reasoning methods, assumptions, subarguments and objections. It is the only supported source language. Backwards compatibility is never a project requirement. Its finite authored support/attack semantics are defined in [argument-model.md](docs/argument-model.md) and [grounded-reasoning.md](docs/grounded-reasoning.md); they do not implement the complete ASPIC+ framework.

## Source and Python API

- `eal.parser.parse(source: str) -> Program` raises `EALSyntaxError` on lexical or syntactic errors. Source starts with `language "EAL/2";`.
- `eal.semantics.validate(program, *, registry=None) -> list[Diagnostic]` performs static checks. Any diagnostic prevents assessment. `Diagnostic` has `code`, `message`, optional `declaration`, optional `span`, and optional `expected`/`actual` descriptions. `SourceSpan` positions are one-based, with an exclusive end: `line`, `column`, `end_line`, `end_column`.
- `eal.evaluator.evaluate(program, records, *, now, context, registry=None) -> dict` takes explicit observations, context and a timezone-aware ISO-8601 time or `datetime`. Assessment performs no implicit collection and supplies no implicit clock. The default registry provides built-in methods.
- `canonical_digest(value)` is SHA-256 of UTF-8 canonical JSON: sorted keys, compact separators, no NaN. `environment_fingerprint(name, context)` hashes `{"environment": name, "context": context}`. `Program.source_digest` hashes the exact UTF-8 source bytes.

`Program` retains declaration maps for environments, tools, evidence, assumptions, reasoning, claims, arguments, objections, patterns and applications. `locations` retains source spans and `lowering_diagnostics` retains pattern-expansion errors. A `Reasoning` has one required `.method: str`. Tool `.mode` remains `deterministic` or `nondeterministic` and describes collection variability.

## Complete source example

```eal
language "EAL/2";
environment lab { require "site" == "bench"; }
tool test_runner { version "1.0"; mode deterministic; }
evidence test_result {
  tool test_runner; kind test; environment lab; max_age 3600;
  input {"suite": "smoke"};
  require "passed" == true;
}
assumption configured {
  statement "The measured configuration applies to the stated environment.";
  environment lab; validate test_result;
  valid_from "2026-01-01T00:00:00Z";
  valid_until "2027-01-01T00:00:00Z";
}
reasoning measured_support {
  method "structured/1";
  rationale "A passing result supplies bounded support for this claim.";
}
claim works {
  statement "The component passes the smoke suite at this configuration.";
  environment lab;
}
pattern measured(c: claim, r: reasoning, e: evidence, a: assumption) {
  conclusion c; reasoning r;
  evidence e; assumptions a;
}
apply measurement = measured(c=works, r=measured_support, e=test_result, a=configured);
```

Pattern bodies contain one argument's clauses and reference only their typed parameters. Parameter kinds are `claim`, `reasoning`, `evidence` and `assumption`. Named application bindings must cover exactly those parameters and resolve to declarations of the required kinds. An application produces one ordinary argument under its own name, with `.origin` identifying the pattern and application. It retains the supplied evidence, assumption and claim identities. No recursion, nested applications, implicit global capture or assumption discharge is defined. Applications undergo the same checks and evaluation as directly written arguments.

All top-level declarations share a namespace; pattern parameters have closed lexical scope. Lists use comma-separated identifiers. An argument needs at least one evidence, assumption or premise source. An objection needs at least one evidence or premise source. Environments and evidence need at least one predicate; evidence `input` defaults to `{}`. Source is limited to 1 MiB, expanded declaration/body records to 4096, applications to 1000, total expanded references to 100000 and ordinary premise depth to 128. The declaration bound counts each source declaration, each pattern body and each generated argument. Ordinary claim-premise cycles are rejected. Finite attack and objection-support cycles can remain undecided.

## Typed methods and propositions

A reasoning declaration has the form `reasoning NAME { method "IDENTIFIER/VERSION"; rationale STRING; ... }`, optionally followed by `backing` evidence and `require` output predicates. Every method, including `structured/1`, is selected by its exact installed versioned identifier. Reasoning `mode` and unversioned aliases are rejected.

Built-in contracts are `structured/1`, `deductive/1`, `inductive/1`, `abductive/1`, `causal/1`, `counterfactual/1`, `analogical/1` and `temporal/1`. The corresponding computational evidence kinds are `logical_case`, `sample`, `hypotheses`, `experiment`, `causal_model`, `analogy` and `trace`; structured support has no designated kind. Each computation receives the union of direct evidence, backing and assumption-validation observations, deduplicated by evidence identity. Exactly one designated computational input is required. Premise claims remain explicit graph dependencies, not implicit mathematical inputs.

Built-in and installed methods follow the same typed contract and binding rules, including runtime schema and byte-limit checks on computational inputs and outputs. `MethodContract` specifies input, formal-query and output schemas, output interpretation, admitted quantities, units, implementation identity and resource bounds. Query fields must be required input fields with identical schemas. `MethodRegistry.with_method(contract)` returns a new registry and cannot replace an installed identifier. Source can select host-installed code but cannot import or configure it. Pass `registry=` to validation, evaluation, formatting and discovery; pass `method_registry=` to `ReasoningService`. CLI, host and MCP accept `--methods package.module:function`. See [method-extensions.md](docs/method-extensions.md).

A claim may contain a scalar `proposition`. Every argument for that claim needs an explicit `binding` to its designated computational evidence. The interpreter checks subject, quantity, units, scope, whole interval containment, exact formal query and output predicate. A typed proposition supplies its result criterion; untyped computational conclusions require reasoning output predicates. `structured/1` can omit them. Claim statements and rationales remain authored prose. See [typed-propositions.md](docs/typed-propositions.md).

Predicates compare scalar fields with `== != < <= > >=`. Ordered comparisons require finite numeric operands or strings of equal type; booleans never equal numbers. Missing fields and incompatible types fail. JSON keys are unique strings. No general-purpose source evaluation is used.

## Evidence record and time

```json
{
  "evidence_id": "test_result",
  "source_digest": "<exact source digest>",
  "tool": "test_runner",
  "evidence_kind": "test",
  "tool_version": "1.0",
  "mode": "deterministic",
  "environment": "lab",
  "environment_fingerprint": "<environment and context digest>",
  "collected_at": "2026-09-23T12:00:00Z",
  "run_id": "<nonempty invocation identifier>",
  "input_digest": "<canonical input digest>",
  "status": "ok",
  "value": {"passed": true},
  "data_digest": "<canonical value digest>"
}
```

Records are observations, not conclusions. Errors use `status: "error"`. Missing, stale, future-dated, malformed, wrong-source, wrong-tool, wrong-input, wrong-environment or digest-mismatched records provide no support. Digests bind supplied records to requests but do not authenticate an untrusted producer. Imported observations retain their original `collected_at`; `ingested_at` records storage time.

File-import envelopes require `observed_at`, `context`, `value` and an acquisition `request` containing exactly `tool`, `tool_version`, `mode`, `input` and `context`. That request must match the current acquisition; it is distinct from the source and evidence identifiers assigned by collection. Missing or mismatched acquisition metadata produces a stored error. The current envelope has no compatibility fallback. See [MCP and tools](docs/mcp-and-tools.md).

Evidence is age-eligible at exactly `max_age`, but not when older. Assumption intervals are half-open `[valid_from, valid_until)` and are checked at assessment time. Every argument dependency uses its conclusion's named environment. Freshness, fingerprints and asserted intervals do not establish continuous physical validity.

## Assessment and acceptance

Assessment returns `language`, `source_digest`, `assessed_at`, `context_fingerprint`, `valid`, `diagnostics`, named environment/evidence/assumption/reasoning/objection/argument/claim results, the constructed `dialectic` graph and `method_registry_fingerprint`. Named results retain statuses, explanatory reasons and dependencies. Arguments expose `reasoning_result`; typed arguments also expose correspondence checks.

Claims and arguments report `supported`, `contested`, `unsupported` or `out_of_scope`, with a separate `grounded_label`. A locally usable accepted derivation is supported; a locally usable rejected or undecided derivation is contested. A claim without a usable derivation is unsupported. An independent accepted alternative can preserve support. Objections report `active`, `defeated`, `undecided` or `inactive`.

`solve_composed(nodes, claims, attacks)` applies the finite support/attack equations: an applicable node needs every premise claim accepted and every attacker rejected; a claim needs one accepted derivation. Local failure, a rejected required premise or an accepted attacker rejects a node. All labels begin undecided and grow monotonically to the least-information fixed point. Rejection never establishes falsity. Bounds are 4096 nodes, 4096 claims and 131072 combined attack, premise and derivation relationships. The result includes a replayable trace.

## Formatting, discovery and host integration

`format_source(source)` parses, validates and emits canonical source; `format_program(program)` emits checked IR. `semantic_ir(program)` excludes source digests and locations for round-trip comparisons. Formatting preserves declarations and applications. Exact source identity remains distinct from meaning: changed source bytes require recollecting observations.

`ReasoningService.describe()` returns language syntax, executable examples and method/binding contracts. `format(source)` returns canonical `source`, `source_digest` and `observation_recollection_required`. MCP exposes `eal_describe`, `eal_format`, `eal_validate`, `eal_collect`, `eal_reason`, `eal_explain` and `eal_grounded` through the shared service.

`AuthoringSession` supplies that configured reference to an authoring callback, validates complete EAL/2 drafts, and retains bounded repair diagnostics. Acceptance means valid syntax, semantics, at least one claim and argument, and presence of requested claim identifiers. Its `fidelity_unverified` flag remains true: an independent reviewer must compare the source, scope, evidence and warrant to the engineering question before registering an artefact.

An optional `ArtifactRegistry` pins exact source bytes, installed method fingerprint, context and claims. `FamilyRegistry` maps finite typed bindings to reviewed artefact cases. `CandidateIndex` offers lexical family suggestions, optionally augmented by reviewed aliases. Suggestions cannot authorise an assessment. For a model-facing recipient route, `TaskApplicabilityRegistry` binds one exact question to a reviewed family case and claim. The trusted launcher supplies the original question, principal and grants; the model can nominate only a task ID. `TaskFamilyHost.assess_task` checks applicability and grants before collecting the target claim's transitive evidence, premise, argument, objection and defence closure. Required collection failures or unusable records refuse issuance. The host persists the principal, task review and packet identity and rechecks them in `finish_task` and `explain_task`; recipient wording cannot change the status. A reviewed recipient MCP endpoint exposes only candidate, assess, explain and finish task tools. This exact-question contract does not infer coverage for paraphrases or unseen tasks. See [task applicability](docs/eal2-task-applicability.md) and [MCP and tools](docs/mcp-and-tools.md).

Stateful `run_agent` retains active source, context, time and current collection/assessment. Validation adopts a revised draft only when valid; revision invalidates earlier observations and results. `assess` performs four separately recorded and budgeted calls: validation, fresh collection, reasoning and explanation. `host_mode="stateless"` uses explicit full-source/full-identifier requests for controlled comparisons. `interaction_mode="text"` and `"native"` share operation semantics; native transport requires a configured capable provider. One-shot `eal-host` remains stateless.

A finished host interaction is separate from a correct engineering answer. See [model-loop.md](docs/model-loop.md) and [model-evaluation.md](docs/model-evaluation.md). The [23 September 2026 regression report](docs/eal2-model-results.md) measures EAL/2 package 2.1.0 with selected models and hosts on previously exposed tasks. Human comprehension, generalisation to unseen tasks and the effect of EAL notation remain unmeasured. Historical reports retain their original versions and measurements.
