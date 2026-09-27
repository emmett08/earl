"""Semantic regressions: provenance, freshness, scoped assumptions and derivation."""
from copy import deepcopy

import pytest

from eal.evaluator import assess_evidence_record, canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.semantics import parse_time

SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; }
evidence observed { tool runner; kind test; environment lab; max_age 60;
 input {"suite":"smoke"}; require "passed" == true;
}
evidence counterexample { tool runner; kind test; environment lab; max_age 60; require "found" == true; }
assumption stable { statement "Configuration persists for the stated interval.";
 environment lab; validate observed; valid_from "2026-09-23T11:00:00Z"; valid_until "2026-09-23T13:00:00Z";
}
reasoning method { method "structured/1"; rationale "Passing the smoke test supports this bounded test claim."; }
reasoning alternative_method { method "structured/1"; rationale "An independent relation supports the bounded test claim."; }
claim working { statement "The smoke test passes."; environment lab; }
claim downstream { statement "The follow-up conclusion follows under the declared relation."; environment lab; }
argument base { conclusion working; reasoning method; evidence observed; assumptions stable; }
argument nested { conclusion downstream; reasoning method; premises working; }
'''
CONTEXT = {'site': 'bench'}
NOW = '2026-09-23T12:00:00Z'


def record(program, name, value, collected_at=NOW):
    evidence = program.evidence[name]
    tool = program.tools[evidence.tool]
    acquisition = {'tool': tool.name, 'tool_version': tool.version,
                   'input': evidence.input, 'context': CONTEXT}
    return {'evidence_id': name, 'source_digest': program.source_digest,
            'tool': tool.name, 'tool_version': tool.version,
            'tool_binding_digest': '0' * 64,
            'evidence_kind': evidence.kind, 'environment': evidence.environment,
            'environment_fingerprint': environment_fingerprint(evidence.environment, CONTEXT),
            'input_digest': canonical_digest(evidence.input), 'collected_at': collected_at,
            'input': evidence.input, 'context': CONTEXT,
            'acquisition_request': acquisition,
            'acquisition_request_digest': canonical_digest(acquisition),
            'request_digest': canonical_digest({'evidence_id': name,
                                                'environment': evidence.environment, **acquisition}),
            'run_id': 'test-run', 'status': 'ok', 'value': value, 'data_digest': canonical_digest(value)}


def run(source=SOURCE, *, values=None, now=NOW):
    program = parse(source)
    values = values if values is not None else {'observed': {'passed': True}}
    records = {name: record(program, name, value) for name, value in values.items()}
    return evaluate(program, records, now=now, context=CONTEXT)


def test_nested_subarguments_and_observation_supply_support():
    result = run()
    assert result['valid']
    assert result['claims']['working']['status'] == 'supported'
    assert result['claims']['downstream']['status'] == 'supported'
    assert result['arguments']['nested']['dependencies']['premises'] == ['working']
    assert result['evidence']['observed']['tool_binding_digest'] == '0' * 64


def test_unsupported_never_means_false_and_missing_sources_propagate():
    result = run(values={})
    assert result['claims']['working']['status'] == 'unsupported'
    assert result['claims']['downstream']['status'] == 'unsupported'
    assert 'falsity' in result['claims']['working']['reasons'][0]


@pytest.mark.parametrize('key,value', [
    ('source_digest', 'other'), ('tool', 'other'), ('tool_version', '2'),
    ('tool_binding_digest', 'invalid'), ('evidence_kind', 'sample'), ('environment', 'elsewhere'),
    ('environment_fingerprint', 'other'), ('input_digest', 'other'),
    ('input', {'suite': 'other'}), ('context', {'site': 'elsewhere'}),
    ('acquisition_request_digest', 'other'), ('request_digest', 'other'),
    ('data_digest', 'other'), ('run_id', ''), ('status', 'error'),
    ('collected_at', '2026-09-23T12:00:01Z'), ('collected_at', '2026-09-23T11:58:59Z'),
    ('collected_at', '2026-09-23T12:00:00'),
])
def test_record_mismatch_missing_or_stale_fails_closed(key, value):
    program = parse(SOURCE)
    item = record(program, 'observed', {'passed': True})
    item[key] = value
    result = evaluate(program, {'observed': item}, now=NOW, context=CONTEXT)
    assert result['evidence']['observed']['status'] == 'unavailable'
    assert result['claims']['downstream']['status'] == 'unsupported'


def test_acquisition_fields_compare_json_types_and_current_binding():
    program = parse(SOURCE)
    item = record(program, 'observed', {'passed': True})
    assert evaluate(program, {'observed': item}, now=NOW, context=CONTEXT,
                    binding_digests={'observed': '1' * 64})['evidence']['observed']['status'] == 'unavailable'
    item['input'] = {'suite': 'smoke'}
    item['context'] = {'site': 'bench'}
    assert evaluate(program, {'observed': item}, now=NOW, context=CONTEXT,
                    binding_digests={'observed': '0' * 64})['evidence']['observed']['status'] == 'available'
    alternate = SOURCE.replace('"suite":"smoke"', '"suite":1')
    other = parse(alternate)
    forged = record(other, 'observed', {'passed': True})
    forged['input'] = {'suite': True}
    assert evaluate(other, {'observed': forged}, now=NOW, context=CONTEXT)['evidence']['observed']['status'] == 'unavailable'


def test_record_diagnostic_entry_and_order_are_preserved():
    program = parse(SOURCE)
    missing = evaluate(program, {}, now=NOW, context=CONTEXT)
    assert missing['evidence']['observed'] == {
        'status': 'unavailable', 'reasons': ['No evidence record is available'],
        'availability_issues': ['missing_observation']}

    item = record(program, 'observed', {'passed': True})
    item.update(source_digest='other', status='error', run_id='',
                collected_at='2026-09-23T12:00:00', data_digest='other')
    entry = evaluate(program, {'observed': item}, now=NOW, context=CONTEXT)['evidence']['observed']
    assert entry == {
        'status': 'unavailable', 'tool': 'runner', 'tool_version': '1',
        'tool_binding_digest': '0' * 64, 'run_id': '',
        'availability_issues': ['invalid_observation', 'tool_error'],
        'reasons': [
            'Record source_digest does not match the declared evidence request',
            'Tool execution did not produce an ok observation',
            'Record requires a nonempty run_id',
            'Record collected_at must be an ISO-8601 timestamp with timezone',
            'Record data_digest does not match its JSON value',
        ],
    }
    missing_field = run(values={'observed': {}})['evidence']['observed']
    assert missing_field['reasons'] == ["Field 'passed' is missing"]
    false_value = run(values={'observed': {'passed': False}})['evidence']['observed']
    assert false_value['reasons'] == ["Field 'passed' == True does not hold (observed False)"]


def test_evidence_age_boundary_and_assumption_half_open_interval():
    program = parse(SOURCE)
    item = record(program, 'observed', {'passed': True}, '2026-09-23T11:59:00Z')
    assert evaluate(program, {'observed': item}, now=NOW, context=CONTEXT)['claims']['working']['status'] == 'supported'
    item = record(program, 'observed', {'passed': True}, '2026-09-23T13:00:00Z')
    result = evaluate(program, {'observed': item}, now='2026-09-23T13:00:00Z', context=CONTEXT)
    assert result['evidence']['observed']['status'] == 'available'
    assert result['assumptions']['stable']['status'] == 'unsupported'


def test_runtime_environment_conditions_and_fingerprints_are_enforced():
    program = parse(SOURCE)
    item = record(program, 'observed', {'passed': True})
    result = evaluate(program, {'observed': item}, now=NOW, context={'site': 'field'})
    assert result['claims']['working']['status'] == 'out_of_scope'


def test_boolean_and_numeric_values_are_not_interchangeable():
    result = run(values={'observed': {'passed': 1}})
    assert result['evidence']['observed']['status'] == 'unavailable'


def test_structural_evidence_verdict_distinguishes_false_from_invalid():
    program = parse(SOURCE)

    def check(item, *, in_scope=True):
        return assess_evidence_record(program, 'observed', item, instant=parse_time(NOW),
                                      context=CONTEXT, environment_matched=in_scope)

    false = check(record(program, 'observed', {'passed': False}))
    assert false.complete and false.entry['status'] == 'unavailable'
    assert false.entry['availability_issues'] == ['predicate_not_met']
    assert false.entry == run(values={'observed': {'passed': False}})['evidence']['observed']
    true = check(record(program, 'observed', {'passed': True}))
    assert true.complete and true.entry['status'] == 'available'
    assert true.entry['availability_issues'] == []
    for value in ({}, {'passed': 1}):
        invalid = check(record(program, 'observed', value))
        assert not invalid.complete and invalid.entry['status'] == 'unavailable'
        assert invalid.entry['availability_issues'] == ['invalid_observation']
    stale = check(record(program, 'observed', {'passed': True}, '2026-09-23T11:58:59Z'))
    assert not stale.complete
    assert stale.entry['availability_issues'] == ['stale_observation']
    out_of_scope = check(record(program, 'observed', {'passed': True}), in_scope=False)
    assert not out_of_scope.complete
    assert out_of_scope.entry['availability_issues'] == ['out_of_scope']
    mismatched = record(program, 'observed', {'passed': True})
    mismatched['input_digest'] = 'other'
    assert not check(mismatched).complete
    assert check(mismatched).entry['availability_issues'] == ['invalid_observation']
    assert check(None).entry['availability_issues'] == ['missing_observation']
    failed = record(program, 'observed', {'passed': True})
    failed['status'] = 'error'
    assert check(failed).entry['availability_issues'] == ['tool_error']


def test_active_claim_objection_propagates_through_nested_subarguments():
    source = SOURCE + 'objection attack { target claim working; evidence counterexample; }'
    result = run(source, values={'observed': {'passed': True}, 'counterexample': {'found': True}})
    assert result['claims']['working']['status'] == 'contested'
    assert result['claims']['downstream']['status'] == 'contested'
    assert run(source)['claims']['downstream']['status'] == 'supported'


def test_attack_on_one_reasoning_method_preserves_an_independent_argument():
    source = SOURCE + '''
