"""EAL/3 scalar propositions and versioned method/input correspondence.

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
from .builtin_methods import BUILTIN_SPECS

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
# These read-only discovery views derive from the same versioned specifications
# used to construct the registered MethodContracts.
OUTPUTS = {mode: dict(spec.outputs) for mode, spec in BUILTIN_SPECS.items() if spec.outputs}
QUERY_FIELDS = {mode: spec.query_fields for mode, spec in BUILTIN_SPECS.items() if spec.outputs}
_COMPARISONS = {'==': operator.eq, '!=': operator.ne, '<': operator.lt,
                '<=': operator.le, '>': operator.gt, '>=': operator.ge}


def describe_bindings(registry=None):
    """Machine-readable, versioned discovery of the implemented closed fragment."""
    from .methods import default_registry
    registry = registry or default_registry()
    return {'schema': SCHEMA, 'registry_fingerprint': registry.fingerprint, 'quantities': dict(QUANTITIES),
            'units': {name: {'dimension': dim, 'base_scale': scale} for name, (dim, scale) in UNITS.items()},
            'methods': registry.describe(),
            'envelope_fields': ['schema', 'method', 'subject', 'quantity', 'unit', 'scope',
                                'valid_from', 'valid_until', 'payload'],
            'interval': 'half-open [valid_from, valid_until); input must contain claim interval',
            'interpretation': 'metadata correspondence; physical relevance and prose correspondence remain asserted'}


def _contract(method, registry=None):
    from .methods import default_registry
    return (registry or default_registry()).get(method)


def _output_type(method, path, registry=None):
    contract = _contract(method, registry)
    return contract.output_type(path) if contract else None


def proposition_errors(proposition: Proposition, method: str | None = None, registry=None):
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
    if method is not None:
        from .methods import schema_errors
        contract = _contract(method, registry)
        if contract is None:
            errors.append(f'Unknown registered method {method!r}')
            return errors
        errors.extend(schema_errors(proposition.query, contract.query_schema, 'query'))
        output = contract.output_type(proposition.result.path)
        if output is None:
            errors.append(f'Method {method!r} has no typed result {proposition.result.path!r}')
        elif (output == 'boolean') != isinstance(expected, bool):
            errors.append('Proposition result type does not match the method output type')
        if proposition.quantity not in contract.quantities:
            errors.append(f'Method {method!r} does not accept quantity {proposition.quantity!r}')
    return errors


def prepare_binding(proposition: Proposition, method: str, evidence_id: str, value, registry=None):
    """Check complete input correspondence before passing a payload to a method."""
    from .semantics import parse_time
    contract = _contract(method, registry)
    if contract is None:
        return None, {"status": "unsupported", "reasons": [f"Unknown registered method {method!r}"]}
    fields = {'schema', 'method', 'subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until', 'payload'}
    trace = {'evidence_id': evidence_id, 'method': contract.identifier, 'proposition': asdict(proposition),
             'method_contract': contract.describe(),
             'prose_verified': False, 'physical_interpretation_verified': False}
    reasons = []
    if not isinstance(value, dict) or set(value) != fields:
        return None, {**trace, 'status': 'unsupported', 'reasons': ['Typed input requires exactly the declared envelope fields']}
    for key, expected in (('schema', SCHEMA), ('method', contract.identifier), ('subject', proposition.subject),
                          ('quantity', proposition.quantity), ('scope', proposition.scope)):
        if value.get(key) != expected:
            reasons.append(f'Typed input {key} does not match the proposition or method')
    unit = value.get('unit')
    if not isinstance(unit, str) or unit not in UNITS or UNITS[unit][0] != QUANTITIES[proposition.quantity]:
        reasons.append('Typed input unit is incompatible with the proposition quantity')
    if contract.exact_unit and unit != proposition.unit:
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
        for key in contract.query_fields:
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


def check_result(proposition: Proposition, method: str, details: dict, trace: dict, registry=None):
    """Evaluate the formal result predicate, converting only physical statistics."""
    actual = details
    for field in proposition.result.path.split('.'):
        if not isinstance(actual, dict) or field not in actual:
            return {**trace, 'status': 'unsupported', 'reasons': ['Bound method output is missing']}
        actual = actual[field]
    output = _output_type(method, proposition.result.path, registry)
    if output is None:
        return {**trace, 'status': 'unsupported', 'reasons': ['Bound method output is not declared by the method contract']}
    is_numeric = type(actual) in (int, float) and (not isinstance(actual, float) or math.isfinite(actual))
    if output == 'boolean' and type(actual) is not bool or output != 'boolean' and not is_numeric:
        return {**trace, 'status': 'unsupported', 'reasons': ['Bound method output has an incompatible type']}
    output_unit = None if output == 'boolean' else '1'
    if output == 'basis':
        ratio = Fraction(UNITS[trace['input_unit']][1]) / Fraction(UNITS[proposition.unit][1])
        if ratio != 1:
            exact = Fraction(str(actual)) * ratio
            try:
                actual = float(exact)
            except OverflowError:
                return {**trace, 'status': 'unsupported', 'reasons': ['Unit conversion exceeds the finite numeric range']}
            if exact != 0 and actual == 0:
                return {**trace, 'status': 'unsupported', 'reasons': ['Unit conversion underflow would erase a nonzero result']}
        output_unit = proposition.unit
        if type(actual) is float and not math.isfinite(actual):
            return {**trace, 'status': 'unsupported', 'reasons': ['Converted result is not finite']}
    holds = _COMPARISONS[proposition.result.operator](actual, proposition.result.expected)
    return {**trace, 'status': 'supported' if holds else 'unsupported', 'holds': holds,
            'actual': actual, 'output_unit': output_unit,
            'reasons': [f'Bound result {proposition.result.path!r} {proposition.result.operator} '
                        f'{proposition.result.expected!r} {"holds" if holds else "does not hold"}']}
