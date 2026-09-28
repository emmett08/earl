"""Prospective allocation simulation for the actual paired repeated-session design."""
from __future__ import annotations

import copy
import itertools
import math
import random

from .allocation_assessment import ScenarioAssessment, monte_carlo_interval
from .design import MAX_SEQUENCES
from .information_config import validate_information_design
from .trajectory_simulation import TrajectorySimulator
from .pilot_data import PairedTrajectory, PilotSummary


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
        if summary['minimum_complete_repetitions_per_stratum'] < config.get('minimum_pilot_repetitions', 4):
            blockers.append('Pilot replication is below the declared minimum for nuisance estimation')
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
            assessment = ScenarioAssessment(config, simulator)
            outcomes = [assessment.run(case_ids, candidate['repetitions'], scenario, rng, config['simulations'], screening=True)
                        for scenario in config['scenarios']]
            precise = all('precision_or_feasibility' not in s['calibration_failures'] for s in outcomes)
            calibrated = all(not s['calibration_failures'] for s in outcomes)
            entries.append({**candidate, 'case_ids': case_ids, 'paired_sequences': pairs,
                'planned_sessions': pairs * 2 * (horizon + 1), 'eligible': True,
                'precision_not_ruled_out': precise, 'calibration_not_ruled_out': calibrated,
                'eligible_for_validation': calibrated, 'evaluation_validated': False, 'scenarios': outcomes,
                'failed_stress_scenarios': [s['scenario']['name'] for s in outcomes
                    if s['scenario'].get('purpose') == 'stress' and s['calibration_failures']]})
        feasible = [entry for entry in entries if entry.get('eligible_for_validation')]
        chosen = None
        validation = []
        # Screening never certifies a selected candidate. Spend new simulation
        # draws on validation; multiplicity is controlled across all attempted
        # candidate/scenario validations by a Bonferroni MC confidence level.
        mc_confidence = 1 - .05 / max(1, len(entries) * len(config['scenarios']) * 4)
        if not blockers:
            for entry in sorted(feasible, key=lambda item: item['planned_sessions']):
                fresh = random.Random(config['seed'] + 104729 + entry['repetitions'])
                assessment = ScenarioAssessment(config, simulator)
                checked = [assessment.run(entry['case_ids'], entry['repetitions'], scenario, fresh,
                    config.get('validation_simulations', 10000), mc_confidence=mc_confidence)
                    for scenario in config['scenarios']]
                validation.append({'repetitions': entry['repetitions'], 'scenarios': checked,
                    'seed': config['seed'] + 104729 + entry['repetitions'], 'mc_confidence': mc_confidence})
                if all(not s['calibration_failures'] for s in checked):
                    entry['evaluation_validated'] = True
                    chosen = entry
                    break
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
        return {'schema': 'EAL/model-transfer-information-result/2',
                'status': 'allocation_identified' if proposal else 'no_supported_allocation',
                'execution_kind': 'empirical_planning' if live else 'synthetic_rehearsal',
                'pilot_run_id': provenance.get('run_id'), 'pilot_data_sha256': fingerprint,
                'configuration': config, 'pilot_summary': summary, 'blockers': blockers,
                'hoeffding_reference_minimum_pairs': math.ceil(2 * math.log(6 / (1 - target['confidence']))
                                                        / target['correctness_half_width'] ** 2),
                'empirical_bernstein_zero_variance_minimum_pairs': math.ceil(14 * math.log(12 / (1 - target['confidence'])) / (3 * target['correctness_half_width']) + 1),
                'executable_maximum_pairs': MAX_SEQUENCES // 2,
                'hoeffding_reference_minimum_repetitions': math.ceil(2 * math.log(6 / (1 - target['confidence']))
                    / target['correctness_half_width'] ** 2 / (len(source_plan['cases']) * expected_cells)),
                'candidates': entries, 'fresh_seed_validation': validation, 'proposed_evaluation_plan': proposal,
                'selection_rule': 'Smallest allocation passing precision, joint decision assurance, false-success and coverage checks, followed by fresh-seed validation. No synthetic proposal.',
                'monte_carlo_scope': 'Screening intervals are pointwise. Fresh validation adjusts MC confidence across candidate/scenario/criterion checks. Calibration tolerance qualifies approximate resource inference, not the practical effect thresholds.',
                'assumptions': ['Independent matched sequence executions conditional on fixed task/model/tool cells.',
                    'Whole-trajectory resampling is supplemented by mean-one variance correction and declared unseen-variation/tail scenarios; these remain assumptions.',
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
