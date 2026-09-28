"""Adverse and analytic calibration of planning and practical decisions."""
from dataclasses import replace
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys

import pytest

from experiments.model_transfer.decision_statistics import DecisionStatistics, PracticalDecision, SequenceOutcome
from experiments.model_transfer.information_design import AllocationPlanner, monte_carlo_interval
from experiments.model_transfer.trajectory_simulation import TrajectorySimulator
from experiments.model_transfer.pilot_data import PairedTrajectory, PilotExtractor, PilotSummary, SessionMeasure
from experiments.model_transfer.statistical_quantiles import student_t_quantile


def pilot(repetitions=3, horizon=2):
    pairs = []
    for donor, receiver, tools, repeat in itertools.product(('plain', 'reasoning'), ('plain', 'reasoning'), (False, True), range(repetitions)):
        ordinary = tuple(SessionMeasure(True, 100 + 5 * repeat, .0001, .1, ((.001, .0001),)) for _ in range(horizon + 1))
        eal = tuple(SessionMeasure(True, 50 + 20 * repeat + i, .0001, .1, ((.001, .0001),)) for i in range(horizon + 1))
        pairs.append(PairedTrajectory(str(len(pairs)), 'task', donor, receiver, tools, repeat, ordinary, eal, ('ordinary', 'eal')))
    return pairs


def specification():
    return {'recipient_horizon': 2, 'correctness_margin': .05, 'minimum_correctness': .9, 'minimum_token_reduction': .2}


def configuration():
    return {'schema': 'EAL/model-transfer-information-design/1', 'seed': 7301, 'simulations': 100,
            'budget_usd': 2, 'practical_decision': specification(),
            'information_target': {'method': 'precision', 'confidence': .95, 'correctness_half_width': .9,
                                   'token_reduction_half_width': .9, 'assurance': .8},
            'candidates': [{'cases': 1, 'repetitions': 4}],
            'scenarios': [scenario(0), scenario(.3), scenario(.3, -.1)]}


def scenario(reduction=.3, quality=0, **extras):
    return {'name': f'{reduction}:{quality}', 'token_reduction': reduction, 'correctness_difference': quality,
            'missing_probability': 0, 'cost_multiplier': 1, 'purpose': 'design', **extras}


def plan():
    return {'recipient_sessions': 2, 'cases': ['task'], 'models': {'plain': {}, 'reasoning': {}},
            'study_id': 'pilot-study', 'study_role': 'pilot', 'repetitions': 3}


def test_student_quantiles_match_analytic_cauchy_normal_and_published_t_values():
    assert student_t_quantile(.9875, 1) == pytest.approx(math.tan(math.pi * (.9875 - .5)), rel=1e-11)
    assert student_t_quantile(.975, 5) == pytest.approx(2.5705818356363, rel=1e-10)
    assert student_t_quantile(.9875, 5) == pytest.approx(3.1633814497486, rel=1e-10)
    assert student_t_quantile(.975, math.inf) == pytest.approx(1.9599639845401)


def test_hoeffding_counts_sequences_not_serially_repeated_sessions():
    small = PracticalDecision(specification()).evaluate(pilot(horizon=2), study_role='pilot', independent_evaluation=False)
    long_spec = {**specification(), 'recipient_horizon': 10}
    long = PracticalDecision(long_spec).evaluate(pilot(horizon=10), study_role='pilot', independent_evaluation=False)
    assert small['quality_sampling_half_width'] == long['quality_sampling_half_width']
    expected = math.sqrt(2 * math.log(120) / 24)
    assert small['quality_sampling_half_width'] == pytest.approx(expected)
    assert long['status'] == 'pilot_only'


