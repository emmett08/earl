"""Optional sampled negative-finding method with explicit observation limits.

The two query modes share a sampled upper-bound property. A reported violating
sample is a counterexample within the declared sample set even if the trace has
gaps. Non-detection requires complete *sampled* coverage and declared detector
capability. Neither mode establishes a continuous-time or physical conclusion.
"""
from __future__ import annotations

from .methods import MethodContract, default_registry
from .propositions import QUANTITIES


NUMBER = {'type': 'number', 'minimum': -1e100, 'maximum': 1e100}
NONNEGATIVE = {'type': 'number', 'minimum': 0, 'maximum': 1e100}
FRACTION = {'type': 'number', 'minimum': 0, 'maximum': 1}
PROPERTY = {'type': 'object', 'properties': {
    'operator': {'type': 'string', 'enum': ['lt', 'le']}, 'value': NUMBER},
    'required': ['operator', 'value'], 'additionalProperties': False}
DETECTOR_CONTRACT = {'type': 'object', 'properties': {
    'maximum_detection_limit': NONNEGATIVE, 'minimum_sensitivity': FRACTION},
    'required': ['maximum_detection_limit', 'minimum_sensitivity'],
    'additionalProperties': False}
CALIBRATION = {'type': 'object', 'properties': {
    'detection_limit': NONNEGATIVE, 'sensitivity_lower_bound': FRACTION},
    'required': ['detection_limit', 'sensitivity_lower_bound'],
    'additionalProperties': False}
EVENT = {'type': 'object', 'properties': {'time': NUMBER, 'value': NUMBER},
         'required': ['time', 'value'], 'additionalProperties': False}
QUERY = {
    'mode': {'type': 'string', 'enum': ['counterexample', 'non_detection']},
    'start': NUMBER, 'end': NUMBER, 'max_gap': NONNEGATIVE,
    'property': PROPERTY, 'semantics': {'type': 'string', 'enum': ['sampled']},
    'detector_contract': DETECTOR_CONTRACT,
}


def sampled_negative(payload):
    """Return a finding only when its selected mode has a valid witness.

    The input schema checks shapes and finite bounds before this callback runs.
    Calibration fields remain assertions supplied by acquisition; the method
    compares them but does not authenticate the instrument or its measurements.
    """
    start, end, max_gap = (payload[key] for key in ('start', 'end', 'max_gap'))
    if end < start or max_gap <= 0:
        raise ValueError('Sampled interval requires end >= start and max_gap > 0')
    events = payload['events']
    previous = None
    largest_gap = 0
    for event in events:
        at = event['time']
        if at < start or at > end or previous is not None and at <= previous:
            raise ValueError('Samples must be strictly ordered within the declared interval')
        if previous is not None:
            largest_gap = max(largest_gap, at - previous)
        previous = at
    coverage = events[0]['time'] == start and events[-1]['time'] == end and largest_gap <= max_gap
    property_spec = payload['property']
    bound = property_spec['value']
    # Keep the strict and inclusive upper-bound cases explicit at the boundary.
    if property_spec['operator'] == 'lt':
        violating = [event['time'] for event in events if event['value'] >= bound]
    else:
        violating = [event['time'] for event in events if event['value'] > bound]

    mode = payload['mode']
    if mode == 'counterexample':
        if not violating:
            raise ValueError('No observed violating sample; partial sampling cannot establish absence')
        detector_checked = False
    else:
        if violating:
            raise ValueError('A violating sample prevents a non-detection finding')
        if not coverage:
            raise ValueError('Non-detection requires both endpoints and every sampled gap within max_gap')
        calibration = payload.get('calibration')
        if calibration is None:
            raise ValueError('Non-detection requires documented detector calibration')
        contract = payload['detector_contract']
        if contract['minimum_sensitivity'] <= 0:
            raise ValueError('Non-detection requires a positive minimum sensitivity')
        if contract['maximum_detection_limit'] > bound:
            raise ValueError('Detector limit could miss values violating the declared upper bound')
        if calibration['detection_limit'] > contract['maximum_detection_limit']:
            raise ValueError('Documented detector limit exceeds the declared maximum')
        if calibration['sensitivity_lower_bound'] < contract['minimum_sensitivity']:
            raise ValueError('Documented detector sensitivity is below the declared minimum')
        detector_checked = True

    return {
        'finding': True, 'mode': mode, 'sample_size': len(events),
        'violation_count': len(violating), 'coverage': coverage,
        'largest_gap': largest_gap, 'detector_contract_met': detector_checked,
        'continuous_truth_established': False,
    }


INPUT_SCHEMA = {'type': 'object', 'properties': {
    **QUERY,
    'events': {'type': 'array', 'items': EVENT, 'minItems': 1, 'maxItems': 10_000},
    'calibration': CALIBRATION,
}, 'required': [*QUERY, 'events'], 'additionalProperties': False}
QUERY_SCHEMA = {'type': 'object', 'properties': QUERY,
                'required': list(QUERY), 'additionalProperties': False}
OUTPUT_SCHEMA = {'type': 'object', 'properties': {
    'finding': {'type': 'boolean'},
    'mode': QUERY['mode'],
    'sample_size': {'type': 'integer', 'minimum': 1, 'maximum': 10_000},
    'violation_count': {'type': 'integer', 'minimum': 0, 'maximum': 10_000},
    'coverage': {'type': 'boolean'},
    'largest_gap': {'type': 'number', 'minimum': 0, 'maximum': 2e100},
    'detector_contract_met': {'type': 'boolean'},
    'continuous_truth_established': {'type': 'boolean'},
}, 'required': ['finding', 'mode', 'sample_size', 'violation_count', 'coverage',
                'largest_gap', 'detector_contract_met', 'continuous_truth_established'],
    'additionalProperties': False}

SAMPLED_NEGATIVE_CONTRACT = MethodContract(
    identifier='engineering/sampled-negative/1', evidence_kind='sampled_negative_trace',
    input_schema=INPUT_SCHEMA, query_schema=QUERY_SCHEMA, output_schema=OUTPUT_SCHEMA,
    outputs={'finding': 'boolean'},
    quantities=tuple(name for name in QUANTITIES if name != 'proposition'),
    exact_unit=True, implementation=sampled_negative,
    implementation_version='eal-sampled-negative-1',
)


def sampled_negative_registry():
    """Install explicitly with `--methods eal.sampled_negative:sampled_negative_registry`."""
    return default_registry().with_method(SAMPLED_NEGATIVE_CONTRACT)
