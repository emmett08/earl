# EAL language reference

A source starts with `language "EAL/2";` and ends at EOF. Other language headers are rejected. Declarations are top-level and case-sensitive. Clauses end with semicolons and appear in the order specified by [the grammar](../grammar/EAL.g4). Identifiers use letters, digits and underscores, starting with a letter or underscore. Global declarations share one namespace; pattern parameters have a closed local namespace. Forward global references are allowed. Duplicate symbols are rejected. `//` and `/* ... */` comments are supported.

## Declarations

| Declaration | Required clauses in order | Optional clauses after the required clauses |
|---|---|---|
| `environment NAME` | One or more `require` predicates over context | — |
| `tool NAME` | `version` string; `mode deterministic` or `mode nondeterministic` | — |
| `evidence NAME` | `tool` name; `kind` identifier; `environment` name; `max_age` seconds; then one or more `require` predicates over observed value | `input` JSON value may appear between `max_age` and the predicates |
| `assumption NAME` | `statement` string; `environment` name; `validate` evidence name | `valid_from` timestamp; `valid_until` timestamp |
| `reasoning NAME` | `method` versioned string; `rationale` string | `backing` evidence names; `require` predicates over computed method outputs |
| `claim NAME` | `statement` string; `environment` name | `proposition` block |
| `argument NAME` | `conclusion` claim name; `reasoning` name | `evidence` names; `assumptions` names; `premises` claim names; `binding` evidence name |
| `objection NAME` | `target` category and name | `evidence` names; `premises` claim names; at least one source required |
| `pattern NAME(...)` | Typed parameters and an argument body | Body uses only its parameters |
| `apply NAME = PATTERN(...)` | Named bindings from every pattern parameter to a global declaration | Ends with a semicolon |

The [typed proposition reference](typed-propositions.md) defines the proposition block, its formal `query`, permitted result predicates, unit conversions and exact input correspondence. Every argument for a typed claim needs an explicit binding. A successful scalar calculation cannot silently support a different quantity or formal query. See [the vocabulary](vocabulary.md) for keyword distinctions and [the task suite](engineering-tasks.md) for positive and adverse examples.

Name lists use commas. An argument requires at least one evidence, assumption or premise. An untyped computational conclusion requires at least one reasoning output predicate; a typed conclusion supplies its formal result condition. `structured/1` reasoning can omit result predicates. Available methods and typed evidence schemas are defined in [reasoning methods](reasoning-modes.md).

The current profile requires an argument’s conclusion, evidence, assumptions, premise claims and reasoning backing to use the same named environment. An explicit comparison model can represent observations from several conditions within that environment; implicit transfer between differently scoped claims is rejected. The engineer defines which context fields adequately represent the question.

## Reusable argument patterns

```eal
pattern check(c: claim, r: reasoning, e: evidence) {
  conclusion c;
  reasoning r;
  evidence e;
  binding e;
}
apply pressure_check = check(c=pressure, r=contrast, e=trial);
```

This fragment assumes the three global declarations already exist. Parameter kinds are `claim`, `reasoning`, `evidence` and `assumption`. The body uses ordinary argument clauses, with `conclusion` and `reasoning` required. Every body reference must name a declared parameter of the required kind; a global name cannot be captured implicitly. Each application supplies exactly the declared named bindings. A body requires at least one evidence, assumption or premise source. Invalid definitions are diagnosed even when unused.

An application expands to one argument named by its `apply` declaration. That name can be an objection target. Expansion substitutes declaration identities; it does not copy observations, discharge assumptions or broaden an environment or time interval. The expanded argument undergoes the same checks as a directly written argument, including typed proposition binding. Multiple applications using the same evidence still use one identified observation.

Patterns cannot contain declarations or other applications. Applications are flat and nonrecursive, with at most 1,000 applications and 100,000 total expanded references per source. Forward references are allowed. [The reusable measurement example](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/examples/reusable-measurements.eal) shows shared evidence in complete source. [The design record](eal2-design.md) explains why this bounded derived form was selected.

## Predicates and numbers