def test_missing_correctness_is_adversely_bounded_without_erasing_known_tokens():
    data = pilot()
    first = data[0]
    data[0] = replace(first, eal=(first.eal[0], replace(first.eal[1], correctness=None), first.eal[2]))
    result = PracticalDecision(specification()).evaluate(data, study_role='evaluation', independent_evaluation=True)
    assert result['quality_difference_bounds'] == [-1 / 48, 0]
    assert result['token_reduction'] is not None
    assert not result['interval_criteria_met']


def test_cheap_wrong_answers_fail_absolute_quality_even_if_both_arms_wrong():
    data = [replace(p, ordinary=tuple(replace(s, correctness=False) for s in p.ordinary),
                    eal=tuple(replace(s, correctness=False, tokens=s.tokens * .05) for s in p.eal)) for p in pilot(repetitions=30)]
    result = PracticalDecision(specification()).evaluate(data, study_role='evaluation', independent_evaluation=True)
    assert result['token_reduction'] > .2
    assert result['quality_difference_bounds'] == [0, 0]
    assert not result['practical_point_criteria_met']
    assert result['status'] == 'criterion_not_supported'


def test_resource_zero_variance_cannot_certify_absence_of_unobserved_tails():
    data = [SequenceOutcome(('case',), 0, 0, 100, 50, 1, 1) for _ in range(100)]
    result = DecisionStatistics().calculate(data)
    assert result['token_reduction'] == .5
    assert result['token_reduction_interval'] is None
    assert 'unobserved resource tails' in result['token_interval_reason']


def test_null_nonzero_and_adverse_simulation_calibration():
    rng = random.Random(781)
    coverage, adverse_rejections, nonzero_direction = 0, 0, 0
    repetitions = 200
    for _ in range(repetitions):
        outcomes = [SequenceOutcome(('cell',), 0, 0, 100, 100 + rng.gauss(0, 15), 1, 1) for _ in range(100)]
        result = DecisionStatistics().calculate(outcomes)
        lo, hi = result['token_reduction_interval']
        coverage += lo <= 0 <= hi
        nonzero = DecisionStatistics().calculate([replace(o, eal_tokens=o.eal_tokens * .6) for o in outcomes])
        nonzero_direction += nonzero['token_reduction_interval'][0] > .2
        adverse = DecisionStatistics().calculate([replace(o, quality_lower=-.8, quality_upper=-.8,
                                                          eal_correctness_lower=.2, eal_correctness_upper=.2) for o in outcomes])
        adverse_rejections += adverse['quality_interval'][1] < -.05
    assert coverage / repetitions >= .95
    assert nonzero_direction / repetitions >= .95
    assert adverse_rejections == repetitions
    assert monte_carlo_interval(coverage, repetitions)['monte_carlo_95_interval'][0] > .9


def test_simulated_effect_does_not_recentre_every_trial_to_its_target():
    simulator = TrajectorySimulator(pilot(), 2)
    rng = random.Random(831)
    reductions = []
    for _ in range(50):
        outcomes, _ = simulator.simulate(['task'], 3, scenario(), rng)
        reductions.append(DecisionStatistics().calculate(outcomes)['token_reduction'])
    assert statistics.stdev(reductions) > .005
    assert statistics.mean(reductions) == pytest.approx(.3, abs=.025)


def test_whole_trajectory_shocks_missing_annotation_and_missing_usage_are_distinct():
    simulator = TrajectorySimulator(pilot(), 2)
    outcomes, _ = simulator.simulate(['task'], 3, scenario(missing_probability=1), random.Random(99))
    assert all(o.quality_lower == -1 and o.quality_upper == 1 for o in outcomes)
    assert all(o.ordinary_tokens is not None and o.eal_tokens is not None for o in outcomes)
    usage, _ = simulator.simulate(['task'], 3, scenario(missing_probability=1, missing_usage=True), random.Random(99))
    assert all(o.ordinary_tokens is None and o.eal_tokens is None for o in usage)
    shocks, _ = simulator.simulate(['task'], 30, scenario(quality=-.5), random.Random(78))
    assert {o.quality_lower for o in shocks} == {-1, 0}


