"""Perturb unobserved rerun variation without treating two pilot paths as truth."""
from __future__ import annotations

import math
import random
import statistics


def resource_multiplier(totals: list[float], rng: random.Random, *,
                        variance_inflation: float = 1., unseen_cv: float = 0.) -> float:
    """Mean-one positive noise restoring sample variance, with declared sensitivity.

    For an empirical draw X and independent M, E[M]=1 gives
    Var(XM)=Var(X)+E[X²]Var(M). The empirical variance is (n-1)/n
    times the unbiased sample variance. The noise corrects that deficit and
    adds explicit uncertainty; it is a model, not discovery of an unseen tail.
    """
    if len(totals) < 2 or not all(math.isfinite(x) and x >= 0 for x in totals):
        return 1.
    second = statistics.mean(x * x for x in totals)
    if not second:
        return 1.
    target_variance = statistics.variance(totals) * variance_inflation
    multiplier_variance = max(0., (target_variance - statistics.pvariance(totals)) / second) + unseen_cv ** 2
    sigma2 = math.log1p(multiplier_variance)
    return math.exp(rng.gauss(-sigma2 / 2, math.sqrt(sigma2))) if sigma2 else 1.


def changed_quality(correct: int, incorrect: int, baseline: float | None,
                    target: float | None, draw: float) -> int:
    if baseline is None or target is None or not 0 <= target <= 1:
        return correct
    if target > baseline and draw < (target - baseline) / (1 - baseline):
        return correct + incorrect
    if target < baseline and draw < (baseline - target) / baseline:
        return 0
    return correct
