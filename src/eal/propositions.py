"""EAL/0.2 scalar propositions and versioned method/input correspondence.

Metadata asserts an engineering interpretation. Checks establish correspondence
within that interpretation; they cannot authenticate a sensor or interpret prose.
"""
from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import math
import operator
import re

from .model import Proposition

SCHEMA = 'EAL/typed-input/1'
# Unit scales are exact rational multiples of the declared base unit. Absolute
# temperatures and offset conversions are deliberately outside this fragment.
UNITS = {
    '1': ('dimensionless', '1'),
    'Pa': ('pressure', '1'), 'kPa': ('pressure', '1000'), 'MPa': ('pressure', '1000000'),
    's': ('time', '1'), 'ms': ('time', '0.001'), 'us': ('time', '0.000001'),
    'ns': ('time', '0.000000001'), 'min': ('time', '60'), 'h': ('time', '3600'),
    'm': ('length', '1'), 'mm': ('length', '0.001'), 'cm': ('length', '0.01'), 'km': ('length', '1000'),
    'kg': ('mass', '1'), 'g': ('mass', '0.001'),
    'K': ('temperature_difference', '1'), 'delta_degC': ('temperature_difference', '1'),
    'm/s': ('velocity', '1'), 'km/h': ('velocity', '5/18'),
    'm3/s': ('volumetric_flow', '1'), 'L/s': ('volumetric_flow', '0.001'),
}
QUANTITIES = {name: name for name in ('pressure', 'time', 'length', 'mass',
                                     'temperature_difference', 'velocity', 'volumetric_flow', 'dimensionless')}
QUANTITIES.update(probability='dimensionless', proposition='dimensionless')
# Each path denotes a specified statistic, not an arbitrary result field. basis
# means the unit of the measured quantity; boolean results have no numeric unit.
OUTPUTS = {
    'deductive': {'entailed': 'boolean', 'consistent_premises': 'boolean'},
    'inductive': {'estimate': 'dimensionless', 'lower': 'dimensionless', 'upper': 'dimensionless'},
    'abductive': {'best_posterior': 'dimensionless', 'posterior.*': 'dimensionless'},
    'causal': {'estimate': 'basis', 'standard_error': 'basis', 'treatment_mean': 'basis', 'control_mean': 'basis'},
    'counterfactual': {'factual': 'basis', 'counterfactual': 'basis', 'difference': 'basis'},
    'analogical': {'match_fraction': 'dimensionless', 'complete': 'boolean'},
    'temporal': {'holds': 'boolean', 'coverage': 'boolean'},
}
QUERY_FIELDS = {
    'deductive': ('premises', 'conclusion'),
    'inductive': ('confidence',),
    'abductive': ('observed', 'candidates'),
    'causal': ('assignment',),
    'counterfactual': ('variables', 'intervention', 'outcome'),
    'analogical': ('relevant_features', 'source', 'target'),
    'temporal': ('start', 'end', 'max_gap', 'property', 'semantics'),
}
_COMPARISONS = {'==': operator.eq, '!=': operator.ne, '<': operator.lt,
                '<=': operator.le, '>': operator.gt, '>=': operator.ge}


def describe_bindings():
    """Machine-readable, versioned discovery of the implemented closed fragment."""
    return {'schema': SCHEMA, 'quantities': dict(QUANTITIES),
            'units': {name: {'dimension': dim, 'base_scale': scale} for name, (dim, scale) in UNITS.items()},
            'methods': {f'{mode}/1': {'outputs': dict(paths), 'query_fields': list(QUERY_FIELDS[mode])}
                        for mode, paths in OUTPUTS.items()},
            'envelope_fields': ['schema', 'method', 'subject', 'quantity', 'unit', 'scope',
                                'valid_from', 'valid_until', 'payload'],
            'interval': 'half-open [valid_from, valid_until); input must contain claim interval',
            'interpretation': 'metadata correspondence; physical relevance and prose correspondence remain asserted'}


def _output_type(mode, path):
    paths = OUTPUTS.get(mode, {})
    if path in paths:
        return paths[path]
    if mode == 'abductive' and re.fullmatch(r'posterior\.[A-Za-z_][A-Za-z0-9_]{0,63}', path):
        return 'dimensionless'
    return None


