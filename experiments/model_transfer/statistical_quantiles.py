"""Student t quantiles using the regularised incomplete beta and bisection.

No third-party dependency. Unlike a truncated asymptotic expansion, inversion
controls numerical error directly; it does not make a delta-method confidence
interval exact for a non-normal resource ratio.
"""
from __future__ import annotations

import math
import statistics


def _beta_fraction(a: float, b: float, x: float) -> float:
    """Modified Lentz evaluation of the incomplete-beta continued fraction."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d
    for m in range(1, 1001):
        twice = 2 * m
        aa = m * (b - m) * x / ((qam + twice) * (a + twice))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        result *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + twice) * (qap + twice))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        change = d * c
        result *= change
        if abs(change - 1.0) <= 4e-15:
            return result
    raise ArithmeticError('Incomplete-beta continued fraction did not converge')


def _regularised_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    scale = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        value = scale * _beta_fraction(a, b, x) / a
    else:
        value = 1.0 - scale * _beta_fraction(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, value))


def student_t_quantile(probability: float, degrees: float) -> float:
    """Numerically invert Student's t CDF for finite positive df or infinity."""
    if not math.isfinite(probability) or not 0.0 < probability < 1.0:
        raise ValueError('Quantile probability must be finite and in (0, 1)')
    if math.isnan(degrees) or degrees <= 0:
        raise ValueError('Degrees of freedom must be positive')
    if math.isinf(degrees):
        return statistics.NormalDist().inv_cdf(probability)
    if probability == 0.5:
        return 0.0
    if probability < 0.5:
        return -student_t_quantile(1.0 - probability, degrees)
    tail = 1.0 - probability

    def survival(value: float) -> float:
        root_ratio = math.sqrt(degrees) / value if value else math.inf
        # This form avoids overflowing value**2 for an extreme quantile.
        x = (root_ratio ** 2 / (1.0 + root_ratio ** 2)
             if root_ratio <= 1.0 else 1.0 / (1.0 + (value / math.sqrt(degrees)) ** 2))
        return 0.5 * _regularised_beta(x, degrees / 2.0, 0.5)

    low, high = 0.0, 1.0
    while survival(high) > tail:
        high *= 2.0
        if not math.isfinite(high):
            raise ArithmeticError('Student t quantile exceeds floating-point range')
    for _ in range(120):
        midpoint = (low + high) / 2.0
        if survival(midpoint) > tail:
            low = midpoint
        else:
            high = midpoint
        if high - low <= 4e-14 * max(1.0, high):
            break
    return (low + high) / 2.0
