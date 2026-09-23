from pathlib import Path

import pytest

from eal.extensions import example_registry
from eal.reachability import REACHABILITY_CONTRACT
from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.semantics import validate
from test_typed_propositions import SOURCE


@pytest.mark.parametrize('source', [SOURCE, *(path.read_text() for path in Path('examples').glob('*.eal'))])
def test_canonical_source_round_trip_preserves_typed_ir_and_is_idempotent(source):
    registry = example_registry().with_method(REACHABILITY_CONTRACT)
    formatted = format_source(source, registry=registry)
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
    assert format_source(formatted, registry=registry) == formatted
    assert not validate(parse(formatted), registry=registry)


def test_contextual_words_remain_identifiers_in_eal2_sources():
    source = '''language "EAL/2";
    environment scope { require "site" == "bench"; }
    tool quantity { version "1"; mode deterministic; }
    evidence unit { tool quantity; kind subject; environment scope; max_age 1; require "ok" == true; }
    reasoning proposition { method "structured/1"; rationale "A bounded authored relation."; }
    claim binding { statement "The stated test passes."; environment scope; }
    argument result { conclusion binding; reasoning proposition; evidence unit; }
    claim query { statement "The same test passes."; environment scope; }
    '''
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))


def test_formatter_rejects_invalid_semantics_without_repair():
    with pytest.raises(ValueError, match='missing_binding'):
        format_source(SOURCE.replace('binding trial;', ''))
