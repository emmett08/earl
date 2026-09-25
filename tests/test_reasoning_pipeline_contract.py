"""Whole-result characterisation for the validation and dialectical stages."""
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.semantics import validate


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool collector { version "1"; mode deterministic; }
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
        'tool': declaration.tool, 'tool_version': '1', 'mode': 'deterministic',
        'evidence_kind': declaration.kind, 'environment': declaration.environment,
        'environment_fingerprint': environment_fingerprint(declaration.environment, CONTEXT),
        'input_digest': canonical_digest(declaration.input), 'collected_at': collected_at,
        'run_id': 'stage-fixture', 'status': 'ok', 'value': value,
        'data_digest': canonical_digest(value),
    }


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize('missing,stale,context,expected_digest', [
    ((), (), CONTEXT, 'c70ab60c7f447cee629e399a049ce513073b5b9031a649d82e2a7c7c43bbc4d7'),
    (('defence',), (), CONTEXT, 'c345a9c713187194c26d5abd7483fa47f55f53b2170032781a18dc7cfd4b1504'),
    (('positive',), (), CONTEXT, '225da311b89e52a6edb22556d6701a568e21eed8617ba1ff99d829ab2d0b3db5'),
    ((), ('negative',), CONTEXT, 'e10bcf5571e51d6271f8ea347d601d3d01cc94f3712c4a439001e9ccf0ccf605'),
    ((), (), {'site': 'elsewhere'}, 'e693d5cd5d41824de52a795124646a17ecb52bd9f6359930d391795c0661730d'),
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