objection attack { target reasoning method; evidence counterexample; }
argument alternative { conclusion working; reasoning alternative_method; evidence observed; }
'''
    result = run(source, values={'observed': {'passed': True}, 'counterexample': {'found': True}})
    assert result['arguments']['base']['status'] == 'contested'
    assert result['claims']['working']['status'] == 'supported'
    assert result['claims']['working']['supporting_arguments'] == ['alternative']
    # The downstream argument itself uses the challenged reasoning method.
    assert result['claims']['downstream']['status'] == 'contested'


def test_assumption_objection_affects_only_dependent_arguments():
    source = SOURCE + '''
objection attack { target assumption stable; evidence counterexample; }
argument alternative { conclusion working; reasoning alternative_method; evidence observed; }
'''
    result = run(source, values={'observed': {'passed': True}, 'counterexample': {'found': True}})
    assert result['assumptions']['stable']['status'] == 'contested'
    assert result['claims']['working']['status'] == 'supported'
    assert result['claims']['downstream']['status'] == 'supported'


def test_changed_source_invalidates_reused_observations():
    program = parse(SOURCE)
    item = record(program, 'observed', {'passed': True})
    edited = parse(SOURCE + '\n// changed source identity\n')
    result = evaluate(edited, {'observed': item}, now=NOW, context=CONTEXT)
    assert result['evidence']['observed']['status'] == 'unavailable'


def test_pure_evaluation_is_reproducible_and_does_not_mutate_inputs():
    program = parse(SOURCE)
    records = {'observed': record(program, 'observed', {'passed': True})}
    before = deepcopy(records)
    first = evaluate(program, records, now=NOW, context=CONTEXT)
    assert first == evaluate(program, records, now=NOW, context=CONTEXT)
    assert records == before


def test_explicit_time_and_finite_json_are_required():
    with pytest.raises(ValueError):
        run(now='2026-09-23T12:00:00')
    with pytest.raises(ValueError):
        canonical_digest({'x': float('nan')})


def test_inductive_computation_and_declared_threshold_control_derivation():
    source = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool counter { version "1"; }
evidence sample_data { tool counter; kind sample; environment lab; max_age 60;
 require "trials" >= 1;
}
reasoning estimate_rate { method "inductive/1";
 rationale "The Wilson lower confidence limit exceeds the declared target under the sampling assumptions.";
 require "lower" > 0.8;
}
claim reliable { statement "The stated confidence procedure has a lower limit above 0.8."; environment lab; }
argument estimation { conclusion reliable; reasoning estimate_rate; evidence sample_data; }
'''
    result = run(source, values={'sample_data': {'successes': 98, 'trials': 100, 'confidence': 0.95}})
    assert result['claims']['reliable']['status'] == 'supported'
    details = result['arguments']['estimation']['reasoning_result']['details']
    assert 0.8 < details['lower'] < details['estimate'] < details['upper'] < 1
    low = run(source, values={'sample_data': {'successes': 70, 'trials': 100, 'confidence': 0.95}})
    assert low['evidence']['sample_data']['status'] == 'available'
    assert low['claims']['reliable']['status'] == 'unsupported'
    assert low['arguments']['estimation']['reasoning_result']['predicates'][0]['holds'] is False
    malformed = run(source, values={'sample_data': {'successes': 101, 'trials': 100, 'confidence': 0.95}})
    assert malformed['claims']['reliable']['status'] == 'unsupported'
    assert malformed['arguments']['estimation']['reasoning_result']['status'] == 'unsupported'


