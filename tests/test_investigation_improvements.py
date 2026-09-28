"""Adversarial verification of inference, mechanism isolation and cost accounting."""
from copy import deepcopy
from dataclasses import asdict
import itertools
import json
import math
from pathlib import Path
import random
import statistics

import pytest

from experiments.model_transfer.bounded_statistics import bounded_interval, bounded_radius
from experiments.model_transfer.decision_statistics import DecisionStatistics, SequenceOutcome, joint_supported
from experiments.model_transfer.nuisance import resource_multiplier
from experiments.model_transfer.task_manifest import manifest_cases, cases_for_plan
from experiments.model_transfer.conventional_reasoner import evaluate
from experiments.model_transfer.cases import CASES
from experiments.model_transfer.scoring import ReferenceScorer
from experiments.model_transfer.adoption_costs import new_ledger, assess_costs, validate_ledger


def test_empirical_bernstein_zero_error_sample_still_has_uncertainty_and_improves_on_range_only():
    n = 2000
    interval, radius = bounded_interval([0.] * n, [0.] * n, (-1, 1), .05 / 6)
    assert radius == pytest.approx(14 * math.log(240) / (3 * (n - 1)))
    assert 0 < radius < bounded_radius([0.] * n, [0.] * n, 2, .05 / 6, 'hoeffding')
    assert interval == [-radius, radius]


def test_exact_binomial_tail_calibrates_one_sided_quality_bound():
    n, alpha = 300, .05
    for probability in [.01, .5, .99]:
        error = 0.
        for k in range(n + 1):
            values = [1.] * k + [0.] * (n - k)
            lower = bounded_interval(values, values, (0, 1), alpha)[0][0]
            if lower > probability:
                error += math.comb(n, k) * probability ** k * (1 - probability) ** (n - k)
        assert error <= alpha


def test_missing_outcome_envelopes_cover_every_latent_completion():
    lo = [0., -.5, -1., -.2, 0.]
    hi = [0., .5, 1., .6, 0.]
    outer, _ = bounded_interval(lo, hi, (-1, 1), .05)
    for values in itertools.product(*[(a, b) for a, b in zip(lo, hi)]):
        inner, _ = bounded_interval(list(values), list(values), (-1, 1), .05)
        assert outer[0] <= inner[0] and outer[1] >= inner[1]


def test_iut_bounds_are_separate_from_simultaneous_estimation_and_require_all_components():
    rows = [SequenceOutcome(('stratum',), 0, 0, 100, 65 + i % 7, 1, 1) for i in range(2000)]
    result = DecisionStatistics().calculate(rows)
    assert result['decision_lower_bounds']['quality_difference'] > result['quality_interval'][0]
    spec = {'correctness_margin': .05, 'minimum_correctness': .9, 'minimum_token_reduction': .2}
    assert joint_supported(result, spec)
    for key, threshold in [('quality_difference', -.05), ('eal_correctness', .90), ('token_reduction', .20)]:
        changed = deepcopy(result)
        changed['decision_lower_bounds'][key] = threshold
        assert not joint_supported(changed, spec)


def test_resource_resampling_corrects_two_point_variance_without_changing_mean():
    rng = random.Random(281)
    totals = [80., 120.]
    sample = [rng.choice(totals) * resource_multiplier(totals, rng) for _ in range(30000)]
    assert statistics.mean(sample) == pytest.approx(100, abs=.8)
    assert statistics.variance(sample) == pytest.approx(statistics.variance(totals), rel=.06)


def manifest():
    return json.loads(Path('experiments/model_transfer/evaluation-tasks.example.json').read_text())


def test_conventional_evaluator_agrees_with_independent_references_without_using_them():
    cases = (*CASES, *manifest_cases(manifest()))
    reference = ReferenceScorer()
    for case in cases:
        for session in range(11):
            assert evaluate(case, case.measurement(session), case.time(session)) == reference.reference(case, session)['decision']


def test_evaluation_manifest_rejects_false_keys_silent_changes_and_shadowed_calibration():
    source = manifest()
    wrong = deepcopy(source); wrong['cases'][0]['timeline'][0]['expected'] = 'not_ready'
    with pytest.raises(ValueError, match='answer key'):
        manifest_cases(wrong)
    wrong = deepcopy(source); wrong['cases'][0]['timeline'][1]['facts'] = []
    with pytest.raises(ValueError, match='invalidation'):
        manifest_cases(wrong)
    wrong = deepcopy(source); wrong['cases'][0]['identifier'] = CASES[0].identifier
    with pytest.raises(ValueError, match='shadow'):
        cases_for_plan({'task_manifest': wrong})


def test_cadence_changes_are_explicit_and_do_not_claim_external_authorship():
    source = manifest()
    assert source['provenance']['construction'] == 'internal_synthetic'
    cases = manifest_cases(source)
    assert len(cases) == 18
    assert len({case.family for case in cases}) == 6
    for case in cases:
        revisions = [case.context_at(i)['evidence_revision'] for i in range(11)]
        assert len(set(revisions)) == (1 if case.identifier.endswith('stable') else 6 if case.identifier.endswith('periodic') else 11)


