# EAL/2 source language

This is the reference for authored syntax, static checks and typed proposition binding in the current [grammar](../grammar/EAL.g4). [Vocabulary](vocabulary.md) distinguishes terms; the [argument model](argument-model.md) defines support and attack; [reasoning methods](reasoning-modes.md) define computations; [MCP and tools](mcp-and-tools.md) defines acquisition. The [API load-test case](../examples/api-load-test/README.md) is the maintained end-to-end example.

## Contents

- [Source structure](#source-structure)
- [Declarations](#declarations)
- [Reusable argument patterns](#reusable-argument-patterns)
- [Predicates and time](#predicates-and-time)
- [Typed propositions and observations](#typed-propositions-and-observations)
- [Method selection and static checks](#method-selection-and-static-checks)
- [Validation and canonical formatting](#validation-and-canonical-formatting)

## Source structure

The first statement is `language "EAL/2";`; any other header fails validation. Top-level declarations can refer to later global declarations. Names are case-sensitive and unique across declaration kinds. They start with a letter or underscore and continue with letters, digits or underscores; some keyword spellings are admitted as contextual identifiers by the grammar. Pattern parameters form a separate, closed scope. Comments use `//` or `/* ... */`. Each clause ends in `;`, and clause order follows the grammar. A syntax error rejects the parse, including an ANTLR error-recovery tree.

The source byte limit is 1 MiB and the token limit is 100,000. Structural validation allows at most 4,096 declaration/body records after pattern expansion and a premise depth of 128. These limits bound this implementation's domain.

## Declarations

| Form | Required clauses in order | Optional clauses in grammar order |
|---|---|---|
| `environment NAME` | One or more `require` predicates over supplied context | — |
| `tool NAME` | `version` string | — |
| `evidence NAME` | `tool` reference; `kind` identifier; `environment` reference; `max_age` seconds; one or more `require` predicates over observation value | `input` JSON before predicates |
| `assumption NAME` | `statement` string; `environment` reference; `validate` evidence reference | `valid_from` then `valid_until` |
| `reasoning NAME` | `method` exact versioned string; `rationale` string | `backing` evidence list; zero or more `require` result predicates |
| `claim NAME` | `statement` string; `environment` reference | One `proposition` block |
| `argument NAME` | `conclusion` claim; `reasoning` declaration | `evidence`, `assumptions`, `premises` lists; `binding` evidence |
| `objection NAME` | `target` category and name | `evidence`, `premises` lists; one or both required |
| `pattern NAME(...)` | Typed parameters and one argument body | — |
| `apply NAME = PATTERN(...)` | All named parameter bindings to global declarations | — |

Lists use commas. An argument needs at least one direct evidence, assumption or premise claim. A typed conclusion requires `binding` to a designated computational evidence source among its direct evidence, reasoning backing or assumption validation evidence. An untyped computational conclusion needs a `reasoning require` predicate. The authored `structured/1` method may omit result predicates. Objection target categories are `claim`, `reasoning`, `assumption`, `argument` and `objection`.

An argument's conclusion, evidence, assumptions, premise claims and reasoning backing must use the same named environment. An objection's evidence and premise claims must share an environment compatible with its target. A reasoning-target objection affects applications of that reasoning declaration within the objection's environment. The conclusion-to-premise graph must be acyclic; attack and objection-support cycles are permitted and may remain undecided. Their calculation is in the [argument model](argument-model.md).

Source selects a tool by name and exact version. The trusted host binding specifies execution, while the observation records the selected binding's digest. A tool declaration has no repeatability classification: actual variability depends on inputs, state, software and collection conditions.

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

This fragment assumes a typed `pressure` claim and suitable global declarations. Parameter kinds are `claim`, `reasoning`, `evidence` and `assumption`. Each body reference must be a parameter of the correct kind; global names cannot be captured implicitly. Each application supplies every parameter once and expands to one ordinary argument under the `apply` name. Expansion preserves evidence identity and undergoes the ordinary binding, scope and method checks. An objection may target one application. Unused definitions are checked. Patterns cannot nest, recurse, declare other objects or execute collection. Limits are 1,000 applications and 100,000 expanded references.

## Predicates and time

```eal
require "instrument.maximum_error_ms" <= 1;
require "algorithm" == "sha256";
require "entailed" == true;
```

A dotted path selects object fields from context, observation value or a computation's output according to the enclosing declaration. `==`, `!=`, `<`, `<=`, `>` and `>=` compare scalars. A missing field, incompatible operand or nonfinite number cannot satisfy a predicate. Booleans differ from numbers; ordered comparisons need numbers or strings. String order is lexicographical, so use explicit timestamp clauses or a temporal method for instants. Each declaration's predicates combine conjunctively. JSON can contain null, finite numbers, strings, booleans, arrays and unique-key objects; it never executes code.

`max_age` is finite nonnegative seconds measured from the record's original `collected_at` to assessment `now`. Age exactly at the bound is eligible; a future-dated observation is not. `ingested_at` marks storage and does not refresh an observation. `valid_from` and `valid_until` require timezone-aware ISO-8601 instants and form `[valid_from, valid_until)`. The evaluator tests an assumption's interval at assessment time and requires usable validation evidence. A historical assessment supplies historical `now` and context explicitly. These checks do not prove continuous physical conditions.

## Typed propositions and observations

A bounded scalar proposition identifies a subject, quantity, input unit, episode or model scope, interval, formal question and result condition. The claim's `statement` remains prose. The interpreter checks the represented calculation and correspondence to its typed proposition; it cannot prove that the prose describes the calculation or that a producer measured the asserted quantity.

```eal
claim raised {
  statement "The treatment mean pressure exceeds control by at least 5 kPa.";
  environment lab;
  proposition {
    subject "pump-A";
    quantity "pressure";
    unit "kPa";
    scope "experiment-v1";
    valid_from "2026-09-23T10:00:00Z";
    valid_until "2026-09-23T11:00:00Z";
    query {"assignment": "randomised"};
    result "estimate" >= 5;
  }
}
argument comparison {
  conclusion raised;
  reasoning contrast;
  evidence trial;
  binding trial;
}
```

The fragment assumes `lab`, a `causal/1` reasoning declaration named `contrast`, and `trial` of kind `experiment`. Its observation value must be the versioned input envelope below. The surrounding observation record separately identifies the exact source, evidence request, environment, tool and original observation time.

```json
{
  "schema": "EAL/typed-input/1",
  "method": "causal/1",
  "subject": "pump-A",
  "quantity": "pressure",
  "unit": "Pa",
  "scope": "experiment-v1",
  "valid_from": "2026-09-23T10:00:00Z",
  "valid_until": "2026-09-23T11:00:00Z",
  "payload": {
    "assignment": "randomised",
    "treatment": [10000, 12000],
    "control": [3000, 4000]
  }
}
```

The mean contrast is 7,500 Pa, converted to 7.5 kPa for `result "estimate" >= 5;`. This establishes the numerical relation conditional on supplied data and experiment design. A changed subject, quantity, scope, incompatible unit, formal question or method fails correspondence. The envelope has exactly the nine displayed top-level keys, and its interval must contain the full proposition interval. Each `query` field must be a required method input with identical schema and must equal the payload field under canonical JSON comparison. `true` cannot stand for `1`; parsed `1` and `1.0` may have different canonical spellings. In this causal example, the observed group values remain in the payload without becoming part of the declared question.

Built-in query fields are: `deductive/1` (`premises`, `conclusion`); `inductive/1` (`confidence`); `abductive/1` (`observed`, `candidates`); `causal/1` (`assignment`); `counterfactual/1` (`variables`, `intervention`, `outcome`); `analogical/1` (`relevant_features`, `source`, `target`); and `temporal/1` (`start`, `end`, `max_gap`, `property`, `semantics`). The [reasoning method reference](reasoning-modes.md) gives input schemas, result paths and calculations. A usable negative result may support an explicitly negative predicate such as `result "entailed" == false;`. A failed execution, inconsistent deductive case or incomplete temporal trace remains unusable.

The implemented quantity identities are `pressure`, `time`, `length`, `mass`, `temperature_difference`, `velocity`, `volumetric_flow`, `probability`, `dimensionless` and `proposition`. Exact units and permissible quantities are discoverable through `eal_describe` or `eal.propositions.describe_bindings()`. A proposition's unit describes its input measurement basis; output meaning is separately `basis`, `dimensionless` or Boolean. `basis` conversion uses rational scale factors followed, where needed, by finite floating-point output; overflow or underflow that erases a nonzero result fails binding. Temporal and counterfactual methods require exact input units because their queries contain dimensional constants. General dimensional algebra and vector propositions are outside this fragment.

## Method selection and static checks

`method "name/1";` or `method "namespace/name/1";` resolves an exact installed contract. Built-ins include `structured/1` and seven computational methods. Host extensions use the same selector, output predicates and typed binding. An unknown or unversioned method is a static error even if unused. Source cannot install Python functions, change a registry or choose an executable collector. Assessments record `method_registry_fingerprint`.

The selected contract fixes which input fields may occur in a typed `query` and which result paths can be required. Every query field must be required by the method input schema with the same type, and output predicates must address declared, compatible scalar fields. See [host-registered methods](reasoning-modes.md#host-registered-methods) for registration, execution limits and versioning; the implementation is in the [method registry](../src/eal/methods.py) and [example extension](../src/eal/extensions.py).

## Validation and canonical formatting

Recognition produces typed intermediate representation. Independent passes check IR shape, unique identity, reference kinds, predicate types, registered method contracts, typed query/output correspondence, dependencies, scopes and bounds. Diagnostics provide a code, message, declaration and, where available, one-based source span with exclusive end; contract mismatches can include expected and actual types. Open JSON output fields retain runtime checks. Malformed Python-created IR is checked too.

`format_source(source)` validates and emits canonical source. `format_program(program)` applies the same checks to IR; `semantic_ir(program)` supports parse–format–parse comparisons. Formatting retains meaning and authored pattern/application forms, but can change comments and declaration order across categories. Changed exact source bytes change its digest, so observations must be recollected or explicitly rebound through the normal collection workflow.
