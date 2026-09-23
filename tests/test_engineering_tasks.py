"""Known-answer corpus checks run the real parser, evidence adapter and service."""
import json
from pathlib import Path

import pytest

from eal.benchmark import check_task, load_suite

SUITE = Path(__file__).resolve().parents[1] / "benchmarks/engineering-v1/suite.json"
TASKS = load_suite(SUITE)["tasks"]
FRESH_SUITE = SUITE.parents[1] / "engineering-v2/suite.json"
FRESH_TASKS = load_suite(FRESH_SUITE)["tasks"]


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task["id"])
def test_committed_engineering_answers(task, tmp_path):
    result = check_task(task, SUITE.parent, tmp_path)
    assert result["passed"], result["errors"]


def test_suite_has_required_families_and_distinguishing_adverse_cases():
    assert {"nested_model", "fault_revision", "causal_counterfactual", "calibration_interval",
            "objection_composition", "text_model_workflow", "typed_result_binding"} <= {t["family"] for t in TASKS}
    names = {t["id"] for t in TASKS}
    assert {"typed-incompatible-unit", "typed-wrong-quantity", "typed-wrong-scope",
            "typed-overgeneralised-time", "nested-missing-measurement", "calibration-exact-expiry"} <= names
    assert {t["split"] for t in TASKS} == {"development", "held_out"}


def test_reference_oracle_is_distinct_from_observation_inputs():
    for task in TASKS:
        assert task["oracle"].strip()
        observations = json.loads((SUITE.parent / task["observations"]).read_text())
        assert all("expected" not in observation and "oracle" not in observation for observation in observations.values())


@pytest.mark.parametrize("task", FRESH_TASKS, ids=lambda task: task["id"])
def test_fresh_defence_method_and_repair_answers(task, tmp_path):
    result = check_task(task, FRESH_SUITE.parent, tmp_path)
    assert result["passed"], result["errors"]


def test_fresh_suite_is_separate_from_development_knowledge():
    assert not {task["id"] for task in FRESH_TASKS} & {task["id"] for task in TASKS}
    assert all(task["split"] == "held_out" for task in FRESH_TASKS)
    assert {task["family"] for task in FRESH_TASKS} >= {"defence_composition", "registered_method", "text_model_workflow", "typed_negative_finding"}
