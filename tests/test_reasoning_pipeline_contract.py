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
# typed evidence diagnostics, assumption applicability and calculation completeness.
@pytest.mark.parametrize('missing,stale,context,expected_digest', [
    ((), (), CONTEXT, 'fdd74c440b62c351ebf88f655655c9cf40138bf1f2ee80b9037b79bb3ab931a6'),
    (('defence',), (), CONTEXT, '8853f08e13c35ca33412bcad13e59f96503b066aacd482aec78f7246e7cd079c'),
    (('positive',), (), CONTEXT, '2dd5e7d11d7580527125de53612ee3a170240730b044fe841f2f7ee2188063c2'),
    ((), ('negative',), CONTEXT, '64c93f89b75b39bc4a4e9ec2066bb1cf41c363f766636dd20cb79c68023d418c'),
    ((), (), {'site': 'elsewhere'}, '64dc838cafb8677b9d4edbebeb1588547c465363d53f5da89dfc1e446913301b'),
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
    diagnostics = [asdict(item) for item in validate(replace(program, authored=None))]
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

    from eal.limits import ExecutionLimits
    longer = replace(program, authored=None, arguments={**program.arguments,
        'extra': replace(program.arguments['route'], name='extra', conclusion='extra_claim', premises=('dependent',))},
        claims={**program.claims, 'extra_claim': replace(program.claims['outcome'], name='extra_claim')},
        declaration_count=program.declaration_count + 2, limits=ExecutionLimits(premise_depth=1))
    assert any(item.code == 'resource_limit' for item in validate(longer))


def test_graph_construction_limit_keeps_partial_local_result(monkeypatch):
    from eal.limits import ExecutionLimits
    program = parse(SOURCE, limits=ExecutionLimits(composed_edges=1))
    result = evaluate(program, {name: _record(program, name) for name in program.evidence},
                      now=NOW, context=CONTEXT)
    assert not result['valid']
    assert not result['complete']
    assert [item['code'] for item in result['diagnostics']] == ['resource_limit']
    assert result['arguments'] == result['claims'] == result['objections'] == {}
    assert result['reasoning']['authored']['status'] == 'supported'
