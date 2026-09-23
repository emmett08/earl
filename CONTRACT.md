# EAL 0.1 integration contract

EAL is an evidence-based engineering reasoning language: Toulmin-inspired explicit reasoning rationales, backing, premises and objections. It is neither governance nor an approval language. The initial semantics are a bounded, acyclic defeasible argument profile, not full ASPIC+.

## Python API

- `from eal.parser import parse, EALSyntaxError`; `parse(source: str) -> Program`.
- `from eal.semantics import validate`; `validate(program: Program) -> list[Diagnostic]`. A diagnostic has `code`, `message`, and `declaration` (optional). Any diagnostic prevents assessment.
- `from eal.evaluator import evaluate, canonical_digest, environment_fingerprint`; `evaluate(program, records: Mapping[str, Mapping], *, now: datetime | str, context: Mapping[str, JSON]) -> dict`. `now` must be timezone-aware UTC-compatible ISO-8601. The evaluator has no IO or implicit clock. `canonical_digest(value)` is SHA-256 of UTF-8 canonical JSON (sorted keys, compact separators, no NaN). `environment_fingerprint(name, context)` hashes `{"environment": name, "context": context}`.
- `Program.source_digest` is SHA-256 of the exact UTF-8 source. Maps: `environments`, `tools`, `evidence`, `assumptions`, `reasoning`, `claims`, `arguments`, `objections`. Declarations have `.name`. `Tool.version`, `.mode`; `Evidence.tool`, `.kind`, `.environment`, `.max_age` (seconds), `.input` (JSON), `.predicates` (tuple); `Environment.predicates`; `Assumption.environment`, `.validation` (evidence ID), `.valid_from`, `.valid_until`; `Reasoning.mode`, `.predicates`, `.rationale`, `.backing` (tuple of evidence IDs); `Claim.statement`, `.environment`; `Argument.conclusion`, `.reasoning`, `.evidence`, `.assumptions`, `.premises` (ID tuples); `Objection.target_kind` (`claim`, `reasoning`, `assumption`), `.target`, `.evidence` (tuple). `Predicate.path` is a dotted field name, `.operator`, `.expected` (JSON scalar).

## Grammar example

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

All declarations are top-level. Lists are comma separated IDs. Optional argument clauses: evidence, assumptions, premises (at least one source across the three). Optional reasoning backing. Optional assumption dates. Environment requires at least one predicate. Evidence requires at least one predicate. `input` is optional and defaults to `{}`. Allowed scalar comparison operators: `== != < <= > >=`; ordered comparisons require finite numeric operands or string operands of equal type; equality never equates booleans and numbers. Object keys in JSON are strings. Max source 1 MiB; max declarations 4096; premise depth 128. Duplicate symbols and dependency cycles are rejected.

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
