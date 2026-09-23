# EAL 0.1 / 0.2 / 0.3 integration contract

EAL is an evidence-based engineering reasoning language: Toulmin-inspired explicit reasoning rationales, backing, premises and objections. It is neither governance nor an approval language. The initial semantics are a bounded, acyclic defeasible argument profile, not full ASPIC+.

EAL/0.2 adds optional formal `proposition` declarations inside claims and explicit `binding` clauses on their arguments. The original EAL/0.1 profile remains supported; using these additions in an EAL/0.1 programme produces a version diagnostic. See [typed-propositions.md](docs/typed-propositions.md) for the normative query, quantity, unit and interval correspondence rules. Untyped claims retain their authored support meaning in either version.

EAL/0.3 adds explicit versioned `method` references, objection `premises`, and `argument`/`objection` targets. Its composed acceptance semantics are specified in [argument-model.md](docs/argument-model.md) and [grounded-reasoning.md](docs/grounded-reasoning.md). Earlier source versions retain their original objection semantics. The details below describing active evidence-only objections apply to those legacy profiles; EAL/0.3 separates source usability from grounded acceptance.

## Python API

- `from eal.parser import parse, EALSyntaxError`; `parse(source: str) -> Program`.
- `from eal.semantics import validate`; `validate(program: Program, *, registry=None) -> list[Diagnostic]`. A diagnostic has `code`, `message`, and `declaration` (optional). Any diagnostic prevents assessment. The default method registry supplies the built-in methods.
- `from eal.evaluator import evaluate, canonical_digest, environment_fingerprint`; `evaluate(program, records: Mapping[str, Mapping], *, now: datetime | str, context: Mapping[str, JSON], registry=None) -> dict`. `now` must be timezone-aware UTC-compatible ISO-8601. There is no implicit evaluation clock or collection during assessment. Custom methods execute trusted host functions in bounded workers. `canonical_digest(value)` is SHA-256 of UTF-8 canonical JSON (sorted keys, compact separators, no NaN). `environment_fingerprint(name, context)` hashes `{"environment": name, "context": context}`.
- `Program.source_digest` is SHA-256 of the exact UTF-8 source. Maps: `environments`, `tools`, `evidence`, `assumptions`, `reasoning`, `claims`, `arguments`, `objections`. Declarations have `.name`. `Tool.version`, `.mode`; `Evidence.tool`, `.kind`, `.environment`, `.max_age` (seconds), `.input` (JSON), `.predicates` (tuple); `Environment.predicates`; `Assumption.environment`, `.validation` (evidence ID), `.valid_from`, `.valid_until`; `Reasoning.mode`, `.predicates`, `.rationale`, `.backing` (tuple of evidence IDs); `Claim.statement`, `.environment`; `Argument.conclusion`, `.reasoning`, `.evidence`, `.assumptions`, `.premises` (ID tuples); `Objection.target_kind` (`claim`, `reasoning`, `assumption`), `.target`, `.evidence` (tuple). `Predicate.path` is a dotted field name, `.operator`, `.expected` (JSON scalar).

## Grammar example

This example uses the compatible EAL/0.1 subset. EAL/0.2 task sources are included in [the task corpus](benchmarks/engineering-v1).

```eal
language "EAL/0.1";
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
  mode structured;
  rationale "A passing result supplies bounded support for this claim.";
  backing test_result;
}
claim works { statement "The component passes the smoke suite at this configuration."; environment lab; }
argument measurement {
  conclusion works; reasoning measured_support;
  evidence test_result; assumptions configured;
}
```

All declarations are top-level. Lists are comma separated IDs. Optional argument clauses: evidence, assumptions, premises (at least one source across the three). Optional reasoning backing. Optional assumption dates. Environment requires at least one predicate. Evidence requires at least one predicate. `input` is optional and defaults to `{}`. Allowed scalar comparison operators: `== != < <= > >=`; ordered comparisons require finite numeric operands or string operands of equal type; equality never equates booleans and numbers. Object keys in JSON are strings. Max source 1 MiB; max declarations 4096; premise depth 128. Duplicate symbols and ordinary argument-premise dependency cycles are rejected. EAL/0.3 permits cycles involving objections; their grounded labels can remain undecided.

## Evidence record

The runtime produces this mapping for each evidence ID; records are immutable observations, not conclusions:

```json
{
  "evidence_id": "test_result",
  "source_digest": "<program.source_digest>",
  "tool": "test_runner",
  "evidence_kind": "test",
  "tool_version": "1.0",
  "mode": "deterministic",
  "environment": "lab",
  "environment_fingerprint": "<environment_fingerprint('lab', context)>",
  "collected_at": "2026-09-23T12:00:00Z",
  "run_id": "<nonempty invocation identifier>",
  "input_digest": "<canonical_digest(evidence.input)>",
  "status": "ok",
  "value": {"passed": true},
  "data_digest": "<canonical_digest(value)>"
}
```

Mode is `deterministic` or `nondeterministic`, and describes the tool, never the logical soundness of its result. Errors use `status: "error"` and cannot support arguments. Missing, stale, future-dated, malformed, wrong-program, wrong-tool, wrong-input, wrong-environment or digest-mismatched records supply no support. Record integrity fields bind an observation to a request but are not cryptographic provenance authentication; an untrusted caller can forge an entire record. Collection and access controls belong to the host.

## Assessment shape

A JSON-serialisable dict containing `language`, `source_digest`, `assessed_at`, `context_fingerprint`, `valid` (static language validity), `diagnostics` (list), `environments`, `evidence`, `assumptions`, `reasoning`, `objections`, `arguments`, `claims`. Each named entry has `status` and `reasons` (list of explanatory strings); arguments also report dependency IDs; claims report `supporting_arguments` and `contested_arguments`.

