"""Registered computations are typed, versioned, bounded and actually executed."""
from copy import deepcopy
from dataclasses import replace
import math
import time

import pytest

from eal.extensions import RMS_CONTRACT, example_registry
from eal.evaluator import evaluate
from eal.methods import MethodRegistry, default_registry, schema_errors
from eal.modes import assess_mode, validate_mode
from eal.parser import parse
from eal.propositions import describe_bindings
from eal.semantics import validate
from test_evaluator import CONTEXT, NOW, record
from test_typed_propositions import SOURCE, VALUE


def run_method(payload, contract=RMS_CONTRACT):
    registry = default_registry().with_method(contract)
    return assess_mode(contract.identifier, [{'id': 'trial', 'kind': contract.evidence_kind, 'value': payload}], [], registry=registry)


def custom_source():
    return (SOURCE.replace('kind experiment', 'kind measurement_series')
            .replace('method "causal/1"', 'method "engineering/rms/1"')
            .replace('query {"assignment": "randomised"}', 'query {"origin":0}')
            .replace('result "estimate" >= 5', 'result "rms" == 5'))


def test_actual_rms_method_runs_through_unchanged_core_grammar_and_typed_claim():
    source = custom_source()
    program = parse(source)
    registry = example_registry()
    assert not validate(program, registry=registry)
    data = deepcopy(VALUE)
    data.update(method='engineering/rms/1', unit='kPa', payload={'origin': 0, 'samples': [3, 4, 0, 5 * math.sqrt(2)]})
    # Use exact five-valued samples so the declared equality is exact.
    data['payload']['samples'] = [5, -5]
    result = evaluate(program, {'trial': record(program, 'trial', data)}, now=NOW, context=CONTEXT, registry=registry)
    assert result['claims']['raised']['status'] == 'supported'
    computation = result['arguments']['contrast']['reasoning_result']
    assert computation['details']['rms'] == 5
    assert computation['binding']['method'] == 'engineering/rms/1'
    assert computation['binding']['method_contract']['implementation_version'] == 'eal-rms-1'
    assert validate(program)  # Source never installs the missing implementation.


def test_custom_method_does_not_enable_an_obsolete_language_version():
    source = custom_source().replace('EAL/3', 'EAL/0.3')
    assert 'unsupported_language' in {item.code for item in validate(parse(source), registry=example_registry())}


def test_registered_negative_result_remains_successful_computation():
    result = run_method({'origin': 0, 'samples': [0, 0]})
    assert result['status'] == 'supported' and result['details']['rms'] == 0


@pytest.mark.parametrize('payload', [
    {'origin': False, 'samples': [1]}, {'origin': 0, 'samples': [True]},
    {'origin': 0, 'samples': []}, {'origin': 0, 'samples': [1], 'extra': 1},
    {'origin': 0, 'samples': [float('nan')]}, {'origin': 0, 'samples': [1e101]},
])
def test_input_types_shapes_finiteness_and_bounds_are_checked(payload):
    assert run_method(payload)['status'] == 'unsupported'


def _bad_boolean(payload):
    return {'rms': True, 'sample_size': 1}


def _bad_nonfinite(payload):
    return {'rms': math.inf, 'sample_size': 1}


def _throw(payload):
    raise RuntimeError('intentional method failure')


def _hang(payload):
    while True:
        pass


@pytest.mark.parametrize('callback', [_bad_boolean, _bad_nonfinite, _throw, _hang])
def test_bad_output_exception_and_nontermination_never_become_support(callback):
    contract = replace(RMS_CONTRACT, identifier='test/failure/1', implementation=callback, timeout_seconds=.1)
    started = time.monotonic()
    result = run_method({'origin': 0, 'samples': [1]}, contract)
    assert result['status'] == ('incomplete' if callback is _hang else 'unsupported')
    assert result['details'] == {}
    assert result['evidence_id'] == 'trial'
    assert time.monotonic() - started < 3


def _mutate(payload):
    payload['samples'].append(9)
    return {'rms': 1, 'sample_size': len(payload['samples'])}


def test_callback_cannot_mutate_the_callers_input_object():
    payload = {'origin': 0, 'samples': [1]}
    contract = replace(RMS_CONTRACT, identifier='test/mutate/1', implementation=_mutate)
    assert run_method(payload, contract)['status'] == 'supported'
    assert payload == {'origin': 0, 'samples': [1]}


