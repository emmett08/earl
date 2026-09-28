"""Claim packets preserve decisions and withhold raw acquisition data."""
from __future__ import annotations

import json

import pytest

from eal.packets import AssessmentPacketBuilder, PacketLimits


def _assessment():
    digest = "a" * 64
    secret = "Bearer SUPER_SECRET_TOOL_CREDENTIAL"
    return {
        "valid": True, "assessment_id": "assessment-123", "source_digest": digest,
        "context_fingerprint": digest, "method_registry_fingerprint": digest,
        "claims": {
            "pressure": {"status": "contested", "grounded_label": "undecided",
                         "supporting_arguments": [], "contested_arguments": ["experiment"],
                         "objections": ["sensor_fault"], "undecided_objections": [],
                         "proposition": {"unit": "kPa", "result": {
                             "path": "estimate", "operator": ">=", "expected": 2}}},
            "other": {"status": "supported", "supporting_arguments": ["other_argument"],
                      "contested_arguments": [], "objections": []},
        },
        "arguments": {
            "experiment": {"status": "contested", "conclusion": "pressure",
                           "attackers": ["objection:sensor_fault"],
                           "dependencies": {"evidence": ["trial"], "assumptions": ["calibration"],
                                            "premises": [], "reasoning": "causal_reason"},
                           "reasoning_result": {"status": "supported", "method": "causal/1",
                                                "evidence_id": "trial", "input_digest": digest,
                                                "details": {"estimate": 2.8, "standard_error": 0.2,
                                                            "assumptions_verified": False,
                                                            "raw_observation": secret,
                                                            "samples": list(range(10_000))},
                                                "binding": {"status": "supported", "evidence_id": "trial",
                                                            "actual": 2.8, "holds": True, "output_unit": "kPa",
                                                            "prose_verified": False,
                                                            "physical_interpretation_verified": False,
                                                            "formal_query": {"credential": secret}},
                                                "predicates": [{"holds": True, "reason": secret}]}},
            "other_argument": {"status": "supported", "conclusion": "other",
                               "dependencies": {"evidence": [], "assumptions": [], "premises": [],
                                                "reasoning": "structured_reason"},
                               "reasoning_result": {"status": "supported", "method": "structured/1",
                                                    "details": {"authored": True}}},
        },
        "assumptions": {"calibration": {"status": "contested", "validation": "calibration_check",
                                        "objection_statuses": {"calibration_fault": "active"}}},
        "objections": {
            "sensor_fault": {"status": "active", "target_kind": "argument", "target": "experiment",
                             "attackers": ["objection:counter_fault"], "evidence": ["sensor_log"],
                             "reasons": [secret]},
            "counter_fault": {"status": "defeated", "target_kind": "objection", "target": "sensor_fault",
                              "attackers": [], "evidence": []},
            "calibration_fault": {"status": "active", "target_kind": "assumption", "target": "calibration",
                                  "attackers": [], "evidence": []},
            "other_fault": {"status": "inactive", "target_kind": "claim", "target": "other",
                            "attackers": [], "evidence": []},
        },
        "evidence": {name: {"status": "available", "value": secret, "tool": "shell",
                            "reasons": [secret]} for name in
                     ("trial", "calibration_check", "sensor_log")},
        "collection": {"records": {"trial": {"value": secret}}},
    }


