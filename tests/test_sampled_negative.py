"""The optional negative-finding method requires a witnessed or qualified result."""
from copy import deepcopy
import json

import pytest

from eal.evaluator import evaluate
from eal.modes import assess_mode
from eal.parser import parse
from eal.sampled_negative import SAMPLED_NEGATIVE_CONTRACT, sampled_negative_registry
from eal.semantics import validate
from test_evaluator import CONTEXT, NOW, record


BASE_QUERY = {
    'mode': 'counterexample', 'start': 0, 'end': 12, 'max_gap': 4,
    'property': {'operator': 'lt', 'value': 1}, 'semantics': 'sampled',
    'detector_contract': {'maximum_detection_limit': .9, 'minimum_sensitivity': .95},
}
CALIBRATION = {'detection_limit': .8, 'sensitivity_lower_bound': .98}


def source(query, result='"finding" == true'):
    return f'''language "EAL/2";
environment lab {{ require "site" == "bench"; }}
tool sampler {{ version "1"; }}
evidence sampled {{ tool sampler; kind sampled_negative_trace; environment lab;
 max_age 60; require "schema" == "EAL/typed-input/1"; }}
reasoning sampled_method {{ method "engineering/sampled-negative/1";
 rationale "Evaluate the bounded sampled question without a continuous-time inference."; }}
claim finding {{ statement "The selected sampled finding meets its declared conditions.";
 environment lab;
 proposition {{ subject "regulator"; quantity "dimensionless"; unit "1";
  scope "sampled-interval"; valid_from "2026-09-23T11:00:00Z";
  valid_until "2026-09-23T13:00:00Z";
  query {json.dumps(query, sort_keys=True)}; result {result}; }}
}}
argument finding_route {{ conclusion finding; reasoning sampled_method;
 evidence sampled; binding sampled; }}
'''


def value(query, events, calibration=CALIBRATION):
    payload = {**deepcopy(query), 'events': events}
    if calibration is not None:
        payload['calibration'] = deepcopy(calibration)
    return {'schema': 'EAL/typed-input/1',
            'method': SAMPLED_NEGATIVE_CONTRACT.identifier,
            'subject': 'regulator', 'quantity': 'dimensionless', 'unit': '1',
            'scope': 'sampled-interval',
            'valid_from': '2026-09-23T11:00:00Z',
            'valid_until': '2026-09-23T13:00:00Z', 'payload': payload}


def assess(query, events, *, calibration=CALIBRATION, mutate=None, result='"finding" == true'):
    program = parse(source(query, result))
    registry = sampled_negative_registry()
    assert validate(program, registry=registry) == []
    observed = value(query, events, calibration)
    if mutate:
        mutate(observed)
    return evaluate(program, {'sampled': record(program, 'sampled', observed)},
                    now=NOW, context=CONTEXT, registry=registry)


def test_observed_counterexample_can_be_supported_with_partial_sampled_coverage():
    report = assess(BASE_QUERY, [{'time': 8, 'value': 1.2}], calibration=None)
    assert report['valid']
    assert report['claims']['finding']['status'] == 'supported'
    computation = report['arguments']['finding_route']['reasoning_result']
    assert computation['details']['coverage'] is False
    assert computation['details']['violation_count'] == 1
    assert computation['details']['detector_contract_met'] is False
    assert computation['details']['continuous_truth_established'] is False
    assert computation['binding']['formal_query']['mode'] == 'counterexample'


def test_missing_witness_in_partial_trace_does_not_become_an_absence_claim():
    report = assess(BASE_QUERY, [{'time': 8, 'value': .5}], calibration=None)
    assert report['claims']['finding']['status'] == 'unsupported'
    assert 'No observed violating sample' in str(report['arguments']['finding_route']['reasoning_result']['reasons'])


