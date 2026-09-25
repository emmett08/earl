"""Synthetic, labelled controls for independent v3 adjudication and reporting."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from experiments.api_load_test.analysis import markdown, summarise
from experiments.api_load_test.oracle import grade, packet_reference_check, reference, reference_report


def measured_case(count=100):
    """Synthetic boundary fixture, never represented as a live case."""
    workload = {"service": "orders-api", "build_id": "build-a", "run_id": "run-a",
                "concurrent_clients": 5, "request_count": count, "timeout_seconds": 3}
    context = {"service": "orders-api", "build_id": "build-a", "run_id": "run-a",
               "dataset": "measured_controlled_api"}
    rows = [{"request_id": i, "elapsed_ms": 200, "status_code": 500 if i == 99 else 200,
             "identity_matches": True, "error": None,
             "response_identity": {"header_build_id": "build-a", "header_run_id": "run-a",
                                   "body_build_id": "build-a", "body_run_id": "run-a",
                                   "body_request_id": i, "total_pence": 748}}
            for i in range(count)]
    report = {"schema": "eal-live-api-report/2", "dataset": "measured_controlled_api",
              "input": copy.deepcopy(workload), "context": copy.deepcopy(context),
              "requests": rows, "observed_at": "2026-09-25T12:00:00Z"}
    return {"id": "synthetic-case", "target": {"input": workload, "context": context},
            "assessment_time": "2026-09-25T12:05:00Z", "expected_report_id": "target-report",
            "reports": {"target-report": report}}


def correct_answer(truth):
    return {key: copy.deepcopy(truth[key]) for key in
            ("report_id", "status", "scope", "metrics", "failed_checks", "unknown_checks")}


def test_inclusive_raw_boundaries_and_summary_cannot_override_measurements():
    case = measured_case()
    assert reference(case)["status"] == "supported"
    report = case["reports"]["target-report"]
    report["claimed_summary"] = "FAILED: never release this API"
    assert reference(case)["status"] == "supported"
    report["requests"][0]["status_code"] = 503
    report["claimed_summary"] = "PASS: all criteria met"
    truth = reference(case)
    assert truth["status"] == "unsupported" and truth["failed_checks"] == ["errors"]
    assert truth["metrics"]["error_rate_percent"] == 2


def test_nearest_rank_includes_every_attempt_and_transport_failure():
    case = measured_case()
    report = case["reports"]["target-report"]
    for row in report["requests"][:5]:
        row["elapsed_ms"] = 250
    assert reference(case)["metrics"]["p95_ms"] == 200
    report["requests"][5]["elapsed_ms"] = 250
    assert reference(case)["failed_checks"] == ["latency"]
    report["requests"][0]["status_code"] = 0
    assert reference(case)["failed_checks"] == ["latency", "errors"]


@pytest.mark.parametrize("fault,failed", [
    ("stale", ["freshness"]), ("future", ["freshness"]),
    ("identity", ["identity"]), ("incomplete", ["completeness", "sample_size"]),
    ("conflict", ["completeness", "consistency"]),
])
def test_availability_failures_retain_actual_numeric_diagnostics(fault, failed):
    case = measured_case()
    report = case["reports"]["target-report"]
    if fault == "stale":
        case["assessment_time"] = "2026-09-25T12:05:01Z"
    elif fault == "future":
        case["assessment_time"] = "2026-09-25T11:59:59Z"
    elif fault == "identity":
        report["requests"][0]["response_identity"]["header_build_id"] = "other-build"
        assert report["requests"][0]["identity_matches"] is True
    elif fault == "incomplete":
        report["requests"].pop()
    else:
        duplicate = copy.deepcopy(report["requests"][99])
        duplicate["status_code"] = 200
        report["requests"].append(duplicate)
    truth = reference(case)
    assert truth["status"] == "unavailable"
    assert truth["failed_checks"] == failed
    assert truth["unknown_checks"] == []
    assert truth["metrics"]["p95_ms"] == 200


def test_complete_but_undersized_run_is_performance_unsupported():
    truth = reference(measured_case(80))
    assert truth["status"] == "unsupported"
    assert truth["failed_checks"] == ["sample_size"]


@pytest.mark.parametrize("field,value", [("elapsed_ms", "missing"), ("elapsed_ms", float("nan")),
                                         ("elapsed_ms", -1), ("status_code", "200"),
                                         ("identity_matches", "true")])
def test_malformed_measurements_are_unavailable_with_null_metrics(field, value):
    case = measured_case()
    case["reports"]["target-report"]["requests"][0][field] = value
    truth = reference(case)
    assert truth["status"] == "unavailable"
    assert truth["failed_checks"] == ["report_valid"]
    assert set(truth["unknown_checks"]) == {
        "identity", "completeness", "freshness", "sample_size", "latency", "errors", "consistency"}
    assert truth["metrics"] == {"request_count": None, "p95_ms": None, "error_rate_percent": None}


def test_reference_checks_selected_distractor_against_target():
    case = measured_case()
    case["reports"]["other"] = copy.deepcopy(case["reports"]["target-report"])
    case["reports"]["other"]["input"]["run_id"] = "other-run"
    assert reference_report(case, "other")["status"] == "unavailable"
    assert reference(case)["status"] == "supported"
    assert reference_report(case, "absent")["failed_checks"] == ["report_valid"]


def test_grade_requires_inspection_selection_scope_all_failures_and_metrics():
    case = measured_case()
    truth = reference(case)
    answer = correct_answer(truth)
    score = lambda value, **kwargs: grade(value, truth, collected=True,
                                          inspected_report_ids={"target-report"}, **kwargs)
    assert score(answer)["correct"] is True
    assert grade(answer, truth, collected=True, inspected_report_ids={"other"})["correct"] is False
    assert grade(answer, truth, collected=False, inspected_report_ids={"target-report"})["correct"] is False
    for key, changed in (("report_id", "other"), ("scope", {**answer["scope"], "build_id": "other"}),
                         ("failed_checks", ["errors"]), ("unknown_checks", ["errors"]),
                         ("metrics", {**answer["metrics"], "p95_ms": 0})):
        assert score({**answer, key: changed})["correct"] is False
    assert score({**answer, "status": "unsupported"})["false_rejection"] is True
    assert score({**answer, "status": "unavailable"})["false_unavailable"] is True


def test_correct_abstention_requires_evidence_and_matches_core_unsupported_state():
    case = measured_case()
    case["assessment_time"] = "2026-09-25T12:05:01Z"
    truth = reference(case)
    answer = correct_answer(truth)
    outcome = grade(answer, truth, collected=True, inspected_report_ids={"target-report"}, host_status="unsupported")
    assert outcome["correct"] and outcome["correct_unavailable"] and outcome["host_agrees_with_reference"]
    assert grade({**answer, "status": "supported"}, truth, collected=False)["false_support"]
    assert not grade(answer, truth, collected=False)["correct_unavailable"]


def test_unassessable_conditions_cannot_be_scored_as_failed_conditions():
    case = measured_case()
    case["reports"]["target-report"]["requests"][0]["elapsed_ms"] = "missing"
    truth = reference(case)
    answer = correct_answer(truth)
    score = lambda value: grade(value, truth, collected=True, inspected_report_ids={"target-report"})
    assert score(answer)["correct"]
    confused = {**answer, "failed_checks": answer["failed_checks"] + answer["unknown_checks"],
                "unknown_checks": []}
    outcome = score(confused)
    assert outcome["status_correct"] and not outcome["correct"]
    assert not outcome["failed_checks_correct"] and not outcome["unknown_checks_correct"]
    omitted = {key: value for key, value in answer.items() if key != "unknown_checks"}
    assert not score(omitted)["unknown_checks_correct"]


def reference_packet(case):
    """Synthetic packet control; no collector or executable checker is involved."""
    truth = reference(case)
    checks = truth["checks"]
    return {"report_id": truth["report_id"], "metrics": copy.deepcopy(truth["metrics"]),
            "measurement_facts": {"report_valid": checks["report_valid"],
                                  "identity_matches": checks["identity"],
                                  "complete_records": checks["completeness"],
                                  "consistent_records": checks["consistency"],
                                  "age_seconds": 300 if checks["report_valid"] else None}}


@pytest.mark.parametrize("corruption,field", [
    (lambda packet: packet["metrics"].update(p95_ms=150), "metrics"),
    (lambda packet: packet["measurement_facts"].update(identity_matches=False), "measurement_facts"),
    (lambda packet: packet["measurement_facts"].update(age_seconds=0), "measurement_facts"),
    (lambda packet: packet.update(report_id="wrong-report"), "report_id"),
])
def test_private_reference_checks_measurement_only_packets(corruption, field):
    case = measured_case()
    packet = reference_packet(case)
    before = copy.deepcopy(packet)
    assert packet_reference_check(case, "target-report", packet)["agrees"]
    assert packet == before and "status" not in packet
    corruption(packet)
    result = packet_reference_check(case, "target-report", packet)
    assert not result["agrees"] and result["mismatches"] == [field]


def test_private_reference_checks_malformed_facts_and_checked_decisions():
    case = measured_case()
    case["reports"]["target-report"]["requests"][0]["elapsed_ms"] = "missing"
    truth = reference(case)
    packet = reference_packet(case)
    assert packet_reference_check(case, "target-report", packet)["agrees"]
    missing_decision = packet_reference_check(case, "target-report", packet, checked=True)
    assert set(missing_decision["mismatches"]) == {"status", "failed_checks", "unknown_checks"}
    packet.update({key: truth[key] for key in ("status", "failed_checks", "unknown_checks")})
    assert packet_reference_check(case, "target-report", packet, host_status="unsupported")["agrees"]
    packet["unknown_checks"] = []
    result = packet_reference_check(case, "target-report", packet, host_status="supported")
    assert set(result["mismatches"]) == {"unknown_checks", "host_status"}


def write_run(tmp_path, *, transports=("text",), repeats=1, arms=("eal_mcp", "json_prompt")):
    assignments = []
    case_hashes = {}
    for index in range(4):
        case = {"id": f"case-{index}", "synthetic_analysis_control": True}
        case_hashes[case["id"]] = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()
        directory = tmp_path / "cases" / case["id"]
        directory.mkdir(parents=True)
        (directory / "case.json").write_text(json.dumps(case))
    (tmp_path / "case-manifest.json").write_text(json.dumps({"schema": "eal-api-case-freeze/2", "cases": case_hashes}))
    for transport in transports:
        for repeat in range(repeats):
            for index in range(4):
                for arm in arms:
                    assignment = {"id": f"{transport}-{repeat}-{index}-{arm}", "model": "synthetic-model",
                                  "arm": arm, "case_id": f"case-{index}", "case_family": "synthetic",
                                  "repeat": repeat, "block": f"{repeat}:{index}", "transport": transport}
                    assignments.append(assignment)
                    # Rows cover each paired 2x2 cell exactly once.
                    correct = ((index in (0, 1)) if arm in ("eal_mcp", "plain_validator") else (index in (0, 2)))
                    directory = tmp_path / "trials" / assignment["id"]
                    directory.mkdir(parents=True)
                    (directory / "trial.json").write_text(json.dumps({**assignment, "state": "complete",
                        "case_sha256": case_hashes[assignment["case_id"]],
                        "outcome": {"correct": correct}, "model_calls": []}))
    manifest = {"schema": "eal-api-experiment-run/4", "mode": "pilot", "transport": "text", "finalisation": "model",
                "models": [{"id": "synthetic-model"}], "assignments": assignments,
                "plan": {"arms": list(arms), "scope": "Synthetic analysis control"}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_paired_report_counts_discordances_without_claiming_equivalence(tmp_path):
    write_run(tmp_path)
    result = summarise(tmp_path)
    comparison = result["contrasts"][0]
    assert comparison["paired_cases"] == comparison["paired_blocks"] == comparison["paired_completed"] == 4
    assert comparison["both_correct"] == comparison["both_incorrect"] == 1
    assert comparison["reference_arm"] == "eal_mcp" and comparison["comparator"] == "json_prompt"
    assert comparison["reference_only_correct"] == comparison["comparator_only_correct"] == 1
    assert comparison["accuracy_difference"] == 0
    assert comparison["interpretation"] == "development_suite_descriptive"
    text = markdown(result)
    assert "Insufficient blocks" not in text and "does not establish equivalence" in text
    assert "interval" not in comparison


def test_ordinary_validator_adds_paired_explicit_prose_control(tmp_path):
    write_run(tmp_path, arms=("eal_mcp", "json_prompt", "plain_explicit", "plain_validator"))
    result = summarise(tmp_path)
    comparisons = {(row["reference_arm"], row["comparator"]): row for row in result["contrasts"]}
    assert set(comparisons) == {
        ("eal_mcp", "json_prompt"), ("eal_mcp", "plain_explicit"),
        ("eal_mcp", "plain_validator"), ("plain_validator", "plain_explicit")}
    validator = comparisons["plain_validator", "plain_explicit"]
    assert validator["paired_completed"] == validator["paired_cases"] == 4
    assert validator["reference_only_correct"] == validator["comparator_only_correct"] == 1
    assert validator["both_correct"] == validator["both_incorrect"] == 1
    assert validator["accuracy_difference"] == 0
    assert comparisons["eal_mcp", "plain_validator"]["both_correct"] == 2
    text = markdown(result)
    assert "| plain_validator | plain_explicit |" in text
    assert text.index("## Assignment completion") < text.index("## Assigned-answer scores")


def test_calibration_has_only_selected_comparisons(tmp_path):
    write_run(tmp_path, arms=("eal_mcp", "json_prompt", "plain_validator"))
    result = summarise(tmp_path)
    assert {(row["reference_arm"], row["comparator"]) for row in result["contrasts"]} == {
        ("eal_mcp", "json_prompt"), ("eal_mcp", "plain_validator")}


def test_earlier_contract_remains_separate_from_v4_analysis(tmp_path):
    manifest = write_run(tmp_path)
    manifest["schema"] = "eal-api-experiment-run/2"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="requires a v4 manifest"):
        summarise(tmp_path)


def test_failed_and_missing_assignments_remain_in_the_operational_denominator(tmp_path):
    manifest = write_run(tmp_path)
    failed = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    record = json.loads(failed.read_text())
    record["state"] = "failed"  # Even an inconsistent retained success must score zero.
    record["failure"] = "output_truncated"
    record["model_calls"] = [{"error": "Response incomplete", "category": "output_truncated",
                             "estimated_usd": 0.02, "response": {"input_tokens": 100,
                             "output_tokens": 4096, "metadata": {"reasoning_tokens": 4096}}}]
    failed.write_text(json.dumps(record))
    (tmp_path / "trials" / manifest["assignments"][1]["id"] / "trial.json").unlink()
    result = summarise(tmp_path)
    assert result["assigned"] == 8 and not result["complete"]
    assert result["completed"] == 6 and result["failed"] == result["not_attempted"] == 1
    cells = {row["arm"]: row for row in result["cells"]}
    assert cells["eal_mcp"]["failed"] == 1 and cells["eal_mcp"]["not_attempted"] == 0
    assert cells["eal_mcp"]["failure_categories"] == {"output_truncated": 1}
    assert cells["eal_mcp"]["provider_error_categories"] == {"output_truncated": 1}
    assert cells["eal_mcp"]["estimated_usd_known"] == 0.02
    assert cells["eal_mcp"]["output_tokens_known"] == 4096
    assert cells["json_prompt"]["not_attempted_reasons"] == {"no_retained_trial": 1}
    contrast = result["contrasts"][0]
    assert contrast["paired_blocks"] == 4 and contrast["paired_completed"] == 3
    assert contrast["both_incorrect"] == 2
    assert contrast["completed_pair_table"]["both_incorrect"] == 1
    assert all(cell["correct"] == 1 and cell["assigned"] == 4 for cell in result["cells"])


def test_interrupted_trials_retain_settled_and_pending_calls_without_rewriting(tmp_path):
    manifest = write_run(tmp_path)
    path = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row.update(state="running", model_calls=[
        {"turn": 0, "state": "complete", "estimated_usd": 0.01,
         "response": {"input_tokens": 100, "output_tokens": 20, "metadata": {}}},
        {"turn": 1, "state": "in_flight", "estimated_usd": None, "response": None,
         "reserved_usd": 0.1, "started_at": "2026-09-25T12:00:00Z"}])
    path.write_text(json.dumps(row))
    original = path.read_bytes()
    summary = summarise(tmp_path)
    cell = next(item for item in summary["cells"] if item["arm"] == "eal_mcp")
    assert summary["assigned"] == 8 and summary["failed"] == 1 and summary["not_attempted"] == 0
    assert cell["failure_categories"] == {"interrupted": 1}
    assert cell["correct"] == 1 and cell["model_calls"] == 2 and cell["unknown_cost_calls"] == 1
    assert cell["estimated_usd_known"] == 0.01 and cell["input_tokens_known"] == 100
    assert summary["measurement_valid"] and path.read_bytes() == original


@pytest.mark.parametrize("failure", ["host_reference_disagreement", "host_error:ToolExecutionError",
                                     "host_setup_error:ValueError", "host_finalization_error:RuntimeError"])
def test_instrument_failures_suspend_affected_contrasts_but_retain_diagnostics(tmp_path, failure):
    manifest = write_run(tmp_path, arms=("eal_mcp", "json_prompt", "plain_explicit", "plain_validator"))
    path = tmp_path / "trials" / manifest["assignments"][1]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row.update(state="failed", failure=failure, host_checks=[{"report_id": "target", "agrees": False}])
    path.write_text(json.dumps(row))
    result = summarise(tmp_path)
    assert not result["measurement_valid"] and result["invalid_measurements"][0]["reason"] == failure
    contrasts = {item["comparator"]: item for item in result["contrasts"] if item["reference_arm"] == "eal_mcp"}
    assert contrasts["json_prompt"]["interpretation"] == "suspended_invalid_measurement"
    assert contrasts["json_prompt"]["paired_blocks"] == 4
    assert contrasts["json_prompt"]["accuracy_difference"] == 0.25
    assert contrasts["plain_explicit"]["interpretation"] == "development_suite_descriptive"
    report = markdown(result)
    assert "Invalid measurement" in report and "interpretation of affected comparisons is suspended" in report
    assert failure in report


def test_trial_case_digest_must_match_the_frozen_case(tmp_path):
    manifest = write_run(tmp_path)
    path = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row["case_sha256"] = "different-case"
    path.write_text(json.dumps(row))
    summary = summarise(tmp_path)
    assert not summary["measurement_valid"]
    assert summary["invalid_measurements"][0]["reason"] == "trial_case_digest_mismatch"
    assert summary["contrasts"][0]["interpretation"] == "suspended_invalid_measurement"


def test_retained_case_content_must_match_the_freeze(tmp_path):
    write_run(tmp_path)
    (tmp_path / "cases" / "case-0" / "case.json").write_text('{"id":"case-0","changed":true}')
    summary = summarise(tmp_path)
    assert not summary["measurement_valid"] and len(summary["invalid_measurements"]) == 2
    assert {item["reason"] for item in summary["invalid_measurements"]} == {"retained_case_digest_mismatch"}


def test_trial_with_case_digest_requires_its_freeze(tmp_path):
    write_run(tmp_path)
    (tmp_path / "case-manifest.json").unlink()
    summary = summarise(tmp_path)
    assert not summary["measurement_valid"] and len(summary["invalid_measurements"]) == 8
    assert all("missing_case_freeze" in item["reason"] for item in summary["invalid_measurements"])


@pytest.mark.parametrize("freeze_content", ["{bad json", "[]"])
def test_unreadable_freeze_suspends_scores_without_discarding_known_costs(tmp_path, freeze_content):
    manifest = write_run(tmp_path)
    (tmp_path / "case-manifest.json").write_text(freeze_content)
    path = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row["model_calls"] = [{"state": "complete", "estimated_usd": 0.25,
                           "response": {"input_tokens": 200, "output_tokens": 50}}]
    path.write_text(json.dumps(row))
    summary = summarise(tmp_path)
    assert not summary["measurement_valid"] and summary["assigned"] == summary["completed"] == 8
    cell = next(item for item in summary["cells"] if item["arm"] == "eal_mcp")
    assert cell["estimated_usd_known"] == 0.25 and cell["model_calls"] == 1
    assert all("invalid_case_freeze" in item["reason"] for item in summary["invalid_measurements"])


def test_missing_retained_case_suspends_its_attempted_assignments(tmp_path):
    write_run(tmp_path)
    (tmp_path / "cases" / "case-0" / "case.json").unlink()
    summary = summarise(tmp_path)
    assert not summary["measurement_valid"] and len(summary["invalid_measurements"]) == 2
    assert all(item["reason"] == "missing_retained_case" for item in summary["invalid_measurements"])


def test_preflight_without_attempts_needs_no_case_freeze(tmp_path):
    manifest = write_run(tmp_path)
    for assignment in manifest["assignments"]:
        (tmp_path / "trials" / assignment["id"] / "trial.json").unlink()
    (tmp_path / "case-manifest.json").unlink()
    summary = summarise(tmp_path)
    assert summary["measurement_valid"] and not summary["invalid_measurements"]
    assert summary["assigned"] == summary["not_attempted"] == 8


def test_transport_and_case_repetitions_are_not_pooled_as_new_cases(tmp_path):
    write_run(tmp_path, transports=("text", "native"), repeats=2)
    result = summarise(tmp_path)
    assert len(result["contrasts"]) == 2 and len(result["cells"]) == 4
    assert {row["transport"] for row in result["contrasts"]} == {"text", "native"}
    assert all(row["paired_cases"] == 4 and row["paired_blocks"] == 8 for row in result["contrasts"])


def test_checked_answers_are_not_pooled_with_model_answers_or_narrative_presence(tmp_path):
    manifest = write_run(tmp_path, arms=("eal_mcp", "plain_validator"))
    for assignment in list(manifest["assignments"]):
        path = tmp_path / "trials" / assignment["id"] / "trial.json"
        row = json.loads(path.read_text())
        row.update(finalisation="model", answer_origin="model", protocol_complete=True,
                   answer_complete=True, explanation_present=False)
        assignment["finalisation"] = "model"
        path.write_text(json.dumps(row))
        checked = {**assignment, "id": "checked-" + assignment["id"], "finalisation": "checked"}
        manifest["assignments"].append(checked)
        directory = tmp_path / "trials" / checked["id"]
        directory.mkdir()
        (directory / "trial.json").write_text(json.dumps({
            **row, **checked, "answer_origin": "checked_host", "protocol_complete": False,
            "outcome": {"correct": True}, "provider_retries": 1,
            "model_calls": [{"retry_of_turn": 0, "state": "complete", "estimated_usd": 0}]}))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    summary = summarise(tmp_path)
    assert len(summary["cells"]) == 4 and len(summary["contrasts"]) == 2
    for cell in summary["cells"]:
        assert cell["assigned"] == cell["answer_complete"] == 4
        assert cell["explanation_present"] == 0
        if cell["finalisation"] == "model":
            assert cell["correct"] == 2 and cell["protocol_complete"] == 4
            assert cell["answer_origin_counts"] == {"model": 4}
        else:
            assert cell["correct"] == 4 and cell["protocol_complete"] == 0
            assert cell["answer_origin_counts"] == {"checked_host": 4}
            assert cell["provider_retries"] == 4
    assert all(row["paired_blocks"] == 4 for row in summary["contrasts"])
    report = markdown(summary)
    assert "not model-answer accuracy" in report and "no claim about its quality" in report


def test_interrupted_retry_count_comes_from_durable_dispatches(tmp_path):
    manifest = write_run(tmp_path)
    path = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row.update(state="running", model_calls=[
        {"turn": 0, "state": "failed", "error": "HTTP 503", "category": "http_server",
         "estimated_usd": None},
        {"turn": 1, "state": "in_flight", "retry_of_turn": 0, "estimated_usd": None}])
    path.write_text(json.dumps(row))
    original = path.read_bytes()
    cell = next(item for item in summarise(tmp_path)["cells"] if item["arm"] == row["arm"])
    assert cell["provider_retries"] == 1 and cell["unknown_cost_calls"] == 2
    assert cell["failure_categories"] == {"interrupted": 1}
    assert path.read_bytes() == original


def test_mutated_assignments_and_duplicate_blocks_fail_closed(tmp_path):
    manifest = write_run(tmp_path)
    path = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row["case_id"] = "changed"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="identity differs"):
        summarise(tmp_path)