def test_packet_retains_method_binding_assumption_and_objection_status_without_tool_values():
    result = _assessment()
    result["objections"]["sensor_fault"]["premises"] = ["other"]
    result["arguments"]["other_argument"]["dependencies"]["evidence"] = ["other_probe"]
    result["evidence"]["other_probe"] = {"status": "available", "availability_issues": [],
                                          "run_id": "1dcb2b72-2ee2-45fb-a4e2-201010101010",
                                          "value": "Bearer SUPER_SECRET_TOOL_CREDENTIAL"}
    secret = "SUPER_SECRET_TOOL_CREDENTIAL"
    packet = AssessmentPacketBuilder().build(result, claims=["pressure"])
    claim = packet["claims"]["pressure"]
    method = packet["arguments"]["experiment"]["method_result"]
    assert packet["schema"] == "EAL/assessment-packet/1"
    assert packet["full_explanation"]["assessment_id"] == result["assessment_id"]
    assert claim["status"] == "contested"
    assert method["status"] == "supported" and method["evidence_id"] == "trial"
    assert method["outputs"] == {"estimate": 2.8, "standard_error": 0.2}
    assert method["binding"]["actual"] == 2.8 and method["binding"]["prose_verified"] is False
    assert method["assumptions_verified"] is False and method["require_holds"] == [True]
    assert packet["assumptions"]["calibration"]["status"] == "contested"
    assert packet["evidence"]["trial"] == {
        "status": "available", "availability_issues": [], "observation_id": None,
        "age_status": "unknown"}
    assert set(packet["objections"]) == {"sensor_fault", "counter_fault", "calibration_fault"}
    assert packet["premise_claims"]["other"]["status"] == "supported"
    assert {"evidence_id": "other_probe", "observation_id": "1dcb2b72-2ee2-45fb-a4e2-201010101010"} in (
        packet["claims"]["pressure"]["observation_ids"])
    assert packet["evidence"]["other_probe"]["status"] == "available"
    assert packet["omitted"]["objection_premise_routes"] == 1
    assert "other_argument" not in packet["arguments"] and "other_fault" not in packet["objections"]
    assert secret not in json.dumps(packet)


def test_output_is_bounded_and_oversize_summary_names_authoritative_explanation():
    result = _assessment()
    result["arguments"]["experiment"]["reasoning_result"]["details"]["tokens"] = ["raw"] * 100_000
    requested = ["pressure"]
    for index in range(15):
        name = f"additional_claim_{index:02}"
        requested.append(name)
        argument = f"additional_argument_{index:02}"
        result["claims"][name] = {"status": "supported", "supporting_arguments": [argument],
                                  "contested_arguments": [], "objections": []}
        result["arguments"][argument] = {
            "status": "supported", "conclusion": name,
            "dependencies": {"evidence": [], "assumptions": [], "premises": [],
                             "reasoning": "authored_reason"},
            "reasoning_result": {"status": "supported", "method": "structured/1",
                                 "details": {"authored": True, "mechanically_proved": False}},
        }
    packet = AssessmentPacketBuilder(limits=PacketLimits(max_bytes=4096)).build(result, claims=requested)
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode()) <= 4096
    assert packet["claims"]["pressure"]["status"] == "contested"
    assert packet["full_explanation"]["assessment_id"] == "assessment-123"
    assert packet["summary_complete"] is False
    assert packet["omitted"]["details"] == "packet_byte_limit"
    assert "raw" not in json.dumps(packet)


def test_premise_routes_and_installed_method_contract_are_preserved():
    result = _assessment()
    result["claims"]["calibration_claim"] = {"status": "supported", "supporting_arguments": ["calibration_argument"],
                                               "contested_arguments": [], "objections": []}
    result["arguments"]["experiment"]["dependencies"]["premises"] = ["calibration_claim"]
    result["arguments"]["calibration_argument"] = {
        "status": "supported", "conclusion": "calibration_claim", "attackers": [],
        "dependencies": {"premises": [], "evidence": ["calibration_check"], "assumptions": [],
                         "reasoning": "calibration_reason"},
        "reasoning_result": {"status": "supported", "method": "engineering/rms/1",
                             "evidence_id": "calibration_check",
                             "details": {"rms": 0.2, "secret": "Bearer hidden", "raw": [1, 2, 3]}},
    }

    class Registry:
        def get(self, method):
            return type("Contract", (), {"outputs": {"rms": "basis"}})() if method == "engineering/rms/1" else None

    packet = AssessmentPacketBuilder(method_registry=Registry()).build(result, claims=["pressure"])
    assert packet["premise_claims"]["calibration_claim"]["status"] == "supported"
    assert packet["arguments"]["calibration_argument"]["method_result"]["outputs"] == {"rms": 0.2}
    assert "hidden" not in json.dumps(packet)


def test_real_evaluator_packet_retains_premise_and_typed_method_decision():
    from eal.evaluator import evaluate
    from eal.parser import parse
    from test_eal2_runtime import CONTEXT, NOW, SOURCE, records_for

    programme = parse(SOURCE)
    assessed = evaluate(programme, records_for(programme), now=NOW, context=CONTEXT)
    packet = AssessmentPacketBuilder().build({"assessment_id": "checked-assessment", **assessed},
                                              claims=["outcome"])
    assert packet["claims"]["outcome"]["status"] == "supported"
    assert packet["premise_claims"]["increase"]["status"] == "supported"
    assert packet["arguments"]["measured"]["method_result"]["binding"]["actual"] == 7.5
    assert packet["arguments"]["measured"]["method_result"]["outputs"]["estimate"] == 7500


