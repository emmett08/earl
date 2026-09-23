#!/usr/bin/env python3
"""Synthetic planning sensitivity, not EAL/model performance evidence."""
import argparse
import json
from pathlib import Path
from statistics import NormalDist


def simulate(seed=20260923, simulations=10000):
    import numpy as np
    rng = np.random.default_rng(seed)
    # Two one-sided primary contrasts share family alpha=.05 by Bonferroni.
    z = NormalDist().inv_cdf(0.975)
    results = []
    for n in (120, 240, 480, 960):
        for discordance in (0.2, 0.4, 0.6):
            for effect in (0.0, 0.05, 0.10, 0.15):
                plus, minus = (discordance + effect) / 2, (discordance - effect) / 2
                samples = rng.multinomial(n, [plus, minus, 1 - discordance], size=simulations)
                means = (samples[:, 0] - samples[:, 1]) / n
                variance = ((samples[:, 0] + samples[:, 1]) / n - means ** 2) * n / (n - 1)
                se = np.sqrt(variance / n)
                lower = means - z * se
                pass_rate = float(np.mean(lower > 0.05))
                results.append({"independent_templates": n, "discordance_probability": discordance,
                                "true_difference": effect, "probability_lower_bound_exceeds_0_05": pass_rate,
                                "monte_carlo_se": (pass_rate * (1 - pass_rate) / simulations) ** 0.5,
                                "lower_bound_coverage": float(np.mean(lower <= effect)),
                                "mean_margin": float(np.mean(z * se))})
    return {"schema": "EAL/precision-sensitivity/1", "evidence_kind": "synthetic planning simulation",
            "seed": seed, "simulations_per_cell": simulations, "numpy_version": np.__version__,
            "model": "Independent paired template differences in {-1,0,1}; two repetitions within each template are perfectly correlated and count once.",
            "decision": "One-sided 97.5% normal lower bound > 0.05 for each of two primary contrasts; Bonferroni family alpha 0.05.",
            "limitations": ["Discordance scenarios are assumptions, not estimates from new model trials.",
                            "No between-template dependence, scoring error, drift or missingness is simulated.",
                            "Normal bounds are a planning approximation; final inference needs calibration for the chosen task sampling design.",
                            "These results do not select a confirmatory sample size or validate a task population."],
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(simulate(), indent=2, allow_nan=False) + "\n")
    print(args.output)