```eal
require "instrument.maximum_error_ms" <= 1;
require "algorithm" == "sha256";
require "entailed" == true;
```

Paths select fields of JSON objects using dots. Predicates compare a JSON scalar with `==`, `!=`, `<`, `<=`, `>` or `>=`. Missing fields and incompatible types fail the predicate; they do not acquire default values. Booleans are distinct from numbers. Numeric integers and finite floating-point values can be compared. Ordered string comparisons are lexicographical; timestamps intended as instants should use the dedicated timestamp clauses or a temporal evidence contract, not arbitrary string order. Object and array comparisons are excluded. Conditions within an environment, evidence declaration or reasoning step are conjunctive.

Input JSON supports strings, finite numbers, booleans, null, arrays and objects with unique string keys. There is no executable code evaluation. Floating-point arithmetic is used for numerical methods; those methods document their statistical and numerical limits.

## Claims and subarguments

```eal
argument explanation {
  conclusion diagnosis;
  reasoning compare_explanations;
  evidence joint_likelihoods;
  assumptions hypothesis_model;
  premises frequency_estimate, intervention_result, model_applicability;
}
```

This fragment makes three claims into required subarguments. Each can have further premises, its own reasoning method and more than one supporting argument. A claim is supported when at least one uncontested usable argument supports it and there is no active claim-level objection. A reusable subclaim is evaluated once per assessment and retains its identifier; its repeated use does not create independent evidence. Declared evidence is deduplicated by identifier before a reasoning computation, including reasoning backing and assumption-validation observations.

The graph of conclusion-to-premise dependencies is acyclic, even if a cycle contains an alternative grounded argument. The current language rejects such cycles as a whole. Maximum source size is 1 MiB, maximum expanded declaration/body count 4096 and maximum premise depth 128. The declaration bound counts source declarations, pattern bodies and generated arguments. EAL/2 permits cycles involving attacks and objection support. Its finite support/attack solver retains unresolved cycles as undecided; the acyclic constraint still applies to ordinary argument-to-premise composition.

## Time and assumptions

`max_age` is a finite nonnegative number of seconds. At evaluation time `now`, an observation is age-eligible if `0 <= now - collected_at <= max_age`. A future observation is unusable. Imported evidence retains its original observation timestamp. The runtime’s record field `collected_at` denotes that observation time; `ingested_at` records storage time.

`valid_from` and `valid_until` are timezone-aware ISO-8601 timestamps. The assumption interval is inclusive at the start and exclusive at the end. The current evaluator tests the interval at the assessment time, then requires usable validation evidence. To reproduce a historical assessment, supply its historical time and context; a current assessment does not silently substitute the observation time for `now`.

An expired assumption prevents dependent current conclusions from retaining support. Its expiry does not make historical observations false. The declared interval and freshness limit also do not prove continuous physical validity; use appropriate monitoring evidence and a temporal method where that relation is needed.

## Objections and results

```eal
objection sampling_problem {
  target reasoning extrapolate_sample;
  evidence dependence_observation;
}
```

Objections can target a claim, reasoning declaration, assumption, argument application or another objection. Their own evidence and required premise claims determine applicability and acceptance.

`target argument NAME` challenges one application; `target objection NAME` supplies a defence. Claim premises can support either form:

```eal
objection sampling_problem {
  target argument lifetime_estimate;
  premises dependent_samples;
}
objection measured_defence {
  target objection sampling_problem;
  evidence independence_measurement;
  premises validation_applies;
}
```

Every listed evidence and premise is required. A premise claim can have multiple arguments and further subarguments. Attacking an objection uses exactly the same source and applicability requirements as the objection itself. The interpreter does not infer a contradiction or defence from prose.

The objection's evidence and premise claims must share one named environment. That source-derived scope must match a target claim, assumption, argument conclusion or objection. A reasoning target applies only to uses of that reasoning declaration in the objection's environment; a reusable method can remain usable in another declared environment.

