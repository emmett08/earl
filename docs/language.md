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

The first statement is `language "EAL/3"`; any other header fails validation. Top-level declarations can refer to later global declarations. Names are case-sensitive and unique across declaration kinds within their lexical namespace. Modules and argument blocks qualify local names; nearest lexical names resolve before outer names. Forward references are allowed. Each dot-separated name component starts with a letter or underscore and continues with letters, digits or underscores; some keyword spellings are admitted as contextual identifiers by the grammar. Pattern parameters form a separate, closed scope. Comments use `//` or `/* ... */`. Fields end at a newline; singleton fields may appear in any order. Semicolons are rejected. A final flow or directive may end at EOF. Braces group declarations without indentation tokens. JSON arrays and objects, support groups, parameter lists and flows may span lines; multiline comments do not supply field terminators. Discovery identifies the source language and syntax as `EAL/3`, separately from package and observation-record versions. The canonical ANTLR grammar is `EAL.g4` with grammar name `EAL`, because ANTLR identifiers cannot contain a slash. The source header is `language "EAL/3"`. A syntax error rejects the parse, including an ANTLR error-recovery tree.

Default host budgets are 1 MiB of source, 100,000 tokens, 4,096 declaration/body records and premise depth 128. Operators can configure budgets with `ExecutionLimits` or `--limits FILE`; source cannot increase them. [Scoped composition](eal3-composition.md) specifies imports, block arguments, compound patterns, expressions and conditional scope transfer.

## Declarations

| Form | Required fields or flow elements | Optional fields or flow elements |
|---|---|---|
| `environment NAME` | One or more `require` predicates over supplied context | — |
| `tool NAME` | `version` string | — |
| `evidence NAME` | `tool` reference; `kind` identifier; `environment` reference; `max_age` seconds; one or more `require` predicates over observation value | `input` JSON |
| `assumption NAME` | `statement` string; `environment` reference; `validate` evidence reference | `valid_from`, `valid_until` |
| `reasoning NAME` | `method` exact versioned string; `rationale` string | `backing` evidence list; result predicates; reviewed conditional `transfer` |
| `claim NAME` | `statement` string; `environment` reference | One `proposition` block |
| `argument NAME = SUPPORT via REASONING => CLAIM` | Typed support groups, reasoning and conclusion | `binding` evidence after conclusion |
| `objection NAME = SUPPORT -x> KIND TARGET` | Target category and name; at least one supporting evidence or premise | — |
| `pattern NAME(...)` | Typed scalar or list parameters; a flow or declaration block | — |
| `apply NAME = PATTERN(...)` | All named bindings to lexical declarations or typed lists | — |

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

A context supplies defaults before typed validation. The nearest context wins; an explicit field wins over defaults. Duplicate singleton fields or defaults fail recognition, as do required fields still missing after inheritance. Defaults cover `environment`, `tool`, `max_age`, `kind`, `input`, tool `version`, assumption `validate`, reasoning `method` and proposition `subject`, `quantity`, `unit`, `scope`, dates and `query`. They apply only to relevant declaration kinds. Inherited references resolve in the consuming declaration's lexical namespace. Predicates, statements, rationales and result conditions remain explicit. Inheritance does not prove the inherited metadata's physical correctness. Contexts create neither namespaces nor premises; modules create namespaces.

An argument can use both evidence declarations with `[evidence reading, error_rate]`. Within one route, all required support must be usable; alternative routes are expressed as separate arguments concluding the same claim.

Nested arguments are represented through **premise claims**, including claims established by pattern instances:

```eal
pattern measured_route(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
apply child = measured_route(c=measured, r=authored, e=reading)
argument parent = [premises measured] via authored => followup
```

This fragment assumes compatible declarations. `parent` depends on the claim `measured`, preserving every applicable route. Blocks also permit inline local declarations, for example:

```eal
argument parent {
  claim local {
    statement "A local intermediate result."
    environment lab
  }
  argument child = [evidence reading] via authored => local
  [premises local] via authored => followup
}
```

The local names become `parent.local` and `parent.child`; the final flow becomes `parent`. Premise dependency cycles remain invalid. See [compound patterns](eal3-composition.md) for nested applications and termination checks.

