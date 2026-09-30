# EAL/3 source language

This is the reference for authored syntax, static checks and typed proposition binding in the current [grammar](../grammar/EAL.g4). [Vocabulary](vocabulary.md) distinguishes terms; the [argument model](argument-model.md) defines support and attack; [reasoning methods](reasoning-modes.md) define computations; [MCP and tools](mcp-and-tools.md) defines acquisition. The [API load-test case](../examples/api-load-test/README.md) is the maintained end-to-end example.

## Contents

- [Source structure](#source-structure)
- [Declarations](#declarations)
- [Context defaults and nested derivations](#context-defaults-and-nested-derivations)
- [Reusable argument patterns](#reusable-argument-patterns)
- [Predicates and time](#predicates-and-time)
- [Implementation limits](#implementation-limits)
- [Observation records](#observation-records)
- [Typed propositions and observations](#typed-propositions-and-observations)
- [Method selection and static checks](#method-selection-and-static-checks)
- [Validation and canonical formatting](#validation-and-canonical-formatting)

## Source structure

The first statement is `language "EAL/3"`; any other header fails validation. Top-level declarations can refer to later global declarations. Names are case-sensitive and unique across declaration kinds. They start with a letter or underscore and continue with letters, digits or underscores; some keyword spellings are admitted as contextual identifiers by the grammar. Pattern parameters form a separate, closed scope. Comments use `//` or `/* ... */`. Fields end at a newline; singleton fields may appear in any order. Semicolons are rejected. A final flow or directive may end at EOF. Braces group declarations without indentation tokens. JSON arrays and objects, support groups, parameter lists and flows may span lines; multiline comments do not supply field terminators. Discovery identifies the source language and syntax as `EAL/3`, separately from package and observation-record versions. The canonical ANTLR grammar is `EAL.g4` with grammar name `EAL`, because ANTLR identifiers cannot contain a slash. The source header is `language "EAL/3"`. A syntax error rejects the parse, including an ANTLR error-recovery tree.

The source byte limit is 1 MiB and the token limit is 100,000. Structural validation allows at most 4,096 declaration/body records after pattern expansion and a premise depth of 128. These limits bound this implementation's domain.

## Declarations

| Form | Required fields or flow elements | Optional fields or flow elements |
|---|---|---|
| `environment NAME` | One or more `require` predicates over supplied context | — |
| `tool NAME` | `version` string | — |
| `evidence NAME` | `tool` reference; `kind` identifier; `environment` reference; `max_age` seconds; one or more `require` predicates over observation value | `input` JSON |
| `assumption NAME` | `statement` string; `environment` reference; `validate` evidence reference | `valid_from`, `valid_until` |
| `reasoning NAME` | `method` exact versioned string; `rationale` string | `backing` evidence list; zero or more `require` result predicates |
| `claim NAME` | `statement` string; `environment` reference | One `proposition` block |
| `argument NAME = SUPPORT via REASONING => CLAIM` | Typed support groups, reasoning and conclusion | `binding` evidence after conclusion |
| `objection NAME = SUPPORT -x> KIND TARGET` | Target category and name; at least one supporting evidence or premise | — |
| `pattern NAME(...)` | Typed parameters and one argument body | — |
| `apply NAME = PATTERN(...)` | All named parameter bindings to global declarations | — |

References inside support lists retain explicit roles, for example `[evidence probe, trace, assumptions calibrated, premises report_checked]`. Commas separate references and groups; a role appears at most once. `backing [probe, trace]` is a bracketed evidence list. An argument needs at least one direct evidence, assumption or premise claim. A typed conclusion requires `binding` to a designated computational evidence source among its direct evidence, reasoning backing or assumption validation evidence. An untyped computational conclusion needs a `reasoning require` predicate. The authored `structured/1` method may omit result predicates. Objection target categories are `claim`, `reasoning`, `assumption`, `argument` and `objection`.

An argument's conclusion, evidence, assumptions, premise claims and reasoning backing must use the same named environment. An objection's evidence and premise claims must share an environment compatible with its target. A reasoning-target objection affects applications of that reasoning declaration within the objection's environment. The conclusion-to-premise graph must be acyclic; attack and objection-support cycles are permitted and may remain undecided. Their calculation is in the [argument model](argument-model.md).

Source selects a tool by name and exact version. The host TOML binding specifies how to execute it, while each collected observation records the selected binding's identity. The host may run independent read-only calls in parallel when its bindings permit it. These execution settings remain outside EAL. A tool declaration has no repeatability classification: actual variability depends on inputs, state, software and collection conditions.

## Context defaults and nested derivations

```eal
context environment lab, tool probe, max_age 60 {
  evidence reading {
    kind test
    input {"measurement": "probe"}
    require passed == true
  }
  evidence error_rate {
    kind test
    input {"measurement": "errors"}
    require fraction <= 0.01
  }
  context max_age 5 {
    evidence short_lived {
      kind test
      require passed == true
    }
  }
  claim measured {
    statement "The synthetic observation satisfies its acceptance condition."
  }
}
```

A context may contain multiple evidence declarations, claims, assumptions, arguments and further contexts. In this fragment, `reading` and `error_rate` both inherit environment `lab`, tool `probe` and `max_age 60`; `short_lived` inherits the same environment and tool with `max_age 5`. The named environment and tool must be declared elsewhere. Each evidence keeps its own name, kind, input, predicates and observation bindings. Grouping does not assert statistical independence or combine observations.

A context supplies lexical defaults, resolved before ordinary typed validation. Evidence inherits `environment`, `tool` and `max_age`; claims inherit `environment`; assumptions inherit `environment`, `valid_from` and `valid_until`. The nearest context overrides an outer default, and an explicit declaration field overrides either. Duplicate defaults or singleton fields fail recognition. Missing required fields after inheritance fail recognition. Contexts create neither namespaces nor logical premises. Proposition subject, quantity, unit, scope, dates and query remain explicit, so context grouping cannot silently change a formal question. Defaults are limited to `environment`, `tool`, `max_age`, `valid_from` and `valid_until`; `kind`, `input` and predicates remain declaration fields. A declaration may name a different environment or tool explicitly, but its consuming argument must still satisfy the ordinary same-environment checks. Names remain globally unique across contexts.

An argument can use both evidence declarations with `[evidence reading, error_rate]`. Within one route, all required support must be usable; alternative routes are expressed as separate arguments concluding the same claim.

Nested arguments are represented through **premise claims**, including claims established by pattern instances:

```eal
pattern measured_route(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
apply child = measured_route(c=measured, r=authored, e=reading)
argument parent = [premises measured] via authored => followup
```

This fragment assumes compatible declarations. `parent` depends on the claim `measured`, rather than on the identifier `child`. Every applicable route for that claim remains available; the ASPIC+ compiler constructs direct and transitive subarguments for each derivation. Arguments and pattern definitions do not contain inline declarations, nested pattern applications or recursive expansion. A context may group patterns and arguments without adding these capabilities. Premise dependency cycles remain invalid.

## Reusable argument patterns

```eal
pattern check(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c binding e

apply pressure_check = check(c = pressure, r = contrast, e = trial)
```

This fragment assumes a typed `pressure` claim and suitable global declarations. Parameter kinds are `claim`, `reasoning`, `evidence` and `assumption`. Each body reference must be a parameter of the correct kind; global names cannot be captured implicitly. Each application supplies every parameter once and expands to one ordinary argument under the `apply` name. Expansion preserves evidence identity and undergoes the ordinary binding, scope and method checks. An objection may target one application. Unused definitions are checked. Patterns cannot nest, recurse, declare other objects or execute collection. Limits are 1,000 applications and 100,000 expanded references.

## Predicates and time

```eal
require instrument.maximum_error_ms <= 1

require algorithm == "sha256"

require entailed == true
```

Bare keys denote literal property paths; quoted keys retain arbitrary original spellings. String values stay quoted, and JSON object keys follow JSON. There is no implicit identifier lookup or general-purpose expression evaluation. A dotted path selects object fields from context, observation value or a computation's output according to the enclosing declaration. `==`, `!=`, `<`, `<=`, `>` and `>=` compare scalars. A missing field, incompatible operand or nonfinite number cannot satisfy a predicate. Booleans differ from numbers; ordered comparisons need numbers or strings. String order is lexicographical, so use explicit timestamp clauses or a temporal method for instants. Each declaration's predicates combine conjunctively. JSON can contain null, finite numbers, strings, booleans, arrays and unique-key objects; it never executes code.

`max_age` is finite nonnegative seconds measured from an observation's original `collected_at` to assessment `now`. Age exactly at the bound is eligible; a future-dated observation is not. `ingested_at` marks storage and does not refresh an observation. An assumption's optional `valid_from` and `valid_until` require timezone-aware ISO-8601 instants and form `[valid_from, valid_until)`. The evaluator tests this interval at assessment time and independently requires usable validation evidence. An observation can become too old before its assumption's interval ends when `max_age` is shorter than that interval. Conversely, a fresh observation cannot support an assumption after its interval ends. A historical assessment supplies historical `now` and context explicitly. These checks do not prove continuous physical conditions.

## Implementation limits

These bounds describe the current implementation; contexts do not impose a one-evidence limit.

| Area | Current restriction |
|---|---|
| Contexts | Five supported defaults, applied only to their documented declaration kinds. Global names, with no context-local namespace or automatic environment conversion. |
| Argument composition | Nested derivations through premise claims and named pattern instances. No inline argument declarations, recursive patterns, or pattern applications inside pattern bodies. Premise cycles are invalid. |
| Predicates | Six scalar comparators over literal keys/property paths. No arithmetic, function calls, implicit variable lookup or arbitrary expression execution. String values and JSON object keys stay quoted. |
| Typed propositions | Explicit subject, quantity, unit, scope, dates, query and result binding. Inheritance does not fill proposition metadata or prove that prose matches the formal question. |
| Source and graph | 1 MiB source, 100,000 tokens, 4,096 declaration/body records after expansion, at most 128 premise edges in a chain. |
| Pattern expansion | 1,000 applications and 100,000 expanded references, also subject to the source/graph bounds. |
| Collection | At most 128 evidence requests per collection. Declaring more evidence in one context does not remove this host-operation bound. |
| ASPIC+ compilation | At most 64 evidence declarations and 64 combined argument, assumption and objection rules. The emitted theory must also satisfy the solver bounds below. |
| ASPIC+ solver | An acyclic rule profile with grounded semantics and minimum-rank preferences: 64 formal premises, 64 rules, eight antecedents per rule, 128 distinct atoms, 128 contrary pairs, 128 constructed arguments and 4,096 defeat witnesses. Alternatives and nested routes can reach these bounds before the source limit. |
| Reviewed directives | `strict`, `rank` and directed `contrary` affect the opt-in ASPIC+ compiler. Ordinary authored assessment validates them without applying those formal inference effects. Review references are supplied metadata. |

An assessment checks the declared argument against the supplied observations and installed method contracts. It does not establish observation authenticity, prove arbitrary claim prose, or infer physical continuity from freshness alone. Unsupported or missing support does not assert falsity. More detailed host limits are in the [integration contract](../CONTRACT.md); the [ASPIC+ method](aspic-method.md) specifies its omitted cases and failure behaviour.

## Observation records

EAL/3 source declares what to observe and how to use the result. It has no `observation` declaration. For example:

```eal
evidence calibration {
  tool probe
  kind test
  environment lab
  max_age 86400
  input {"sensor": "pump-A"}
  require "within_tolerance" == true
}

assumption calibrated {
  statement "The pump sensor was calibrated for this assessment."
  environment lab
  validate calibration
  valid_from "2026-09-23T10:00:00Z"
  valid_until "2026-09-24T10:00:00Z"
}
```

Here `calibration` identifies a tool request and acceptance condition, and `calibrated` uses it during the stated interval. The tool emits a JSON result such as `{"value":{"within_tolerance":true},"observed_at":"2026-09-23T10:00:00Z"}`. The host stores the value in a separate `EAL/observation-record/1` record with the evidence ID, tool and request identity, context, original observation time and result digest. The input JSON and predicates are authored definitions, not measured results. A successful negative measurement remains an observation even when it does not satisfy `require`.

The durable record can be reused by later sessions and models while its acquisition identity still matches the current request and its original time satisfies `max_age`. A registered claim assessment looks for an eligible record before calling a collector; it recollects missing or expired evidence and recomputes the argument. Changes to an assumption's dates affect the assessment, not the measurement time. Tool or context changes can invalidate reuse independently of time. The observation record is separate from the authored argument so it can be refreshed without rewriting the source or changing the source digest. A `json_file` tool binding imports an externally stored observation envelope when measurements must travel as a file.

## Typed propositions and observations

A bounded scalar proposition identifies a subject, quantity, input unit, episode or model scope, interval, formal question and result condition. The claim's `statement` remains prose. The interpreter checks the represented calculation and correspondence to its typed proposition; it cannot prove that the prose describes the calculation or that a producer measured the asserted quantity.

```eal
claim raised {
  statement "The treatment mean pressure exceeds control by at least 5 kPa."
  environment lab
  proposition {
    subject "pump-A"
    quantity "pressure"
    unit "kPa"
    scope "experiment-v1"
    valid_from "2026-09-23T10:00:00Z"
    valid_until "2026-09-23T11:00:00Z"
    query {"assignment": "randomised"}
    result "estimate" >= 5
  }
}

argument comparison = [evidence trial] via contrast => raised binding trial
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

The mean contrast is 7,500 Pa, converted to 7.5 kPa for `result "estimate" >= 5`. This establishes the numerical relation conditional on supplied data and experiment design. A changed subject, quantity, scope, incompatible unit, formal question or method fails correspondence. The envelope has exactly the nine displayed top-level keys, and its interval must contain the full proposition interval. Each `query` field must be a required method input with identical schema and must equal the payload field under canonical JSON comparison. `true` cannot stand for `1`; parsed `1` and `1.0` may have different canonical spellings. In this causal example, the observed group values remain in the payload without becoming part of the declared question.

Built-in query fields are: `deductive/1` (`premises`, `conclusion`); `inductive/1` (`confidence`); `abductive/1` (`observed`, `candidates`); `causal/1` (`assignment`); `counterfactual/1` (`variables`, `intervention`, `outcome`); `analogical/1` (`relevant_features`, `source`, `target`); and `temporal/1` (`start`, `end`, `max_gap`, `property`, `semantics`). The [reasoning method reference](reasoning-modes.md) gives input schemas, result paths and calculations. A usable negative result may support an explicitly negative predicate such as `result "entailed" == false`. A failed execution, inconsistent deductive case or incomplete temporal trace remains unusable.

The implemented quantity identities are `pressure`, `time`, `length`, `mass`, `temperature_difference`, `velocity`, `volumetric_flow`, `probability`, `dimensionless` and `proposition`. Exact units and permissible quantities are discoverable through `eal_describe` or `eal.propositions.describe_bindings()`. A proposition's unit describes its input measurement basis; output meaning is separately `basis`, `dimensionless` or Boolean. `basis` conversion uses rational scale factors followed, where needed, by finite floating-point output; overflow or underflow that erases a nonzero result fails binding. Temporal and counterfactual methods require exact input units because their queries contain dimensional constants. General dimensional algebra and vector propositions are outside this fragment.

## Method selection and static checks

`method "name/1"` or `method "namespace/name/1"` resolves an exact installed contract. Built-ins include `structured/1` and seven computational methods. Host extensions use the same selector, output predicates and typed binding. An unknown or unversioned method is a static error even if unused. Source cannot install Python functions, change a registry or choose an executable collector. Assessments record `method_registry_fingerprint`.

The selected contract fixes which input fields may occur in a typed `query` and which result paths can be required. Every query field must be required by the method input schema with the same type, and output predicates must address declared, compatible scalar fields. See [host-registered methods](reasoning-modes.md#host-registered-methods) for registration, execution limits and versioning; the implementation is in the [method registry](../src/eal/methods.py) and [example extension](../src/eal/extensions.py).

The optional [ASPIC+ method](aspic-method.md) accepts an explicit typed `proposition` whose query binds the whole formal theory; `method "argumentation/aspic/1"` selects the host-installed solver. EAL has one source language. Its top-level `strict NAME reviewed "REFERENCE"`, `rank NAME INTEGER reviewed "REFERENCE"` and `contrary CLAIM to CLAIM reviewed "REFERENCE"` directives declare strict inference, preference rank and directed contrariness within that language. Name resolution checks their target kinds after pattern expansion: `strict` names an argument, `rank` names evidence, an assumption or a defeasible argument, and `contrary` names claims. Objection ranks are rejected because compiled undercuts ignore preference. Validation checks these directives for both operations. `compile-aspic` applies their inference effects; ordinary `reason` uses the authored EAL calculus without applying strictness, ranks or claim contrariness. A programme can therefore receive different results from these two named assessment contracts.

## Validation and canonical formatting

Recognition produces typed intermediate representation. Independent passes check IR shape, unique identity, reference kinds, predicate types, registered method contracts, typed query/output correspondence, dependencies, scopes and bounds. Diagnostics provide a code, message, declaration and, where available, one-based source span with exclusive end; contract mismatches can include expected and actual types. Open JSON output fields retain runtime checks. Malformed Python-created IR is checked too.

`format_source(source)` validates and emits canonical source. `format_program(program)` applies the same checks to IR; `semantic_ir(program)` supports parse–format–parse comparisons. Formatting retains meaning and authored pattern/application forms. It emits typed flows and bare keys where valid, and factors repeated environment, tool and age metadata into a context. It may change comments and declaration order across categories. Changed exact source bytes change its digest. The registered assessment path creates a new source-bound collection from compatible stored observations at their original age and collects the remaining evidence. The lower-level `rebind` operation performs the same check for a named earlier collection.
