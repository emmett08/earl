"""The answer adapter preserves evidence while repairing operation syntax."""

from copy import deepcopy
import json

import jsonschema
import pytest

from experiments.api_load_test.conversation import (
    ConversationError, finish_answer, prepare_packet, repair_feedback,
)
from experiments.api_load_test.materials import finish_schema, operations


@pytest.fixture
def case():
    return {"target": {"input": {"service": "orders-api", "build_id": "build-a",
                                "run_id": "run-a", "concurrent_clients": 5}}}


@pytest.fixture
def packet():
    return {"report_id": "report-a", "metrics": {
        "request_count": 100, "p95_ms": 220.5, "error_rate_percent": 0.0},
        "status": "unsupported", "failed_checks": ["latency"], "unknown_checks": []}


def test_checked_template_is_valid_and_binds_context_without_narrative(case, packet):
    original = deepcopy(packet)
    prepared = prepare_packet(packet, case, "eal_mcp")
    contract = prepared["answer_contract"]
    assert contract["missing_fields"] == []
    answer = finish_answer(contract["finish_template"], packet, case)
    assert answer == {**original, "scope": case["target"]["input"], "explanation": ""}
    assert packet == original
    contract["finish_template"]["failed_checks"].clear()
    assert packet["failed_checks"] == ["latency"]


@pytest.mark.parametrize("arm", ["json_prompt", "plain_brief", "plain_explicit", "plain_review"])
def test_measurement_template_requires_model_decision_without_leaking_checker(case, packet, arm):
    raw = {key: value for key, value in packet.items()
           if key not in {"status", "failed_checks", "unknown_checks"}}
    contract = prepare_packet(raw, case, arm)["answer_contract"]
    assert contract["missing_fields"] == ["status", "failed_checks", "unknown_checks"]
    assert contract["finish_template"] == {"operation": "finish", "metrics": raw["metrics"]}
    with pytest.raises(jsonschema.ValidationError):
        finish_answer(contract["finish_template"], raw, case)
    with pytest.raises(ValueError, match="contains checked decision fields"):
        prepare_packet(packet, case, arm)


def test_plain_validator_receives_same_checked_template(case, packet):
    assert prepare_packet(packet, case, "plain_validator") == prepare_packet(packet, case, "eal_mcp")


@pytest.mark.parametrize("field,value", [
    ("report_id", "older-report"),
    ("scope", {"service": "orders-api", "build_id": "other-build", "run_id": "run-a",
               "concurrent_clients": 5}),
])
def test_explicit_context_conflicts_are_rejected(case, packet, field, value):
    operation = prepare_packet(packet, case, "eal_mcp")["answer_contract"]["finish_template"]
    operation[field] = value
    with pytest.raises(ConversationError) as caught:
        finish_answer(operation, packet, case)
    feedback = repair_feedback(caught.value, operations("eal_mcp"), packet, case, "eal_mcp", operation)
    assert feedback["fields"] == [field]
    assert operation[field] == value


def test_explicit_matching_context_and_explanation_are_retained(case, packet):
    operation = {"operation": "finish", **packet, "scope": deepcopy(case["target"]["input"]),
                 "explanation": "The measured latency exceeds 200 ms."}
    assert finish_answer(operation, packet, case) == {key: value for key, value in operation.items()
                                                    if key != "operation"}


def test_missing_operation_is_diagnosed_and_never_inferred(case, packet):
    with pytest.raises(jsonschema.ValidationError):
        finish_answer(packet, packet, case)
    feedback = repair_feedback(ValueError("Unknown operation"), operations("eal_mcp"),
                               packet, case, "eal_mcp", packet)
    assert feedback["fields"] == ["operation"]
    assert feedback["error"] == "operation_protocol"
    assert feedback["evidence_changed"] is False
    assert feedback["answer_contract"]["finish_template"]["metrics"] == packet["metrics"]
    assert "not the report" in feedback["instruction"]


def test_repair_lists_all_missing_fields_without_inventing_unknown_measurements(case, packet):
    operation = {"operation": "finish", "metrics": packet["metrics"]}
    with pytest.raises(jsonschema.ValidationError) as caught:
        jsonschema.validate(operation, finish_schema())
    raw = {"report_id": packet["report_id"], "metrics": packet["metrics"]}
    feedback = repair_feedback(caught.value, operations("plain_brief"), raw, case, "plain_brief", operation)
    assert feedback["fields"] == ["status", "failed_checks", "unknown_checks"]
    assert "unknown_checks" not in feedback["answer_contract"]["finish_template"]
    assert feedback["answer_contract"]["finish_template"]["metrics"]["p95_ms"] == 220.5


