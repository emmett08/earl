import pytest

from eal.extensions import example_registry
from eal.reachability import REACHABILITY_CONTRACT
from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.semantics import validate
from test_typed_propositions import SOURCE
from _runtime_cases import PRESSURE_SOURCE, REACHABILITY_SOURCE, RMS_SOURCE


@pytest.mark.parametrize('source', [SOURCE, PRESSURE_SOURCE, RMS_SOURCE, REACHABILITY_SOURCE])
def test_canonical_source_round_trip_preserves_typed_ir_and_is_idempotent(source):
    registry = example_registry().with_method(REACHABILITY_CONTRACT)
    formatted = format_source(source, registry=registry)
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
    assert format_source(formatted, registry=registry) == formatted
    assert not validate(parse(formatted), registry=registry)


def test_contextual_words_remain_identifiers_in_eal2_sources():
    source = '''language "EAL/2";
    environment scope { require "site" == "bench"; }
    tool quantity { version "1"; }
    evidence unit { tool quantity; kind subject; environment scope; max_age 1; require "ok" == true; }
    reasoning proposition { method "structured/1"; rationale "A bounded authored relation."; }
    claim binding { statement "The stated test passes."; environment scope; }
    argument result { conclusion binding; reasoning proposition; evidence unit; }
    claim query { statement "The same test passes."; environment scope; }
    '''
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))


def test_removed_tool_mode_words_can_be_ordinary_names():
    source = '''language "EAL/2";
    environment deterministic { require "site" == "bench"; }
    tool mode { version "1"; }
    evidence nondeterministic { tool mode; kind test; environment deterministic;
      max_age 1; require "ok" == true; }
    reasoning reasoning_step { method "structured/1"; rationale "The bounded observation supports the claim."; }
    claim checked { statement "The check passes."; environment deterministic; }
    argument check { conclusion checked; reasoning reasoning_step; evidence nondeterministic; }
    '''
    formatted = format_source(source)
    assert 'tool mode {\n  version "1";\n}' in formatted
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))


def test_formatter_rejects_invalid_semantics_without_repair():
    with pytest.raises(ValueError, match='missing_binding'):
        format_source(SOURCE.replace('binding trial;', ''))
