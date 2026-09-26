"""Whole-result characterisation for the validation and dialectical stages."""
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.semantics import validate
from _provenance import synthetic_provenance


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool collector { version "1"; }
evidence positive { tool collector; kind test; environment lab; max_age 60; require "holds" == true; }
evidence negative { tool collector; kind test; environment lab; max_age 60; require "holds" == true; }
evidence defence { tool collector; kind test; environment lab; max_age 60; require "holds" == true; }
assumption applicable { statement "Assumption applies."; environment lab; validate positive; }
reasoning authored { method "structured/1"; rationale "Bounded source support."; }
claim outcome { statement "The bounded outcome."; environment lab; }
claim critique { statement "The measured critique."; environment lab; }
claim dependent { statement "The dependent claim."; environment lab; }
argument route { conclusion outcome; reasoning authored; evidence positive; assumptions applicable; }
argument critique_route { conclusion critique; reasoning authored; evidence negative; }
argument dependent_route { conclusion dependent; reasoning authored; premises outcome; }
objection challenge { target claim outcome; premises critique; }
objection defence_route { target objection challenge; evidence defence; }
'''
NOW = '2026-09-23T12:00:00Z'
CONTEXT = {'site': 'bench'}


def _record(program, name, *, collected_at=NOW):
    declaration = program.evidence[name]
    value = {'holds': True}
    return {
        'evidence_id': name, 'source_digest': program.source_digest,
        'tool': declaration.tool, 'tool_version': '1',
        'evidence_kind': declaration.kind, 'environment': declaration.environment,
        'environment_fingerprint': environment_fingerprint(declaration.environment, CONTEXT),
        'input_digest': canonical_digest(declaration.input), 'collected_at': collected_at,
        'run_id': 'stage-fixture', 'status': 'ok', 'value': value,
        'data_digest': canonical_digest(value),
        **synthetic_provenance(program, name, CONTEXT),
    }


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize('missing,stale,context,expected_digest', [
    ((), (), CONTEXT, 'cc0e4f60b76c933c69b1bf863426663fd5cfa57c065c5296c78367a221fcee9e'),
    (('defence',), (), CONTEXT, '957e2da71501524ebda55e3f873275cb892e6403c539fc43f0e36fa597dc0ffc'),
    (('positive',), (), CONTEXT, 'bd8c19cee29b319c1190e6736be1711ee66a8fa74012322df56118110bab1ac2'),
    ((), ('negative',), CONTEXT, '49921072a49fa7525c3a90280cddb31444d34239e9461ce65ae68dc4f70f703c'),
    ((), (), {'site': 'elsewhere'}, 'ca5fc814c44f13d8ef939a809cc3a19bb91106afc7ac032e094c053b78b33b8d'),
])
def test_full_result_is_stable_across_pipeline_stages(missing, stale, context, expected_digest):
    program = parse(SOURCE)
    records = {name: _record(program, name, collected_at=(
        '2026-09-23T11:58:00Z' if name in stale else NOW))
        for name in program.evidence if name not in missing}
    result = evaluate(program, records, now=NOW, context=context)
    assert result['valid'], result['diagnostics']
    assert _digest(result) == expected_digest


def test_validation_diagnostics_order_and_spans_are_stable():
    program = parse(SOURCE)
    program = replace(program,
        claims={**program.claims, 'outcome': replace(program.claims['outcome'], statement='')},
        arguments={**program.arguments, 'route': replace(program.arguments['route'],
                    reasoning='missing_reason', evidence=('missing_evidence',))})
    diagnostics = [asdict(item) for item in validate(program)]
    assert [(item['code'], item['declaration']) for item in diagnostics] == [
        ('empty_statement', 'outcome'), ('unknown_reference', 'route'),
        ('unknown_reference', 'route')]
    assert _digest(diagnostics) == '3bf32773d2a164c59eac0b6a374faf42fa3ab9f51dc2f40020a08c7c51384b7d'


def test_dependency_pass_keeps_cycle_and_depth_guards(monkeypatch):
    from eal import semantics

    program = parse(SOURCE)
    cyclic = replace(program, arguments={**program.arguments,
        'route': replace(program.arguments['route'], premises=('dependent',))})
    cycle = next(item for item in validate(cyclic) if item.code == 'dependency_cycle')
    assert cycle.declaration == 'outcome'
    assert cycle.span == program.locations['outcome']

    monkeypatch.setattr(semantics, 'MAX_PREMISE_DEPTH', 0)
    assert any(item.code == 'resource_limit' for item in validate(program))


def test_graph_construction_limit_keeps_partial_local_result(monkeypatch):
    from eal import dialectic

    monkeypatch.setattr(dialectic, 'MAX_COMPOSED_EDGES', 1)
    program = parse(SOURCE)
    result = evaluate(program, {name: _record(program, name) for name in program.evidence},
                      now=NOW, context=CONTEXT)
    assert not result['valid']
    assert [item['code'] for item in result['diagnostics']] == ['resource_limit']
    assert result['arguments'] == result['claims'] == result['objections'] == {}
    assert result['reasoning']['authored']['status'] == 'supported'