def test_deductive_entailment_countermodel_and_inconsistency_do_not_collapse():
    source = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool encoder { version "1"; }
evidence formal_case { tool encoder; kind logical_case; environment lab; max_age 60;
 require "conclusion" == "q";
}
reasoning entails { method "deductive/1"; rationale "Finite propositional entailment within the encoded premises.";
 require "entailed" == true;
}
claim conclusion { statement "The encoded conclusion follows from the encoded premises."; environment lab; }
argument formal { conclusion conclusion; reasoning entails; evidence formal_case; }
'''.replace('claim conclusion', 'claim conclusion_claim').replace('conclusion conclusion;', 'conclusion conclusion_claim;')
    case = {'premises': ['p', {'implies': ['p', 'q']}], 'conclusion': 'q'}
    result = run(source, values={'formal_case': case})
    assert result['claims']['conclusion_claim']['status'] == 'supported'
    invalid = run(source, values={'formal_case': {**case, 'premises': ['p']}})
    assert invalid['claims']['conclusion_claim']['status'] == 'unsupported'
    assert invalid['arguments']['formal']['reasoning_result']['details']['counterexample']

    inconsistent = run(source, values={'formal_case': {**case, 'premises': ['p', {'not': 'p'}]}})
    assert inconsistent['claims']['conclusion_claim']['status'] == 'unsupported'
    assert inconsistent['arguments']['formal']['reasoning_result']['details']['consistent_premises'] is False
