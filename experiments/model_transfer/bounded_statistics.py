"""Finite-sample bounds for independent bounded trajectory outcomes.

Maurer and Pontil (2009), Theorem 11, arXiv:0907.3740, permits different
distributions. Missing values are handled by envelopes around latent outcomes;
no independence assumption is made about the missingness process.
"""
from __future__ import annotations

import math


def mean(values) -> float:
    return math.fsum(values) / len(values)


def sample_variance(values) -> float:
    centre = mean(values)
    return math.fsum((value - centre) ** 2 for value in values) / (len(values) - 1)


def bounded_radius(lower: list[float], upper: list[float], width: float,
                   tail_alpha: float, method: str = 'empirical_bernstein') -> float:
    if not lower or len(lower) != len(upper) or not 0 < tail_alpha < 1 or width <= 0:
        raise ValueError('Nonempty bounded observations and a valid tail probability are required')
    if any(not math.isfinite(a + b) or a > b or b - a > width for a, b in zip(lower, upper)):
        raise ValueError('Invalid observation envelopes')
    n = len(lower)
    if method == 'hoeffding':
        return width * math.sqrt(math.log(1 / tail_alpha) / (2 * n))
    if method != 'empirical_bernstein':
        raise ValueError('Unknown bounded mean method')
    if n < 2:
        return width
    midpoints = [(a + b) / 2 for a, b in zip(lower, upper)]
    # The centred Euclidean norm is a contraction. The triangle inequality
    # bounds the standard deviation of EVERY completion of the missing values.
    sd_upper = math.sqrt(sample_variance(midpoints)) + math.sqrt(
        sum(((b - a) / 2) ** 2 for a, b in zip(lower, upper)) / (n - 1))
    variance_upper = min(sd_upper ** 2, n * width ** 2 / (4 * (n - 1)))
    log_term = math.log(2 / tail_alpha)
    return math.sqrt(2 * variance_upper * log_term / n) + 7 * width * log_term / (3 * (n - 1))


def bounded_interval(lower: list[float], upper: list[float], support: tuple[float, float],
                     tail_alpha: float, method: str = 'empirical_bernstein') -> tuple[list[float], float]:
    if any(a < support[0] or b > support[1] for a, b in zip(lower, upper)):
        raise ValueError('Observation lies outside its declared support')
    radius = bounded_radius(lower, upper, support[1] - support[0], tail_alpha, method)
    return [max(support[0], mean(lower) - radius),
            min(support[1], mean(upper) + radius)], radius
