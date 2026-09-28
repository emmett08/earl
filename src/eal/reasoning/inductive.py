"""Estimate a binomial proportion using the Wilson score interval."""
from __future__ import annotations

import math
from statistics import NormalDist

from .strategy import BuiltinStrategy
from .validation import _integer, _number, _object, _result


def _inductive(value):
    _object(value, ("successes", "trials", "confidence"), "sample")
    n = _integer(value["trials"], "trials", minimum=1)
    k = _integer(value["successes"], "successes", maximum=n)
    confidence = _number(value["confidence"], "confidence")
    if not 0.001 <= confidence <= 0.999999:
        raise ValueError("confidence must be in [0.001, 0.999999]")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = k / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return _result(True, "Wilson interval computed under the stated binomial sampling model",
                   estimate=p, lower=max(0.0, centre - half), upper=min(1.0, centre + half),
                   sample_size=n, successes=k, confidence=confidence, method="wilson_score",
                   interpretation="approximate_frequentist", assumptions_verified=False)


STRATEGY = BuiltinStrategy("inductive", _inductive)