@pytest.mark.parametrize("case,expected_issue,expected_age", [
    ("predicate", "predicate_not_met", "within_max_age"),
    ("stale", "stale_observation", "stale"),
    ("error", "tool_error", "no_observation"),
    ("missing", "missing_observation", "unknown"),
])
def test_stored_observation_identity_and_availability_distinguish_failure_modes(
        case, expected_issue, expected_age):
    from eal.evaluator import canonical_digest, evaluate
    from eal.parser import parse
    from test_evaluator import CONTEXT, NOW, SOURCE, record

    programme = parse(SOURCE)
    secret = "Bearer secret-from-collector"
    value = {"passed": case != "predicate", "opaque_token": secret}
    observation = record(programme, "observed", value,
                         collected_at="2026-09-23T11:58:59Z" if case == "stale" else NOW)
    observation["run_id"] = "9d71c0a2-1010-4a4a-8787-0123456789ab"
    if case == "error":
        observation["status"] = "error"
        observation["error"] = {"message": secret}
    records = {} if case == "missing" else {"observed": observation}
    assessment_id = "8aa32f00-0000-4000-8000-000000000000"
    collection_id = "7bc32f00-0000-4000-8000-000000000000"
    assessment = {"assessment_id": assessment_id, "collection_id": collection_id,
                  **evaluate(programme, records, now=NOW, context=CONTEXT)}
    collection = {"collection_id": collection_id, "source_digest": programme.source_digest,
                  "context": CONTEXT, "records": records}
    assert assessment["context_fingerprint"] == canonical_digest(CONTEXT)
    packet = AssessmentPacketBuilder().build(assessment, claims=["downstream"], collection=collection)
    measured = packet["evidence"]["observed"]
    assert measured["status"] == "unavailable"
    assert measured["availability_issues"] == [expected_issue]
    assert measured["age_status"] == expected_age
    expected_id = None if case == "missing" else observation["run_id"]
    assert measured["observation_id"] == expected_id
    assert packet["claims"]["downstream"]["observation_ids"] == [
        {"evidence_id": "observed", "observation_id": expected_id}]
    if case == "stale":
        assert measured["age_seconds"] == 61
        assert measured["observed_at"] == "2026-09-23T11:58:59Z"
    if case == "error":
        assert measured["attempted_at"] == NOW
        assert "observed_at" not in measured and "age_seconds" not in measured
    assert secret not in json.dumps(packet)


def test_collection_identity_and_issue_omission_fail_closed():
    from eal.evaluator import evaluate
    from eal.parser import parse
    from test_evaluator import CONTEXT, NOW, SOURCE, record

    programme = parse(SOURCE)
    observation = record(programme, "observed", {"passed": True},
                         collected_at="2026-09-23T11:58:59Z")
    observation["status"] = "error"
    collection_id = "2d00e23f-0000-4000-8000-000000000000"
    assessment = {"assessment_id": "stored", "collection_id": collection_id,
                  **evaluate(programme, {"observed": observation}, now=NOW, context=CONTEXT)}
    collection = {"collection_id": collection_id, "source_digest": programme.source_digest,
                  "context": CONTEXT, "records": {"observed": observation}}
    packet = AssessmentPacketBuilder(limits=PacketLimits(max_availability_issues=1)).build(
        assessment, claims=["working"], collection=collection)
    assert packet["evidence"]["observed"]["availability_issues"] == ["stale_observation"]
    assert packet["evidence"]["observed"]["age_status"] == "no_observation"
    assert packet["omitted"]["availability_issues"] == 1
    assert packet["summary_complete"] is False

    with pytest.raises(ValueError, match="Collection ID differs"):
        AssessmentPacketBuilder().build(assessment, claims=["working"],
                                        collection={**collection, "collection_id": "other"})
    with pytest.raises(ValueError, match="Collection context differs"):
        AssessmentPacketBuilder().build(assessment, claims=["working"],
                                        collection={**collection, "context": {"site": "other"}})
    changed = {**observation, "run_id": "other"}
    with pytest.raises(ValueError, match="Observation ID differs"):
        AssessmentPacketBuilder().build(assessment, claims=["working"],
                                        collection={**collection, "records": {"observed": changed}})
