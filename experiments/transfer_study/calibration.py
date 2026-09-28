"""Reproducible estimator calibration, not evidence of EAL effectiveness."""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

from .inference import BoundedPairedEstimator, OutcomeBounds
from .workspace import write_json


@dataclass(frozen=True)
class Scenario:
    name: str
    eal_probability: float
    ordinary_probability: float
    paired_correlation: bool = False
    informative_missingness: bool = False
    cross_case_dependence: bool = False


SCENARIOS = (
    Scenario("null", 0.5, 0.5),
    Scenario("benefit", 0.85, 0.25),
    Scenario("harm", 0.25, 0.85),
    Scenario("within_pair_dependence", 0.75, 0.25, paired_correlation=True),
    Scenario("informative_missingness", 0.5, 0.5, informative_missingness=True),
    Scenario("cross_case_dependence", 0.5, 0.5, cross_case_dependence=True),
)


class CalibrationStudy:
    """Exercise a prespecified set of data-generating processes and tolerances."""

    def run(self, *, replications: int = 5000, pairs: int = 120, seed: int = 20260928) -> dict:
        if type(replications) is not int or replications < 100 or type(pairs) is not int or pairs < 1:
            raise ValueError("Use at least 100 replications and one pair")
        estimator = BoundedPairedEstimator()
        # Monte Carlo errors are bounded separately; zero events do not imply zero probability.
        mc_radius = BoundedPairedEstimator(OutcomeBounds(0, 1)).half_width(replications)
        results = []
        for scenario in SCENARIOS:
            rng = random.Random(f"{seed}:{scenario.name}")
            covered = favourable = withheld = 0
            effect = scenario.eal_probability - scenario.ordinary_probability
            for _ in range(replications):
                values = []
                common = rng.random()
                for _ in range(pairs):
                    u = common if scenario.cross_case_dependence else rng.random()
                    v = u if scenario.paired_correlation else rng.random()
                    eal = int(u < scenario.eal_probability)
                    ordinary = int(v < scenario.ordinary_probability)
                    left = OutcomeBounds(eal, eal)
                    right = OutcomeBounds(ordinary, ordinary)
                    if scenario.informative_missingness:
                        if eal == 0:
                            left = OutcomeBounds(0, 1)
                        if ordinary == 1:
                            right = OutcomeBounds(0, 1)
                    values.append(left.difference(right))
                interval = estimator.estimate(values, independent=not scenario.cross_case_dependence)["interval"]
                if interval is None:
                    withheld += 1
                else:
                    covered += interval[0] <= effect <= interval[1]
                    favourable += interval[0] > 0.10
            def rate(count):
                value = count / replications
                return {"count": count, "rate": value,
                        "monte_carlo_95_bounds": [max(0, value - mc_radius), min(1, value + mc_radius)]}
            coverage = rate(covered) if not scenario.cross_case_dependence else None
            positive = rate(favourable)
            checks = {"dependent_intervals_withheld": withheld == replications} if scenario.cross_case_dependence else {
                "coverage_lower_bound_at_least_095": coverage["monte_carlo_95_bounds"][0] >= .95}
            if effect <= 0:
                checks["false_benefit_upper_bound_at_most_005"] = positive["monte_carlo_95_bounds"][1] <= .05
            if scenario.name == "benefit":
                checks["benefit_detection_lower_bound_at_least_080"] = positive["monte_carlo_95_bounds"][0] >= .80
            results.append({"scenario": scenario.name, "true_effect": effect, "coverage": coverage,
                            "meaningful_benefit": positive, "withheld_intervals": withheld,
                            "checks": checks})
        return {"schema": "EAL/transfer-calibration/1", "seed": seed, "replications": replications,
                "pairs": pairs, "meaningful_difference": .10, "results": results,
                "precision": [{"half_width": h, "required_independent_pairs": estimator.required_pairs(h)}
                              for h in (.30, .20, .10)],
                "passed": all(all(row["checks"].values()) for row in results),
                "interpretation": "Synthetic operating characteristics only. Monte Carlo bounds are marginal. "
                "Cross-case dependence is declared, not inferred from data. No EAL performance finding."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replications", type=int, default=5000)
    parser.add_argument("--pairs", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = CalibrationStudy().run(replications=args.replications, pairs=args.pairs, seed=args.seed)
    write_json(args.output, result)
    print(f"Calibration {'passed' if result['passed'] else 'failed'}: {args.output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
