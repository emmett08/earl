"""Synthetic, labelled controls for independent v2 adjudication and reporting."""
from __future__ import annotations

import copy
import json

import pytest

from experiments.api_load_test.analysis import markdown, summarise
from experiments.api_load_test.oracle import grade, reference, reference_report


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
    return {key: copy.deepcopy(truth[key]) for key in ("report_id", "status", "scope", "metrics", "failed_checks")}


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
                         ("failed_checks", ["errors"]), ("metrics", {**answer["metrics"], "p95_ms": 0})):
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


def write_run(tmp_path, *, transports=("text",), repeats=1):
    assignments = []
    for transport in transports:
        for repeat in range(repeats):
            for index in range(4):
                for arm in ("eal_mcp", "json_prompt"):
                    assignment = {"id": f"{transport}-{repeat}-{index}-{arm}", "model": "synthetic-model",
                                  "arm": arm, "case_id": f"case-{index}", "case_family": "synthetic",
                                  "repeat": repeat, "block": f"{repeat}:{index}", "transport": transport}
                    assignments.append(assignment)
                    # Rows cover each paired 2x2 cell exactly once.
                    correct = ((index in (0, 1)) if arm == "eal_mcp" else (index in (0, 2)))
                    directory = tmp_path / "trials" / assignment["id"]
                    directory.mkdir(parents=True)
                    (directory / "trial.json").write_text(json.dumps({**assignment, "state": "complete",
                        "outcome": {"correct": correct}, "model_calls": []}))
    manifest = {"schema": "eal-api-experiment-run/2", "mode": "pilot", "transport": "text",
                "models": [{"id": "synthetic-model"}], "assignments": assignments,
                "plan": {"arms": ["eal_mcp", "json_prompt"], "scope": "Synthetic analysis control"}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_paired_report_counts_discordances_without_claiming_equivalence(tmp_path):
    write_run(tmp_path)
    result = summarise(tmp_path)
    comparison = result["contrasts"][0]
    assert comparison["paired_cases"] == comparison["paired_blocks"] == comparison["paired_completed"] == 4
    assert comparison["both_correct"] == comparison["both_incorrect"] == 1
    assert comparison["eal_only_correct"] == comparison["comparator_only_correct"] == 1
    assert comparison["accuracy_difference"] == 0
    assert comparison["interpretation"] == "development_suite_descriptive"
    text = markdown(result)
    assert "Insufficient blocks" not in text and "does not establish equivalence" in text
    assert "interval" not in comparison


def test_failed_and_missing_assignments_remain_in_the_operational_denominator(tmp_path):
    manifest = write_run(tmp_path)
    failed = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    record = json.loads(failed.read_text())
    record["state"] = "failed"  # Even an inconsistent retained success must score zero.
    failed.write_text(json.dumps(record))
    (tmp_path / "trials" / manifest["assignments"][1]["id"] / "trial.json").unlink()
    result = summarise(tmp_path)
    assert result["assigned"] == 8 and not result["complete"]
    contrast = result["contrasts"][0]
    assert contrast["paired_blocks"] == 4 and contrast["paired_completed"] == 3
    assert contrast["both_incorrect"] == 2
    assert contrast["completed_pair_table"]["both_incorrect"] == 1
    assert all(cell["correct"] == 1 and cell["assigned"] == 4 for cell in result["cells"])


def test_transport_and_case_repetitions_are_not_pooled_as_new_cases(tmp_path):
    write_run(tmp_path, transports=("text", "native"), repeats=2)
    result = summarise(tmp_path)
    assert len(result["contrasts"]) == 2 and len(result["cells"]) == 4
    assert {row["transport"] for row in result["contrasts"]} == {"text", "native"}
    assert all(row["paired_cases"] == 4 and row["paired_blocks"] == 8 for row in result["contrasts"])


def test_mutated_assignments_and_duplicate_blocks_fail_closed(tmp_path):
    manifest = write_run(tmp_path)
    path = tmp_path / "trials" / manifest["assignments"][0]["id"] / "trial.json"
    row = json.loads(path.read_text())
    row["case_id"] = "changed"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="identity differs"):
        summarise(tmp_path)
