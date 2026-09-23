"""Independent EAL/2 contracts: one semantics, exact methods, stable extensions."""
from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.extensions import RMS_CONTRACT
from eal.methods import default_registry
from eal.model import Diagnostic, SourceSpan
from eal.modes import assess_mode, validate_mode
from eal.parser import parse
from eal.semantics import validate

NOW = '2026-09-23T12:00:00Z'
CONTEXT = {'site': 'bench'}
SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool observer { version "1"; mode deterministic; }
evidence measurement { tool observer; kind experiment; environment lab; max_age 60; require "schema" == "EAL/typed-input/1"; }
evidence calibration { tool observer; kind test; environment lab; max_age 60; require "holds" == true; }
assumption calibrated { statement "The instrument calibration applies."; environment lab; validate calibration;
 valid_until "2026-09-23T12:00:30Z";
}
reasoning contrast { method "causal/1"; rationale "The randomised experiment estimates the pressure difference."; }
reasoning compose { method "structured/1"; rationale "The measured contrast supports the calibrated conclusion."; }
claim increase { statement "The treatment raises pressure by at least 5 kPa."; environment lab;
 proposition {
  subject "pump-A"; quantity "pressure"; unit "kPa"; scope "trial-1";
  valid_from "2026-09-23T10:00:00Z"; valid_until "2026-09-23T11:00:00Z";
  query {"assignment":"randomised"}; result "estimate" >= 5;
 }
}
claim outcome { statement "The calibrated trial supports the increase."; environment lab; }
argument measured { conclusion increase; reasoning contrast; evidence measurement; binding measurement; }
argument calibrated_route { conclusion outcome; reasoning compose; assumptions calibrated; premises increase; }
'''
VALUE = {'schema': 'EAL/typed-input/1', 'method': 'causal/1', 'subject': 'pump-A',
         'quantity': 'pressure', 'unit': 'Pa', 'scope': 'trial-1',
         'valid_from': '2026-09-23T10:00:00Z', 'valid_until': '2026-09-23T11:00:00Z',
         'payload': {'assignment': 'randomised', 'treatment': [10000, 12000], 'control': [3000, 4000]}}


def records_for(program, context=CONTEXT, *, stale=()):
    records = {}
    for name, evidence in program.evidence.items():
        tool = program.tools[evidence.tool]
        value = deepcopy(VALUE if name == 'measurement' else {'holds': True})
        records[name] = {'evidence_id': name, 'source_digest': program.source_digest,
                         'tool': tool.name, 'tool_version': tool.version, 'mode': tool.mode,
                         'evidence_kind': evidence.kind, 'environment': evidence.environment,
                         'environment_fingerprint': environment_fingerprint(evidence.environment, context),
                         'input_digest': canonical_digest(evidence.input), 'run_id': 'fixed-observation',
                         'collected_at': '2026-09-23T11:58:00Z' if name in stale else NOW,
                         'status': 'ok', 'value': value, 'data_digest': canonical_digest(value)}
    return records


@pytest.mark.parametrize('addition,stale,context,now,expected,label', [
    ('', (), CONTEXT, NOW, 'supported', 'accepted'),
    ('objection circular { target claim outcome; premises outcome; }', (), CONTEXT, NOW, 'contested', 'undecided'),
    ('objection challenge { target assumption calibrated; evidence calibration; }', (), CONTEXT, NOW, 'contested', 'rejected'),
    ('', ('measurement',), CONTEXT, NOW, 'unsupported', 'rejected'),
    ('', (), CONTEXT, '2026-09-23T12:00:30Z', 'unsupported', 'rejected'),
    ('', (), {'site': 'elsewhere'}, NOW, 'out_of_scope', 'rejected'),
])
def test_unused_extension_preserves_conclusions_and_all_qualifications(addition, stale, context, now, expected, label):
    program = parse(SOURCE + addition)
    records = records_for(program, context, stale=stale)
    original_records = deepcopy(records)
    builtin = default_registry()
    extended = builtin.with_method(RMS_CONTRACT)
    before = evaluate(program, records, now=now, context=context, registry=builtin)
    after = evaluate(program, records, now=now, context=context, registry=extended)
    assert before['valid'] and after['valid']
    assert before['claims']['outcome']['status'] == expected
    assert before['claims']['outcome']['grounded_label'] == label
    # Registry inventory is audit metadata; every evaluated result and reason,
    # including typed input, scope, time, dependencies and attacks, is unchanged.
    assert before.pop('method_registry_fingerprint') != after.pop('method_registry_fingerprint')
    assert before == after
    assert records == original_records
    if not stale and context == CONTEXT:
        binding = before['arguments']['measured']['reasoning_result']['binding']
        assert binding['actual'] == 7.5 and binding['output_unit'] == 'kPa'
        assert binding['proposition']['scope'] == 'trial-1'
        assert binding['proposition']['valid_until'] == '2026-09-23T11:00:00Z'
        assert binding['physical_interpretation_verified'] is False


@pytest.mark.parametrize('old_version', ['EAL/0.1', 'EAL/0.2', 'EAL/0.3', 'EAL/1'])
def test_legacy_versions_have_no_runtime_semantics(old_version):
    program = replace(parse(SOURCE), language=old_version)
    result = evaluate(program, {}, now=NOW, context=CONTEXT)
    assert result['valid'] is False
    assert any(d['code'] == 'unsupported_language' and d['expected'] == 'EAL/2'
               and d['actual'] == old_version for d in result['diagnostics'])
    assert result['arguments'] == result['claims'] == {}


def test_builtin_api_and_source_require_exact_versioned_method_identifiers():
    registry = default_registry()
    assert registry.get('causal') is None
    assert registry.get('structured') is None
    assert registry.get('causal/2') is None
    assert registry.get('causal/1').identifier == 'causal/1'
    assert validate_mode('causal', ['experiment'])
    assert assess_mode('structured', [{'id': 'e', 'kind': 'test', 'value': {}}], [])['status'] == 'unsupported'
    program = parse(SOURCE.replace('method "causal/1"', 'method "causal"'))
    diagnostic = next(d for d in validate(program) if d.code == 'invalid_method_reference')
    assert diagnostic.declaration == 'contrast'
    assert diagnostic.span == program.locations['contrast']
    assert diagnostic.actual == 'causal'


def test_reasoning_and_computation_explanations_identify_methods_without_reasoning_modes():
    program = parse(SOURCE)
    result = evaluate(program, records_for(program), now=NOW, context=CONTEXT)
    assert result['valid']
    for name, method in [('contrast', 'causal/1'), ('compose', 'structured/1')]:
        entry = result['reasoning'][name]
        assert entry['method'] == method and 'mode' not in entry
        assert any(method in reason for reason in entry['reasons'])
        assert not hasattr(program.reasoning[name], 'mode')
    assert result['arguments']['measured']['reasoning_result']['method'] == 'causal/1'
    assert result['evidence']['measurement']['mode'] == 'deterministic'


def test_static_diagnostics_retain_lowering_spans_and_attach_declaration_spans():
    program = parse(SOURCE.replace('premises increase;', 'premises missing;'))
    explicit = SourceSpan(20, 3, 20, 9)
    lowered = Diagnostic('pattern_binding_kind', 'Wrong kind', 'calibrated_route', explicit,
                         'claim', 'evidence')
    program = replace(program, lowering_diagnostics=(lowered,))
    diagnostics = validate(program)
    assert diagnostics[0] == lowered
    reference = next(d for d in diagnostics if d.code == 'unknown_reference')
    assert reference.span == program.locations['calibrated_route']
    assert reference.expected == 'premise claim' and reference.actual == 'missing'
    result = evaluate(program, {}, now=NOW, context=CONTEXT)
    assert result['diagnostics'][0]['span'] == asdict(explicit)
    assert result['claims'] == {}


def test_defence_and_alternative_derivation_obey_one_fixed_point():
    source = SOURCE + '''
argument independent { conclusion outcome; reasoning compose; evidence calibration; }
objection challenge { target argument calibrated_route; evidence calibration; }
objection defence { target objection challenge; evidence calibration; }
objection reply { target objection defence; evidence calibration; }
'''
    program = parse(source)
    result = evaluate(program, records_for(program), now=NOW, context=CONTEXT)
    assert result['valid']
    assert result['objections']['reply']['status'] == 'active'
    assert result['objections']['defence']['status'] == 'defeated'
    assert result['objections']['challenge']['status'] == 'active'
    assert result['arguments']['calibrated_route']['grounded_label'] == 'rejected'
    assert result['arguments']['independent']['grounded_label'] == 'accepted'
    assert result['claims']['outcome']['supporting_arguments'] == ['independent']
    assert result['claims']['outcome']['status'] == 'supported'
