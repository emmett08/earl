"""Recognition, linking and resource checks on real ANTLR-generated code."""
import pytest

from eal.parser import EALSyntaxError, parse
from eal.semantics import validate

BASE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence observation {
 tool runner; kind test; environment lab; max_age 60;
 input {"suite": "smoke", "args": [1, true, null]}; require "passed" == true;
}
assumption stable { statement "The measured configuration persists.";
 environment lab; validate observation; valid_until "2027-01-01T00:00:00Z";
}
reasoning measured { method "structured/1"; rationale "The bounded test result supports the stated test claim."; }
claim working { statement "The smoke test passes."; environment lab; }
argument first { conclusion working; reasoning measured; evidence observation; assumptions stable; }
'''


def codes(source):
    return {d.code for d in validate(parse(source))}


def test_real_antlr_visitor_builds_typed_ast():
    program = parse(BASE)
    assert not validate(program)
    assert program.evidence['observation'].input == {'suite': 'smoke', 'args': [1, True, None]}
    assert program.evidence['observation'].kind == 'test'
    assert program.reasoning['measured'].method == 'structured/1'
    assert not hasattr(program.reasoning['measured'], 'mode')
    assert program.assumptions['stable'].valid_from is None
    assert program.assumptions['stable'].valid_until == '2027-01-01T00:00:00Z'
    assert len(program.source_digest) == 64


@pytest.mark.parametrize('source', [
    BASE.replace('require "passed" == true;', 'require "passed" = true;'),
    BASE + 'garbage',
    BASE.replace('"suite": "smoke"', '"suite": "smoke", "suite": "other"'),
])
def test_malformed_sources_are_rejected(source):
    with pytest.raises(EALSyntaxError):
        parse(source)


def test_duplicate_and_unknown_symbols():
    assert 'duplicate_symbol' in codes(BASE + 'claim working { statement "duplicate"; environment lab; }')
    assert 'unknown_reference' in codes(BASE.replace('reasoning measured;', 'reasoning missing;'))


def test_conditional_scopes_cannot_be_silently_mixed():
    source = BASE.replace('claim working {', 'environment field { require "site" == "field"; }\nclaim working {')
    source = source.replace('statement "The smoke test passes."; environment lab;',
                            'statement "The smoke test passes."; environment field;')
    assert 'environment_mismatch' in codes(source)


def test_cycle_in_subarguments_is_rejected():
    source = BASE + '''
claim followup { statement "Follow-up claim"; environment lab; }
argument next { conclusion followup; reasoning measured; premises working; }
argument cyclic { conclusion working; reasoning measured; premises followup; }
'''
    assert 'dependency_cycle' in codes(source)


def test_time_and_numeric_types_are_checked_before_evaluation():
    assert 'invalid_timestamp' in codes(BASE.replace('2027-01-01T00:00:00Z', '2027-01-01'))
    assert 'invalid_timestamp' in codes(BASE.replace('2027-01-01T00:00:00Z', '9999-12-31T23:59:59-01:00'))
    assert 'invalid_age' in codes(BASE.replace('max_age 60', 'max_age -1'))
    assert 'invalid_comparison' in codes(BASE.replace('"passed" == true', '"passed" >= true'))
    assert 'invalid_number' in codes(BASE.replace('"passed" == true', '"passed" >= 1e999'))


def test_computational_methods_require_outputs_and_matching_evidence():
    source = BASE.replace('method "structured/1";', 'method "inductive/1";')
    assert 'missing_reasoning_predicate' in codes(source)
    assert 'reasoning_evidence_contract' in codes(source)
    source = source.replace('kind test;', 'kind sample;').replace(
        'rationale "The bounded test result supports the stated test claim.";',
        'rationale "The interval estimates a population proportion."; require "lower" > 0.5;')
    assert not validate(parse(source))


def test_parser_resource_limit():
    with pytest.raises(EALSyntaxError, match='bytes'):
        parse(' ' * (1024 * 1024 + 1))


def test_premise_depth_is_bounded_without_recursive_static_walk():
    declarations = ['language "EAL/2";', 'environment e { require "x" == 1; }',
                    'reasoning r { method "structured/1"; rationale "Declared relation"; }']
    for index in range(130):
        declarations.append(f'claim c{index} {{ statement "Claim"; environment e; }}')
        if index:
            declarations.append(f'argument a{index} {{ conclusion c{index}; reasoning r; premises c{index-1}; }}')
    assert 'resource_limit' in codes('\n'.join(declarations))


def test_static_validation_rejects_input_nesting_beyond_digest_resources():
    nested = '[' * 65 + '0' + ']' * 65
    source = BASE.replace('{"suite": "smoke", "args": [1, true, null]}', nested)
    assert 'invalid_input' in codes(source)


def test_versioned_methods_are_explicit_and_unused_unknowns_are_rejected():
    source = BASE
    assert 'invalid_method_reference' in codes(source.replace('method "structured/1";', 'method "structured";'))
    unknown = source + 'reasoning unused { method "unknown/contract/1"; rationale "Unknown"; }'
    assert 'unknown_method' in codes(unknown)
    from eal.methods import default_registry
    identifier = default_registry().get('structured/1').identifier
    assert not validate(parse(source.replace('method "structured/1";', f'method "{identifier}";')))


@pytest.mark.parametrize('language', ['EAL/0.1', 'EAL/0.2', 'EAL/0.3', 'EAL/1', 'EAL/2.0'])
def test_previous_and_unrecognised_language_versions_are_rejected(language):
    assert 'unsupported_language' in codes(BASE.replace('EAL/2', language))


@pytest.mark.parametrize('mode', ['structured', 'deductive', 'inductive', 'abductive',
                                  'causal', 'counterfactual', 'analogical', 'temporal'])
def test_source_reasoning_mode_is_rejected(mode):
    with pytest.raises(EALSyntaxError):
        parse(BASE.replace('method "structured/1";', f'mode {mode};'))
