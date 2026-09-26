# EAL/2 integration contract

EAL/2 is an engineering reasoning language with explicit claims, evidence, reasoning methods, assumptions, subarguments and objections. It is the supported source language. Its finite authored support/attack semantics are defined in [argument-model.md](docs/argument-model.md) and [grounded-reasoning.md](docs/grounded-reasoning.md); they do not implement the complete ASPIC+ framework. A separately installed [bounded ASPIC+ method](docs/aspic-method.md) constructs and evaluates an explicit formal theory within the ordinary evidence and typed-method boundary. An opt-in compiler can instead derive a bounded ASPIC+ snapshot from checked EAL declarations and observations without changing the default EAL assessment.

## Source and Python API

- `eal.parser.parse(source: str) -> Program` raises `EALSyntaxError` on lexical or syntactic errors. Source starts with `language "EAL/2";`.
- `eal.semantics.validate(program, *, registry=None) -> list[Diagnostic]` performs static checks. Any diagnostic prevents assessment. `Diagnostic` has `code`, `message`, optional `declaration`, optional `span`, and optional `expected`/`actual` descriptions. `SourceSpan` positions are one-based, with an exclusive end: `line`, `column`, `end_line`, `end_column`.
- `eal.evaluator.evaluate(program, records, *, now, context, registry=None, binding_digests=None) -> dict` takes explicit observations, context and a timezone-aware ISO-8601 time or `datetime`. Assessment performs no implicit collection and supplies no implicit clock. The default registry provides built-in methods. Passing current evidence-ID-to-binding digests checks the selected operator configuration; without them, pure evaluation checks only the supplied record's internal identity fields. `ReasoningService.reason` supplies the current mapping.
- `canonical_digest(value)` is SHA-256 of UTF-8 canonical JSON: sorted keys, compact separators, no NaN. `environment_fingerprint(name, context)` hashes `{"environment": name, "context": context}`. `Program.source_digest` hashes the exact UTF-8 source bytes.

`Program` retains declaration maps for environments, tools, evidence, assumptions, reasoning, claims, arguments, objections, patterns and applications. `locations` retains source spans and `lowering_diagnostics` retains pattern-expansion errors. A `Reasoning` has one required `.method: str`. A tool declaration has a name and required `.version: str`; EAL/2 source has no collection-variability mode.

## Complete source example