def test_strict_and_inclusive_upper_bounds_have_different_boundary_witnesses():
    at_boundary = [{'time': 8, 'value': 1}]
    assert assess(BASE_QUERY, at_boundary)['claims']['finding']['status'] == 'supported'
    inclusive = {**BASE_QUERY, 'property': {'operator': 'le', 'value': 1}}
    assert assess(inclusive, at_boundary)['claims']['finding']['status'] == 'unsupported'
    assert assess(inclusive, [{'time': 8, 'value': 1.1}])['claims']['finding']['status'] == 'supported'


def test_complete_non_detection_requires_declared_detector_capability():
    query = {**BASE_QUERY, 'mode': 'non_detection'}
    events = [{'time': t, 'value': v} for t, v in ((0, .4), (4, .5), (8, .6), (12, .7))]
    report = assess(query, events)
    assert report['claims']['finding']['status'] == 'supported'
    details = report['arguments']['finding_route']['reasoning_result']['details']
    assert details['coverage'] is True and details['violation_count'] == 0
    assert details['detector_contract_met'] is True
    assert details['continuous_truth_established'] is False


@pytest.mark.parametrize('events,calibration,fragment', [
    ([{'time': 0, 'value': .3}, {'time': 8, 'value': .4},
      {'time': 12, 'value': .5}], CALIBRATION, 'both endpoints and every sampled gap'),
    ([{'time': 0, 'value': .3}, {'time': 4, 'value': .4}], CALIBRATION,
     'both endpoints and every sampled gap'),
    ([{'time': 0, 'value': .3}, {'time': 4, 'value': .4},
      {'time': 8, 'value': .5}, {'time': 12, 'value': .6}], None, 'requires documented detector'),
    ([{'time': 0, 'value': .3}, {'time': 4, 'value': .4},
      {'time': 8, 'value': .5}, {'time': 12, 'value': .6}],
     {'detection_limit': .8, 'sensitivity_lower_bound': .8},
     'sensitivity is below'),
    ([{'time': 0, 'value': .3}, {'time': 4, 'value': .4},
      {'time': 8, 'value': .5}, {'time': 12, 'value': .6}],
     {'detection_limit': .95, 'sensitivity_lower_bound': .98},
     'limit exceeds'),
    ([{'time': 0, 'value': .3}, {'time': 4, 'value': .4},
      {'time': 8, 'value': 1.1}, {'time': 12, 'value': .6}],
     CALIBRATION, 'violating sample prevents'),
])
def test_non_detection_fails_closed_for_incomplete_or_inadequate_inputs(events, calibration, fragment):
    query = {**BASE_QUERY, 'mode': 'non_detection'}
    report = assess(query, events, calibration=calibration)
    computation = report['arguments']['finding_route']['reasoning_result']
    assert computation['status'] == 'unsupported'
    assert report['claims']['finding']['status'] == 'unsupported'
    assert fragment in str(computation['reasons'])


def test_a_detector_limit_above_the_property_boundary_cannot_clear_non_detection():
    query = {**BASE_QUERY, 'mode': 'non_detection', 'detector_contract': {
        'maximum_detection_limit': 1.1, 'minimum_sensitivity': .95}}
    events = [{'time': t, 'value': .5} for t in (0, 4, 8, 12)]
    report = assess(query, events, calibration={'detection_limit': 1.0,
                                                'sensitivity_lower_bound': .98})
    assert report['claims']['finding']['status'] == 'unsupported'
    assert 'could miss values' in str(report['arguments']['finding_route']['reasoning_result']['reasons'])


