"""Calculate the independent-group mean contrast and standard error."""
from __future__ import annotations

import math
from fractions import Fraction
from statistics import stdev

from .strategy import BuiltinStrategy
from .validation import _list, _number, _object, _result


def _causal(value):
    _object(value, ("assignment", "treatment", "control"), "experiment")
    if value["assignment"] != "randomised":
        raise ValueError("This causal calculation requires declared randomised assignment")
    groups = []
    for name in ("treatment", "control"):
        groups.append([_number(item, name) for item in _list(value[name], name, minimum=2)])
    treatment, control = groups
    # Subtract the represented means before rounding: two large, neighbouring
    # integer means must not collapse to the same binary64 value and erase an
    # observed treatment effect. Fraction also retains each supplied float's
    # exact binary value; it does not infer additional measurement precision.
    mt = sum(map(Fraction, treatment), Fraction()) / len(treatment)
    mc = sum(map(Fraction, control), Fraction()) / len(control)
    def numeric(value):
        rounded = value.numerator if value.denominator == 1 else float(value)
        if value and rounded == 0:
            raise ValueError("Computed mean or contrast underflows the representable number range")
        return rounded

    # Compute standard deviations before combining their contributions. Forming
    # floating variances first can underflow even when the final square root is
    # representable (for example, a standard error of 1e-200).
    se = math.hypot(stdev(treatment) / math.sqrt(len(treatment)),
                    stdev(control) / math.sqrt(len(control)))
    if se == 0 and any(any(item != group[0] for item in group) for group in groups):
        raise ValueError("Computed standard error underflows the representable number range")
    return _result(True, "Randomised two-group mean contrast computed; assignment and causal assumptions require evidence",
                   estimate=numeric(mt - mc), standard_error=se,
                   treatment_mean=numeric(mt), control_mean=numeric(mc),
                   treatment_size=len(treatment), control_size=len(control),
                   sample_size=len(treatment) + len(control), assumptions_verified=False)


STRATEGY = BuiltinStrategy("causal", _causal)