def test_budget_reservations_do_not_shrink_with_token_reductions():
    data = [replace(p, ordinary=tuple(replace(s, requests=((1., .0001),)) for s in p.ordinary),
                    eal=tuple(replace(s, requests=((1., .0001),)) for s in p.eal)) for p in pilot()]
    outcomes, execution = TrajectorySimulator(data, .5).simulate(['task'], 3, scenario(.9), random.Random(8))
    assert execution['budget_stopped'] and execution['charged_usd'] == 0
    assert len(outcomes) == 24
    assert all(o.eal_tokens is None and o.ordinary_tokens is None for o in outcomes)


def test_deadline_counts_setup_and_sessions_and_retains_stopped_denominator():
    data = [replace(p, setup_seconds=(.3, .3)) for p in pilot()]
    outcomes, execution = TrajectorySimulator(data, 2, .5).simulate(['task'], 3, scenario(), random.Random(8))
    assert execution['time_stopped'] and not execution['budget_stopped']
    assert execution['elapsed_seconds'] > .5
    assert len(outcomes) == 24
    assert any(o.eal_tokens is None or o.ordinary_tokens is None for o in outcomes)


def test_horizon_labels_cannot_extrapolate_unobserved_sessions():
    with pytest.raises(ValueError, match='actual declared'):
        PracticalDecision({**specification(), 'recipient_horizon': 10}).evaluate(
            pilot(), study_role='pilot', independent_evaluation=False)


def test_planner_replay_provenance_and_independent_export():
    config = configuration()
    config['information_target']['confidence'] = .9
    planner = AllocationPlanner(config)
    provenance = {'execution_kind': 'live', 'run_id': 'pilot-001'}
    first = planner.plan(pilot(), plan(), provenance, 'data-hash')
    assert first == planner.plan(pilot(), plan(), provenance, 'data-hash')
    assert first['proposed_evaluation_plan']['pilot_run_ids'] == ['pilot-001']
    assert first['proposed_evaluation_plan']['study_role'] == 'evaluation'
    assert first['proposed_evaluation_plan']['study_id'] != plan()['study_id']
    assert all(s['quality_coverage']['estimate'] >= .95 for s in first['candidates'][0]['scenarios'])
    scripted = planner.plan(pilot(), plan(), {'execution_kind': 'scripted'}, 'data-hash', allow_scripted=True)
    assert scripted['execution_kind'] == 'synthetic_rehearsal'
    assert scripted['proposed_evaluation_plan'] is None
    with pytest.raises(ValueError, match='recorded live'):
        planner.plan(pilot(), plan(), {}, 'data-hash')


def test_incomplete_pilot_does_not_count_planned_repetitions_as_observed_information():
    data = [replace(p, eal=tuple(replace(s, tokens=None, correctness=None) for s in p.eal)) for p in pilot()]
    summary = PilotSummary().describe(data)
    assert summary['minimum_complete_repetitions_per_stratum'] == 0
    assert not summary['within_cell_variance_identified']
    result = AllocationPlanner(configuration()).plan(data, plan(), {'execution_kind': 'live', 'run_id': 'x'}, 'hash')
    assert result['proposed_evaluation_plan'] is None
    assert result['blockers']


def test_practical_precision_unattainable_is_reported_without_allocation():
    config = configuration()
    config['information_target']['correctness_half_width'] = .025
    result = AllocationPlanner(config).plan(pilot(), plan(), {'execution_kind': 'live', 'run_id': 'pilot'}, 'hash')
    assert result['status'] == 'no_supported_allocation'
    assert result['quality_bound_minimum_pairs'] == math.ceil(2 * math.log(120) / .025 ** 2)
    assert not result['candidates'][0]['precision_target_satisfied']
    assert result['candidates'][0]['scenarios'][0]['quality_precision']['estimate'] == 0


