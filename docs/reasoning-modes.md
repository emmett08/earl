# Executable reasoning methods

A reasoning declaration selects an operation appropriate to the evidence and states result requirements. A claim may depend on several subarguments using different operations. The interpreter evaluates their dependencies before using their results. These operations support engineering reasoning; they do not reduce reasoning to one universal inference operation.

The implemented methods form a bounded computational vocabulary, rather than an exhaustive taxonomy of human reasoning. `structured/1` preserves an explicitly authored relationship. The other methods calculate properties of a particular logical case, statistical sample, hypothesis model, experiment, causal model, feature mapping or finite trace. Question formation, explanation construction, model selection and the interpretation of natural-language claims remain authored activities. Subarguments can supply reasons for their modelling choices and evidence relevance.

## Composition and result requirements

The argument graph composes claims through `premises`. Each premise must have its own supporting argument; dependent support is recalculated when a premise, condition, assumption or observation becomes unavailable or contested. Independent alternative arguments can support the same claim.

For example, a reliability claim can depend on an inductive subargument about a sampled failure proportion, a temporal subargument about an observed operating interval, and a deductive subargument about a finite propositional consequence. Their results keep their distinct meanings. The interpreter neither averages those results into one confidence number nor treats repeated use of a record as independent corroboration.

An untyped computational conclusion requires a `require` predicate on the reasoning result. A typed proposition supplies its own checked output condition; it can also retain reasoning predicates. For example:

```eal
reasoning estimate_reliability {
  method "inductive/1";
  rationale "The declared Bernoulli sample estimates success probability under the stated operating conditions.";
  backing test_sample;
  require "lower" >= 0.95;
}
```

The predicate refers to a scalar field in `details`, without a `details.` prefix. Consult the [language reference](language.md) for full declaration syntax and the working examples for complete programmes.

A successful method calculation establishes its documented computational result. The argument's result predicates specify the threshold needed for the conclusion. The relevance of that threshold to an authored natural-language claim remains an explicit part of the reasoning rationale. In particular, propositional atoms are supplied symbols: this version does not automatically translate claim prose into logical formulas or prove that a supplied formula expresses that prose.

The calculation uses the union of direct argument evidence, reasoning backing and assumption-validation evidence, deduplicated by evidence identifier. Each computational method requires **exactly one** record with its designated kind. Records of other kinds may support the same argument. Multiple designated records are rejected as ambiguous; any aggregation must be an explicit prior operation with a stated sampling or dependence model. Supporting premise claims remain graph dependencies, rather than being silently converted to observations or logical atoms.

| Method | Designated kind | Result the implementation calculates |
|---|---|---|
| `structured/1` | No designated kind | Availability of authored support; no automatic proof of its sufficiency |
| `deductive/1` | `logical_case` | Finite propositional entailment and premise satisfiability |
| `inductive/1` | `sample` | Binomial proportion estimate and Wilson interval |
| `abductive/1` | `hypotheses` | Bayesian posterior over supplied candidate explanations |
| `causal/1` | `experiment` | Difference of means and independent-group standard error |
| `counterfactual/1` | `causal_model` | Intervention outcome in a supplied acyclic affine structural model |
| `analogical/1` | `analogy` | Exact correspondence of declared relevant scalar features |
| `temporal/1` | `trace` | A universal sample predicate and declared sampling-contract coverage |

The computation helper returns `{status, reasons, details}`. Here `supported` means that the bounded calculation or authored-support check succeeds; the argument evaluator separately checks result requirements, scope, observation freshness, assumptions, premise status and objections. `unsupported` means insufficient input, malformed input, an exceeded computational bound, or a method-specific inability to use the computation. An inconsistent logical case and an incomplete temporal sampling contract are unusable in this profile. A consistent countermodel or an observed temporal violation is a usable result: a requirement such as `require "entailed" == false;` or `require "holds" == false;` can support a claim about that failure. A probability estimate, contrast or feature-match fraction can be validly calculated even when it fails an argument's required threshold.

