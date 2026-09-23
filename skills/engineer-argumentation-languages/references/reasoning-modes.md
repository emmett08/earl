# Multiple reasoning modes and subarguments

Choose methods from the engineering question. Treat a mode’s evidence contract, computation, output interpretation and applicable assumptions as separate specifications. Compose local arguments into a claim/subargument graph; do not flatten a complex argument into a list of evidence.

| Mode | Required inputs | Bounded computation | Interpretive limit |
|---|---|---|---|
| Deductive | Formal premises and conclusion | Entailment check or checked derivation, including premise consistency | Establishes a relation between formulae under a specified logic; empirical premises still need support |
| Inductive | Sampling data, target population, sampling model | Estimate and stated uncertainty procedure | Generalisation depends on sampling assumptions; a confidence interval is not a probability of the fixed parameter |
| Abductive | Candidate explanations, priors and joint likelihood of observations | Comparative explanatory score or Bayesian posterior under the declared model | Ranking within supplied candidates does not prove the winning explanation or candidate completeness |
| Causal | Intervention/design information, treatment/outcome data and causal assumptions | Identified contrast or a stated causal-model computation | Association alone does not establish intervention effect; assignment metadata is a claim about design |
| Counterfactual | Structural model, factual/exogenous context and intervention | Recompute after replacing intervened equations with the same exogenous context | Result is conditional on the model and supplied context; fitted prediction alone is insufficient |
| Analogical | Source/target structures, relevant correspondences and transfer rationale | Verify mapping or bounded feature correspondence | Similarity is not truth preservation or a calibrated confidence score |
| Temporal | Timestamped observations, horizon, monitoring and gap contract | Evaluate a specified finite-trace property | Sampled observations do not establish continuous physical compliance without additional assumptions |
| Authored structured support | Declared premises, evidence and rationale | Conjunctive premise composition with alternative derivations | Applies an author-supplied support relation; it does not discover or prove the prose rationale |

For every implemented mode, specify a typed input schema, admissible values, resource limits, deterministic evaluator, explicit output fields, result predicates, failure cases and tests against known answers. Reject missing or mismatched evidence kinds. Retain model assumptions as named dependencies rather than hiding them in method prose. Keep extensions open to additional methods, such as numerical modelling, optimisation, mechanistic explanation and adversarial counterexample search, with their own contracts.

Example composition: a deductive subargument establishes a controller property for a mathematical model; an inductive subargument estimates observed failure frequency; a causal subargument estimates an intervention’s effect; a model-fit argument supports applicability to the device. Their conclusions become premises of a qualified engineering claim. An objection to model fidelity affects the arguments that require that model. Independent observations remain distinct and reusable.

When implementing a first bounded profile, say exactly which part of each method is computed. A feature comparison is a bounded analogy aid rather than a complete theory of analogical reasoning. A supplied-noise counterfactual calculation is distinct from recovering unobserved exogenous variables from factual observations. A finite trace calculation is distinct from general temporal theorem proving.
