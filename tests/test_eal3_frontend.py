"""Typed reusable arguments, hygienic lowering and source-aware diagnostics."""
from dataclasses import replace

import pytest

from eal import abstractions
from eal.abstractions import lower_patterns
from eal.evaluator import evaluate
from eal.formatter import format_program, format_source, semantic_ir
from eal.model import ArgumentOrigin, SourceSpan
from eal.parser import EALSyntaxError, parse
from eal.semantics import validate
from test_evaluator import CONTEXT, NOW, record
from test_typed_propositions import SOURCE, VALUE


BASE = '''language "EAL/3"

environment lab {
  require "site" == "bench"
}

tool runner {
  version "1"
}

evidence samples {
  tool runner
  kind test
  environment lab
  max_age 60
  require "ok" == true
}

assumption stable {
  statement "The same configuration persists."
  environment lab
  validate samples
}

reasoning measured {
  method "structured/1"
  rationale "The test supports the bounded claim."
}

claim pressure {
  statement "Pressure is acceptable."
  environment lab
}

claim calibrated {
  statement "The instrument is calibrated."
  environment lab
}
'''
PATTERN = '''pattern check(c: claim, r: reasoning, e: evidence, a: assumption, p: claim) = [evidence e, assumptions a, premises p] via r => c
'''
APPLICATION = '''apply pressure_check=check(c=pressure, r=measured, e=samples, a=stable, p=calibrated)
'''


def diagnostics(source):
    return {diagnostic.code for diagnostic in validate(parse(source))}


def test_patterns_expand_typed_references_and_retain_authored_structure():
    program = parse(BASE + PATTERN + APPLICATION)
    assert not validate(program)
    argument = program.arguments['pressure_check']
    assert (argument.conclusion, argument.reasoning, argument.evidence,
            argument.assumptions, argument.premises) == (
        'pressure', 'measured', ('samples',), ('stable',), ('calibrated',))
    assert argument.origin == ArgumentOrigin('check', 'pressure_check')
    assert program.patterns['check'].parameters[0].kind == 'claim'
    assert program.applications['pressure_check'].arguments[0].reference == 'pressure'
    assert lower_patterns(program) == program
    # Seven base declarations, pattern and application, pattern body and output.
    assert program.declaration_count == 11


def test_forward_references_and_alpha_renaming_cannot_capture_global_names():
    original = parse('''language "EAL/3"
''' + APPLICATION + BASE.split('\n', 1)[1] + PATTERN)
    renamed = PATTERN.replace('c: claim', 'pressure: claim').replace('=> c', '=> pressure')
    alpha_renamed = parse(BASE + renamed + APPLICATION.replace('c=pressure', 'pressure=pressure'))
    assert original.arguments == alpha_renamed.arguments
    source = BASE + renamed + APPLICATION.replace('c=pressure', 'pressure=calibrated').replace('p=calibrated', 'p=pressure')
    program = parse(source)
    assert not program.lowering_diagnostics
    assert program.arguments['pressure_check'].conclusion == 'calibrated'
    assert program.arguments['pressure_check'].premises == ('pressure',)
    assert original.arguments['pressure_check'].conclusion == 'pressure'


def test_same_evidence_and_assumption_identity_survive_multiple_applications():
    program = parse(BASE + PATTERN + APPLICATION + APPLICATION.replace('pressure_check', 'independent'))
    first, second = program.arguments.values()
    assert first.evidence == second.evidence == ('samples',)
    assert first.assumptions == second.assumptions == ('stable',)
    assert len(program.evidence) == len(program.assumptions) == 1


@pytest.mark.parametrize('old,new,code', [
    ('c: claim', 'c: evidence', 'pattern_reference_kind'),
    ('r: reasoning', 'r: claim', 'pattern_reference_kind'),
    ('e: evidence', 'e: claim', 'pattern_reference_kind'),
    ('a: assumption', 'a: evidence', 'pattern_reference_kind'),
    ('p: claim', 'p: assumption', 'pattern_reference_kind'),
    ('c: claim', 'c: imaginary', 'invalid_pattern_parameter_kind'),
    ('c: claim,', 'c: claim, c: claim,', 'duplicate_pattern_parameter'),
    ('=> c', '=> pressure', 'unbound_pattern_reference'),
])
def test_unused_malformed_patterns_are_rejected(old, new, code):
    program = parse(BASE + PATTERN.replace(old, new))
    assert code in {diagnostic.code for diagnostic in validate(program)}
    diagnostic = next(d for d in program.lowering_diagnostics if d.code == code)
    assert diagnostic.span == program.locations['check']