def test_costs_require_complete_coverage_and_rates_preserve_zero_and_fixed_setup():
    plan = {'recipient_sessions': 1}
    ledger = new_ledger(plan, 'run')
    report = {'cumulative_resources': {arm: [{'resources': {'known_cost_usd': 1, 'cost_accounting_complete': True}},
                                             {'resources': {'known_cost_usd': 2, 'cost_accounting_complete': True}}]
                                     for arm in ('ordinary', 'eal')}}
    assert assess_costs(report, ledger, plan, 'run')['cumulative'][0]['saving_usd'] is None
    for row in ledger['coverage']:
        row.update(through_session=1, evidence='time-log: complete, including zero activity')
    ledger['events'].append({'id':'author-1','arm':'eal','category':'authoring','session':0,
                             'seconds':3600.,'hourly_usd':20.,'evidence':'time-log: line 1'})
    result = assess_costs(report, ledger, plan, 'run')
    assert [row['saving_usd'] for row in result['cumulative']] == [-20., -20.]
    assert result['first_observed_cost_crossing'] is None
    ledger['events'][0]['hourly_usd'] = None
    assert assess_costs(report, ledger, plan, 'run')['status'] == 'incomplete'
    ledger['events'].append(deepcopy(ledger['events'][0]))
    with pytest.raises(ValueError, match='unique'):
        validate_ledger(ledger, plan, 'run')
    with pytest.raises(ValueError, match='identity'):
        validate_ledger(ledger, plan, 'different-run')


def test_reasoning_controls_share_inputs_and_do_not_call_the_scoring_oracle(tmp_path, monkeypatch):
    from experiments.model_transfer.project import Project
    from experiments.model_transfer.reasoning_context import prepare_reasoning_context
    from experiments.model_transfer.corpus_reference import CorpusReference
    def forbidden(*args, **kwargs):
        raise AssertionError('Scoring oracle leaked into model context')
    case = manifest_cases(manifest())[0]
    monkeypatch.setattr(ReferenceScorer, 'reference', forbidden)
    monkeypatch.setattr(CorpusReference, 'reference', forbidden)
    project = Project(tmp_path, case, 'eal')
    facts = prepare_reasoning_context(project, 'Assess', reasoner='facts', reuse='compatible')
    conventional = prepare_reasoning_context(project, 'Assess', reasoner='conventional', reuse='compatible')
    assert not any(e.get('kind') == 'eal_assess' for e in project.events)
    eal = prepare_reasoning_context(project, 'Assess', reasoner='eal', reuse='compatible')
    assert conventional == eal
    packets = [json.loads(messages[0]['content'].split('\n', 1)[1]) for messages in (facts, conventional, eal)]
    assert packets[0]['inputs'] == packets[1]['inputs'] == packets[2]['inputs']
    assert 'decision' not in packets[0] and packets[1]['decision'] == 'ready'


def test_evidence_revision_invalidates_real_host_reuse(tmp_path):
    from experiments.model_transfer.project import Project
    for case in manifest_cases(manifest())[:3]:
        project = Project(tmp_path / case.identifier, case, 'eal')
        project.context('Assess')
        project.set_session(1)
        project.context('Assess again')
        assessment = next(e['assessment'] for e in reversed(project.events) if e.get('kind') == 'eal_assess')
        changed = case.identifier.endswith('frequent')
        assert assessment['reused_count'] == (0 if changed else 1)
        assert assessment['collected_count'] == (1 if changed else 0)


def test_cost_cli_uses_new_versions_and_keeps_unmeasured_coverage_unknown(tmp_path):
    import subprocess
    import sys
    plan = {'recipient_sessions': 1}
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    (tmp_path / 'provenance.json').write_text(json.dumps({'run_id': 'test-run'}))
    old, new = tmp_path / 'costs-v1.json', tmp_path / 'costs-v2.json'
    command = [sys.executable, '-m', 'experiments.model_transfer.adoption_costs']
    subprocess.run(command + ['init', str(tmp_path), '--ledger', str(old)], check=True)
    before = old.read_bytes()
    subprocess.run(command + ['record', str(tmp_path), '--ledger', str(old), '--output', str(new),
        '--arm', 'eal', '--category', 'authoring', '--session', '0', '--seconds', '60',
        '--evidence', 'synthetic test time record'], check=True)
    assert old.read_bytes() == before
    ledger = json.loads(new.read_text())
    assert ledger['events'][0]['hourly_usd'] is None
    assert all(row['through_session'] == -1 for row in ledger['coverage'])


def test_uncertain_boundary_screen_advances_without_certifying_allocation():
    from experiments.model_transfer.allocation_assessment import ScenarioAssessment
    config = json.loads(Path('experiments/model_transfer/information-design.json').read_text())
    assessment = ScenarioAssessment(config, None)
    counters = {'false_success': 10, 'joint_coverage': 195, 'precision': 190, 'practical_support': 190}
    scenario = {'require_information': True, 'decision_role': 'null'}
    assert assessment.failures(counters, 200, scenario, .95, True, screening=True) == []
    assert 'false_success' in assessment.failures(counters, 200, scenario, .95, True)