def proposition_errors(proposition: Proposition, mode: str | None = None):
    """Static shape/type errors without reading observations."""
    from .semantics import parse_time, _check_json_resources
    errors = []
    for key in ('subject', 'scope'):
        value = getattr(proposition, key)
        if not value.strip() or len(value) > 4096:
            errors.append(f'{key} must be nonblank and at most 4096 characters')
    if proposition.quantity not in QUANTITIES:
        errors.append(f'Unknown quantity {proposition.quantity!r}')
    if proposition.unit not in UNITS:
        errors.append(f'Unknown unit {proposition.unit!r}')
    elif proposition.quantity in QUANTITIES and UNITS[proposition.unit][0] != QUANTITIES[proposition.quantity]:
        errors.append(f'Unit {proposition.unit!r} does not measure quantity {proposition.quantity!r}')
    try:
        if parse_time(proposition.valid_from) >= parse_time(proposition.valid_until):
            errors.append('Proposition valid_from must precede valid_until')
    except (ValueError, TypeError):
        errors.append('Proposition interval requires ISO-8601 timestamps with timezones')
    expected = proposition.result.expected
    if not isinstance(expected, (bool, int, float)) or isinstance(expected, float) and not math.isfinite(expected):
        errors.append('A scalar proposition result must compare a finite number or boolean')
    if isinstance(expected, bool) and proposition.result.operator not in ('==', '!='):
        errors.append('Boolean proposition results support only == and !=')
    try:
        _check_json_resources(proposition.query)
        json.dumps(proposition.query, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        errors.append('Proposition query must be finite JSON')
    if mode is not None:
        if not isinstance(proposition.query, dict) or set(proposition.query) != set(QUERY_FIELDS.get(mode, ())):
            errors.append(f'Method {mode!r} requires exactly these query fields: {", ".join(QUERY_FIELDS.get(mode, ()))}')
        output = _output_type(mode, proposition.result.path)
        if output is None:
            errors.append(f'Method {mode!r} has no typed result {proposition.result.path!r}')
        elif (output == 'boolean') != isinstance(expected, bool):
            errors.append('Proposition result type does not match the method output type')
        required_quantity = {'deductive': 'proposition', 'inductive': 'probability',
                             'abductive': 'probability', 'analogical': 'dimensionless'}.get(mode)
        if required_quantity and proposition.quantity != required_quantity:
            errors.append(f'Method {mode!r} requires quantity {required_quantity!r}')
        if mode in ('causal', 'counterfactual', 'temporal') and proposition.quantity == 'proposition':
            errors.append(f'Method {mode!r} requires a numerical measured quantity')
    return errors


def prepare_binding(proposition: Proposition, mode: str, evidence_id: str, value):
    """Check complete input correspondence before passing a payload to a method."""
    from .semantics import parse_time
    fields = {'schema', 'method', 'subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until', 'payload'}
    trace = {'evidence_id': evidence_id, 'method': f'{mode}/1', 'proposition': asdict(proposition),
             'prose_verified': False, 'physical_interpretation_verified': False}
    reasons = []
    if not isinstance(value, dict) or set(value) != fields:
        return None, {**trace, 'status': 'unsupported', 'reasons': ['Typed input requires exactly the declared envelope fields']}
    for key, expected in (('schema', SCHEMA), ('method', f'{mode}/1'), ('subject', proposition.subject),
                          ('quantity', proposition.quantity), ('scope', proposition.scope)):
        if value.get(key) != expected:
            reasons.append(f'Typed input {key} does not match the proposition or method')
    unit = value.get('unit')
    if not isinstance(unit, str) or unit not in UNITS or UNITS[unit][0] != QUANTITIES[proposition.quantity]:
        reasons.append('Typed input unit is incompatible with the proposition quantity')
    if mode in ('temporal', 'counterfactual') and unit != proposition.unit:
        reasons.append('This method embeds dimensional query constants and requires the exact proposition unit')
    try:
        start, end = parse_time(value['valid_from']), parse_time(value['valid_until'])
        if start >= end or start > parse_time(proposition.valid_from) or end < parse_time(proposition.valid_until):
            reasons.append('Typed input interval does not contain the whole proposition interval')
    except (ValueError, TypeError, OverflowError):
        reasons.append('Typed input interval requires valid timezone-aware timestamps')
    # Match the intended mathematical question independently of measured values.
    # JSON canonicalisation distinguishes booleans from numbers and retains the
    # whole formula/model, including unused premises and zero coefficients.
    payload = value['payload']
    if not isinstance(payload, dict):
        reasons.append('Typed input payload must be an object')
    else:
        for key in QUERY_FIELDS.get(mode, ()):
            expected = json.dumps(proposition.query.get(key), sort_keys=True, separators=(',', ':'), allow_nan=False)
            try:
                actual = json.dumps(payload[key], sort_keys=True, separators=(',', ':'), allow_nan=False)
            except (KeyError, ValueError, TypeError, RecursionError):
                actual = None
            if actual != expected:
                reasons.append(f'Typed input query field {key!r} does not match the declared proposition query')
    # Hash the entire formal problem, rather than only its numerical answer.
    try:
        encoded = json.dumps(value['payload'], sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
        trace.update(input_payload_digest=hashlib.sha256(encoded).hexdigest(), formal_query=value['payload'], input_unit=unit)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        reasons.append('Typed input payload must be finite JSON')
    trace.update(status='unsupported' if reasons else 'bound', reasons=reasons)
    return (None if reasons else value['payload']), trace


def check_result(proposition: Proposition, mode: str, details: dict, trace: dict):
    """Evaluate the formal result predicate, converting only physical statistics."""
    actual = details
    for field in proposition.result.path.split('.'):
        if not isinstance(actual, dict) or field not in actual:
            return {**trace, 'status': 'unsupported', 'reasons': ['Bound method output is missing']}
        actual = actual[field]
    output = _output_type(mode, proposition.result.path)
    is_numeric = type(actual) in (int, float) and (not isinstance(actual, float) or math.isfinite(actual))
    if output == 'boolean' and type(actual) is not bool or output != 'boolean' and not is_numeric:
        return {**trace, 'status': 'unsupported', 'reasons': ['Bound method output has an incompatible type']}
    output_unit = None if output == 'boolean' else '1'
    if output == 'basis':
        ratio = Fraction(UNITS[trace['input_unit']][1]) / Fraction(UNITS[proposition.unit][1])
        if ratio != 1:
            actual = float(Fraction(str(actual)) * ratio)
        output_unit = proposition.unit
        if type(actual) is float and not math.isfinite(actual):
            return {**trace, 'status': 'unsupported', 'reasons': ['Converted result is not finite']}
    holds = _COMPARISONS[proposition.result.operator](actual, proposition.result.expected)
    return {**trace, 'status': 'supported' if holds else 'unsupported', 'holds': holds,
            'actual': actual, 'output_unit': output_unit,
            'reasons': [f'Bound result {proposition.result.path!r} {proposition.result.operator} '
                        f'{proposition.result.expected!r} {"holds" if holds else "does not hold"}']}
