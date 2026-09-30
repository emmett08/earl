"""Whole-result characterisation for the validation and dialectical stages."""
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.semantics import validate
from _provenance import synthetic_provenance


SOURCE = '''language "EAL/3"

environment lab {
  require "site" == "bench"
}

tool collector {
  version "1"
}

evidence positive {
  tool collector
  kind test
  environment lab
  max_age 60
  require "holds" == true
}

evidence negative {
  tool collector
  kind test
  environment lab
  max_age 60
  require "holds" == true
}

evidence defence {
  tool collector
  kind test
  environment lab
  max_age 60
  require "holds" == true
}

assumption applicable {
  statement "Assumption applies."
  environment lab
  validate positive
}

reasoning authored {
  method "structured/1"
  rationale "Bounded source support."
}

claim outcome {
  statement "The bounded outcome."
  environment lab
}

claim critique {
  statement "The measured critique."
  environment lab
}

claim dependent {
  statement "The dependent claim."
  environment lab
}

argument route = [evidence positive, assumptions applicable] via authored => outcome

argument critique_route = [evidence negative] via authored => critique

argument dependent_route = [premises outcome] via authored => dependent

objection challenge = [premises critique] -x> claim outcome

objection defence_route = [evidence defence] -x> objection challenge
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


# Full-result hashes include source digests and spans for EAL/3,
# typed evidence diagnostics and assumption applicability.
@pytest.mark.parametrize('missing,stale,context,expected_digest', [
    ((), (), CONTEXT, '7ace35d71c54c64477797b5761d02ab81010f990b97a78078120fc6441d9618f'),
    (('defence',), (), CONTEXT, 'b754839e29d756dcd3ed2a2b6bfc55d0966b146a000b4f0ba8d7d3dae96795dc'),
    (('positive',), (), CONTEXT, 'd0ec20f03d4dba508b4f329e3f16f645880e6004d8c0ba0ae9dff77b53a01b23'),
    ((), ('negative',), CONTEXT, '2ba1e735b5cc83a07101fa23a3c6a01bcd51c6b1327597b622807e7df73d69f1'),
    ((), (), {'site': 'elsewhere'}, 'e7af82c31e61438f3778f83141831e944ce7bae7a6a193d6312c8c26c7523275'),
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
    assert _digest(diagnostics) == '05fd2ee24e2bbb8795bf7810308d3378e3c6a4ce430eb144210a3a7e0ed6c31b'


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