## Evidence value schemas

The following objects are the `value` of an evidence record. Execution provenance, collection time, tool identity and environment belong to the surrounding evidence record. Fields shown are mandatory and additional fields in these schema objects are rejected. All numbers must be finite. Booleans are not numbers. Units must be normalised consistently before calculation; the scalar proposition system checks its closed quantity/unit catalogue; general dimensional algebra is not implemented.

### Structured reasoning

`structured/1` requires at least one supplied evidence record or a usable premise claim. The evaluator checks actual availability first. A contested premise remains usable for calculating the structure, while the surrounding argument retains its contested status. Result fields are `authored: true` and `mechanically_proved: false`. No numeric confidence is manufactured from authored prose.

### Deductive reasoning

```json
{
  "premises": ["p", {"implies": ["p", "q"]}],
  "conclusion": "q"
}
```

A formula is an atom string or an object with exactly one of these keys: `not` takes one formula; `and` and `or` take a list of at least two formulas; `implies` takes exactly two. Atoms are case-sensitive identifiers. All valuations of the distinct atoms are enumerated. The result includes `entailed`, `consistent_premises`, `counterexample`, `atoms`, `valuations` and `satisfying_premise_valuations`.

`entailed` has its classical meaning: every valuation satisfying the premises satisfies the conclusion. When the premises are inconsistent, classical entailment is vacuously true, `consistent_premises` is false, and the method returns `unsupported`. A consistent case with a countermodel returns `supported` with `entailed: false`; an argument can use that result to establish non-entailment. Its declared result predicate decides whether that finding supports its conclusion. An empty premise list is allowed when testing a tautology.

The finite domain is at most 12 atoms, 128 premise formulas, 512 formula nodes in total and formula depth 32. This implements propositional entailment only. First-order quantification, arithmetic proof and natural-language validity require another explicitly integrated reasoning operation.

### Inductive reasoning

```json
{"successes": 20, "trials": 25, "confidence": 0.95}
```

For success count \(k\), trial count \(n\), \(\hat p=k/n\), confidence level \(c\) and standard-normal quantile \(z=\Phi^{-1}((1+c)/2)\), the implemented Wilson interval has centre and half-width

\[
 m=\frac{\hat p+z^2/(2n)}{1+z^2/n},\qquad
 h=\frac{z\sqrt{\hat p(1-\hat p)/n+z^2/(4n^2)}}{1+z^2/n}.
\]

The endpoints are \(m-h\) and \(m+h\), clipped to \([0,1]\) for floating-point round-off. Result fields include `estimate`, `lower`, `upper`, `sample_size`, `successes`, `confidence`, `method: "wilson_score"` and `interpretation: "approximate_frequentist"`. The example produces approximately `[0.6086905, 0.9113942]`.

The sampling model assumes independent Bernoulli observations with a common success probability and an appropriate sampling/stopping procedure. The record's counts do not establish those assumptions. The interval has nominal approximate repeated-sampling coverage; its confidence level is not a posterior probability that the fixed parameter lies inside this realised interval. It does not supply an exact guarantee or repair selection bias, dependent sampling, repeated optional inspection or a changing population. Those issues require explicit modelling or a different statistical procedure.

`trials` is an integer from 1 to 1,000,000,000; `successes` is an integer between zero and `trials`; `confidence` lies in `[0.001, 0.999999]`.

### Abductive reasoning

```json
{
  "observed": "The measured output is absent",
  "candidates": [
    {"name": "power_fault", "prior": 0.2, "likelihood": 0.8},
    {"name": "other_condition", "prior": 0.8, "likelihood": 0.1}
  ]
}
```

For supplied candidates \(H_i\) and the described observation \(E\), the calculation uses

\[
P(H_i\mid E)=\frac{P(H_i)P(E\mid H_i)}{\sum_jP(H_j)P(E\mid H_j)}.
\]

