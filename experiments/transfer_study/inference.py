"""Conservative finite-sample inference for independent matched cases.

Hoeffding (1963), Theorem 2: bounded, independent observations need not be
identically distributed. Missing observations widen the identified set.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomeBounds:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) for x in (self.lower, self.upper)) or self.lower > self.upper:
            raise ValueError("Outcome bounds must be ordered and finite")

    def difference(self, other: OutcomeBounds) -> OutcomeBounds:
        return OutcomeBounds(self.lower - other.upper, self.upper - other.lower)


@dataclass(frozen=True)
class BoundedPairedEstimator:
    """Estimate a case-weighted effect without dropping unknown outcomes.

The supplied support covers each *paired difference*, not each arm score.
For binary correctness its width is two. Dependence inside a pair is allowed;
cross-case interference invalidates the interval.
"""

    support: OutcomeBounds = OutcomeBounds(-1, 1)
    alpha: float = 0.05

    def __post_init__(self) -> None:
        if not 0 < self.alpha < 1 or self.support.lower >= self.support.upper:
            raise ValueError("Invalid coverage or support")

    def half_width(self, pairs: int) -> float:
        if type(pairs) is not int or pairs < 1:
            raise ValueError("At least one independent pair is required")
        return (self.support.upper - self.support.lower) * math.sqrt(
            math.log(2 / self.alpha) / (2 * pairs))

    def required_pairs(self, half_width: float) -> int:
        if not math.isfinite(half_width) or half_width <= 0:
            raise ValueError("Precision must be positive and finite")
        return math.ceil((self.support.upper - self.support.lower) ** 2 *
                         math.log(2 / self.alpha) / (2 * half_width ** 2))

    def estimate(self, differences: list[OutcomeBounds], *, independent: bool = True) -> dict:
        if any(x.lower < self.support.lower or x.upper > self.support.upper for x in differences):
            raise ValueError("Observation lies outside declared support")
        count = len(differences)
        if not count:
            return {"pairs": 0, "estimate": None, "identified_bounds": None,
                    "interval": None, "unknown_pairs": 0, "method": "hoeffding"}
        lower = sum(x.lower for x in differences) / count
        upper = sum(x.upper for x in differences) / count
        radius = self.half_width(count)
        return {"pairs": count, "estimate": lower if lower == upper else None,
                "identified_bounds": [lower, upper],
                "interval": [max(self.support.lower, lower - radius),
                             min(self.support.upper, upper + radius)] if independent else None,
                "confidence_level": 1 - self.alpha,
                "unknown_pairs": sum(x.lower != x.upper for x in differences),
                "method": "hoeffding", "independent_cases": independent}
