"""Independent comparator properties on selected synthetic records."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from benchmarks.equal_checker import (
    CheckerInputError,
    evidence_for_state,
    evaluate,
    graph_for_root,
    parity_suite,
)


COHORT = Path(__file__).resolve().parents[1] / "benchmarks/experiments/cross-model-delivery"


def test_selected_pilot_and_new_cohort_match_fixed_oracles_and_tamper_gate():
    for fixtures, cases, mutations, additional in (
        (None, 12, 60, 0), (COHORT, 9, 45, 5)
    ):
        report = parity_suite() if fixtures is None else parity_suite(fixtures)
        assert (report["parity"], report["cases_total"]) == (cases, cases)
        assert (report["tamper_pass"], report["tamper_total"]) == (mutations, mutations)
        assert (report["fixture_tamper_pass"], report["fixture_tamper_total"]) == (
            additional, additional)
        assert report["passed"]
        assert len({entry["source_sha256"] for entry in report["cases"]}) == (
            4 if fixtures is None else 3)
        assert all(entry["graph_sha256"] and entry["evidence_sha256"]
                   for entry in report["cases"])


def test_negative_finding_needs_each_distinct_position():
    graph = graph_for_root("loop_preconditions")
    complete = evidence_for_state("loop_preconditions", "complete_inspection")
    incomplete = evidence_for_state("loop_preconditions", "partial_inspection")
    now = "2026-09-24T12:00:00Z"
    assert evaluate(graph, complete, now).status == "supported"
    result = evaluate(graph, incomplete, now)
    assert result.status == "unsupported"
    assert any(check["op"] == "has_keys_equal" and not check["ok"]
               for check in result.trace["routes"][0]["checks"])


def test_matching_positive_route_and_objection_response_transitions():
    graph = graph_for_root("network_failover")
    now = "2026-09-24T12:00:00Z"
    assert evaluate(graph, evidence_for_state("network_failover", "qualifying_test", COHORT),
                    now).status == "supported"
    challenged = evaluate(graph, evidence_for_state("network_failover", "buffer_challenge", COHORT), now)
    assert challenged.status == "contested"
    assert challenged.trace["objections"][0]["active"]
    assert not challenged.trace["objections"][0]["answered"]
    answered = evaluate(graph, evidence_for_state("network_failover", "separate_trace", COHORT), now)
    assert answered.status == "supported"
    assert answered.trace["objections"][0]["answered"]
    unrelated = evidence_for_state("network_failover", "separate_trace", COHORT)
    unrelated["packet_trace_reader"]["value"]["profile"] = "other_profile"
    assert evaluate(graph, unrelated, now).status == "contested"
    optional_alert_missing = evidence_for_state("network_failover", "buffer_challenge", COHORT)
    del optional_alert_missing["buffer_alert_reader"]
    assert evaluate(graph, optional_alert_missing, now).status == "supported"
    stale_alert = evidence_for_state("network_failover", "buffer_challenge", COHORT)
    stale_alert["buffer_alert_reader"]["observed_at"] = "2026-09-24T11:29:59Z"
    assert evaluate(graph, stale_alert, now).status == "supported"
    stale_answer = evidence_for_state("network_failover", "separate_trace", COHORT)
    stale_answer["packet_trace_reader"]["observed_at"] = "2026-09-24T11:29:59Z"
    assert evaluate(graph, stale_answer, now).status == "contested"


def test_alternative_positive_route_is_independently_sufficient():
    graph = graph_for_root("asset_direction")
    graph["routes"].append({"id": "alternative_current_record", "all": [
        {"op": "eq", "record": "probe_reader", "path": ["value", "unit"], "value": "AH-74"},
        {"op": "is_true", "record": "probe_reader", "path": ["value", "pass"]},
    ]})
    evidence = evidence_for_state("asset_direction", "different_unit")
    result = evaluate(graph, evidence, "2026-09-24T12:00:00Z")
    assert result.status == "supported"
    assert [route["ok"] for route in result.trace["routes"]] == [False, True]


def test_typed_scope_time_and_boolean_validation_fail_closed():
    graph = graph_for_root("loop_preconditions")
    evidence = evidence_for_state("loop_preconditions", "complete_inspection")
    now = "2026-09-24T12:00:00Z"
    tampered = copy.deepcopy(evidence)
    tampered["wiring_reader"]["value"]["checked_connectors"] = True
    assert evaluate(graph, tampered, now).status == "unsupported"
    tampered = copy.deepcopy(evidence)
    tampered["wiring_reader"]["request"]["context"] = {"loop": "HL-5", "run": "Q18"}
    assert "context" in evaluate(graph, tampered, now).trace["reason"]
    tampered = copy.deepcopy(evidence)
    tampered["wiring_reader"]["observed_at"] = "2026-09-24T10:59:59Z"
    assert evaluate(graph, tampered, now).status == "unsupported"
    with pytest.raises(CheckerInputError, match="time-zone"):
        evaluate(graph, evidence, "2026-09-24T12:00:00")


def test_nested_boolean_cannot_spoof_numeric_acquisition_input():
    graph = graph_for_root("thermal_soak")
    evidence = evidence_for_state("thermal_soak", "recent_qualifying", COHORT)
    graph["evidence"]["soak_reader"]["input"] = {"run": {"attempt": 1, "flags": [False]}}
    evidence["soak_reader"]["request"]["input"] = {
        "run": {"attempt": 1, "flags": [False]}}
    now = "2026-09-24T12:00:00Z"
    assert evaluate(graph, evidence, now).status == "supported"
    tampered = copy.deepcopy(evidence)
    tampered["soak_reader"]["request"]["input"]["run"]["attempt"] = True
    result = evaluate(graph, tampered, now)
    assert result.status == "unsupported"
    assert "request mismatch" in result.trace["evidence"][0]["reason"]
    tampered = copy.deepcopy(evidence)
    tampered["soak_reader"]["request"]["input"]["run"]["flags"][0] = 0
    assert evaluate(graph, tampered, now).status == "unsupported"


def test_unrecognised_reasoning_operation_is_not_silently_ignored():
    graph = graph_for_root("asset_direction")
    graph["routes"][0]["all"].append({"op": "external_eal_method", "record": "probe_reader"})
    with pytest.raises(CheckerInputError, match="unsupported predicate"):
        evaluate(graph, evidence_for_state("asset_direction", "matching_record"),
                 "2026-09-24T12:00:00Z")
