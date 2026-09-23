#!/usr/bin/env python3
"""Synthetic sensitivity of finite-task relay intervals; no model calls.

Requires NumPy for this optional analysis script. Trials within each task are
perfectly correlated in this stress scenario. It is a calibration calculation,
not an empirical model-performance estimate.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np


def simulate(seed=20260924, simulations=1000, bootstrap_samples=500):
    rng = np.random.default_rng(seed)
    output = []
    for n in (6, 12, 24, 48):
        for probabilities in ((.2, .6, .2), (.15, .6, .25), (.05, .65, .3)):
            truth = probabilities[2] - probabilities[0]
            rows = rng.choice([-1., 0., 1.], size=(simulations, n), p=probabilities)
            indices = rng.integers(n, size=(simulations, bootstrap_samples, n))
            means = np.take_along_axis(rows[:, None, :], indices, axis=2).mean(axis=2)
            lo, hi = np.quantile(means, [.025, .975], axis=1)
            coverage = float(((lo <= truth) & (hi >= truth)).mean())
            output.append({'independent_tasks': n, 'true_difference': truth,
                           'coverage': coverage, 'coverage_mc_se': math.sqrt(coverage*(1-coverage)/simulations),
                           'interval_above_zero_fraction': float((lo > 0).mean()),
                           'interval_excludes_zero_fraction': float(((lo > 0) | (hi < 0)).mean()),
                           'zero_width_fraction': float((lo == hi).mean()),
                           'mean_interval_width': float((hi-lo).mean())})
    return {'schema': 'EAL/relay-precision-simulation/1', 'seed': seed, 'simulations_per_scenario': simulations,
            'bootstrap_samples': bootstrap_samples, 'measurement_kind': 'synthetic_simulation',
            'repeat_dependence': 'Perfect within-task repeat correlation; two identical repetitions supply one task outcome.',
            'interpretation': 'Coverage is tested only under the declared paired-difference distributions. Small task counts can yield undercoverage. This pilot supplies descriptive intervals, not calibrated general-population tests.',
            'scenarios': output}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(simulate(), indent=2)+'\n')
