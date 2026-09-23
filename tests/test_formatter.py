from pathlib import Path

import pytest

from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.semantics import validate
from test_typed_propositions import SOURCE


@pytest.mark.parametrize('source', [SOURCE, *(path.read_text() for path in Path('examples').glob('*.eal'))])
def test_canonical_source_round_trip_preserves_typed_ir_and_is_idempotent(source):
    formatted = format_source(source)
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
    assert format_source(formatted) == formatted
    assert not validate(parse(formatted))


def test_contextual_new_words_remain_identifiers_in_legacy_sources():
    source = '''language "EAL/0.1";
    environment scope { require "site" == "bench"; }
    tool quantity { version "1"; mode deterministic; }
    evidence unit { tool quantity; kind subject; environment scope; max_age 1; require "ok" == true; }
    reasoning proposition { mode structured; rationale "A bounded authored relation."; }
    claim binding { statement "The stated test passes."; environment scope; }
    argument result { conclusion binding; reasoning proposition; evidence unit; }
    claim query { statement "The same test passes."; environment scope; }
    '''
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))


def test_formatter_rejects_invalid_semantics_without_repair():
    with pytest.raises(ValueError, match='missing_binding'):
        format_source(SOURCE.replace('binding trial;', ''))
