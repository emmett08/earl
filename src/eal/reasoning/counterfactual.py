"""Evaluate a single intervention in an acyclic affine causal model."""
from __future__ import annotations

import math

from .strategy import BuiltinStrategy
from .validation import _name, _number, _object, _result


def _counterfactual(value):
    _object(value, ("variables", "intervention", "outcome"), "causal_model")
    variables = value["variables"]
    if not isinstance(variables, dict) or not 1 <= len(variables) <= 32:
        raise ValueError("variables must contain 1..32 structural equations")
    equations = {}
    for name, equation in variables.items():
        _name(name, "variable name")
        _object(equation, ("intercept", "coefficients", "noise"), "structural equation")
        coefficients = equation["coefficients"]
        if not isinstance(coefficients, dict) or len(coefficients) > 32:
            raise ValueError("coefficients must map at most 32 variables to numbers")
        if any(parent not in variables for parent in coefficients):
            raise ValueError("Structural equation references an unknown parent variable")
        equations[name] = (_number(equation["intercept"], "intercept"),
                           {parent: _number(c, "coefficient") for parent, c in coefficients.items()},
                           _number(equation["noise"], "noise"))
    _object(value["intervention"], ("variable", "value"), "intervention")
    changed = _name(value["intervention"]["variable"], "intervention variable")
    outcome = _name(value["outcome"], "outcome")
    if changed not in equations or outcome not in equations:
        raise ValueError("Intervention and outcome must name declared variables")
    setting = _number(value["intervention"]["value"], "intervention value")
    order = []
    remaining = dict(equations)
    while remaining:
        ready = sorted(name for name, (_, parents, _) in remaining.items()
                       if all(parent in order for parent in parents))
        if not ready:
            raise ValueError("Structural equations must be acyclic, including zero-coefficient references")
        for name in ready:
            order.append(name)
            del remaining[name]

    def solve(intervene):
        result = {}
        for name in order:
            intercept, parents, noise = equations[name]
            if intervene and name == changed:
                result[name] = setting
            else:
                terms = [intercept, noise, *(c * result[parent] for parent, c in parents.items())]
                result[name] = sum(terms) if all(type(term) is int for term in terms) else math.fsum(terms)
            _number(result[name], "Computed structural value")
        return result

    factual, counterfactual = solve(False), solve(True)
    return _result(True, "Intervention evaluated in an acyclic affine model with the same supplied exogenous values",
                   factual=factual[outcome], counterfactual=counterfactual[outcome],
                   difference=counterfactual[outcome] - factual[outcome],
                   factual_values=factual, counterfactual_values=counterfactual,
                   outcome=outcome, evaluation_order=order, assumptions_verified=False)


STRATEGY = BuiltinStrategy("counterfactual", _counterfactual)