def test_negative_detector_limits_are_rejected_in_source_and_calibration():
    query = {**BASE_QUERY, 'mode': 'non_detection', 'detector_contract': {
        'maximum_detection_limit': -.1, 'minimum_sensitivity': .95}}
    diagnostics = validate(parse(source(query)), registry=sampled_negative_registry())
    assert any(d.code == 'proposition_method' for d in diagnostics)

    valid_query = {**BASE_QUERY, 'mode': 'non_detection'}
    events = [{'time': t, 'value': .5} for t in (0, 4, 8, 12)]
    report = assess(valid_query, events, calibration={
        'detection_limit': -.1, 'sensitivity_lower_bound': .98})
    assert report['claims']['finding']['status'] == 'unsupported'
    reasons = report['arguments']['finding_route']['reasoning_result']['reasons']
    assert 'calibration.detection_limit' in str(reasons)


@pytest.mark.parametrize('mutate', [
    lambda observed: observed.update(scope='other-interval'),
    lambda observed: observed['payload'].update(mode='non_detection'),
    lambda observed: observed['payload']['property'].update(value=2),
    lambda observed: observed.update(subject='other-regulator'),
])
def test_typed_scope_subject_mode_and_threshold_mismatch_rejects_fluent_readings(mutate):
    report = assess(BASE_QUERY, [{'time': 8, 'value': 1.2}], mutate=mutate)
    assert report['claims']['finding']['status'] == 'unsupported'
    binding = report['arguments']['finding_route']['reasoning_result']['binding']
    assert binding['status'] == 'unsupported'


def test_only_the_selected_positive_finding_polarity_can_be_claimed():
    witness = [{'time': 8, 'value': 1.2}]
    assert assess(BASE_QUERY, witness)['claims']['finding']['status'] == 'supported'
    assert assess(BASE_QUERY, witness, result='"finding" == false')['claims']['finding']['status'] == 'unsupported'
    nondetection = {**BASE_QUERY, 'mode': 'non_detection'}
    assert assess(nondetection, witness)['claims']['finding']['status'] == 'unsupported'


def test_registered_method_is_opt_in_and_rejects_invalid_event_order():
    program = parse(source(BASE_QUERY))
    assert validate(program)  # Method is not installed by the source.
    registry = sampled_negative_registry()
    assert registry.get(SAMPLED_NEGATIVE_CONTRACT.identifier)
    payload = {**BASE_QUERY, 'events': [
        {'time': 8, 'value': 1.2}, {'time': 4, 'value': .2}]}
    result = assess_mode(SAMPLED_NEGATIVE_CONTRACT.identifier,
                         [{'id': 'sampled', 'kind': 'sampled_negative_trace', 'value': payload}], [],
                         registry=registry)
    assert result['status'] == 'unsupported'


def test_a_partial_counterexample_can_activate_a_declared_objection():
    augmented = source(BASE_QUERY) + '''
evidence baseline { tool sampler; kind validation; environment lab;
 max_age 60; require "passed" == true; }
reasoning baseline_method { method "structured/1";
 rationale "The independent baseline observation supports the initial bounded result."; }
claim initial_result { statement "The initial test supports the bounded result.";
 environment lab; }
argument initial_route { conclusion initial_result; reasoning baseline_method;
 evidence baseline; }
objection observed_violation { target argument initial_route; premises finding; }
'''
    program = parse(augmented)
    registry = sampled_negative_registry()
    assert validate(program, registry=registry) == []

    def run(at, reading):
        observations = {
            'sampled': record(program, 'sampled',
                              value(BASE_QUERY, [{'time': at, 'value': reading}], None)),
            'baseline': record(program, 'baseline', {'passed': True}),
        }
        return evaluate(program, observations, now=NOW, context=CONTEXT, registry=registry)

    witnessed = run(8, 1.2)
    assert witnessed['claims']['finding']['status'] == 'supported'
    assert witnessed['objections']['observed_violation']['status'] == 'active'
    assert witnessed['claims']['initial_result']['status'] == 'contested'
    unwitnessed = run(8, .5)
    assert unwitnessed['claims']['finding']['status'] == 'unsupported'
    assert unwitnessed['objections']['observed_violation']['status'] == 'inactive'
    assert unwitnessed['claims']['initial_result']['status'] == 'supported'
