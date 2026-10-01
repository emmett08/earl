"""Behavioural checks for scoped authoring, hygienic templates and pure expressions."""
from dataclasses import replace
from pathlib import Path
import pytest
from eal.parser import parse, EALSyntaxError
from eal.semantics import validate
from eal.formatter import format_program, semantic_ir
from eal.evaluator import _check_predicate
from eal.runtime import ReasoningService
from eal.limits import ExecutionLimits

BASE = '''language "EAL/3"
environment lab {
  require site == "bench"
}
tool collector {
  version "1"
}
context environment lab, tool collector, max_age 60, kind test {
  evidence first {
    require ok
  }
  evidence second {
    require ok
  }
  claim passed {
    statement "The checks pass under the declared relation."
  }
}
reasoning measured {
  method "structured/1"
  rationale "An explicitly authored relation."
}
'''
RECURSIVE = '''pattern each(c: claim, r: reasoning, es: evidence[]) decreases es {
  when es {
    argument item = [evidence head(es)] via r => c
    apply rest = each(c=c, r=r, es=tail(es))
  }
}
apply checks = each(c=passed, r=measured, es=[first, second])
'''


def round_trip(source, **options):
    program = parse(source, **options)
    assert not validate(program)
    printed = format_program(program)
    assert semantic_ir(parse(printed, **options)) == semantic_ir(program)
    assert format_program(parse(printed, **options)) == printed
    return program


def test_recursive_list_expansion_preserves_evidence_and_terminates_at_empty_list():
    program = round_trip(BASE + RECURSIVE)
    assert list(program.arguments) == ['checks.item', 'checks.rest.item']
    assert program.arguments['checks.item'].evidence == ('first',)
    assert program.arguments['checks.rest.item'].evidence == ('second',)
    assert 'checks.rest.rest' in program.applications
    assert program.arguments['checks.rest.item'].origin.application == 'checks.rest'
    assert not parse(BASE + RECURSIVE.replace('[first, second]', '[]')).arguments


def test_list_support_is_conjunctive_and_preserves_order_and_identity():
    source = BASE + '''pattern together(c: claim, r: reasoning, es: evidence[]) = [evidence es] via r => c
apply checks = together(c=passed, r=measured, es=[second, first])
'''
    program = round_trip(source)
    assert program.arguments['checks'].evidence == ('second', 'first')
    assert {'empty_argument'} <= {d.code for d in validate(parse(source.replace('[second, first]', '[]')))}


def test_modules_and_argument_blocks_bind_forward_local_references():
    source = BASE + '''module release {
  claim ready {
    statement "The declared release condition follows."
    environment lab
  }
  argument assess {
    argument child = [evidence first] via measured => intermediate
    claim intermediate {
      statement "The first check passes."
      environment lab
    }
    [premises intermediate] via measured => ready
  }
}
'''
    program = round_trip(source)
    assert program.arguments['release.assess.child'].conclusion == 'release.assess.intermediate'
    assert program.arguments['release.assess'].premises == ('release.assess.intermediate',)
    assert program.arguments['release.assess'].conclusion == 'release.ready'


def test_nested_pattern_calls_and_local_definitions_are_closed_and_hygienic():
    source = BASE + '''pattern build(c: claim, r: reasoning, e: evidence, env: environment) {
  pattern leaf(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
  claim intermediate {
    statement "A local bounded claim."
    environment env
  }
  apply child = leaf(c=intermediate, r=r, e=e)
  argument parent = [premises intermediate] via r => c
}
apply one = build(c=passed, r=measured, e=first, env=lab)
apply two = build(c=passed, r=measured, e=second, env=lab)
'''
    program = round_trip(source)
    assert program.arguments['one.child'].conclusion == 'one.intermediate'
    assert program.arguments['two.child'].conclusion == 'two.intermediate'
    assert program.arguments['one.parent'].premises == ('one.intermediate',)
    assert program.arguments['two.parent'].premises == ('two.intermediate',)
    assert program.arguments['one.child'].evidence == ('first',)


@pytest.mark.parametrize('replacement, code', [
    ('decreases es', None),
    ('', 'nonterminating_pattern'),
])
def test_recursion_is_statically_checked_even_when_unused(replacement, code):
    source = (BASE + RECURSIVE[:RECURSIVE.index('apply checks')]).replace('decreases es', replacement)
    found = {d.code for d in validate(parse(source))}
    assert (code in found) if code else not found


@pytest.mark.parametrize('change', [
    lambda s: s.replace('es=tail(es)', 'es=es'),
    lambda s: s.replace('when es {', 'context environment lab {'),
])
def test_non_decreasing_or_unguarded_recursion_never_executes(change):
    found = {d.code for d in validate(parse(change(BASE + RECURSIVE)))}
    assert 'nonterminating_pattern' in found


def test_budget_exhaustion_is_invalid_and_does_not_publish_partial_generated_routes():
    program = parse(BASE + RECURSIVE, limits=ExecutionLimits(applications=1))
    assert 'resource_limit' in {d.code for d in validate(program)}
    assert not program.arguments
    larger = parse(BASE + RECURSIVE, limits=ExecutionLimits(applications=10))
    assert not validate(larger)
    assert len(larger.arguments) == 2


def test_import_identity_covers_dependency_bytes_and_tracks_file_locations(tmp_path):
    (tmp_path / 'support.eal').write_text(BASE)
    source = '''language "EAL/3"
import "support.eal" as support
argument ready = [evidence support.first] via support.measured => support.passed
'''
    service = ReasoningService(tmp_path)
    program = service.parse(source)
    assert not validate(program)
    assert program.source_files['support.first'] == 'support.eal'
    assert program.imports.keys() == {'support.eal'}
    assert service.format(source)['source_digest'] == service.parse(service.format(source)['source']).source_digest
    (tmp_path / 'support.eal').write_text(BASE + '// reviewed source revision\n')
    assert service.parse(source).source_digest != program.source_digest


