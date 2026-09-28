"""Condition a supplied finite hypothesis distribution on its likelihoods."""
from __future__ import annotations

import math

from .strategy import BuiltinStrategy
from .validation import _list, _name, _object, _probability, _result, _text


def _abductive(value):
    _object(value, ("observed", "candidates"), "hypotheses")
    _text(value["observed"], "observed evidence description")
    candidates = _list(value["candidates"], "candidates", minimum=2, maximum=128)
    priors, log_weights = {}, {}
    for item in candidates:
        _object(item, ("name", "prior", "likelihood"), "hypothesis")
        name = _name(item["name"], "hypothesis name")
        if name in priors:
            raise ValueError("Hypothesis names must be unique")
        prior = _probability(item["prior"], "prior")
        likelihood = _probability(item["likelihood"], "likelihood")
        priors[name] = prior
        log_weights[name] = (math.log(prior) + math.log(likelihood)
                             if prior > 0 and likelihood > 0 else -math.inf)
    total_prior = math.fsum(priors.values())
    if not math.isclose(total_prior, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Prior probabilities must sum to 1 within absolute tolerance 1e-9")
    maximum = max(log_weights.values())
    if maximum == -math.inf:
        return _result(False, "The supplied hypotheses assign zero probability to the observed evidence",
                       posterior={}, best=None, ties=[], assumptions_verified=False)
    weights = {name: math.exp(weight - maximum) for name, weight in log_weights.items()}
    normaliser = math.fsum(weights.values())
    posterior = {name: weight / normaliser for name, weight in weights.items()}
    best_probability = max(posterior.values())
    ties = sorted(name for name, probability in posterior.items()
                  if math.isclose(probability, best_probability, rel_tol=0.0, abs_tol=1e-12))
    return _result(True, "Posterior probabilities computed within the supplied finite hypothesis model",
                   posterior=posterior, best=ties[0] if len(ties) == 1 else None,
                   best_posterior=best_probability, ties=ties if len(ties) > 1 else [],
                   log_evidence_probability=maximum + math.log(normaliser) - math.log(total_prior),
                   assumptions_verified=False)


STRATEGY = BuiltinStrategy("abductive", _abductive)