@pytest.mark.parametrize('old,new,code', [
    ('check(', 'missing(', 'unknown_pattern'),
    ('c=pressure, ', '', 'missing_pattern_argument'),
    ('c=pressure', 'c=pressure, c=calibrated', 'duplicate_pattern_argument'),
    ('c=pressure', 'extra=pressure', 'unknown_pattern_argument'),
    ('c=pressure', 'c=samples', 'pattern_argument_kind'),
    ('c=pressure', 'c=nonexistent', 'pattern_argument_kind'),
    ('e=samples', 'e=stable', 'pattern_argument_kind'),
])
def test_invalid_applications_never_generate_arguments(old, new, code):
    program = parse(BASE + PATTERN + APPLICATION.replace(old, new))
    assert code in {diagnostic.code for diagnostic in validate(program)}
    assert 'pressure_check' not in program.arguments


def test_pattern_binding_is_checked_as_an_evidence_parameter():
    source = BASE + PATTERN.replace('=> c', '=> c binding c')
    diagnostic = next(d for d in parse(source).lowering_diagnostics if d.code == 'pattern_reference_kind')
    assert (diagnostic.expected, diagnostic.actual) == ('evidence', 'claim')


def test_empty_unused_pattern_is_not_a_valid_definition():
    source = BASE + 'pattern empty(c: claim, r: reasoning) = [] via r => c'
    assert 'empty_pattern' in diagnostics(source)


def test_generated_names_cannot_replace_an_authored_declaration():
    declaration = 'argument pressure_check = [evidence samples] via measured => calibrated'
    program = parse(BASE + PATTERN + declaration + '\n' + APPLICATION)
    assert {'generated_symbol_collision', 'duplicate_symbol'} <= {d.code for d in validate(program)}
    assert program.arguments['pressure_check'].conclusion == 'calibrated'
    assert program.arguments['pressure_check'].origin is None


def test_recursion_and_nested_applications_are_not_grammar_productions():
    with pytest.raises(EALSyntaxError):
        parse(BASE + PATTERN.replace('=> c', 'apply inner=check(c=c)\n conclusion c'))


def test_application_budget_and_expanded_reference_budget_are_enforced(monkeypatch):
    applications = ''.join(APPLICATION.replace('pressure_check', f'use_{i}') for i in range(1001))
    program = parse(BASE + PATTERN + applications)
    assert 'resource_limit' in {d.code for d in validate(program)}
    assert not program.arguments
    monkeypatch.setattr(abstractions, 'MAX_EXPANDED_REFERENCES', 4)
    program = parse(BASE + PATTERN + APPLICATION)
    assert 'resource_limit' in {d.code for d in validate(program)}
    assert not program.arguments


def test_declaration_locations_use_one_based_exclusive_end_positions():
    source = '''language "EAL/3"

reasoning reason {
  method "structured/1"
  rationale "Test"
}
'''
    program = parse(source)
    assert program.locations['reason'] == SourceSpan(3, 1, 6, 2)
    invalid = parse(source.replace('structured/1', 'missing/1'))
    diagnostic = next(d for d in validate(invalid) if d.declaration == 'reason')
    assert diagnostic.span == invalid.locations['reason']


def test_reasoning_method_and_tool_version_are_separate_contracts():
    program = parse(BASE)
    assert program.reasoning['measured'].method == 'structured/1'
    assert not hasattr(program.reasoning['measured'], 'mode')
    assert program.tools['runner'].version == '1'
    assert not hasattr(program.tools['runner'], 'mode')
    with pytest.raises(EALSyntaxError):
        parse(BASE.replace('method "structured/1"', 'mode structured;'))


def test_obsolete_tool_execution_mode_is_rejected_at_recognition():
    with pytest.raises(EALSyntaxError):
        parse(BASE.replace('version "1"', 'version "1"\n mode deterministic'))


def test_pattern_roundtrip_retains_authoring_and_typed_runtime_meaning():
    pattern = '''pattern compare(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c binding e

apply contrast=compare(c=raised, r=difference, e=trial)'''
    source = SOURCE[:SOURCE.index('argument contrast')] + pattern
    program = parse(source)
    formatted = format_source(source)
    assert 'pattern compare(' in formatted and 'apply contrast =' in formatted
    assert 'argument contrast' not in formatted
    assert semantic_ir(program) == semantic_ir(parse(formatted))
    assert format_source(formatted) == formatted
    assert replace(program.arguments['contrast'], origin=None) == parse(SOURCE).arguments['contrast']
    result = evaluate(program, {'trial': record(program, 'trial', VALUE)}, now=NOW, context=CONTEXT)
    assert result['valid'] and result['claims']['raised']['status'] == 'supported'
    assert program.arguments['contrast'].binding == 'trial'


def test_formatter_rejects_stale_generated_ir_instead_of_changing_its_meaning():
    program = parse(BASE + PATTERN + APPLICATION)
    changed = replace(program.arguments['pressure_check'], conclusion='calibrated', premises=())
    inconsistent = replace(program, arguments={'pressure_check': changed})
    with pytest.raises(ValueError, match='stale_pattern_expansion'):
        format_program(inconsistent)
    result = evaluate(inconsistent, {}, now=NOW, context=CONTEXT)
    assert not result['valid']
    assert 'stale_pattern_expansion' in {d['code'] for d in result['diagnostics']}
