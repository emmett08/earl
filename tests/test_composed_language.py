"""Compiler-to-solver contracts for EAL/0.3 objections and defences."""
from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.semantics import validate

NOW = '2026-09-23T12:00:00Z'
CONTEXT = {'site': 'bench'}
BASE = '''language "EAL/0.3";
environment lab { require "site" == "bench"; }
tool collector { version "1"; mode deterministic; }
evidence positive { tool collector; kind test; environment lab; max_age 60; require "holds" == true; }
evidence negative { tool collector; kind test; environment lab; max_age 60; require "holds" == true; }
evidence defence_data { tool collector; kind test; environment lab; max_age 60; require "holds" == true; }
assumption applicable { statement "Applicability holds in the measured context."; environment lab; validate positive; }
reasoning authored { method "structured/1"; rationale "The declared conditional relation supplies support."; }
claim outcome { statement "The bounded conclusion."; environment lab; }
claim critique { statement "The objection's measured grounds."; environment lab; }
argument outcome_route { conclusion outcome; reasoning authored; evidence positive; assumptions applicable; }
argument critique_route { conclusion critique; reasoning authored; evidence negative; }
'''


def assess(source, *, stale=()):
    program = parse(source)
    records = {}
    for name, evidence in program.evidence.items():
        value = {'holds': True}
        records[name] = {'evidence_id': name, 'source_digest': program.source_digest,
                         'tool': evidence.tool, 'tool_version': '1', 'mode': 'deterministic',
                         'evidence_kind': evidence.kind, 'environment': evidence.environment,
                         'environment_fingerprint': environment_fingerprint(evidence.environment, CONTEXT),
                         'input_digest': canonical_digest(evidence.input),
                         'collected_at': '2026-09-23T11:58:00Z' if name in stale else NOW,
                         'run_id': 'composed-test', 'status': 'ok', 'value': value,
                         'data_digest': canonical_digest(value)}
    result = evaluate(program, records, now=NOW, context=CONTEXT)
    assert result['valid'], result['diagnostics']
    return result


def test_objection_depending_on_the_claim_it_attacks_has_no_grounded_start():
    source = BASE + 'objection circular { target claim outcome; premises outcome; }'
    result = assess(source)
    assert result['claims']['outcome']['grounded_label'] == 'undecided'
    assert result['claims']['outcome']['status'] == 'contested'
    assert result['objections']['circular']['status'] == 'undecided'
    assert result['arguments']['outcome_route']['locally_usable'] is True


def test_defence_of_an_assumption_then_rebuttal_of_that_defence():
    source = BASE + '''
objection challenged { target assumption applicable; premises critique; }
objection defended { target objection challenged; evidence defence_data; }
'''
    result = assess(source)
    assert result['assumptions']['applicable']['status'] == 'supported'
    assert result['claims']['outcome']['status'] == 'supported'
    assert result['objections']['challenged']['status'] == 'defeated'
    source += 'objection reply { target objection defended; evidence negative; }'
    result = assess(source)
    assert result['objections']['reply']['status'] == 'active'
    assert result['objections']['defended']['status'] == 'defeated'
    assert result['objections']['challenged']['status'] == 'active'
    assert result['assumptions']['applicable']['status'] == 'contested'
    assert result['claims']['outcome']['grounded_label'] == 'rejected'
    assert result['claims']['outcome']['status'] == 'contested'


def test_objection_evidence_and_claim_premises_are_both_required():
    source = BASE + 'objection challenge { target claim outcome; evidence defence_data; premises critique; }'
    assert assess(source)['claims']['outcome']['status'] == 'contested'
    for stale in ({'negative'}, {'defence_data'}):
        result = assess(source, stale=stale)
        assert result['claims']['outcome']['status'] == 'supported'
        assert result['objections']['challenge']['status'] == 'inactive'
        assert result['objections']['challenge']['grounded_label'] == 'rejected'


def test_support_rejection_retains_unsupported_distinction_and_final_premise_labels():
    source = BASE + '''
claim dependent { statement "Requires the conclusion."; environment lab; }
argument dependent_route { conclusion dependent; reasoning authored; premises outcome; }
'''
    result = assess(source, stale={'positive'})
    entry = result['arguments']['dependent_route']
    assert entry['locally_usable'] is True
    assert entry['source_usable'] is False
    assert entry['premise_labels'] == {'outcome': 'rejected'}
    assert entry['grounded_label'] == 'rejected'
    assert entry['status'] == 'unsupported'


def test_composed_formatter_preserves_ir_and_does_not_require_declaration_order():
    source = BASE + '''
objection reply { target objection challenge; evidence defence_data; premises outcome; }
objection challenge { target argument outcome_route; premises critique; }
'''
    formatted = format_source(source)
    assert semantic_ir(parse(formatted)) == semantic_ir(parse(source))
    first, second = assess(source), assess(formatted)
    assert first['dialectic'] == second['dialectic']


def test_version_and_scope_validation_for_composed_objections():
    source = BASE + 'objection challenge { target objection challenge; premises critique; }'
    assert 'versioned_construct' in {d.code for d in validate(parse(source.replace('EAL/0.3', 'EAL/0.2')))}
    assert 'empty_objection' in {d.code for d in validate(parse(BASE + 'objection empty { target claim outcome; }'))}
    source = BASE + '''
environment peer { require "site" == "bench"; }
evidence peer_observation { tool collector; kind test; environment peer; max_age 60; require "holds" == true; }
objection challenge { target claim outcome; premises critique; }
objection wrong_scope { target objection challenge; evidence peer_observation; }
'''
    assert 'environment_mismatch' in {d.code for d in validate(parse(source))}
