"""Independent semantic and interaction regressions for EAL/2."""
from dataclasses import replace

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from _provenance import synthetic_provenance


NOW = "2026-09-23T12:00:00Z"
CONTEXT = {"site": "bench"}
BASE = '''language "EAL/2"

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
  require "passed" == true
}

evidence negative {
  tool collector
  kind test
  environment lab
  max_age 60
  require "passed" == true
}

evidence independent {
  tool collector
  kind test
  environment lab
  max_age 60
  require "passed" == true
}

reasoning authored {
  method "structured/1"
  rationale "Apply the stated conditional support relation."
}

claim foundation {
  statement "The bounded foundation claim."
  environment lab
}

claim downstream {
  statement "The dependent engineering claim."
  environment lab
}

claim critique {
  statement "The objection\'s stated premise."
  environment lab
}

argument first_route = [evidence positive] via authored => foundation

argument downstream_route = [premises foundation] via authored => downstream

argument critique_route = [evidence negative] via authored => critique
'''


def assess(source, *, missing=(), values=None, registry=None):
    program = parse(source)
    records = {}
    for name, evidence in program.evidence.items():
        if name in missing:
            continue
        value = values[name] if values is not None and name in values else {"passed": True}
        tool = program.tools[evidence.tool]
        records[name] = {"evidence_id": name, "source_digest": program.source_digest,
                         "tool": tool.name, "tool_version": tool.version,
                         "evidence_kind": evidence.kind, "environment": evidence.environment,
                         "environment_fingerprint": environment_fingerprint(evidence.environment, CONTEXT),
                         "input_digest": canonical_digest(evidence.input), "collected_at": NOW,
                         "run_id": "independent-semantic-review", "status": "ok", "value": value,
                         "data_digest": canonical_digest(value),
                         **synthetic_provenance(program, name, CONTEXT)}
    result = evaluate(program, records, now=NOW, context=CONTEXT, registry=registry)
    assert result["valid"], result["diagnostics"]
    return result


def claim_statuses(result):
    return {name: value["status"] for name, value in result["claims"].items()}


def test_grounded_defence_reinstates_both_local_and_dependent_arguments():
    source = BASE + '''objection challenge = [premises critique] -x> argument first_route

objection defence = [evidence independent] -x> objection challenge
'''
    result = assess(source)
    assert claim_statuses(result) == {"foundation": "supported", "downstream": "supported", "critique": "supported"}
    without_defence = assess(source, missing={"independent"})
    assert without_defence["claims"]["foundation"]["status"] == "contested"
    assert without_defence["claims"]["downstream"]["status"] == "contested"


def test_claim_cannot_bootstrap_its_own_only_defence():
    source = BASE + '''objection challenge = [premises critique] -x> argument first_route

objection defence = [premises foundation] -x> objection challenge
'''
    result = assess(source)
    assert result["claims"]["foundation"]["status"] == "contested"
    assert result["claims"]["downstream"]["status"] == "contested"
    assert result["claims"]["foundation"]["grounded_label"] == "undecided"
    assert result["objections"]["defence"]["grounded_label"] == "undecided"


def test_independent_route_can_ground_a_defence_that_was_previously_circular():
    source = BASE + '''argument independent_route = [evidence independent] via authored => foundation

objection challenge = [premises critique] -x> argument first_route

objection defence = [premises foundation] -x> objection challenge
'''
    result = assess(source)
    assert result["claims"]["foundation"]["status"] == "supported"
    assert result["arguments"]["first_route"]["status"] == "supported"
    assert result["claims"]["downstream"]["status"] == "supported"


def test_objection_without_an_accepted_premise_cannot_defeat_an_argument():
    source = BASE + '''objection challenge = [premises critique] -x> argument first_route
'''
    result = assess(source, missing={"negative"})
    assert result["claims"]["critique"]["status"] == "unsupported"
    assert result["claims"]["foundation"]["status"] == "supported"
    assert result["claims"]["downstream"]["status"] == "supported"


def test_defence_does_not_depend_on_declaration_order():
    challenge = '''objection challenge = [premises critique] -x> argument first_route
'''
    defence = '''objection defence = [evidence independent] -x> objection challenge
'''
    first, second = assess(BASE + challenge + defence), assess(BASE + defence + challenge)
    for section in ("claims", "arguments", "objections"):
        labels = lambda result: {name: entry["grounded_label"] for name, entry in result[section].items()}
        assert labels(first) == labels(second)


