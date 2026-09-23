"""Adversarial source/interchange cases and method predicate type checking."""
from dataclasses import replace

import pytest

from eal.evaluator import evaluate
from eal.extensions import example_registry
from eal.formatter import format_program, format_source, semantic_ir
from eal.model import Claim, Predicate
from eal.parser import EALSyntaxError, parse
from eal.semantics import validate
from test_evaluator import CONTEXT, NOW
from test_language import BASE


def codes(program, **kwargs):
    return {diagnostic.code for diagnostic in validate(program, **kwargs)}


@pytest.mark.parametrize("original", [
    '"EAL/2"', '"bench"', '"1"', '"suite"', '"smoke"',
    '"The measured configuration persists."', '"structured/1"',
    '"The bounded test result supports the stated test claim."',
    '"The smoke test passes."',
])
def test_every_source_string_rejects_unpaired_unicode_surrogates(original):
    with pytest.raises(EALSyntaxError, match=r"\d+:\d+: String contains an unpaired Unicode surrogate"):
        parse(BASE.replace(original, '"\\ud800"', 1))


def test_a_valid_surrogate_pair_formats_to_utf8_and_preserves_meaning():
    source = BASE.replace('"The smoke test passes."', '"Sensor \\ud83d\\ude00"')
    formatted = format_source(source)
    assert "Sensor 😀" in formatted
    formatted.encode("utf-8")
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))


@pytest.mark.parametrize("method,path,operand,expected,actual", [
    ("deductive/1", "entailed", "1", "boolean", "number"),
    ("inductive/1", "lower", "true", "number", "boolean"),
    ("causal/1", "estimate", '"zero"', "number", "string"),
    ("abductive/1", "posterior.fault", "null", "number", "null"),
    ("structured/1", "authored", "0", "boolean", "number"),
    ("engineering/rms/1", "sample_size", "false", "number", "boolean"),
])
def test_impossible_method_predicates_are_rejected_before_collection(method, path, operand, expected, actual):
    source = f'''language "EAL/2";
    reasoning r {{ method "{method}"; rationale "A bounded finding."; require "{path}" == {operand}; }}'''
    program = parse(source)
    diagnostic = next(d for d in validate(program, registry=example_registry())
                      if d.code == "reasoning_predicate_type")
    assert (diagnostic.expected, diagnostic.actual) == (expected, actual)
    assert diagnostic.span == program.locations["r"]
    result = evaluate(program, {}, now=NOW, context=CONTEXT, registry=example_registry())
    assert not result["valid"]
    assert result["reasoning"] == {}


@pytest.mark.parametrize("path", ["missing", "rms.field", "sample_size.field"])
def test_closed_extension_contract_rejects_missing_or_nonscalar_result_paths(path):
    source = f'''language "EAL/2";
    reasoning r {{ method "engineering/rms/1"; rationale "RMS comparison."; require "{path}" > 0; }}'''
    assert "reasoning_predicate_path" in codes(parse(source), registry=example_registry())


def test_runtime_checked_open_output_fields_remain_usable():
    # The abductive contract admits additional JSON outputs. Its method returns
    # the string-valued best candidate, which the example explicitly tests.
    source = '''language "EAL/2";
    reasoning r { method "abductive/1"; rationale "Best model."; require "best" == "fault"; }'''
    assert not validate(parse(source))


@pytest.mark.parametrize("bad_input", [{1: "renamed during JSON printing"}, (1, 2), {"bad": b"bytes"}, {"bad": "\ud800"}])
def test_direct_ir_rejects_values_whose_json_serialisation_changes_or_loses_meaning(bad_input):
    program = parse(BASE)
    observation = replace(program.evidence["observation"], input=bad_input)
    changed = replace(program, evidence={"observation": observation})
    assert "invalid_input" in codes(changed)
    with pytest.raises(ValueError, match="invalid_input"):
        format_program(changed)


@pytest.mark.parametrize("bad_age", [True, "60", None])
def test_direct_ir_cannot_use_wrong_scalar_types_to_bypass_recognition(bad_age):
    program = parse(BASE)
    observation = replace(program.evidence["observation"], max_age=bad_age)
    changed = replace(program, evidence={"observation": observation})
    assert "invalid_ir" in codes(changed)
    assert not evaluate(changed, {}, now=NOW, context=CONTEXT)["valid"]


def test_direct_ir_checks_identity_duplicates_and_real_declaration_count(monkeypatch):
    program = parse(BASE)
    assert "declaration_identity" in codes(replace(program, tools={"renamed": program.tools["runner"]}))
    duplicate = Claim("runner", "A separate claim", "lab")
    assert "duplicate_symbol" in codes(replace(program, claims={**program.claims, "runner": duplicate}))
    from eal import semantics
    monkeypatch.setattr(semantics, "MAX_DECLARATIONS", program.declaration_count - 1)
    assert "resource_limit" in codes(replace(program, declaration_count=0))


def test_direct_ir_cannot_introduce_unrepresentable_names_or_operators():
    program = parse(BASE)
    tool = replace(program.tools["runner"], name="claim")
    assert "invalid_identifier" in codes(replace(program, tools={"claim": tool}))
    environment = replace(program.environments["lab"], predicates=(Predicate("site", "is", "bench"),))
    changed = replace(program, environments={"lab": environment})
    assert "invalid_comparison" in codes(changed)
    assert not evaluate(changed, {}, now=NOW, context=CONTEXT)["valid"]


def test_direct_ir_cannot_introduce_structured_predicate_operands():
    program = parse(BASE)
    environment = replace(program.environments["lab"], predicates=(Predicate("site", "==", {"site": "bench"}),))
    assert "invalid_predicate" in codes(replace(program, environments={"lab": environment}))


def test_direct_ir_cannot_remove_required_environment_predicates():
    program = parse(BASE)
    environment = replace(program.environments["lab"], predicates=())
    assert "missing_predicate" in codes(replace(program, environments={"lab": environment}))