Each `likelihood` is the probability of the **whole supplied observation** under that hypothesis. The implementation never decomposes it into independent products. Priors must sum to one within absolute tolerance `1e-9`; that finite-precision tolerance is normalised. Candidate names must be unique, with 2–128 candidates. Computation uses logarithms to avoid premature underflow of prior–likelihood products.

Results include `posterior`, `best`, `best_posterior`, `ties` and `log_evidence_probability`. A numerical tie within absolute posterior tolerance `1e-12` yields `best: null` and lists the tied names. An observation assigned probability zero by every candidate yields `unsupported` with an empty posterior. This result calls for revising the model or observation, rather than choosing a candidate arbitrarily.

The interpretation requires the supplied hypotheses to be mutually exclusive and exhaustive for the model, and their priors and likelihoods to be justified. These assumptions are not verified by normalisation. The implementation ranks supplied explanations; it neither discovers hypotheses nor establishes that the best explanation is true. A low-probability omitted explanation cannot be detected from this input alone.

### Causal reasoning

```json
{
  "assignment": "randomised",
  "treatment": [3, 5, 7],
  "control": [1, 2, 3]
}
```

The implemented calculation is a two-arm difference of means,

\[
\widehat\Delta=\bar Y_T-\bar Y_C,\qquad
\widehat{\mathrm{SE}}=\sqrt{s_T^2/n_T+s_C^2/n_C},
\]

where each \(s^2\) is the unbiased sample variance using divisor \(n-1\). Results include `estimate`, `standard_error`, both group means, both group sizes and `sample_size`. Each group requires 2–10,000 observations. The example gives effect estimate 3 and standard error \(\sqrt{5/3}\).

The standard error is an independent-group estimator. It is not a paired, repeated-measures, clustered or covariate-adjusted estimator. Under a finite-population completely randomised design, the same Neyman variance form generally estimates an upper bound on randomisation variance when treatment effects vary. Interpretation must therefore state the population, estimand and design.

`assignment: "randomised"` is required metadata, rather than proof that randomisation occurred. A causal interpretation additionally depends on the actual allocation procedure, consistency, absence of interference, handling of missing outcomes and the relation between the sample and the target population. This method supplies neither a p-value nor a causal-discovery procedure. Argument assumptions and subarguments must address the premises needed for the intended interpretation.

### Counterfactual reasoning

```json
{
  "variables": {
    "x": {"intercept": 1, "coefficients": {}, "noise": 2},
    "y": {"intercept": 4, "coefficients": {"x": 2}, "noise": 1}
  },
  "intervention": {"variable": "x", "value": 5},
  "outcome": "y"
}
```

Every variable has the affine structural equation

\[
X_i=b_i+\sum_{j\in\operatorname{pa}(i)}a_{ij}X_j+u_i.
\]

`intercept` supplies \(b_i\), `coefficients` supplies the parent coefficients and `noise` supplies the realised exogenous value \(u_i\). Every parent must be a declared variable. The graph must be acyclic, including explicitly listed zero-coefficient dependencies. The interpreter evaluates the factual model in topological order, replaces the intervention variable's equation by its supplied value, and evaluates the modified model with the **same** exogenous values.

Results include `factual`, `counterfactual/1`, `difference`, `factual_values`, `counterfactual_values`, `outcome` and `evaluation_order`. The example gives factual `y = 11`, counterfactual `y = 15` and difference 4. Setting `x` replaces its whole equation, including its noise term.

The result is conditional on the supplied equations and realised exogenous values. Those values must already be known or justified elsewhere. This version does not infer hidden noise from observations, identify a causal graph, estimate coefficients, or compute a distribution over possible exogenous states. It implements the intervention and prediction steps for a bounded model, rather than a complete counterfactual discovery or abduction system. There are at most 32 variables and one intervention per calculation.

### Analogical reasoning

