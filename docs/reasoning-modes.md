# Executable reasoning methods

A reasoning declaration selects an operation appropriate to the evidence and states result requirements. A claim may depend on several subarguments using different operations. The interpreter evaluates their dependencies before using their results. These operations support engineering reasoning; they do not reduce reasoning to one universal inference operation.

The implemented methods form a bounded computational vocabulary, rather than an exhaustive taxonomy of human reasoning. `structured/1` preserves an explicitly authored relationship. The other methods calculate properties of a particular logical case, statistical sample, hypothesis model, experiment, causal model, feature mapping or finite trace. An optional installed method constructs and evaluates one finite ASPIC+ theory. Question formation, explanation construction, model selection and the interpretation of natural-language claims remain authored activities. Subarguments can supply reasons for their modelling choices and evidence relevance.

## Contents

1. [Contextual interpretation and enthymemes](#contextual-interpretation-and-enthymemes)
2. [Composition and result requirements](#composition-and-result-requirements)
3. [Evidence value schemas](#evidence-value-schemas)
4. [Bounds, failure behaviour and extensions](#bounds-failure-behaviour-and-extensions)
5. [Implementation structure](#implementation-structure)

## Contextual interpretation and enthymemes

Before selecting a method, identify the argument that the source actually expresses. An enthymeme can leave a premise, conclusion or inferential connection implicit; a local omission may be supplied elsewhere. [Contextual interpretation and reconstruction](argument-reconstruction.md) uses whole–part reading to recover such dependencies, retain alternative readings and distinguish reconstruction from a proposed repair. An invalid inference need not have a faithful completion. The reconstructed argument still needs a method appropriate to its intended support and evidence for its empirical dependencies.

This is an authoring procedure, not an additional executable reasoning mode. A reasoning-capable, long-context LLM can be evaluated as an implementation for proposing readings; EAL has no installed whole-document reconstruction operation. In particular, `abductive/1` ranks supplied hypotheses rather than discovering missing premises, and a solver's successful entailment check cannot establish fidelity to the prose. See the [worked load-test reading](../examples/api-load-test/README.md#reconstruct-an-abbreviated-performance-argument).

## Composition and result requirements

The argument graph composes claims through `premises`. Each premise must have its own supporting argument; dependent support is recalculated when a premise, condition, assumption or observation becomes unavailable or contested. Independent alternative arguments can support the same claim.

For example, a reliability claim can depend on an inductive subargument about a sampled failure proportion, a temporal subargument about an observed operating interval, and a deductive subargument about a finite propositional consequence. Their results keep their distinct meanings. The interpreter neither averages those results into one confidence number nor treats repeated use of a record as independent corroboration.

An untyped computational conclusion requires a `require` predicate on the reasoning result. A typed proposition supplies its own checked output condition; it can also retain reasoning predicates. For example:

```eal
reasoning estimate_reliability {
  method "inductive/1"
  rationale "The declared Bernoulli sample estimates success probability under the stated operating conditions."
  backing [test_sample]
  require "lower" >= 0.95
}
```

The predicate refers to a scalar field in `details`, without a `details.` prefix. Consult the [language reference](language.md) for full declaration syntax and the [API load-test example](../examples/api-load-test/README.md) for one complete programme with an installed typed method.

A successful method calculation establishes its documented computational result. The argument's result predicates specify the threshold needed for the conclusion. The relevance of that threshold to an authored natural-language claim remains an explicit part of the reasoning rationale. In particular, propositional atoms are supplied symbols: EAL/3 does not translate claim prose into logical formulae or prove that a supplied formula expresses that prose.

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

The host-installed `argumentation/aspic/1` method adds `aspic_theory` evidence, finite strict/defeasible argument construction, undermining, rebutting and undercutting defeats, and grounded acceptance. Its [exact theory schema, preference rule, bounds and example](aspic-method.md) are separate from the core EAL objection calculus. Install it explicitly through `--methods eal.aspic:aspic_registry`.

The computation helper returns `{status, reasons, details, method}`, with the selected `evidence_id` beside `details` for computational methods. `details` contains only method output, so a declared result field named `evidence_id` cannot be overwritten by execution metadata. Here `supported` means that the bounded calculation or authored-support check succeeds; the argument evaluator separately checks result requirements, scope, observation freshness, assumptions, premise status and objections. `unsupported` means insufficient input, malformed input, an exceeded computational bound, or a method-specific inability to use the computation. An inconsistent logical case and an incomplete temporal sampling contract are unusable in this profile. A consistent countermodel or an observed temporal violation is a usable result: a requirement such as `require "entailed" == false` or `require "holds" == false` can support a claim about that failure. A probability estimate, contrast or feature-match fraction can be validly calculated even when it fails an argument's required threshold.

## Evidence value schemas

For an untyped claim, the following objects are the designated evidence record's `value`. For a typed proposition they are its `EAL/typed-input/1` envelope's `payload`, after the [formal correspondence check](language.md#typed-propositions-and-observations). Execution provenance, collection time, tool identity and environment belong to the surrounding evidence record. Fields shown are mandatory and additional fields in these schema objects are rejected. All numbers must be finite. Booleans are not numbers. Units must be normalised consistently before calculation; the scalar proposition system checks its closed quantity/unit catalogue; general dimensional algebra is not implemented.

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

For success count $k$, trial count $n$, $\hat p=k/n$, confidence level $c$ and standard-normal quantile $z=\Phi^{-1}((1+c)/2)$, the implemented Wilson interval has centre and half-width

$$
\begin{aligned}
m &= \frac{\hat p+z^2/(2n)}{1+z^2/n},\\
h &= \frac{z\sqrt{\hat p(1-\hat p)/n+z^2/(4n^2)}}{1+z^2/n}.
\end{aligned}
$$

The endpoints are $m-h$ and $m+h$, clipped to $[0,1]$ for floating-point round-off. Result fields include `estimate`, `lower`, `upper`, `sample_size`, `successes`, `confidence`, `method: "wilson_score"` and `interpretation: "approximate_frequentist"`. The example produces approximately `[0.6086905, 0.9113942]`.

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

For supplied candidates $H_i$ and the described observation $E$, the calculation uses

$$
P(H_i\mid E)=\frac{P(H_i)P(E\mid H_i)}{\sum_jP(H_j)P(E\mid H_j)}.
$$

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

$$
\widehat\Delta=\bar Y_T-\bar Y_C,\qquad
\widehat{\mathrm{SE}}=\sqrt{s_T^2/n_T+s_C^2/n_C},
$$

where each $s^2$ is the unbiased sample variance using divisor $n-1$. Results include `estimate`, `standard_error`, both group means, both group sizes and `sample_size`. Each group requires 2–10,000 observations. The example gives effect estimate 3 and standard error $\sqrt{5/3}$.

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

$$
X_i=b_i+\sum_{j\in\mathrm{pa}(i)}a_{ij}X_j+u_i.
$$

`intercept` supplies $b_i$, `coefficients` supplies the parent coefficients and `noise` supplies the realised exogenous value $u_i$. Every parent must be a declared variable. The graph must be acyclic, including explicitly listed zero-coefficient dependencies. The interpreter evaluates the factual model in topological order, replaces the intervention variable's equation by its supplied value, and evaluates the modified model with the **same** exogenous values.

Results include `factual`, `counterfactual`, `difference`, `factual_values`, `counterfactual_values`, `outcome` and `evaluation_order`. The example gives factual `y = 11`, counterfactual `y = 15` and difference 4. Setting `x` replaces its whole equation, including its noise term.

The result is conditional on the supplied equations and realised exogenous values. Those values must already be known or justified elsewhere. The method does not infer hidden noise from observations, identify a causal graph, estimate coefficients, or compute a distribution over possible exogenous states. It implements the intervention and prediction steps for a bounded model. There are at most 32 variables and one intervention per calculation.

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

A trace with a gap can have `holds: true` and `coverage: false`. A complete trace containing a violating sample has `holds: false` and `coverage: true`. This distinction prevents sample agreement from concealing missing observations. Even complete coverage establishes no continuous-time property between samples and makes no claim about times outside the interval. The method implements neither eventuality nor full temporal logic. The caller must use another explicit model to justify interpolation or continuous-time bounds. A trace contains 1–10,000 events.

## Bounds, failure behaviour and extensions

Calculations preserve integer counts, timestamp coordinates and scalar comparisons. Causal means and their contrast are accumulated as exact rational values of the supplied numbers; integral results stay integers and other results are rounded only for output. The causal standard error combines standard deviations without first squaring small floating-point values. A nonzero causal mean, contrast or standard error that cannot be represented without becoming zero yields an unsupported result. Entirely integer affine structural equations preserve integer arithmetic. Other statistical calculations and mixed floating-point structural equations use double-precision arithmetic. Numeric input magnitude is at most `1e100`; structural intermediate values have the same bound. Real-number equality is a computational comparison, not measurement equivalence. Underflow of extremely small posterior terms or variance terms can still occur after stable calculation, so inputs requiring arbitrary precision need a different backend.

A supplied calculation value is checked before evaluation: at most 100,000 JSON nodes, nesting depth 64, 10,000 items per array or object and 4,096 characters per string. Every computational method also enforces its registered input/output schemas and serialised byte bounds; formula, candidate, feature and structural-model limits apply in addition. Unknown fields, unsupported schema forms, nonfinite numbers, invalid references, cycles and exceeded limits return an explicit unsupported result. There is no evaluation of embedded Python, shell commands or unbounded symbolic search in these methods.

### Host-registered methods

An operator can register a new pure calculation without adding grammar keywords. Source selects its exact versioned method identifier, for example `method "engineering/rms/1"`, but cannot import the implementation. A `MethodContract` declares one evidence kind, bounded input/query/output schemas, claim-addressable output paths, compatible quantity and unit rules, trusted implementation function, implementation version and resource limits. Built-ins use the same binding and schema checks. Duplicate identities and unknown schema features fail registration. A new method needs a mathematical interpretation, independently known reference cases, malformed-input and limit cases, and explicit modelling assumptions; a registered type contract alone cannot establish mathematical correctness.

Custom functions execute in a fresh POSIX worker with time, address-space, CPU, JSON-size and output bounds. Startup has a separate five-second wall-clock deadline. After startup, the registered `timeout_seconds` bounds execution wall time; the cumulative OS CPU limit adds that allowance to CPU already consumed during startup, rounded up to whole seconds. The address-space limit applies to the whole worker. This boundary controls resources; it does not sandbox filesystem or network access or prove purity. Runtime checks a loaded entry-point code digest against the registered digest, and discovery/assessments record the method-registry fingerprint. These identify declared code and contracts, but do not hash every imported dependency or guarantee reproducibility of an external environment. Changing a method's meaning calls for a new identifier/version and preserved dependencies. The maintained [API load-test case](../examples/api-load-test/README.md) installs `engineering/api-load-criteria/1` explicitly. It accepts count, nearest-rank p95 and failed-request percentage; it returns separate threshold results and `passes`/`fails` booleans. The source qualifies the report's identity, completeness and age before this method runs. A threshold failure can support the explicit negative claim; collection failure supports neither claim.

An LLM can propose a declaration or model through a host; the server reports the bounded computation and dependencies without pretending that the model itself has been established.

The foundations and the limits of each correspondence are documented in [sources.md](sources.md). The relationships among claims, objections and supporting subarguments are specified in [argument-model.md](argument-model.md).

## Implementation structure

Each built-in mode has its own module in `src/eal/reasoning/` and one immutable
`BuiltinStrategy` object containing its name and computational function.
`deductive.py`, `inductive.py`, `abductive.py`, `causal.py`, `counterfactual.py`,
`analogical.py`, `temporal.py` and `structured.py` own their respective
implementations. `validation.py` owns shared JSON bounds and domain validators.
`builtin_methods.py` remains the single source of versioned method schemas.

This is a Strategy design using first-class functions. The objects select pure
algorithms; the functions need no per-instance state or inheritance. The package
registry contains selection only. A new computational algorithm changes its own
module and registration/specification, without adding algorithm branches to
`modes.py`. A table of functions in separate modules would also be sufficient;
the immutable strategy record makes each name/function association explicit.
Command would add no useful behaviour here: computations have no queued action,
undo or replay lifecycle. If named strategy records cease to aid registration,
the records can be reduced to a function mapping.

`modes.py` is the assessment facade: it selects evidence, applies shared schema
and resource checks and attaches provenance. `structured/1` deliberately retains
a distinct availability check because it uses authored evidence or premise
support, rather than one designated computational input. Its marker cannot be
substituted for a numerical or logical proof. Custom methods retain their bounded
worker execution path.

At registration, `MethodRegistry` captures the strategy's function. Assessment
executes that captured function, so changing the selection table cannot redirect
an existing registered contract. Source and executable digests, schemas, method
versions and the CPython 3.12 registry fingerprint remain checked against the
existing snapshot. Mathematical reference cases, negative findings, malformed
inputs, resource boundaries and post-registration code changes have separate
tests. These checks establish the retained contracts; they do not establish
general reasoning coverage or model performance.

The design separates independently changing algorithms (single responsibility),
keeps the common assessment path stable when adding methods (open–closed),
requires each registered implementation to preserve its own declared input and
output contract (substitution), exposes a single computation callback (interface
segregation), and makes assessment depend on a registered contract rather than a
concrete algorithm (dependency inversion). Different method meanings remain
explicit; SOLID does not make Wilson estimation interchangeable with deduction.
