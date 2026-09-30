"""EAL/3 source notation preserves the existing typed and ASPIC+ contracts."""
from dataclasses import replace
import itertools

import pytest

from eal.aspic_compiler import compile_eal_aspic
from eal.aspic_export import export_aspic_view
from eal.evaluator import evaluate
from eal.formatter import format_source, semantic_ir
from eal.parser import EALSyntaxError, parse
from eal.semantics import validate
from test_evaluator import CONTEXT, NOW, record


SOURCE = '''language "EAL/3"
environment lab {
  require site == "bench"
}
tool collector {
  version "1"
}
context environment lab, tool collector, max_age 60 {
  evidence observation {
    kind test
    require ok == true
  }
  claim measured {
    statement "The synthetic measurement meets its condition."
  }
  claim followup {
    statement "The declared implication follows from the measured claim."
  }
}
reasoning authored {
  method "structured/1"
  rationale "A bounded authored relation, conditional on the supplied observation."
}
pattern measured_route(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
apply child=measured_route(c=measured, r=authored, e=observation)
argument parent = [premises measured] via authored => followup
strict parent reviewed "synthetic-review/conditional-implication"
rank observation 700 reviewed "synthetic-review/measurement"
'''


def test_scoped_pattern_instance_supplies_a_nested_formal_derivation():
    program = parse(SOURCE)
    assert not validate(program)
    assert program.arguments['child'].origin.pattern == 'measured_route'
    assert program.arguments['parent'].premises == ('measured',)
    assert program.evidence['observation'].environment == 'lab'
    records = {'observation': record(program, 'observation', {'ok': True})}
    result = compile_eal_aspic(SOURCE, records, goal='followup', now=NOW, context=CONTEXT).to_dict()
    view = export_aspic_view(result)
    by_id = {a['id']: a for a in view['arguments']}
    parent = next(a for a in view['arguments'] if a['origin']['name'] == 'parent')
    child = by_id[parent['direct_subarguments'][0]]
    assert parent['top'] == 'strict' and child['origin']['name'] == 'child'
    assert child['top'] == 'defeasible'
    assert parent['strength'] == 500  # Its fallible subargument remains fallible.
    assert parent['origin']['formal_review']['kind'] == 'strict'
    evidence = [a for a in view['arguments'] if a['origin']['kind'] == 'evidence']
    assert len(evidence) == 1 and evidence[0]['rank'] == 700
    assert parent['label'] == 'in'
    assert semantic_ir(program) == semantic_ir(parse(format_source(SOURCE)))


def test_nested_defaults_local_override_and_lexical_extent():
    source = SOURCE.replace('  claim measured {', '''  context max_age 5 {
    evidence short_lived {
      kind test
      require ok == true
    }
  }
  evidence explicit {
    kind test
    max_age 10
    require ok == true
  }
  claim measured {''')
    program = parse(source)
    assert program.evidence['short_lived'].max_age == 5
    assert program.evidence['explicit'].max_age == 10
    assert program.evidence['observation'].max_age == 60
    assert not validate(program)
    assert semantic_ir(program) == semantic_ir(parse(format_source(source)))


def test_multiple_scoped_evidence_keep_distinct_requests_and_required_support():
    source = SOURCE.replace('  claim measured {', '''  evidence corroboration {
    kind test
    input {"measurement": "errors"}
    require fraction <= 0.01
  }
  claim measured {''').replace('[premises measured]', '[evidence corroboration, premises measured]')
    program = parse(source)
    assert not validate(program)
    assert set(program.evidence) == {'observation', 'corroboration'}
    for evidence in program.evidence.values():
        assert (evidence.environment, evidence.tool, evidence.max_age) == ('lab', 'collector', 60)
    assert semantic_ir(program) == semantic_ir(parse(format_source(source)))

    records = {
        'observation': record(program, 'observation', {'ok': True}),
        'corroboration': record(program, 'corroboration', {'fraction': 0.005}),
    }
    assert records['observation']['request_digest'] != records['corroboration']['request_digest']
    result = evaluate(program, records, now=NOW, context=CONTEXT)
    assert result['claims']['followup']['status'] == 'supported'

    records['corroboration'] = record(program, 'corroboration', {'fraction': 0.02})
    for supplied in (records, {'observation': records['observation']}):
        result = evaluate(program, supplied, now=NOW, context=CONTEXT)
        assert result['claims']['measured']['status'] == 'supported'
        assert result['claims']['followup']['status'] == 'unsupported'


def test_singleton_fields_can_be_reordered_without_changing_the_ir():
    fields = ['tool collector', 'kind test', 'environment lab', 'max_age 60', 'require ok == true']
    base = parse('language "EAL/3"\nevidence e {\n' + '\n'.join(fields) + '\n}\n')
    for order in itertools.permutations(fields):
        candidate = parse('language "EAL/3"\nevidence e {\n' + '\n'.join(order) + '\n}\n')
        assert replace(candidate, source_digest=base.source_digest) == base


@pytest.mark.parametrize('source, message', [
    (SOURCE.replace('kind test', 'kind test\nkind test'), 'Duplicate field'),
    (SOURCE.replace('tool collector, max_age 60', 'tool collector, tool collector, max_age 60'), 'Duplicate context'),
    (SOURCE.replace('[premises measured]', '[premises measured, premises followup]'), 'Duplicate support'),
    (SOURCE.replace('    kind test\n', ''), 'Missing field'),
    (SOURCE.replace('    require ok == true\n', ''), 'requires at least one'),
    (SOURCE.replace('max_age 60', 'max_age 60;'), 'recognition error'),
])
def test_malformed_eal3_fields_fail_before_evaluation(source, message):
    with pytest.raises(EALSyntaxError, match=message):
        parse(source)


def test_premises_remain_claim_typed_and_inline_argument_blocks_are_rejected():
    program = parse(SOURCE.replace('[premises measured]', '[premises child]'))
    assert 'unknown_reference' in {d.code for d in validate(program)}
    with pytest.raises(EALSyntaxError):
        parse(SOURCE + 'argument inline {\nargument nested = [premises measured] via authored => followup\n}\n')


def test_multiline_json_keys_and_flow_continuation_preserve_typed_values():
    source = SOURCE.replace('    kind test\n', '''    kind test
    input {
      "route": "/orders",
      "values": [1, true, null, {"a": 2}]
    }
''').replace('[premises measured] via authored => followup', '[premises measured]\nvia authored\n=> followup')
    program = parse(source)
    assert program.evidence['observation'].input['values'] == [1, True, None, {'a': 2}]
    assert semantic_ir(program) == semantic_ir(parse(format_source(source)))