def test_null_measurements_remain_evidence_values_and_null_scope_is_invalid(case, packet):
    packet.update(metrics={key: None for key in packet["metrics"]}, status="unavailable",
                  failed_checks=["report_valid"], unknown_checks=["latency"])
    operation = prepare_packet(packet, case, "plain_validator")["answer_contract"]["finish_template"]
    assert finish_answer(operation, packet, case)["metrics"] == packet["metrics"]
    operation["scope"] = None
    with pytest.raises(jsonschema.ValidationError) as caught:
        finish_answer(operation, packet, case)
    feedback = repair_feedback(caught.value, operations("plain_validator"), packet, case,
                               "plain_validator", operation)
    assert feedback["fields"] == ["scope"]
    assert feedback["answer_contract"]["finish_template"]["status"] == "unavailable"


def test_finish_requires_inspection_and_preinspection_feedback_supplies_no_evidence(case, packet):
    operation = prepare_packet(packet, case, "eal_mcp")["answer_contract"]["finish_template"]
    with pytest.raises(ConversationError, match="Inspect a report") as caught:
        finish_answer(operation, None, case)
    feedback = repair_feedback(caught.value, operations("eal_mcp"), None, case, "eal_mcp", operation)
    assert feedback["answer_contract"]["operation_template"] == {"operation": "assess_load_test"}
    assert "finish_template" not in feedback["answer_contract"]


def test_json_syntax_error_does_not_become_a_measurement_failure(case, packet):
    with pytest.raises(json.JSONDecodeError) as caught:
        json.loads('{"operation":')
    feedback = repair_feedback(caught.value, operations("eal_mcp"), packet, case, "eal_mcp")
    assert feedback["fields"] == []
    assert "valid JSON" in feedback["message"]
    assert feedback["answer_contract"]["finish_template"]["failed_checks"] == ["latency"]


def test_nested_missing_fields_are_named(case, packet):
    operation = prepare_packet(packet, case, "eal_mcp")["answer_contract"]["finish_template"]
    operation["metrics"] = {"request_count": 100}
    with pytest.raises(jsonschema.ValidationError) as caught:
        finish_answer(operation, packet, case)
    feedback = repair_feedback(caught.value, operations("eal_mcp"), packet, case, "eal_mcp", operation)
    assert feedback["fields"] == ["metrics.p95_ms", "metrics.error_rate_percent"]


def test_native_checked_template_has_function_name_and_only_function_arguments(case, packet):
    prepared = prepare_packet(packet, case, "eal_mcp", native_tools=True)
    contract = prepared["answer_contract"]
    template = contract["finish_template"]
    assert template["name"] == "finish"
    assert "operation" not in template["arguments"]
    assert set(template["arguments"]) == {"metrics", "status", "failed_checks", "unknown_checks"}
    assert "do not put operation in the arguments" in contract["instruction"]
    # The provider supplies this internal envelope after parsing a native call.
    internal = {"operation": template["name"], **template["arguments"]}
    assert finish_answer(internal, packet, case)["status"] == "unsupported"


def test_native_repair_template_preserves_measurement_only_boundary(case, packet):
    raw = {"report_id": packet["report_id"], "metrics": packet["metrics"]}
    operation = {"operation": "finish", "metrics": raw["metrics"]}
    with pytest.raises(jsonschema.ValidationError) as caught:
        finish_answer(operation, raw, case)
    feedback = repair_feedback(caught.value, operations("plain_brief"), raw, case,
                               "plain_brief", operation, native_tools=True)
    template = feedback["answer_contract"]["finish_template"]
    assert template == {"name": "finish", "arguments": {"metrics": raw["metrics"]}}
    assert feedback["fields"] == ["status", "failed_checks", "unknown_checks"]


def test_native_preinspection_guidance_never_supplies_an_operation_argument(case):
    feedback = repair_feedback(ConversationError("Inspect a report before finishing."),
                               operations("eal_mcp"), None, case, "eal_mcp", native_tools=True)
    contract = feedback["answer_contract"]
    assert contract["operation_template"] == {"name": "assess_load_test", "arguments": {}}
    assert contract["missing_fields"] == ["report_id"]
    assert contract["instruction"].startswith("Call the named function")
