"""Typed scientific questions, units and computation-to-claim bindings."""
from copy import deepcopy

import pytest

from eal.evaluator import evaluate
from eal.parser import parse
from eal.semantics import validate
from test_evaluator import record, CONTEXT, NOW

SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool readings { version "1"; }
evidence trial { tool readings; kind experiment; environment lab; max_age 60;
 require "schema" == "EAL/typed-input/1";
}
reasoning difference { method "causal/1"; rationale "Difference of means in the declared randomised experiment."; }
claim raised { statement "The treatment mean pressure exceeds control by at least 5 kPa.";
 environment lab;
 proposition {
  subject "pump-A"; quantity "pressure"; unit "kPa"; scope "experiment-v1";
  valid_from "2026-09-23T10:00:00Z"; valid_until "2026-09-23T11:00:00Z";
  query {"assignment":"randomised"};
  result "estimate" >= 5;
 }
}
argument contrast { conclusion raised; reasoning difference; evidence trial; binding trial; }
'''
VALUE = {'schema': 'EAL/typed-input/1', 'method': 'causal/1', 'subject': 'pump-A',
         'quantity': 'pressure', 'unit': 'Pa', 'scope': 'experiment-v1',
         'valid_from': '2026-09-23T10:00:00Z', 'valid_until': '2026-09-23T11:00:00Z',
         'payload': {'assignment': 'randomised', 'treatment': [10000, 12000], 'control': [3000, 4000]}}


def run(value=None, source=SOURCE):
    program = parse(source)
    return evaluate(program, {'trial': record(program, 'trial', VALUE if value is None else value)},
                    now=NOW, context=CONTEXT)


def test_pressure_contrast_converts_units_and_reports_full_formal_input():
    result = run()
    assert result['valid']
    assert result['claims']['raised']['status'] == 'supported'
    binding = result['arguments']['contrast']['reasoning_result']['binding']
    assert binding['actual'] == 7.5
    assert binding['output_unit'] == 'kPa'
    assert binding['formal_query'] == VALUE['payload']
    assert len(binding['input_payload_digest']) == 64
    assert binding['evidence_id'] == 'trial'
    assert binding['proposition']['query'] == {'assignment': 'randomised'}
    assert not binding['prose_verified'] and not binding['physical_interpretation_verified']


@pytest.mark.parametrize('key,value', [
    ('quantity', 'volumetric_flow'), ('unit', 'L/s'), ('subject', 'pump-B'), ('scope', 'experiment-v2'),
    ('method', 'causal/2'), ('schema', 'EAL/typed-input/2'),
    ('valid_from', '2026-09-23T10:00:01Z'), ('valid_until', '2026-09-23T10:59:59Z'),
    ('valid_from', '2026-09-23T10:00:00'), ('unit', []),
])
def test_mismatched_quantity_unit_subject_scope_contract_or_time_cannot_support(key, value):
    data = deepcopy(VALUE)
    data[key] = value
    result = run(data)
    assert result['claims']['raised']['status'] == 'unsupported'


def test_enclosing_interval_and_equivalent_timezone_are_accepted():
    data = deepcopy(VALUE)
    data.update(valid_from='2026-09-23T10:00:00+01:00', valid_until='2026-09-23T12:00:00Z')
    assert run(data)['claims']['raised']['status'] == 'supported'


def test_changed_measurements_can_change_result_without_changing_formal_question():
    data = deepcopy(VALUE)
    data['payload']['treatment'] = [6000, 7000]
    result = run(data)
    assert result['evidence']['trial']['status'] == 'available'
    assert result['arguments']['contrast']['reasoning_result']['status'] == 'supported'
    assert result['claims']['raised']['status'] == 'unsupported'
    assert result['arguments']['contrast']['reasoning_result']['binding']['holds'] is False


def test_changed_query_is_rejected_even_if_numerical_result_would_pass():
    data = deepcopy(VALUE)
    data['payload']['assignment'] = 'observational'
    result = run(data)
    binding = result['arguments']['contrast']['reasoning_result']['binding']
    assert binding['status'] == 'unsupported'
    assert any('query field' in reason for reason in binding['reasons'])


@pytest.mark.parametrize('old,new,code', [
    ('EAL/2', 'EAL/0.2', 'unsupported_language'),
    ('quantity "pressure"', 'quantity "flow"', 'invalid_proposition'),
    ('unit "kPa"', 'unit "L/s"', 'invalid_proposition'),
    ('binding trial;', '', 'missing_binding'),
    ('result "estimate" >= 5', 'result "estimate" == true', 'proposition_method'),
    ('result "estimate" >= 5', 'result "sample_size" >= 5', 'proposition_method'),
    ('query {"assignment":"randomised"}', 'query {}', 'proposition_method'),
    ('query {"assignment":"randomised"}', 'query {"assignment":"randomised","extra":1}', 'proposition_method'),
])
def test_static_typed_contract_diagnostics(old, new, code):
    assert code in {d.code for d in validate(parse(SOURCE.replace(old, new)))}


def test_negative_entailment_is_usable_and_whole_logical_query_is_bound():
    query = {'premises': ['p'], 'conclusion': 'q'}
    source = SOURCE.replace('kind experiment', 'kind logical_case').replace('method "causal/1"', 'method "deductive/1"')
    source = source.replace('quantity "pressure"; unit "kPa"', 'quantity "proposition"; unit "1"')
    source = source.replace('query {"assignment":"randomised"}', 'query {"premises":["p"],"conclusion":"q"}')
    source = source.replace('result "estimate" >= 5', 'result "entailed" == false')
    data = deepcopy(VALUE)
    data.update(method='deductive/1', quantity='proposition', unit='1', payload=query)
    result = run(data, source)
    assert result['claims']['raised']['status'] == 'supported'
    binding = result['arguments']['contrast']['reasoning_result']['binding']
    assert binding['actual'] is False and binding['output_unit'] is None
    assert binding['formal_query']['conclusion'] == 'q'
    data['payload'] = {'premises': ['p'], 'conclusion': 'p'}
    assert run(data, source)['claims']['raised']['status'] == 'unsupported'


def test_untyped_alternative_cannot_bypass_typed_claim_binding():
    source = SOURCE + '\nargument bypass { conclusion raised; reasoning difference; evidence trial; }'
    assert 'missing_binding' in {d.code for d in validate(parse(source))}


def test_prose_changes_do_not_change_formal_meaning():
    a = run()
    b = run(source=SOURCE.replace('The treatment mean pressure exceeds control by at least 5 kPa.',
                                 'Incorrect prose about a different pump and flow.'))
    assert a['claims']['raised']['proposition'] == b['claims']['raised']['proposition']
    assert b['claims']['raised']['prose_verified'] is False
    assert a['claims']['raised']['status'] == b['claims']['raised']['status']