def test_reasoning_objection_only_attacks_applications_in_its_source_environment():
    source = BASE + '''environment peer {
  require "site" == "bench"
}

evidence peer_check {
  tool collector
  kind test
  environment peer
  max_age 60
  require "passed" == true
}

claim peer_claim {
  statement "Independent environmental application."
  environment peer
}

argument peer_route = [evidence peer_check] via authored => peer_claim

objection challenge = [evidence negative] -x> reasoning authored
'''
    result = assess(source)
    assert result["claims"]["foundation"]["status"] == "contested"
    assert result["claims"]["peer_claim"]["status"] == "supported"


def _custom_result(payload):
    return {"value": payload["origin"] + sum(payload["values"])}


def _method_contract():
    from eal.methods import MethodContract

    number = {"type": "number"}
    return MethodContract(
        identifier="review/sum/1", evidence_kind="sum_input",
        input_schema={"type": "object", "properties": {"origin": number,
                      "values": {"type": "array", "items": number}},
                      "required": ["origin", "values"], "additionalProperties": False},
        query_schema={"type": "object", "properties": {"origin": number},
                      "required": ["origin"], "additionalProperties": False},
        output_schema={"type": "object", "properties": {"value": number},
                       "required": ["value"], "additionalProperties": False},
        outputs={"value": "basis"}, quantities=("time",), exact_unit=True,
        implementation=_custom_result, implementation_version="review-1")


def test_custom_registration_cannot_replace_a_builtin_execution_profile():
    from eal.methods import default_registry

    registry = default_registry()
    original = registry.get("deductive/1").identifier
    with pytest.raises(ValueError):
        registry.with_method(replace(_method_contract(), builtin_mode="deductive"))
    assert registry.get("deductive/1").identifier == original


def test_registry_contracts_and_fingerprint_survive_caller_mutation():
    from eal.methods import default_registry

    supplied = _method_contract()
    registry = default_registry().with_method(supplied)
    fingerprint = registry.fingerprint
    supplied.query_schema["properties"].clear()
    retrieved = registry.get("review/sum/1")
    retrieved.outputs["value"] = "boolean"
    described = registry.describe()
    described["review/sum/1"]["quantities"].append("pressure")
    assert registry.fingerprint == fingerprint
    assert registry.get("review/sum/1").query_fields == ("origin",)
    assert registry.get("review/sum/1").output_type("value") == "basis"


def test_custom_numeric_contract_rejects_boolean_observations():
    from eal.methods import execute_extension

    result = execute_extension(_method_contract(), {"origin": 0, "values": [True]})
    assert result["status"] == "unsupported"
    assert result["details"] == {}


def test_custom_method_checks_question_identity_even_when_scalar_answer_is_unchanged():
    from eal.methods import default_registry

    source = '''language "EAL/2"

environment lab {
  require "site" == "bench"
}

tool collector {
  version "1"
}

evidence series {
  tool collector
  kind sum_input
  environment lab
  max_age 60
  require "schema" == "EAL/typed-input/1"
}

reasoning sum_method {
  method "review/sum/1"
  rationale "Apply the registered sum method."
}

claim timing {
  statement "The declared time statistic is 5 ms."
  environment lab
  proposition {
    subject "controller"
    quantity "time"
    unit "ms"
    scope "case-1"
    valid_from "2026-09-23T11:00:00Z"
    valid_until "2026-09-23T13:00:00Z"
    query {"origin": 0}
    result "value" == 5
  }
}

argument sum_route = [evidence series] via sum_method => timing binding series
'''
    registry = default_registry().with_method(_method_contract())
    envelope = {"schema": "EAL/typed-input/1", "method": "review/sum/1", "subject": "controller",
                "quantity": "time", "unit": "ms", "scope": "case-1",
                "valid_from": "2026-09-23T11:00:00Z", "valid_until": "2026-09-23T13:00:00Z",
                "payload": {"origin": 0, "values": [2, 3]}}
    supported = assess(source, values={"series": envelope}, registry=registry)
    assert supported["claims"]["timing"]["status"] == "supported"
    assert supported["method_registry_fingerprint"] == registry.fingerprint
    changed = {**envelope, "payload": {"origin": 100, "values": [-95]}}
    blocked = assess(source, values={"series": changed}, registry=registry)
    assert blocked["claims"]["timing"]["status"] == "unsupported"
    binding = blocked["arguments"]["sum_route"]["reasoning_result"]["binding"]
    assert any("query field 'origin'" in reason for reason in binding["reasons"])
