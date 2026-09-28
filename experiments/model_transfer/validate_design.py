"""Reproduce finite-sample quality checks and joint-decision simulation evidence."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random

from .allocation_assessment import monte_carlo_interval
from .bounded_statistics import bounded_interval
from .decision_statistics import DecisionStatistics, SequenceOutcome, joint_supported


def validate(*, simulations: int = 1000, pairs: int = 1200, seed: int = 20260929, boundary_simulations: int = 10000) -> dict:
    rng = random.Random(seed)
    spec = {'correctness_margin': .05, 'minimum_correctness': .90, 'minimum_token_reduction': .20}
    scenarios = [
        ('benefit', .97, .97, .30, .15), ('no_saving', .97, .97, 0., .15),
        ('quality_boundary', .99, .94, .30, .15), ('absolute_boundary', .90, .90, .30, .15),
        ('saving_boundary', .97, .97, .20, .15), ('harm', .97, .80, .30, .15),
        ('high_variance', .97, .97, .30, .60), ('rare_errors', .999, .949, .30, .15)]
    results = []
    for name, ordinary_q, eal_q, reduction, cv in scenarios:
        counters = {'joint_success': 0, 'joint_coverage': 0, 'quality_coverage': 0, 'token_coverage': 0}
        draws = max(simulations, boundary_simulations) if name == 'saving_boundary' else simulations
        for _ in range(draws):
            rows = []
            sigma2 = math.log1p(cv ** 2)
            for i in range(pairs):
                # Ten answers in each arm can be perfectly serially dependent;
                # each row is an independent complete trajectory, not a session.
                ordinary = float(rng.random() < ordinary_q)
                eal = float(rng.random() < eal_q)
                common = math.exp(rng.gauss(-sigma2 / 2, math.sqrt(sigma2)))
                relative = math.exp(rng.gauss(-sigma2 / 2, math.sqrt(sigma2)))
                rows.append(SequenceOutcome((i % 8,), eal - ordinary, eal - ordinary,
                    1000 * common, 1000 * (1 - reduction) * common * relative, eal, eal))
            result = DecisionStatistics().calculate(rows)
            qi, ai, ti = result['quality_interval'], result['eal_correctness_interval'], result['token_reduction_interval']
            qc = qi[0] <= eal_q - ordinary_q <= qi[1]
            tc = ti is not None and ti[0] <= reduction <= ti[1]
            counters['joint_success'] += joint_supported(result, spec)
            counters['quality_coverage'] += qc
            counters['token_coverage'] += tc
            counters['joint_coverage'] += qc and tc and ai[0] <= eal_q <= ai[1]
        partial_null = eal_q - ordinary_q <= -.05 + 1e-12 or eal_q <= .9 or reduction <= .2
        results.append({'name': name, 'truth': {'ordinary_correctness': ordinary_q,
            'eal_correctness': eal_q, 'token_reduction': reduction, 'resource_cv': cv},
            'partial_null': partial_null, 'replications': draws, **{key: monte_carlo_interval(value, draws)
                                           for key, value in counters.items()}})
    alternatives = []
    for n in (224, 512, 1024, 1536, 15344):
        alternatives.append({'paired_trajectories': n, 'sessions': n * 22,
            'zero_variance_quality_half_width': {method: bounded_interval([0.] * n, [0.] * n,
                (-1, 1), .05 / 6, method)[1] for method in ('empirical_bernstein', 'hoeffding')}})
    return {'schema': 'EAL/design-validation/1', 'execution_kind': 'synthetic', 'seed': seed,
        'base_simulations_per_scenario': simulations, 'saving_boundary_simulations': max(simulations, boundary_simulations), 'paired_trajectories': pairs,
        'results': results, 'analytic_method_comparison': alternatives,
        'scope': 'Known synthetic generating processes and production decision analysis. '
            'No live performance, task-population generalisation or budget adequacy is established.',
        'checks': {'benefit_joint_success_lower_at_least_80_percent': results[0]['joint_success']['mc_interval'][0] >= .8,
            'partial_null_false_success_upper_at_most_6_percent': all(
                row['joint_success']['mc_interval'][1] <= .06 for row in results if row['partial_null']),
            'joint_coverage_lower_at_least_94_percent': all(row['joint_coverage']['mc_interval'][0] >= .94 for row in results)}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulations', type=int, default=1000)
    parser.add_argument('--boundary-simulations', type=int, default=10000)
    parser.add_argument('--pairs', type=int, default=1200)
    parser.add_argument('--seed', type=int, default=20260929)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.simulations < 100 or args.boundary_simulations < 100 or args.pairs < 16:
        raise ValueError('Use a new path, at least 100 simulations and at least 16 pairs')
    result = validate(simulations=args.simulations, pairs=args.pairs, seed=args.seed, boundary_simulations=args.boundary_simulations)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['checks']))
    if not all(result['checks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