def test_registry_identity_changes_with_contract_version_or_schema_and_is_discoverable():
    registry = example_registry()
    changed = default_registry().with_method(replace(RMS_CONTRACT, implementation_version='rms-corrected-2'))
    assert changed.fingerprint != registry.fingerprint
    described = describe_bindings(registry=registry)
    assert described['registry_fingerprint'] == registry.fingerprint
    assert described['methods']['engineering/rms/1']['query_schema']['required'] == ['origin']
    assert len(described['methods']['engineering/rms/1']['implementation_source_digest']) == 64


def test_registration_and_discovery_do_not_expose_mutable_runtime_contracts():
    registry = example_registry()
    original = registry.fingerprint
    selected = registry.get('engineering/rms/1')
    selected.output_schema['properties']['rms']['type'] = 'boolean'
    registry.describe()['engineering/rms/1']['query_schema']['required'].clear()
    assert registry.fingerprint == original
    assert run_method({'origin': 0, 'samples': [1]})['status'] == 'supported'


def test_duplicate_ids_builtin_profiles_bad_contracts_and_nonfunction_callbacks_are_rejected():
    with pytest.raises(ValueError):
        example_registry().with_method(RMS_CONTRACT)
    with pytest.raises(ValueError):
        default_registry().with_method(replace(RMS_CONTRACT, builtin_mode='deductive'))
    with pytest.raises(ValueError):
        MethodRegistry([replace(RMS_CONTRACT, builtin_mode='deductive')])
    with pytest.raises(ValueError):
        default_registry().with_method(replace(RMS_CONTRACT, evidence_kind=None))
    with pytest.raises(ValueError):
        default_registry().with_method(replace(RMS_CONTRACT, outputs={'missing': 'basis'}))
    with pytest.raises(ValueError):
        default_registry().with_method(replace(RMS_CONTRACT, query_schema={'type': 'object', 'properties': {'unknown': {'type': 'number'}}, 'required': ['unknown'], 'additionalProperties': False}))
    class CallableObject:
        def __call__(self, payload):
            return payload
    with pytest.raises(ValueError, match='Python function'):
        default_registry().with_method(replace(RMS_CONTRACT, implementation=CallableObject()))


def test_boolean_is_not_integer_and_unknown_versions_are_not_inferred():
    assert schema_errors(True, {'type': 'integer'})
    assert validate_mode('engineering/rms/2', ['measurement_series'], registry=example_registry())
    assert default_registry().get('causal/1').identifier == 'causal/1'
    assert default_registry().get('causal') is None
    assert default_registry().get('causal/2') is None


def test_schema_alternatives_share_the_resource_budget():
    schema = {'anyOf': [{'type': 'boolean'}, {'type': 'number'}]}
    assert schema_errors(1, schema, max_nodes=2)
    assert not schema_errors(1, schema, max_nodes=3)


def test_dimensionless_statistic_is_reported_separately_from_input_quantity():
    source = custom_source().replace('result "rms" == 5', 'result "sample_size" == 2')
    program = parse(source)
    data = deepcopy(VALUE)
    data.update(method='engineering/rms/1', unit='kPa', payload={'origin': 0, 'samples': [5, -5]})
    result = evaluate(program, {'trial': record(program, 'trial', data)}, now=NOW, context=CONTEXT, registry=example_registry())
    binding = result['arguments']['contrast']['reasoning_result']['binding']
    assert binding['proposition']['quantity'] == 'pressure'
    assert binding['proposition']['unit'] == 'kPa'
    assert binding['actual'] == 2 and binding['output_unit'] == '1'
    assert binding['method_contract']['outputs']['sample_size'] == 'dimensionless'


def test_registry_snapshots_entrypoint_identity_without_reopening_source(monkeypatch):
    import eal.methods
    registry = example_registry()
    fingerprint = registry.fingerprint
    monkeypatch.setattr(eal.methods, '_source_digest', lambda function: 'changed-file-content')
    assert registry.fingerprint == fingerprint
    assert registry.get('engineering/rms/1').describe()['implementation_source_digest'] != 'changed-file-content'
    assert len(registry.get('engineering/rms/1').describe()['implementation_code_digest']) == 64