## Reusable argument patterns

```eal
pattern check(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c binding e

apply pressure_check = check(c = pressure, r = contrast, e = trial)
```

This fragment assumes a typed `pressure` claim and suitable declarations. Supported parameter kinds are `claim`, `reasoning`, `evidence`, `assumption`, `environment` and `tool`, optionally followed by `[]`. Scalar flows expand under the application name. Compound blocks introduce hygienic names under that application and can contain declarations, patterns, applications, objections and reviewed directives. Every external identity must be an explicit parameter; global data capture is rejected. Named bindings must supply all parameters exactly once with the declared kinds. Lists retain order and evidence identity, and flatten only into matching support groups. Unused definitions are checked.

A recursive pattern declares `decreases LIST`, branches with `when LIST { ... } else { ... }`, and passes `tail(LIST)` to a recursive call. `head(LIST)` is valid only in its nonempty guard. Cycles through multiple templates require the same guarded strict decrease. Expansion also obeys host application, depth, reference and declaration budgets. It never executes collectors. [Scoped composition](eal3-composition.md) contains the complete example.

## Predicates and time

```eal
require instrument.maximum_error_ms <= 1

require algorithm == "sha256"

require entailed == true
```

Bare identifiers denote property paths in the enclosing context, evidence value or method output. `field("arbitrary key")` addresses other spellings; a directly quoted left operand of a comparison retains its established field-path meaning. Use `literal("text")` to compare a string literal in that position. String values and JSON object keys remain quoted.

Pure expressions support the six scalar comparators, `and`, `or`, `not`, `+`, `-`, `*`, `/`, `%`, parentheses and registered `count`, `sum`, `min`, `max`, `abs`, `all`, `any`, `quantity` and `literal` functions. There is no source execution or dynamic function installation. `quantity(distance,"m") / quantity(duration,"s")` computes a dimensional quantity; comparisons and additive operations require compatible dimensions. Known unit incompatibilities fail statically, including dynamic numerical inputs with literal units. Other type failures, nonfinite arithmetic and division by zero fail at runtime. Typed result expressions can only use registered output paths and convert basis-valued outputs into the proposition unit before evaluation.

Missing fields remain unknown under negation. Boolean composition uses three-valued logic: `missing or true` is true and `missing and false` is false; an invalid operation is never hidden by another Boolean operand. Booleans differ from numbers. Ordered comparisons use finite numbers, strings or compatible quantities. JSON remains finite scalar, array or unique-key object data. Predicates in one declaration combine conjunctively.

`max_age` is finite nonnegative seconds measured from an observation's original `collected_at` to assessment `now`. Age exactly at the bound is eligible; a future-dated observation is not. `ingested_at` marks storage and does not refresh an observation. An assumption's optional `valid_from` and `valid_until` require timezone-aware ISO-8601 instants and form `[valid_from, valid_until)`. The evaluator tests this interval at assessment time and independently requires usable validation evidence. An observation can become too old before its assumption's interval ends when `max_age` is shorter than that interval. Conversely, a fresh observation cannot support an assumption after its interval ends. A historical assessment supplies historical `now` and context explicitly. These checks do not prove continuous physical conditions.

## Implementation limits

The language supports multiple evidence declarations per context, lexical modules/imports, block arguments, compound typed patterns, terminating list recursion, pure expressions and reviewed conditional scope transfer. Budgets are host policy, not syntax constants. Discovery returns `execution_limits`; compiled snapshots and `aspic-view/3` capture those limits. A TOML file containing only `[limits]` can override positive integer fields; omitted fields retain defaults.

Default limits include 128 evidence acquisitions per collection; 64 formal premises and rules, eight antecedents per rule, 128 atoms, 128 arguments and 4,096 defeat witnesses. Operators may raise them. Construction and extension enumeration have separate work budgets. Exceeding a budget yields an error or an explicit incomplete calculation with no acceptance conclusion, rather than a truncated complete graph. Transport, collector output and method worker byte/time limits remain separate operational policy.

