"""Prospective allocation simulation for the actual paired repeated-session design."""
from __future__ import annotations

import copy
import itertools
import math
import random
import statistics

from .decision_statistics import DecisionStatistics
from .design import MAX_SEQUENCES
from .information_config import validate_information_design
from .trajectory_simulation import TrajectorySimulator
from .pilot_data import PairedTrajectory, PilotSummary


def monte_carlo_interval(successes: int, count: int) -> dict:
    """Pointwise Wilson 95% interval; uncertainty about one simulation cell only."""
    z = statistics.NormalDist().inv_cdf(.975)
    rate = successes / count
    denominator = 1 + z * z / count
    centre = (rate + z * z / (2 * count)) / denominator
    radius = z / denominator * math.sqrt(rate * (1 - rate) / count + z * z / (4 * count * count))
    return {'estimate': rate, 'monte_carlo_95_interval': [max(0, centre - radius), min(1, centre + radius)],
            'successes': successes, 'replications': count}


class AllocationPlanner:
    def __init__(self, config: dict):
        self.config = validate_information_design(config)

    def plan(self, pilot: list[PairedTrajectory], source_plan: dict, provenance: dict,
             fingerprint: str, *, allow_scripted: bool = False) -> dict:
        config = self.config
        live = provenance.get('execution_kind') == 'live'
        if not live and not allow_scripted:
            raise ValueError('Empirical allocation requires recorded live execution; use --allow-scripted only for a labelled rehearsal')
        horizon = config['practical_decision']['recipient_horizon']
        if source_plan['recipient_sessions'] != horizon or any(len(p.eal) != horizon + 1 for p in pilot):
            raise ValueError('The pilot must actually observe the declared horizon; trajectories are never extrapolated')
        units = [(p.case, p.donor, p.receiver, p.native_tools, p.repeat) for p in pilot]
        expected = set(itertools.product(source_plan['cases'], source_plan['models'], source_plan['models'],
                                         (False, True), range(source_plan['repetitions'])))
        if len(units) != len(expected) or set(units) != expected:
            raise ValueError('Retain every planned paired unit exactly once; missing outcomes remain inside its trajectory')
        summary = PilotSummary().describe(pilot)
        blockers = []
        if not live:
            blockers.append('Synthetic or unverified execution cannot establish empirical allocation')
        if source_plan.get('study_role') != 'pilot':
            blockers.append('Allocation inputs must be a prospectively labelled pilot')
        if not provenance.get('run_id'):
            blockers.append('Pilot run identity is missing')
        if provenance.get('pilot_accounting_complete') is False:
            blockers.append('Pilot-wide API receipt reconciliation failed; unassigned attempts cannot be excluded')
        if not summary['within_cell_variance_identified']:
            blockers.append('Within-cell variability requires at least two independent pilot repetitions in every cell')
        if any(s.tokens is None or s.cost_usd is None for p in pilot for arm in (p.eal, p.ordinary) for s in arm):
            blockers.append('Incomplete pilot resource measurements cannot identify the empirical cost distribution')
        if any(s.correctness is None for p in pilot for arm in (p.eal, p.ordinary) for s in arm[1:]):
            blockers.append('Complete pilot recipient annotation is required before empirical allocation')
        if any(not s.budget_accounting_complete for p in pilot for arm in (p.eal, p.ordinary) for s in arm):
            blockers.append('Pilot request reservations and charges are incomplete; budget feasibility is unidentified')
        if any(value is None for p in pilot for value in p.setup_seconds) or any(
                s.elapsed_seconds is None for p in pilot for arm in (p.eal, p.ordinary) for s in arm):
            blockers.append('Pilot setup or session timing is missing; deadline feasibility is unidentified')
        target = config['information_target']
        simulator = TrajectorySimulator(pilot, config['budget_usd'], config.get('time_limit_seconds', 7200),
                                        config.get('workflow_overhead_seconds', 0))
        rng = random.Random(config['seed'])
        entries = []
        observed_cases = {p.case for p in pilot}
        expected_cells = len(source_plan['models']) ** 2 * 2
        for candidate in config['candidates']:
            case_ids = list(source_plan['cases'])
            pairs = candidate['cases'] * expected_cells * candidate['repetitions']
            invalid = (candidate['cases'] != len(source_plan['cases']) or not set(case_ids) <= observed_cases
                       or pairs * 2 > MAX_SEQUENCES)
            if invalid:
                entries.append({**candidate, 'eligible': False, 'reason': 'Candidate must retain the complete fixed task pool and executable sequence limit'})
                continue
            actual_cells = {p.stratum for p in pilot if p.case in case_ids}
            if len(actual_cells) != candidate['cases'] * expected_cells:
                entries.append({**candidate, 'eligible': False, 'reason': 'Pilot is missing a planned model/tool cell'})
                continue
            outcomes = []
            for scenario in config['scenarios']:
                counters = {key: 0 for key in ('precision', 'quality_precision', 'token_precision', 'practical_support',
                                              'budget_complete', 'deadline_complete', 'effect_attainable', 'quality_coverage', 'absolute_quality_coverage', 'token_coverage', 'joint_coverage',
                                              'token_interval_available')}
                spends, elapsed = [], []
                for _ in range(config['simulations']):
                    trial, execution = simulator.simulate(case_ids, candidate['repetitions'], scenario, rng)
                    result = DecisionStatistics(target['confidence']).calculate(trial)
                    qi, ti = result['quality_interval'], result['token_reduction_interval']
                    quality_bounds = result['quality_difference_bounds']
                    quality_precision = (qi is not None and result['quality_sampling_half_width']
                        + (quality_bounds[1] - quality_bounds[0]) / 2 <= target['correctness_half_width'])
                    token_precision = (ti is not None and result['token_sampling_half_width']
                                       <= target['token_reduction_half_width'])
                    counters['quality_precision'] += quality_precision
                    counters['token_precision'] += token_precision
                    counters['precision'] += (quality_precision and token_precision and not execution['budget_stopped']
                                              and not execution['time_stopped'] and execution['timing_known'])
                    counters['practical_support'] += bool(qi and ti and qi[0] >= -config['practical_decision']['correctness_margin']
                                                          and result['eal_correctness_interval'][0] >= config['practical_decision']['minimum_correctness']
                                                          and ti[0] >= config['practical_decision']['minimum_token_reduction'])
                    counters['budget_complete'] += not execution['budget_stopped']
                    counters['deadline_complete'] += not execution['time_stopped'] and execution['timing_known']
                    counters['effect_attainable'] += execution['effect_attainable']
                    truth_known = (execution['effect_attainable'] and not summary['missing_paired_recipient_fraction'])
                    counters['quality_coverage'] += bool(truth_known and qi and qi[0] <= scenario['correctness_difference'] <= qi[1])
                    ai = result['eal_correctness_interval']
                    counters['absolute_quality_coverage'] += bool(truth_known and ai and ai[0] <= execution['eal_correctness_truth'] <= ai[1])
                    counters['token_coverage'] += bool(ti and ti[0] <= scenario['token_reduction'] <= ti[1])
                    counters['joint_coverage'] += bool(truth_known and qi and ai and ti
                        and qi[0] <= scenario['correctness_difference'] <= qi[1]
                        and ai[0] <= execution['eal_correctness_truth'] <= ai[1]
                        and ti[0] <= scenario['token_reduction'] <= ti[1])
                    counters['token_interval_available'] += ti is not None
                    spends.append(execution['charged_usd'])
                    elapsed.append(execution['elapsed_seconds'])
                outcomes.append({'scenario': scenario, **{key: monte_carlo_interval(value, config['simulations'])
                    for key, value in counters.items()}, 'mean_charged_usd': statistics.mean(spends),
                    'mean_elapsed_seconds': statistics.mean(elapsed),
                    'coverage_truth_available': not summary['missing_paired_recipient_fraction'],
                    'coverage_denominator': 'All simulated trials; unavailable intervals count as no coverage. '
                        'Quality coverage requires fully annotated pilot outcomes.'})
                if summary['missing_paired_recipient_fraction']:
                    outcomes[-1]['quality_coverage'] = None
                    outcomes[-1]['absolute_quality_coverage'] = None
                    outcomes[-1]['joint_coverage'] = None
            required = [s for s in outcomes if s['scenario'].get('purpose', 'design') == 'design']
            precise = all(s['precision']['monte_carlo_95_interval'][0] >= target['assurance'] for s in required)
            calibrated = all(s['joint_coverage'] is not None
                           and s['joint_coverage']['monte_carlo_95_interval'][0] >= target['confidence']
                           and s['effect_attainable']['successes'] == config['simulations']
                           for s in required)
            entries.append({**candidate, 'case_ids': case_ids, 'paired_sequences': pairs,
                            'planned_sessions': pairs * 2 * (horizon + 1), 'eligible': True,
                            'precision_target_satisfied': precise, 'coverage_calibration_satisfied': calibrated,
                            'eligible_for_evaluation': precise and calibrated, 'scenarios': outcomes,
                            'failed_stress_scenarios': [s['scenario']['name'] for s in outcomes
                                if s['scenario'].get('purpose') == 'stress'
                                and (s['precision']['monte_carlo_95_interval'][0] < target['assurance']
                                     or s['joint_coverage'] is None
                                     or s['joint_coverage']['monte_carlo_95_interval'][0] < target['confidence']
                                     or s['effect_attainable']['successes'] != config['simulations'])]})
        feasible = [entry for entry in entries if entry.get('eligible_for_evaluation')]
        chosen = min(feasible, key=lambda e: e['planned_sessions']) if feasible and not blockers else None
        proposal = None
        if chosen:
            proposal = copy.deepcopy(source_plan)
            proposal.update(cases=chosen['case_ids'], repetitions=chosen['repetitions'],
                study_role='evaluation', study_id=source_plan['study_id'] + '-evaluation',
                pilot_run_ids=[provenance['run_id']], pilot_data_sha256=[fingerprint],
                practical_decision=config['practical_decision'], information_target=config['information_target'],
                seed=config['seed'] + 1, budget_usd=config['budget_usd'],
                time_limit_seconds=config.get('time_limit_seconds', 7200),
                workflow_overhead_seconds=config.get('workflow_overhead_seconds', 0))
        return {'schema': 'EAL/model-transfer-information-result/1',
                'status': 'allocation_identified' if proposal else 'no_supported_allocation',
                'execution_kind': 'empirical_planning' if live else 'synthetic_rehearsal',
                'pilot_run_id': provenance.get('run_id'), 'pilot_data_sha256': fingerprint,
                'configuration': config, 'pilot_summary': summary, 'blockers': blockers,
                'quality_bound_minimum_pairs': math.ceil(2 * math.log(6 / (1 - target['confidence']))
                                                        / target['correctness_half_width'] ** 2),
                'executable_maximum_pairs': MAX_SEQUENCES // 2,
                'quality_bound_minimum_repetitions': math.ceil(2 * math.log(6 / (1 - target['confidence']))
                    / target['correctness_half_width'] ** 2 / (len(source_plan['cases']) * expected_cells)),
                'candidates': entries, 'proposed_evaluation_plan': proposal,
                'selection_rule': 'Smallest executable allocation whose Monte Carlo lower precision-assurance '
                    'bound reaches the target and whose lower joint-coverage bound reaches nominal confidence '
                    'in every predeclared design scenario; stress failures remain explicit limitations; no synthetic proposal.',
                'monte_carlo_scope': 'Intervals are pointwise for each candidate/scenario cell, not simultaneous '
                    'confidence statements across the selected grid. Allocation remains conditional on the simulated distributions.',
                'assumptions': ['Independent matched sequence executions conditional on fixed task/model/tool cells.',
                    'Within-cell empirical whole-trajectory resampling represents rerun variation; unseen tails are not identified.',
                    'Hypothetical token effects rescale EAL usage at fixed token mix; cost sensitivity is explicit.',
                    'Retained request reservations never shrink when simulated token usage shrinks.',
                    'Rare-tail multipliers are conservative expenditure stresses, not claims of provider-feasible individual responses.',
                    'Sequential elapsed time includes retained session and setup timing plus a declared workflow overhead '
                        'allowance; deadline feasibility is conditional on that allowance.',
                    'Quality and missingness perturbations share one draw per arm trajectory, allowing perfect serial dependence.',
                    'Pilot missing measurements remain missing; incomplete budget-truncated sequences remain in denominators.',
                    'Every candidate retains the complete registered task pool; repetitions never create new task identities.'],
                'interpretation': 'Prospective precision sensitivity under declared generating assumptions, not observed '
                    'post-hoc power, empirical EAL efficacy, or evidence about independently sampled task populations. '
                    'A null proposal means the budget, available cases, data or precision criterion does not support an allocation.'}
