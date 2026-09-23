"""Adversarial cases for installed contracts and scalar result correspondence."""
from copy import deepcopy
from dataclasses import replace
from types import FunctionType

import pytest

from eal.extensions import RMS_CONTRACT
from eal.evaluator import evaluate
from eal.methods import MethodRegistry, default_registry, schema_errors
from eal.model import Predicate, Proposition
from eal.modes import assess_mode
from eal.parser import parse
from eal.propositions import check_result
from test_evaluator import CONTEXT, NOW, record
from test_method_extensions import custom_source
from test_typed_propositions import VALUE


@pytest.mark.parametrize('allowed, supplied', [
    ({'enabled': True}, {'enabled': 1}),
    ([False], [0]),
    ({'values': [1]}, {'values': [True]}),
])
def test_nested_enumerations_preserve_boolean_and_numeric_types(allowed, supplied):
    schema = {'type': 'json', 'enum': [allowed]}
    assert schema_errors(supplied, schema)
    assert not schema_errors(deepcopy(allowed), schema)


def test_query_field_cannot_have_a_different_type_in_the_input_contract():
    query = deepcopy(RMS_CONTRACT.query_schema)
    query['properties']['origin'] = {'type': 'boolean'}
    with pytest.raises(ValueError, match='query.*schema'):
        default_registry().with_method(replace(RMS_CONTRACT, query_schema=query))


def test_query_field_must_be_required_by_the_input_contract():
    input_schema = deepcopy(RMS_CONTRACT.input_schema)
    input_schema['required'].remove('origin')
    with pytest.raises(ValueError, match='query.*required'):
        default_registry().with_method(replace(RMS_CONTRACT, input_schema=input_schema))


def _pressure_result(expected):
    return Proposition('pump-A', 'pressure', 'Pa', 'experiment-v1',
                       '2026-09-23T10:00:00Z', '2026-09-23T11:00:00Z',
                       Predicate('rms', '==', expected), {'origin': 0})


def _large_result(payload):
    return {'rms': 1e308, 'sample_size': len(payload['samples'])}


def _tiny_result(payload):
    return {'rms': 5e-324, 'sample_size': len(payload['samples'])}


@pytest.mark.parametrize('callback,input_unit,proposition_unit,reason', [
    (_large_result, 'MPa', 'Pa', 'conversion'),
    (_tiny_result, 'Pa', 'MPa', 'underflow'),
])
def test_conversion_failure_cannot_support_zero_from_a_valid_extension_result(
        callback, input_unit, proposition_unit, reason):
    output_schema = deepcopy(RMS_CONTRACT.output_schema)
    del output_schema['properties']['rms']['maximum']
    contract = replace(RMS_CONTRACT, exact_unit=False, implementation=callback,
                       output_schema=output_schema)
    registry = default_registry().with_method(contract)
    source = custom_source().replace('unit "kPa"', f'unit "{proposition_unit}"')
    program = parse(source.replace('result "rms" == 5', 'result "rms" == 0'))
    data = deepcopy(VALUE)
    data.update(method=contract.identifier, unit=input_unit,
                payload={'origin': 0, 'samples': [1]})
    result = evaluate(program, {'trial': record(program, 'trial', data)},
                      now=NOW, context=CONTEXT, registry=registry)
    assert result['valid']
    assert result['claims']['raised']['status'] == 'unsupported'
    computation = result['arguments']['contrast']['reasoning_result']
    assert computation['status'] == 'supported'
    assert computation['binding']['status'] == 'unsupported'
    assert reason in computation['binding']['reasons'][0].lower()


def test_unknown_result_path_cannot_be_compared_as_an_implicit_number():
    proposition = replace(_pressure_result(1), result=Predicate('undeclared', '==', 1))
    result = check_result(proposition, RMS_CONTRACT.identifier, {'undeclared': 1},
                          {'input_unit': 'Pa'}, registry=default_registry().with_method(RMS_CONTRACT))
    assert result['status'] == 'unsupported'


def _numeric_identity(payload):
    return {'evidence_id': 2}


def test_declared_output_is_not_overwritten_by_interpreter_evidence_metadata():
    contract = replace(RMS_CONTRACT, implementation=_numeric_identity,
                       output_schema={'type': 'object',
                           'properties': {'evidence_id': {'type': 'integer'}},
                           'required': ['evidence_id'], 'additionalProperties': False},
                       outputs={'evidence_id': 'dimensionless'})
    registry = default_registry().with_method(contract)
    program = parse(custom_source().replace('result "rms" == 5', 'result "evidence_id" == 2'))
    data = deepcopy(VALUE)
    data.update(method=contract.identifier, unit='kPa', payload={'origin': 0, 'samples': [1]})
    result = evaluate(program, {'trial': record(program, 'trial', data)},
                      now=NOW, context=CONTEXT, registry=registry)
    assert result['claims']['raised']['status'] == 'supported'
    computation = result['arguments']['contrast']['reasoning_result']
    assert computation['details'] == {'evidence_id': 2}
    assert computation['evidence_id'] == 'trial'
    assert computation['binding']['actual'] == 2


def _changed_builtin(payload):
    return {'status': 'supported', 'reasons': [], 'details': {
        'estimate': 999, 'standard_error': 0, 'treatment_mean': 999, 'control_mean': 0}}


def _causal_input():
    return [{'id': 'trial', 'kind': 'experiment', 'value': {
        'assignment': 'randomised', 'treatment': [2, 2], 'control': [1, 1]}}]


def test_builtin_executes_the_registered_entrypoint_after_dispatch_table_changes(monkeypatch):
    import eal.modes
    registry = default_registry()
    fingerprint = registry.fingerprint
    monkeypatch.setitem(eal.modes._COMPUTATIONS, 'causal', _changed_builtin)
    result = assess_mode('causal/1', _causal_input(), [], registry=registry)
    assert result['status'] == 'supported'
    assert result['details']['estimate'] == 1
    assert registry.fingerprint == fingerprint


def test_changed_registered_builtin_code_cannot_keep_its_old_identity(monkeypatch):
    import eal.modes
    original = default_registry().get('causal/1')
    # Mutate a private function copy, keeping the actual built-in untouched.
    callback = FunctionType(original.implementation.__code__, original.implementation.__globals__)
    monkeypatch.setitem(eal.modes._COMPUTATIONS, 'causal', callback)
    registry = MethodRegistry([replace(original, implementation=callback)])
    callback.__code__ = _changed_builtin.__code__
    result = assess_mode('causal/1', _causal_input(), [], registry=registry)
    assert result['status'] == 'unsupported'
    assert 'registered code identity' in result['reasons'][0]
