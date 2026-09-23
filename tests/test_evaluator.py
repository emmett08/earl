"""Semantic regressions: provenance, freshness, scoped assumptions and derivation."""
from copy import deepcopy

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse

SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode nondeterministic; }
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
    return {'evidence_id': name, 'source_digest': program.source_digest,
            'tool': tool.name, 'tool_version': tool.version, 'mode': tool.mode,
            'evidence_kind': evidence.kind, 'environment': evidence.environment,
            'environment_fingerprint': environment_fingerprint(evidence.environment, CONTEXT),
            'input_digest': canonical_digest(evidence.input), 'collected_at': collected_at,
            'run_id': 'test-run', 'status': 'ok', 'value': value, 'data_digest': canonical_digest(value)}


def run(source=SOURCE, *, values=None, now=NOW):
    program = parse(source)
    values = values if values is not None else {'observed': {'passed': True}}
    records = {name: record(program, name, value) for name, value in values.items()}
    return evaluate(program, records, now=now, context=CONTEXT)


def test_nested_subarguments_and_nondeterministic_observation_supply_support():
    result = run()
    assert result['valid']
    assert result['claims']['working']['status'] == 'supported'
    assert result['claims']['downstream']['status'] == 'supported'
    assert result['arguments']['nested']['dependencies']['premises'] == ['working']
    assert result['evidence']['observed']['mode'] == 'nondeterministic'


def test_unsupported_never_means_false_and_missing_sources_propagate():
    result = run(values={})
    assert result['claims']['working']['status'] == 'unsupported'
    assert result['claims']['downstream']['status'] == 'unsupported'
    assert 'falsity' in result['claims']['working']['reasons'][0]


@pytest.mark.parametrize('key,value', [
    ('source_digest', 'other'), ('tool', 'other'), ('tool_version', '2'),
    ('mode', 'deterministic'), ('evidence_kind', 'sample'), ('environment', 'elsewhere'),
    ('environment_fingerprint', 'other'), ('input_digest', 'other'),
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
tool counter { version "1"; mode deterministic; }
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
tool encoder { version "1"; mode deterministic; }
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
