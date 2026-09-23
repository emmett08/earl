# EAL/0.1 and EAL/0.2 language reference

A source starts with `language "EAL/0.1";` or `language "EAL/0.2";` and ends at EOF. Declarations are top-level, case-sensitive and terminated by braces. Clauses end with semicolons and appear in the order specified by [the grammar](../grammar/EAL.g4). Identifiers use letters, digits and underscores, starting with a letter or underscore. All declarations share one symbol namespace. Forward references are allowed. Duplicate symbols are rejected. `//` and `/* ... */` comments are supported. The new EAL/0.2 words are contextual, preserving identifiers accepted by EAL/0.1.

## Declarations

| Declaration | Required clauses in order | Optional clauses after the required clauses |
|---|---|---|
| `environment NAME` | One or more `require` predicates over context | — |
| `tool NAME` | `version` string; `mode deterministic` or `mode nondeterministic` | — |
| `evidence NAME` | `tool` name; `kind` identifier; `environment` name; `max_age` seconds; then one or more `require` predicates over observed value | `input` JSON value may appear between `max_age` and the predicates |
| `assumption NAME` | `statement` string; `environment` name; `validate` evidence name | `valid_from` timestamp; `valid_until` timestamp |
| `reasoning NAME` | `mode` name; `rationale` string | `backing` evidence names; `require` predicates over computed method outputs |
| `claim NAME` | `statement` string; `environment` name | EAL/0.2: `proposition` block |
| `argument NAME` | `conclusion` claim name; `reasoning` name | `evidence` names; `assumptions` names; `premises` claim names; EAL/0.2: `binding` evidence name |
| `objection NAME` | `target claim`, `target reasoning` or `target assumption` followed by the target name; `evidence` names | — |

The [typed proposition reference](typed-propositions.md) defines the EAL/0.2 block, its formal `query`, permitted result predicates, unit conversions and exact input correspondence. Every argument for a typed claim needs an explicit binding. A successful scalar calculation cannot silently support a different quantity or formal query. See [the vocabulary](vocabulary.md) for keyword distinctions and [the task suite](engineering-tasks.md) for positive and adverse examples.

Name lists use commas. An argument requires at least one evidence, assumption or premise. A computational reasoning mode requires at least one result predicate. `structured` reasoning can omit result predicates. Available modes and typed evidence schemas are defined in [reasoning methods](reasoning-modes.md).

The current profile requires an argument’s conclusion, evidence, assumptions, premise claims and reasoning backing to use the same named environment. An explicit comparison model can represent observations from several conditions within that environment; implicit transfer between differently scoped claims is rejected. The engineer defines which context fields adequately represent the question.

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

This fragment makes three claims into required subarguments. Each can have further premises, its own reasoning mode and more than one supporting argument. A claim is supported when at least one uncontested usable argument supports it and there is no active claim-level objection. A reusable subclaim is evaluated once per assessment and retains its identifier; its repeated use does not create independent evidence. Declared evidence is deduplicated by identifier before a reasoning computation, including reasoning backing and assumption-validation observations.

The graph of conclusion-to-premise dependencies is acyclic, even if a cycle contains an alternative grounded argument. The current language rejects such cycles as a whole. Maximum source size is 1 MiB, maximum declaration count 4096 and maximum premise depth 128. The independent grounded operation supports cyclic attack graphs with its own limits.

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

An objection is active when all its evidence is available and its predicates hold. A claim-level objection contests all arguments for that claim. A reasoning-level or assumption-level objection affects the arguments using its target and their dependent claims. Other independent arguments can preserve support. Objections are authored target relations supported by observations; the interpreter does not infer semantic contradiction from prose.

Claim/argument results are `supported`, `contested`, `unsupported` or `out_of_scope`. Evidence has `available`/`unavailable`; objections have `active`/`inactive`. Detailed reasons distinguish missing, expired, mismatched, failed and predicate-rejected observations even where they share the same broad status. `unsupported` does not mean false; `contested` records unresolved opposition.

The result’s `valid` field reports static language validity. Each argument includes dependencies and a `reasoning_result` containing method output and predicate results. Claim text and reasoning rationale remain explanatory prose. Formal deductive inputs are supplied in `logical_case` evidence; premise claim strings are not automatically translated into those formulae, and the formula conclusion is not automatically equated with a prose claim. The author must maintain that correspondence explicitly.

## Worked sources

[latency.eal](../examples/latency.eal) demonstrates temporal assumption expiry and a subordinate claim. [mixed-reasoning.eal](../examples/mixed-reasoning.eal) composes all seven computational methods under a diagnosis using distinct input schemas and declared modelling assumptions. Its observations and likelihoods are synthetic. [live.eal](../examples/live.eal) executes real local deterministic and nondeterministic commands.

No arguments are automatically generated from natural-language claims. The examples show how an engineer or model can supply a precise graph that the interpreter can compute and explain.
