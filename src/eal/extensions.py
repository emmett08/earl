"""An optional host-registered engineering method; not enabled by default."""
from __future__ import annotations

import math

from .methods import MethodContract, default_registry
from .propositions import QUANTITIES


def root_mean_square(payload):
    """RMS deviation from the declared dimensional origin, over finite samples."""
    origin = payload['origin']
    deviations = [value - origin for value in payload['samples']]
    # hypot scales intermediate values and avoids squaring overflow/underflow.
    return {'rms': math.hypot(*deviations) / math.sqrt(len(deviations)), 'sample_size': len(deviations)}


NUMBER = {'type': 'number', 'minimum': -1e100, 'maximum': 1e100}
RMS_CONTRACT = MethodContract(
    identifier='engineering/rms/1', evidence_kind='measurement_series',
    input_schema={'type': 'object', 'properties': {
        'origin': NUMBER, 'samples': {'type': 'array', 'items': NUMBER, 'minItems': 1, 'maxItems': 10_000}},
        'required': ['origin', 'samples'], 'additionalProperties': False},
    query_schema={'type': 'object', 'properties': {'origin': NUMBER},
                  'required': ['origin'], 'additionalProperties': False},
    output_schema={'type': 'object', 'properties': {
        'rms': {'type': 'number', 'minimum': 0, 'maximum': 2e100},
        'sample_size': {'type': 'integer', 'minimum': 1, 'maximum': 10_000}},
        'required': ['rms', 'sample_size'], 'additionalProperties': False},
    outputs={'rms': 'basis', 'sample_size': 'dimensionless'},
    quantities=tuple(name for name in QUANTITIES if name != 'proposition'),
    exact_unit=True, implementation=root_mean_square, implementation_version='eal-rms-1',
)


def example_registry():
    """Explicit host factory: `--methods eal.extensions:example_registry`."""
    return default_registry().with_method(RMS_CONTRACT)