@pytest.mark.parametrize('path', ['../outside.eal', '/tmp/outside.eal', 'config.toml'])
def test_workspace_import_resolver_refuses_escape_or_non_source_files(tmp_path, path):
    result = ReasoningService(tmp_path).validate('language "EAL/3"\nimport ' + repr(path).replace("'", '"') + ' as support\n')
    assert result['valid'] is False


def test_import_cycle_is_a_diagnostic_not_unbounded_recursion(tmp_path):
    (tmp_path / 'cycle.eal').write_text('language "EAL/3"\nimport "cycle.eal" as again\n')
    assert ReasoningService(tmp_path).validate('language "EAL/3"\nimport "cycle.eal" as cycle\n')['valid'] is False


@pytest.mark.parametrize('expression, values, holds, comparable', [
    ('not failed and count(samples) == 2', {'failed': False, 'samples': [1, 3]}, True, True),
    ('sum(samples) / count(samples) < 3', {'samples': [1, 3]}, True, True),
    ('not missing', {}, False, False),
    ('missing or ready', {'ready': True}, True, True),
    ('missing and ready', {'ready': False}, False, True),
    ('count(samples) == 0 or sum(samples) / count(samples) > 0', {'samples': []}, False, False),
    ('quantity(distance, "m") / quantity(duration, "s") == quantity(velocity, "km/h")', {'distance': 10, 'duration': 2, 'velocity': 18}, True, True),
    ('samples == true', {'samples': 1}, False, False),
    ('field("service-name") == "orders"', {'service-name': 'orders'}, True, True),
])
def test_expression_types_unknowns_and_dimensions(expression, values, holds, comparable):
    program = round_trip(BASE.replace('require ok', 'require ' + expression))
    check = _check_predicate(program.evidence['first'].predicates[0], values)
    assert (check.holds, check.comparable) == (holds, comparable)


@pytest.mark.parametrize('expression', ['1 and true', 'count(5) == 1', 'shell("echo hi") == 0', 'quantity(1,"unknown") > quantity(2,"m")'])
def test_invalid_unused_expressions_are_static_errors(expression):
    assert 'invalid_expression' in {d.code for d in validate(parse(BASE.replace('require ok', 'require ' + expression)))}


def test_dynamic_quantity_dimensions_are_checked_before_evaluation():
    program = parse(BASE.replace('require ok', 'require quantity(distance, "m") < quantity(duration, "s")'))
    assert any(d.code == 'invalid_expression' and 'dimensions' in d.message for d in validate(program))


def test_arbitrary_json_key_stays_a_field_expression():
    program = round_trip(BASE.replace('require ok', 'require field("sensor value$") == 3'))
    result = _check_predicate(program.evidence['first'].predicates[0], {'sensor value$': 3})
    assert result.holds


def test_expression_depth_is_host_owned_and_fails_closed():
    source = BASE.replace('require ok', 'require ' + '+'.join(['reading'] * 30) + ' > 0')
    program = parse(source, limits=ExecutionLimits(expression_depth=10))
    assert any('depth budget' in d.message for d in validate(program))


def test_repeated_imports_use_one_immutable_source_snapshot():
    library = 'language "EAL/3"\nenvironment lab {\n require true\n}\n'
    calls = []
    def resolver(path):
        calls.append(path)
        return library if len(calls) == 1 else library.replace('true', 'false')
    program = round_trip('language "EAL/3"\nimport "lib.eal" as one\nimport "lib.eal" as two\n', resolver=lambda _: library)
    captured = parse('language "EAL/3"\nimport "lib.eal" as one\nimport "lib.eal" as two\n', resolver=resolver)
    assert calls == ['lib.eal']
    assert semantic_ir(captured) == semantic_ir(program)


def test_context_false_and_zero_are_not_collapsed_by_formatting():
    source = BASE.replace('max_age 60, kind test', 'max_age 60, kind test, input false').replace('evidence first {', 'evidence first {\n    input 0')
    program = round_trip(source)
    assert type(program.evidence['first'].input) is int
    assert program.evidence['second'].input is False


def test_compact_nested_application_can_be_an_objection_target():
    source = BASE + '''pattern build(c: claim, r: reasoning, e: evidence) {
  pattern leaf(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
  apply child = leaf(c=c, r=r, e=e)
  objection disputed = [evidence e] -x> argument child
}
apply checks = build(c=passed, r=measured, e=first)
'''
    program = round_trip(source)
    assert program.objections['checks.disputed'].target == 'checks.child'


def test_unused_compound_metadata_is_validated():
    source = BASE + '''pattern unused() {
  reasoning invalid {
    method "uninstalled/1"
    rationale "No installed method."
  }
}
'''
    assert any(d.code == 'unknown_method' for d in validate(parse(source)))


def test_direct_compact_ir_uses_captured_host_application_budget():
    from eal.abstractions import lower_patterns
    source = BASE + '''pattern route(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
apply one = route(c=passed, r=measured, e=first)
apply two = route(c=passed, r=measured, e=second)
'''
    core = replace(parse(source), authored=None)
    limited = lower_patterns(replace(core, limits=ExecutionLimits(applications=1)))
    assert any(d.code == 'resource_limit' for d in limited.lowering_diagnostics)
    assert not lower_patterns(replace(core, limits=ExecutionLimits(applications=2))).lowering_diagnostics
