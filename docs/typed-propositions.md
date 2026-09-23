# Typed propositions in EAL/0.2

EAL/0.2 adds a bounded scalar proposition fragment. A proposition names the subject, measured quantity, unit, model or episode scope, interval, mathematical question and predicate on a specified method result. A supporting argument explicitly binds that proposition to its computational evidence. The interpreter checks the correspondence before evaluating the predicate. Explanatory `statement` text is retained separately and is never proved by parsing or by a successful numerical calculation.

```eal
language "EAL/0.2";
environment lab { require "site" == "bench"; }
tool readings { version "1"; mode deterministic; }
evidence trial {
  tool readings;
  kind experiment;
  environment lab;
  max_age 60;
  require "schema" == "EAL/typed-input/1";
}
reasoning contrast {
  mode causal;
  rationale "Compare group means under the stated randomised experiment.";
}
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

The value returned by `readings` is the following versioned input envelope. The runtime's observation record still binds this value to the exact source, evidence request, environment fingerprint, tool version, original observation time and payload digest.

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

The checked mean difference is 7500 Pa, converted to 7.5 kPa for the proposition. Changing `quantity` to `volumetric_flow`, `unit` to `L/s`, the subject, the experiment scope or the mathematical question cannot support this proposition. Compatible units are converted only where the method permits it. The collector's physical interpretation remains an assertion: matching metadata does not establish that a sensor actually measured pressure or that allocation was randomised.

## Formal question and identity

`query` specifies the mathematical question independently of observed numerical values. It has an exact field contract for each method. Every declared query field must equal the corresponding input-payload field as canonical JSON; extra or missing query fields are rejected. Comparisons preserve JSON types, so `true` cannot substitute for `1`. Exact JSON numeric spelling after parsing may distinguish an integer from a float (for example, `1` and `1.0`); use the same representation in the query and collector.

| Method contract | Required query fields | Typed results | Quantity |
|---|---|---|---|
| `deductive/1` | `premises`, `conclusion` | `entailed`, `consistent_premises` (boolean) | `proposition`, unit `1` |
| `inductive/1` | `confidence` | `estimate`, `lower`, `upper` | `probability`, unit `1` |
| `abductive/1` | `observed`, `candidates` | `best_posterior`, `posterior.NAME` | `probability`, unit `1` |
| `causal/1` | `assignment` | `estimate`, `standard_error`, `treatment_mean`, `control_mean` | numerical quantity; result has its units |
| `counterfactual/1` | `variables`, `intervention`, `outcome` | `factual`, `counterfactual`, `difference` | numerical quantity; result has its units |
| `analogical/1` | `relevant_features`, `source`, `target` | `match_fraction`; `complete` (boolean) | `dimensionless`, unit `1` |
| `temporal/1` | `start`, `end`, `max_gap`, `property`, `semantics` | `holds`, `coverage` (boolean) | numerical quantity being sampled |

Statistical sample counts, causal observation arrays and temporal events are supplied by the observation; the source pins their question and scope. For deduction and counterfactual evaluation the whole formal problem is pinned. Returning the result of `p` implying `p` cannot answer a declared question about `p` implying `q`. Changing an intervention or a temporal property similarly fails correspondence.

An assessment exposes the declaration's proposition, evidence ID, method/version, entire observed formal query, `input_payload_digest`, comparison value, result unit and explicit correspondence failures. The proposition plus bound method and query determine formal meaning. Altering prose alone never alters that meaning. An author must still inspect whether prose describes the formal proposition accurately.

## Quantities, units and time

The proposition's `quantity` and `unit` identify the **input measurement basis**. A result's interpretation is separately fixed by the method contract: `basis` retains the measurement unit, `dimensionless` has unit `1`, and `boolean` has no numerical unit. For example, the sample count of pressure observations is dimensionless; it is never interpreted as pressure. Assessments explicitly report `output_unit` beside the comparison value.

The implemented quantities are `pressure`, `time`, `length`, `mass`, `temperature_difference`, `velocity`, `volumetric_flow`, `probability`, `dimensionless` and `proposition`. They are identities, not interchangeable labels. In particular, a dimensionless probability differs from a generic dimensionless number, and temperature differences do not denote absolute temperatures. `eal_describe` reports the exact unit catalogue and method contracts; `eal.propositions.describe_bindings()` exposes the same catalogue to Python callers.

Causal result conversion uses exact rational unit scale factors followed by finite floating-point output where conversion is necessary. It does not increase the precision of the underlying statistical calculation. Temporal and counterfactual inputs require exactly the proposition's unit because their queries include dimensional constants. Temporal `start`, `end`, `max_gap` and event times retain the method's seconds-based time axis; the measured `property.value` uses the proposition's unit. Counterfactual variables all share the one declared measurement unit, coefficients are dimensionless, and intercepts, noise and intervention values use that unit. Mixed-dimension structural models require a future typed expression system.

The proposition interval and envelope interval are half-open `[valid_from, valid_until)`. The envelope must contain the entire proposition interval. This is an asserted domain of the represented observation or model, distinct from its original observation time, maximum age and assessment time. Historical propositions can therefore be considered after the episode, subject to evidence freshness and applicable assumptions. The interval does not prove uninterrupted physical behaviour. Temporal trace coverage is separately checked in the trace's own time axis; mapping an episode's real clock to that axis remains part of the collector's asserted interpretation.

## Composition and compatibility

Every argument supporting a typed claim requires a `binding` to the one designated computational evidence source for its method. Binding an unrelated backing observation, omitting the binding on an alternative route, or using a method with an incompatible result type is a static error. A typed claim may be reused as a premise. Reuse preserves its identity; it does not turn repeated use into independent observations or automatically inject it into another method's mathematical inputs. Those inputs remain explicit in that method's query.

A completed computation with a negative finding can support an explicitly negative predicate, such as `result "entailed" == false` or `result "holds" == false`. Inconsistent logical premises, incomplete temporal coverage and execution errors remain unusable. Method-level `require` predicates remain available; both those predicates and the proposition predicate must hold. In EAL/0.2 a typed proposition supplies the required output predicate itself. Untyped computational claims still require a method-level predicate.

EAL/0.1 retains its existing semantics; using `proposition` or `binding` constructs requires EAL/0.2. Newly introduced words are contextual and can still be identifiers in existing source. EAL/0.3 permits host-registered method extensions through the same typed binding contracts; see [method extensions](method-extensions.md). Custom dimensions, vectors, quantified physical formulae and general dimensional algebra remain outside this scalar fragment.

## Canonical source

`format_source(source)` parses, validates and emits canonical source from the typed intermediate representation. `format_program(program)` performs the same translation for an AST. Invalid source is rejected rather than silently repaired. `semantic_ir(program)` supplies a source-independent dictionary for parse–format–parse comparisons. The CLI and MCP formatting operation use this implementation.

Canonical formatting preserves formal meaning, including queries, types and bindings; it does not preserve comments or declaration order across categories. The exact source digest changes when its bytes change, so existing observation records must be recollected or explicitly rebound through the normal collection workflow. Formatting never edits their provenance.
