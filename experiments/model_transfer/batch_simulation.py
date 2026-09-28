"""Conservatively assess complete concurrent batches from paired trajectories."""
from dataclasses import replace
import math


def simulate_batches(simulator, case_ids, repetitions, scenario, rng):
    from .trajectory_simulation import TrajectorySimulator
    if not hasattr(simulator, '_unbounded'):
        pilot = [pair for members in simulator.strata.values() for pair in members]
        simulator._unbounded = TrajectorySimulator(pilot, math.inf, math.inf)
    outcomes, generating = simulator._unbounded.simulate(case_ids, repetitions, scenario, rng)
    executions = generating['pair_executions']
    spent, elapsed = 0., simulator.workflow_overhead_seconds
    budget_stop = time_stop = stopped = False
    retained = []
    for index in range(0, len(outcomes), simulator.workers):
        batch = outcomes[index:index + simulator.workers]
        timing = executions[index:index + simulator.workers]
        charges = sum(row['charged_usd'] for row in timing)
        # At any instant, paid charges cannot exceed the batch total and each
        # worker has at most one active request. This upper bound avoids an
        # optimistic zero-reservation assumption when admitting a whole batch.
        reserves = sum(row['max_reservation_usd'] for row in timing)
        duration = max(row['elapsed_seconds'] for row in timing)
        if not stopped:
            budget_stop |= spent + charges + reserves > simulator.budget_usd
            time_stop |= elapsed + duration > simulator.time_limit_seconds
            stopped = budget_stop or time_stop
        if stopped:
            retained.extend(replace(row, quality_lower=-1, quality_upper=1, ordinary_tokens=None,
                eal_tokens=None, eal_correctness_lower=0, eal_correctness_upper=1) for row in batch)
        else:
            retained.extend(batch)
            spent += charges
            elapsed += duration
    return retained, {**generating, 'charged_usd': spent, 'elapsed_seconds': elapsed,
        'budget_stopped': budget_stop, 'time_stopped': time_stop,
        'execution_model': 'Conservative complete-batch feasibility; incomplete batches are entirely bounded as unknown.'}