def test_duplicate_units_cannot_inflate_sample_size():
    rows = [{'pair_id': 'a', 'sequence_id': 'a.eal', 'case': 'task', 'donor': 'plain', 'receiver': 'plain',
             'native_tools': False, 'repeat': 0, 'arm': 'eal', 'sessions': []}]
    rows.append({**rows[0], 'pair_id': 'b', 'sequence_id': 'b.eal'})
    with pytest.raises(ValueError, match='Duplicate experimental unit'):
        PilotExtractor().extract(rows, [], 2)


def test_stress_failures_remain_visible_without_becoming_universal_design_requirements():
    config = configuration()
    config['information_target']['confidence'] = .9
    config['scenarios'].append(scenario(name='unrecoverable_usage', purpose='stress', missing_probability=1, missing_usage=True))
    result = AllocationPlanner(config).plan(pilot(), plan(), {'execution_kind': 'live', 'run_id': 'pilot'}, 'hash')
    assert result['proposed_evaluation_plan'] is not None
    assert result['candidates'][0]['failed_stress_scenarios'] == ['unrecoverable_usage']
    assert result['candidates'][0]['scenarios'][-1]['token_interval_available']['estimate'] == 0


def test_precise_but_catastrophically_miscalibrated_tail_model_cannot_propose_evaluation():
    data = [replace(p, ordinary=tuple(replace(s, tokens=100 + 5 * p.repeat) for s in p.ordinary),
                    eal=tuple(replace(s, tokens=100 - 5 * p.repeat) for s in p.eal)) for p in pilot(repetitions=2, horizon=1)]
    config = configuration()
    config.update(simulations=200, candidates=[{'cases': 1, 'repetitions': 16}],
                  scenarios=[scenario(.1, resource_tail_probability=.001, resource_tail_multiplier=1000)])
    config['practical_decision']['recipient_horizon'] = 1
    config['information_target'].update(correctness_half_width=.99, token_reduction_half_width=.1)
    source = {**plan(), 'recipient_sessions': 1, 'repetitions': 2}
    report = AllocationPlanner(config).plan(data, source, {'execution_kind': 'live', 'run_id': 'pilot'}, 'hash')
    candidate = report['candidates'][0]
    assert candidate['scenarios'][0]['precision']['estimate'] > .8
    assert candidate['scenarios'][0]['joint_coverage']['monte_carlo_95_interval'][1] < .5
    assert not candidate['coverage_calibration_satisfied']
    assert report['proposed_evaluation_plan'] is None


def test_cli_rehearsal_retains_raw_rows_and_never_exports_synthetic_allocation(tmp_path):
    from experiments.model_transfer.design import AssignmentSchedule
    source_plan = json.loads(Path('experiments/model_transfer/plan.json').read_text())
    source_plan.update(cases=['fresh_positive'], repetitions=3, recipient_sessions=2,
                       practical_decision=specification())
    rows = [{**allocation, 'sessions': [], 'status': 'not_run', 'cohort': 'diagnostic'}
            for allocation in AssignmentSchedule(source_plan).allocations()]
    (tmp_path / 'plan.json').write_text(json.dumps(source_plan))
    raw_rows = json.dumps(rows)
    (tmp_path / 'rows.json').write_text(raw_rows)
    config = configuration()
    (tmp_path / 'config.json').write_text(json.dumps(config))
    subprocess.run([sys.executable, '-m', 'experiments.model_transfer.plan_information', str(tmp_path),
                    '--config', str(tmp_path / 'config.json'), '--allow-scripted',
                    '--output', str(tmp_path / 'allocation.json'), '--evaluation-plan', str(tmp_path / 'next.json')], check=True)
    report = json.loads((tmp_path / 'allocation.json').read_text())
    assert report['execution_kind'] == 'synthetic_rehearsal'
    assert report['status'] == 'no_supported_allocation'
    assert not (tmp_path / 'next.json').exists()
    assert (tmp_path / 'rows.json').read_text() == raw_rows