```eal
language "EAL/2";
environment lab { require "site" == "bench"; }
tool test_runner { version "1.0"; }
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

A reasoning declaration has the form `reasoning NAME { method "IDENTIFIER/VERSION"; rationale STRING; ... }`, optionally followed by `backing` evidence and `require` output predicates. Every method, including `structured/1`, is selected by its exact installed versioned identifier.

Built-in contracts are `structured/1`, `deductive/1`, `inductive/1`, `abductive/1`, `causal/1`, `counterfactual/1`, `analogical/1` and `temporal/1`. The corresponding computational evidence kinds are `logical_case`, `sample`, `hypotheses`, `experiment`, `causal_model`, `analogy` and `trace`; structured support has no designated kind. Each computation receives the union of direct evidence, backing and assumption-validation observations, deduplicated by evidence identity. Exactly one designated computational input is required. Premise claims remain explicit graph dependencies, not implicit mathematical inputs.

Built-in and installed methods follow the same typed contract and binding rules, including runtime schema and byte-limit checks on computational inputs and outputs. `MethodContract` specifies input, formal-query and output schemas, output interpretation, admitted quantities, units, implementation identity and resource bounds. Query fields must be required input fields with identical schemas. `MethodRegistry.with_method(contract)` returns a new registry and cannot replace an installed identifier. Source can select host-installed code but cannot import or configure it. Pass `registry=` to validation, evaluation, formatting and discovery; pass `method_registry=` to `ReasoningService`. CLI, host and MCP accept `--methods package.module:function`. See [reasoning methods and extensions](docs/reasoning-modes.md).

`eal.aspic:aspic_registry` installs `argumentation/aspic/1` with evidence kind `aspic_theory`. A typed proposition must bind the complete formal `theory` query and may check `grounded_accepted` or `grounded_rejected`. The method returns constructed arguments, defeat witnesses and grounded labels under its stated finite restrictions; it neither interprets prose nor certifies the theory's applicability. In `eal-adequacy/1`, each axiom and ordinary premise needs a reviewed `premise_bindings` entry to a supported EAL claim, and the accepted route must have a typed theory binding and a main result obligation. See the [method contract and example](docs/aspic-method.md).

`compile_eal_aspic(source, records, *, goal, now, context, registry=None, binding_digests=None)` accepts exact EAL/2 source text and defines the separate `EAL/2-compiled-aspic/1` profile. It validates and assesses EAL/2 at the supplied observation snapshot, emits available evidence as ordinary formal premises, locally usable arguments and applicable assumptions as equally ranked defeasible rules, and targeted objections as undercuts. It does not infer strict rules, premise or rule priorities, claim contraries or prose meaning. It returns `CompiledTheory`; `solve()` supplies the formal result, per-route labels, source map and formal-projected claim status, while `to_dict()` also includes the generated theory and ordinary EAL claim status. An invalid source, unknown goal, explicit `argumentation/aspic/1` source argument, or solver bound violation fails rather than silently dropping a route. `ReasoningService.compile_aspic` obtains records from a matching stored collection and checks current tool bindings. See [compilation semantics](docs/aspic-method.md#compile-authored-eal-routes).

A claim may contain a scalar `proposition`. Every argument for that claim needs an explicit `binding` to its designated computational evidence. The interpreter checks subject, quantity, units, scope, whole interval containment, exact formal query and output predicate. A typed proposition supplies its result criterion; untyped computational conclusions require reasoning output predicates. `structured/1` can omit them. Claim statements and rationales remain authored prose. See the [language reference](docs/language.md).

Predicates compare scalar fields with `== != < <= > >=`. Ordered comparisons require finite numeric operands or strings of equal type; booleans never equal numbers. Missing fields and incompatible types fail. JSON keys are unique strings. No general-purpose source evaluation is used.

## Evidence record and time

```json
{
  "evidence_id": "test_result",
  "source_digest": "<exact source digest>",
  "tool": "test_runner",
  "evidence_kind": "test",
  "tool_version": "1.0",
  "tool_binding_digest": "<keyed selected TOML binding identity>",
  "environment": "lab",
  "environment_fingerprint": "<environment and context digest>",
  "collected_at": "2026-09-23T12:00:00Z",
  "run_id": "<nonempty invocation identifier>",
  "input": {"suite": "smoke"},
  "input_digest": "<canonical input digest>",
  "context": {"site": "bench"},
  "acquisition_request": {"tool": "test_runner", "tool_version": "1.0", "input": {"suite": "smoke"}, "context": {"site": "bench"}},
  "acquisition_request_digest": "<canonical acquisition request digest>",
  "request_digest": "<canonical full evidence request digest>",
  "status": "ok",
  "value": {"passed": true},
  "data_digest": "<canonical value digest>"
}
```

Records are observations, not conclusions. Errors use `status: "error"`. Missing, stale, future-dated, malformed, wrong-source, wrong-tool, wrong-input, wrong-environment or digest-mismatched records provide no support. Digests bind supplied records to requests but do not authenticate an untrusted producer. Imported observations retain their original `collected_at`; `ingested_at` records storage time.

File-import envelopes require `observed_at`, `context`, `value` and an acquisition `request` containing exactly `tool`, `tool_version`, `input` and `context`. That request must match the current acquisition; it is distinct from the source and evidence identifiers assigned by collection. The trusted collector adds `tool_binding_digest`, a keyed identity of the selected TOML configuration, to its record. Pure evaluation checks that identity field; the host additionally compares it with its current binding before reasoning over a collection. The private store-local `<database>.binding-key` file must remain private and accompany the database when moving it for continued assessment; a missing key gives a new identity and invalidates older observations. Missing or mismatched acquisition metadata produces a stored error. See [MCP and tools](docs/mcp-and-tools.md).

Evidence is age-eligible at exactly `max_age`, but not when older. Assumption intervals are half-open `[valid_from, valid_until)` and are checked at assessment time. Every argument dependency uses its conclusion's named environment. Freshness, fingerprints and asserted intervals do not establish continuous physical validity.

## Assessment and acceptance

Assessment returns `language`, `source_digest`, `assessed_at`, `context_fingerprint`, `valid`, `diagnostics`, named environment/evidence/assumption/reasoning/objection/argument/claim results, the constructed `dialectic` graph and `method_registry_fingerprint`. Named results retain statuses, explanatory reasons and dependencies. Arguments expose `reasoning_result`; typed arguments also expose correspondence checks.

Claims and arguments report `supported`, `contested`, `unsupported` or `out_of_scope`, with a separate `grounded_label`. A locally usable accepted derivation is supported; a locally usable rejected or undecided derivation is contested. A claim without a usable derivation is unsupported. An independent accepted alternative can preserve support. Objections report `active`, `defeated`, `undecided` or `inactive`.

`solve_composed(nodes, claims, attacks)` applies the finite support/attack equations: an applicable node needs every premise claim accepted and every attacker rejected; a claim needs one accepted derivation. Local failure, a rejected required premise or an accepted attacker rejects a node. All labels begin undecided and grow monotonically to the least-information fixed point. Rejection never establishes falsity. Bounds are 4096 nodes, 4096 claims and 131072 combined attack, premise and derivation relationships. The result includes a replayable trace.

## Formatting, discovery and host integration

`format_source(source)` parses, validates and emits canonical source; `format_program(program)` emits canonical source from checked IR. `semantic_ir(program)` excludes source digests and locations for round-trip comparisons. Formatting preserves declarations and applications. Exact source identity remains distinct from meaning: changed source bytes require recollecting observations.

`ReasoningService.describe()` returns language syntax, executable examples, method/binding contracts and opt-in compiler metadata. `format(source)` returns canonical `source`, `source_digest` and `observation_recollection_required`. MCP exposes `eal_describe`, `eal_format`, `eal_validate`, `eal_collect`, `eal_reason`, `eal_compile_aspic`, `eal_explain` and `eal_grounded` through the shared service. The CLI provides `compile-aspic SOURCE --context JSON --collection COLLECTION_ID --goal CLAIM [--now TIME]`; compilation requires the same source bytes and context as the stored collection and does not overwrite an ordinary `reason` assessment.

`AuthoringSession` supplies that configured reference to an authoring callback, validates complete EAL/2 drafts, and retains bounded repair diagnostics. Acceptance means valid syntax, semantics, at least one claim and argument, and presence of requested claim identifiers. Its `fidelity_unverified` flag remains true: an independent reviewer must compare the source, scope, evidence and warrant to the engineering question before registering an artefact.

An optional `ArtifactRegistry` pins exact source bytes, installed method fingerprint, context and claims. `FamilyRegistry` maps finite typed bindings to reviewed artefact cases. `CandidateIndex` offers lexical family suggestions, optionally augmented by reviewed aliases or a reviewed-snippet RAG index. Suggestions cannot authorise an assessment. For a model-facing recipient route, `TaskApplicabilityRegistry` binds one exact question to a reviewed family case and claim. The trusted launcher supplies the original question, principal and grants; the recipient discovers the unique bound task without submitting an ID. `TaskFamilyHost.assess_bound_task` checks applicability and grants before collecting the target claim's transitive evidence, premise, argument, objection and defence closure. Required collection failures or unusable records refuse issuance. The host persists the principal, task review and packet identity and rechecks them in `finish_bound_task` and `explain_bound_task`; recipient wording cannot change the status. A reviewed recipient MCP endpoint exposes only bound discovery, candidate suggestions, assessment, explanation and finalisation. The bounded recipient model loop separates the host's checked packet from unverified prose; a Responses provider may replay private reasoning items through an opaque per-output handle. This exact-question contract does not infer coverage for paraphrases or unseen tasks. See [MCP and tools](docs/mcp-and-tools.md).

Stateful `run_agent` retains active source, context, time and current collection/assessment. Validation adopts a revised draft only when valid; revision invalidates earlier observations and results. `assess` performs four separately recorded and budgeted calls: validation, fresh collection, reasoning and explanation. `host_mode="stateless"` uses explicit full-source/full-identifier requests for controlled comparisons. `interaction_mode="text"` and `"native"` share operation semantics; native transport requires a configured capable provider. One-shot `eal-host` remains stateless.

A finished host interaction is separate from a correct engineering answer. See [MCP and tools](docs/mcp-and-tools.md) and the [API load-test example](examples/api-load-test/README.md). Human comprehension, generalisation to unseen tasks and the effect of EAL notation remain unmeasured.

## Executable argument host

The source language is `EAL/2`; authored tools declare an interface version, while acquisition records identify the selected host binding. Formal reasoning-method inputs use `EAL/typed-input/1`. The argument host separately uses the `eal2-argument-schemes/1` catalogue, `eal-adequacy/1` contract, `eal-adequacy-result/1` and `eal2-argument-answer/1` packet. The host does not reinterpret a pure `evaluate` result or its `supported` label as evidence sufficiency.

`ArgumentHost.load(service, schemes_toml, *, principal, session_id, authorised_schemes=None, recogniser=None, correspondence_validator=None)` checks each workspace-relative source's exact SHA-256 and the installed method-registry fingerprint. A scheme fixes an EAL claim, `claim`/`decision`/`action` kind, reviewed prose forms, optional follow-up forms, typed slot-to-context bindings and adequacy clauses. Slot substitution changes complete EAL string tokens only; it must leave tool and method selectors unchanged, and the instantiated claim environment must constrain each slot. All tool executables remain in the separate trusted registry.

`resolve(prose, context=None, proposal=None, *, routing_candidate=None)` returns `resolved`, `unresolved` or `ambiguous` without collection. `describe()` exposes each granted scheme's argument form, including conclusion, premise IDs, inference methods, evidence roles/tools, assumptions, objections and adequacy clauses. The built-in recogniser checks reviewed full-string forms; an installed `ArgumentRecogniser` can propose roles, typed bindings and spans. A candidate proposal alone never establishes applicability: an independently installed `CorrespondenceValidator` must approve its mapping; otherwise it stays unresolved. An unmatched later request clears the active interpretation. Follow-up forms can inherit a scheme and validated context within the same principal/session, but never an earlier assessment's support. The model-facing recipient MCP route binds the original prose at launch and exposes only `eal_resolve_bound_prose()`, `eal_assess_bound_prose()` and `eal_finish_prose(assessment_id)` under explicit scheme grants; the operator route exposes `eal_resolve_prose`, `eal_assess_prose` and `eal_finish_prose`.

`assess` checks the scheme and adequacy contract before collection, collects the target claim's transitive evidence and objection closure, reasons over the stored collection, assesses its adequacy, and returns the immutable checked packet with source, context, prose, proposal, template, method-registry and collection identities. `raw_status` is the EAL claim result. The packet can say `supported` only when the required collection is complete and independent adequacy is `adequate`; otherwise the answer status is `unresolved`. `finish(assessment_id)` requires issuance to the same principal/session and current request, checks exact source, current tool-binding configuration and contract identity, and re-evaluates observation/assumption validity at the current time without converting the original assessment into a new one. A stale or superseded packet is refused; reassessment recollects.

`AdequacyContract` fixes the exact instantiated source digest, claim ID, written statement, environment, admitted method identifiers, `reviewed_source` correspondence assertion and finite `EvidenceObligation` clauses. Each clause names a role (`identity`, `scope`, `coverage`, `sampling`, `threshold`, `inference`, `assumption` or `objection`), an EAL observation/result/context target, a dotted scalar field and comparison, plus the reviewer rationale. `AdequacyEvaluator.assess` verifies collection and assessment identities, observed fields, the supported derivation, a main threshold or inference clause, and coverage of used evidence and material assumptions/objections. Clauses concerning assumptions or objections use `about = "assumption:<id>"` or `"objection:<id>"` and must connect to their own sources. Formal deductive premises and the optional ASPIC+ theory's axioms and ordinary premises require explicit `premise_bindings` to supported named EAL claims. Results are `adequate`, `insufficient` or `unresolved` with per-obligation findings. Absence of a contract is unresolved. The reviewed source-correspondence assertion and clause selection are human responsibilities; this contract does not prove arbitrary natural-language equivalence, physical authenticity or completeness of all possible objections.

`ActionGate` confines an action to one existing regular file identified by `ActionScope`. `GuardedFileChange` binds the original prose, exact proposed bytes and expected file hash. `preflight` stages the proposal, runs a host-pinned `ChangeValidator`, obtains a separately checked action-kind argument packet with adequate evidence and matching proposal/source/context, and returns `PreparedAction`. `commit` rechecks the baseline, scope, validator result, context and issued assessment before atomic replacement. `StagedCommandValidator(checks, *, copy_paths=(), max_input_bytes=..., pinned_host_files=...)` runs versioned `StagedCheckCommand` argument vectors on a temporary staged copy and selected project inputs. Every absolute argv file, including interpreters and script inputs, must appear in `pinned_host_files` as `(absolute_path, sha256_of_current_bytes)`; their content is rechecked on each validation, and the settings are immutable and part of `contract_digest`. Those commands run with host privileges, not in an OS sandbox. The gate cannot control other writers, certify unexamined design constraints, or make several file replacements atomic. See [executable argument host](docs/executable-argument-host.md).