Claim statuses: `supported` (one uncontested argument; no active claim objection), `contested` (supported or contested derivation challenged by a relevant objection; no uncontested alternative), `unsupported` (no usable derivation), `out_of_scope` (environment requirements fail). Argument status: `supported`, `contested`, `unsupported`, `out_of_scope`. Active claim objections contest all its arguments; reasoning/assumption objections affect dependent arguments, preserving independent alternatives. Contested premises propagate to dependent arguments. Objections activate only when all listed evidence is available and its declared predicates hold. Each reasoning method used by an argument supplies a human-readable rationale; the evaluator checks declared relations and evidence predicates, not the truth or logical sufficiency of arbitrary prose. Unsupported does not mean false. No probability or automatic preference is invented.

## Reasoning modes

`reasoning NAME { mode MODE; rationale STRING; (backing idList;)? require* }` replaces the earlier draft's generic inference construct. Modes: `structured`, `deductive`, `inductive`, `abductive`, `causal`, `counterfactual`, `analogical`, `temporal`. Evidence has required `kind ID;` after `tool ID;`, an open identifier classified by the author. Computational modes require explicit `require` predicates over their computed `details`; structured mode permits zero predicates. Every argument exposes `reasoning_result` (status, reasons, computed details and evaluated output predicates).

Pure helper API in `eal.modes`: `validate_mode(mode, kinds) -> list[str]`; `assess_mode(mode, evidence, premises) -> dict` with `status`, `reasons`, `details`. Evidence inputs are `{id, kind, value}` for deduplicated direct evidence, method backing and assumption-validation evidence. Premises are claim assessment entries augmented with `id`. Required designated kinds: deductive `logical_case`; inductive `sample`; abductive `hypotheses`; causal `experiment`; counterfactual `causal_model`; analogical `analogy`; temporal `trace`. Structured accepts any kind. Mode computation addresses precisely its encoded mathematical relation; arbitrary prose interpretation remains authored.

Assumption intervals are half-open `[valid_from, valid_until)`. All dependencies of an argument use its conclusion's declared environment; cross-environment derivation needs an explicit new observation and argument. Environment context is supplied by the host, not independently established by fingerprinting. Evidence age is valid at exactly max_age, unavailable when older.

## Canonical source, discovery and models

`eal.formatter.format_source(source)` parses, validates and emits canonical source. `format_program(program)` emits from a checked IR. `semantic_ir(program)` provides a source-digest-independent representation for round-trip checks. Exact source identity is deliberately separate from semantic equivalence: existing observation records cannot be reused under changed source bytes.

`ReasoningService.describe()` returns packaged syntax, an executable example, mode contracts and the versioned typed binding catalogue. `ReasoningService.format(source)` returns canonical `source`, `source_digest` and `observation_recollection_required`. They are exposed as `eal_describe` and `eal_format` through MCP, `describe` and `format` through the CLI/host.

`eal-agent` adds provider-connected interaction and bounded feedback to the single-request `eal-host` interface. A finish response retrieves statuses from an assessment produced during the session; it cannot invent a checked status. Task correspondence remains separate from successful interaction, particularly for source construction or revision. See [model-loop.md](docs/model-loop.md) for APIs, budgets and retained attempts, and [model-evaluation.md](docs/model-evaluation.md) for the paired evaluation procedure. Unknown usage or expense must remain unknown rather than being reported as zero.

## EAL/0.3 extension interfaces

`Reasoning` adds `.method: str | None` and `.selector`, which returns the selected explicit method or legacy mode. Explicit `method` clauses require an installed versioned identifier. `Objection` adds `.premises: tuple[str, ...]`; its target kinds include `argument` and `objection`. An objection's evidence and premise claims are conjunctive grounds. Every objection resolves to exactly one declared environment, including through chains of attacks on objections.

`MethodRegistry.with_method(contract)` returns a new registry; existing identifiers cannot be replaced. A `MethodContract` specifies input, formal-query and output schemas, output interpretations, admitted quantities, unit policy, implementation identity and resource bounds. Source cannot configure or import a callback. See [method-extensions.md](docs/method-extensions.md) for the contract schema subset and execution conditions.

Pass `registry=` to `validate`, `evaluate`, `format_source`, `format_program` and `describe_language`; pass `method_registry=` to `ReasoningService`. CLI, host and MCP server accept the trusted operator option `--methods package.module:function`. Discovery and persisted assessments include `method_registry_fingerprint`. The fingerprint includes the declared implementation version and entry-point source digest; dependency versions and external environment still require reproducible host packaging.

`solve_composed(nodes, claims, attacks)` receives locally usable application nodes, conjunctive premise-claim references, alternative claim derivations and directed attacks. It returns accepted/rejected/undecided labels plus a replayable derivation trace. Rejection is lack of acceptance in that representation, never logical negation of the claim. EAL/0.3 assessments expose these labels alongside supported/contested/unsupported/out_of_scope results and the constructed graph.

Stateful `run_agent` retains exact active source, context, time and current collection/assessment. Operational request schemas omit host-owned source and result identifiers; unanchored source candidates are proposed through validation and adopted only when valid. Fixed context and time remain anchored. The `assess` host operation performs four separately recorded and budgeted MCP calls: validation, fresh collection, reasoning and explanation. Source revision invalidates earlier collection/assessment state. `host_mode="legacy"` retains the full-field protocol for controlled comparisons. `interaction_mode="text"` and `"native"` share host operation semantics; native transport requires an explicitly configured capable provider. This convenience belongs to the agent host: direct MCP and one-shot `eal-host` operations retain their explicit arguments.