The ordinary authored premise graph remains acyclic. The optional ASPIC+ method allows finite premise-founded cyclic rule graphs, grounded/preferred/stable extensions, credulous/sceptical queries and specified minimum-rank or last-link preferences. Recursive paths cannot repeat a conclusion along a branch. This is a finite profile, not arbitrary infinite argument enumeration. Reviewed `strict`, `rank`, `contrary` and `prefer` affect only opt-in formal compilation. Evidence authenticity, prose validity, physical transport justification, first-order proofs and unrestricted arbitrary code remain outside the source language. [Scoped composition](eal3-composition.md) and [ASPIC+ method](aspic-method.md) specify these boundaries.

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

The implemented quantity identities are `pressure`, `time`, `length`, `mass`, `temperature_difference`, `velocity`, `volumetric_flow`, `probability`, `dimensionless` and `proposition`. Exact units and permissible quantities are discoverable through `eal_describe` or `eal.propositions.describe_bindings()`. A proposition's unit describes its input measurement basis; output meaning is separately `basis`, `dimensionless` or Boolean. `basis` conversion uses rational scale factors followed, where needed, by finite floating-point output; overflow or underflow that erases a nonzero result fails binding. Temporal and counterfactual methods require exact input units because their queries contain dimensional constants. Pure `quantity` expressions support dimensional scalar algebra; vector propositions remain outside this fragment.

## Method selection and static checks

`method "name/1"` or `method "namespace/name/1"` resolves an exact installed contract. Built-ins include `structured/1` and seven computational methods. Host extensions use the same selector, output predicates and typed binding. An unknown or unversioned method is a static error even if unused. Source cannot install Python functions, change a registry or choose an executable collector. Assessments record `method_registry_fingerprint`.

The selected contract fixes which input fields may occur in a typed `query` and which result paths can be required. Every query field must be required by the method input schema with the same type, and output predicates must address declared, compatible scalar fields. See [host-registered methods](reasoning-modes.md#host-registered-methods) for registration, execution limits and versioning; the implementation is in the [method registry](../src/eal/methods.py) and [example extension](../src/eal/extensions.py).

The optional [ASPIC+ method](aspic-method.md) accepts an explicit typed `proposition` whose query binds the whole formal theory; `method "argumentation/aspic/2"` selects the host-installed solver. EAL has one source language. Its top-level `strict NAME reviewed "REFERENCE"`, `rank NAME INTEGER reviewed "REFERENCE"`, `contrary CLAIM to CLAIM reviewed "REFERENCE"` and `prefer NAME over NAME reviewed "REFERENCE"` directives declare strict inference, numerical rank, directed contrariness and partial preference within that language. Name resolution checks their target kinds after pattern expansion: `strict` names an argument, `rank` names evidence, an assumption or a defeasible argument, `contrary` names claims, and `prefer` compares fallible premises or defeasible argument rules within the same formal domain. Objection ranks are rejected because compiled undercuts ignore preference. Validation checks these directives for both operations. `compile-aspic` applies their inference effects; ordinary `reason` uses the authored EAL calculus without applying strictness, ranks or claim contrariness. A programme can therefore receive different results from these two named assessment contracts.

## Validation and canonical formatting

Recognition produces typed intermediate representation. Independent passes check IR shape, unique identity, reference kinds, predicate types, registered method contracts, typed query/output correspondence, dependencies, scopes and bounds. Diagnostics provide a code, message, declaration and, where available, one-based source span with exclusive end; contract mismatches can include expected and actual types. Open JSON output fields retain runtime checks. Malformed Python-created IR is checked too.

`format_source(source)` validates and emits canonical source. `format_program(program)` applies the same checks to IR; `semantic_ir(program)` supports parse–format–parse comparisons. Formatting retains meaning, lexical modules/imports, contexts, block arguments and authored pattern/application forms. It emits typed flows and bare keys where valid, and factors repeated environment, tool and age metadata into a context. It may change comments and declaration order across categories. Changed exact source bytes change its digest. The registered assessment path creates a new source-bound collection from compatible stored observations at their original age and collects the remaining evidence. The lower-level `rebind` operation performs the same check for a named earlier collection.