```json
{
  "relevant_features": ["protocol", "voltage"],
  "source": {"protocol": "i2c", "voltage": 3.3},
  "target": {"protocol": "i2c", "voltage": 5}
}
```

Every declared relevant feature must appear in both maps. Values are JSON scalars; equality is exact, except integers and floating-point numbers use numeric equality. Booleans remain distinct from numbers. Results include `complete`, `matched`, `feature_count`, `match_fraction`, `mismatches`, `missing` and `interpretation: "feature_correspondence"`. The example has complete mapping and match fraction 0.5. Missing mappings produce `unsupported`, `complete: false` and `match_fraction: null`.

This is a bounded feature-correspondence operation. It is not a full relational structure-mapping engine. The fraction measures agreement on the declared feature list, rather than a calibrated probability, causal correspondence or justified transfer of the source conclusion. Feature relevance, omitted differences and a proposed conclusion transfer require authored reasoning and supporting subarguments. There are 1–256 unique relevant features.

### Temporal reasoning

```json
{
  "semantics": "sampled",
  "start": 0,
  "end": 2,
  "max_gap": 1,
  "events": [
    {"time": 0, "value": 3},
    {"time": 1, "value": 4},
    {"time": 2, "value": 3}
  ],
  "property": {"operator": "lt", "value": 5}
}
```

Times use one declared numeric time coordinate. Events must be strictly ordered and lie inside the inclusive `[start, end]` interval. Coverage requires an observation exactly at each endpoint and every consecutive observation gap to be at most `max_gap`. A zero-duration interval is allowed with one sample; `max_gap` remains strictly positive.

The comparison operator is one of `lt`, `le`, `eq`, `ne`, `ge` or `gt`. `holds` means that **every supplied sample** satisfies the comparison. `coverage` means that the declared sampling contract is complete. The method is usable whenever coverage is complete; the argument must require the truth value of `holds` appropriate to its claim. A complete trace containing a violation can therefore support a claim that the sampled property was violated. Results also include `sample_size`, `largest_gap`, `violation_count`, `violation_times`, `semantics: "sampled"` and `continuous_truth_established: false`.

A trace with a gap can have `holds: true` and `coverage: false`. A complete trace containing a violating sample has `holds: false` and `coverage: true`. This distinction prevents sample agreement from concealing missing observations. Even complete coverage establishes no continuous-time property between samples and makes no claim about times outside the interval. This version implements neither eventuality nor full temporal logic. The caller must use another explicit model to justify interpolation or continuous-time bounds. A trace contains 1–10,000 events.

## Bounds, failure behaviour and extension

Calculations preserve integer counts, timestamp coordinates and scalar comparisons. Statistical estimates and structural-equation evaluation use ordinary double-precision arithmetic. Numeric input magnitude is at most `1e100`; structural intermediate values have the same bound. Real-number equality is a computational comparison, not measurement equivalence. Underflow of extremely small posterior terms or variance terms can still occur after stable calculation, so inputs requiring arbitrary precision need a different backend.

A supplied calculation value is checked before evaluation: at most 100,000 JSON nodes, nesting depth 64, 10,000 items per array or object and 4,096 characters per string. Formula, candidate, feature and structural-model limits apply in addition. Unknown fields, unsupported schema forms, nonfinite numbers, invalid references, cycles and exceeded limits return an explicit unsupported result. There is no evaluation of embedded Python, shell commands or unbounded symbolic search in these methods.

Adding a method requires a distinct evidence contract, mathematical interpretation, declared computational bound, reference cases with independently known results, malformed-input cases and a documented statement of the assumptions that the calculation cannot verify. An LLM can propose a declaration or model through a host; the server reports the bounded computation and dependencies without pretending that the model itself has been established.

The foundations and the limits of each correspondence are documented in [sources.md](sources.md). The relationships among claims, objections and supporting subarguments are specified in [argument-model.md](argument-model.md).