The interpreter constructs argument-application nodes and objection nodes, then computes a finite least-information fixed point. A node is accepted when its local sources and computation are usable, every required premise claim is accepted, and every attacker is rejected. It is rejected when a local requirement fails, a required claim is rejected, or an attacker is accepted. A claim is accepted when any deriving argument is accepted, and rejected when every deriving argument is rejected. Unresolved nodes retain the label `undecided`; rejection concerns acceptance within this calculation and never establishes claim falsity. [The argument model](argument-model.md) and [grounded construction](grounded-reasoning.md) give the equations and verification.

Claim/argument results remain `supported`, `contested`, `unsupported` or `out_of_scope`. A source-usable derivation which is rejected or undecided is `contested`; a claim without any source-usable derivation is `unsupported`. Each entry exposes its separate `grounded_label`. Objection results are `active` (accepted), `defeated`, `undecided` or `inactive` (no source-usable derivation). Unavailable evidence and an unknown supporting claim therefore cannot activate an objection. An independently accepted defence can restore support to a challenged claim; a defence depending solely on the claim it is meant to restore remains unresolved.

Evidence has `available`/`unavailable`. Detailed reasons distinguish missing, expired, mismatched, failed and predicate-rejected observations even when their broad status is the same.

The result’s `valid` field reports static language validity. Each argument includes dependencies and a `reasoning_result` containing method output and predicate results. Claim text and reasoning rationale remain explanatory prose. Formal deductive inputs are supplied in `logical_case` evidence; premise claim strings are not automatically translated into those formulae, and the formula conclusion is not automatically equated with a prose claim. The author must maintain prose correspondence explicitly. Typed propositions additionally check the declared formal query, identity, dimensions, interval and result against the bound method calculation.

## Worked sources

[latency.eal](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/examples/latency.eal) demonstrates temporal assumption expiry and a subordinate claim. [mixed-reasoning.eal](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/examples/mixed-reasoning.eal) composes all seven computational methods under a diagnosis using distinct input schemas and declared modelling assumptions. Its observations and likelihoods are synthetic. [live.eal](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/examples/live.eal) executes real local deterministic and nondeterministic commands.

No arguments are automatically generated from natural-language claims. The examples show how an engineer or model can supply a precise graph that the interpreter can compute and explain.

## Versioned reasoning methods

```eal
reasoning interval_estimate {
  method "inductive/1";
  rationale "Apply the installed Wilson-interval contract to the declared sample.";
  require "lower" > 0.8;
}
```

The `method` clause selects an installed, versioned host contract. Its string must be the exact contract identifier; `method "inductive"` and reasoning `mode` clauses are rejected. Unknown methods are diagnosed even in unused reasoning declarations. The registered `structured/1` contract accepts authored support without a numerical output predicate.

A host may register another method with its evidence kind, typed input/query/output schemas, supported quantities, units and resource limits. Source cannot install executable code or change registry entries. The API accepts `registry=` in validation, evaluation and formatting; assessments record `method_registry_fingerprint`. See [method extensions](method-extensions.md) for the registration interface and execution boundaries.

The composed graph is bounded to 4096 nodes, 4096 claims and 131072 combined attack, premise and derivation relationships. Construction checks this bound before solving. The `dialectic` result records the constructed attacks and deterministic labelling trace.

## Diagnostics and source positions

Static diagnostics include `code`, `message` and optional `declaration`, `span`, `expected` and `actual` fields. A source span has one-based `line`, `column`, `end_line` and `end_column`; the end is exclusive. Parse/lowering locations let errors identify the relevant declaration or application. The internal argument origin names its pattern and application, preserving that relationship in explanations. Canonical formatting retains authored pattern/application syntax and omits the generated argument declarations.

Method output predicates use `reasoning_predicate_path` for paths excluded by a closed output schema and `reasoning_predicate_type` for incompatible operands. The diagnostic gives expected and actual types. Open JSON result fields are checked at runtime. Python callers constructing the typed IR directly receive `invalid_ir`, `declaration_identity` or the corresponding source-level diagnostic for malformed fields, names, references or JSON values. Canonical formatting rejects those objects before printing them.
