"""Task correspondence tests, independent of worker answers or acquisition."""
from copy import deepcopy
from dataclasses import replace

import pytest

from eal.coordination.contracts import ServerSpec, TaskSpec, validate_anchor
from eal.coordination.profiles import check_task, pin_task, validate_answer
from experiments.mas_coordination.coordinator_demo import prepare_demo


@pytest.fixture
def prepared(tmp_path):
    demo = prepare_demo(tmp_path)
    server = ServerSpec.from_dict({"limits": None, **demo["server"]})
    return server, [TaskSpec.from_dict(value) for value in demo["tasks"]]


def test_two_profiles_pin_without_acquisition_and_reject_mutation(prepared):
    server, tasks = prepared
    for task in tasks:
        anchor = pin_task(server, task)
        assert check_task(server, anchor)["ok"]
        assert validate_anchor(anchor).to_dict() == task.to_dict()
        with pytest.raises(TypeError):
            task.requirements["context"]["dataset"] = "measured"
        changed = deepcopy(anchor)
        changed["task"]["question"] += " changed"
        with pytest.raises(ValueError, match="digest"):
            validate_anchor(changed)
    from eal.coordination.profiles import knowledge
    assert all(knowledge(server).history(task.entry_id)["assessments"] == [] for task in tasks)


@pytest.mark.parametrize("field,value,code", [
    ("run_id", "other-run", "workload_mismatch"),
    ("concurrent_clients", 20, "workload_mismatch"),
    ("maximum_sample_p95_ms", 201, "criteria_mismatch"),
    ("evidence_max_age_seconds", 42, "criteria_mismatch"),
])
def test_complete_api_workload_criteria_and_freshness(prepared, field, value, code):
    server, tasks = prepared
    task = tasks[0].to_dict()
    section = "workload" if field in {"run_id", "concurrent_clients"} else "criteria"
    task["requirements"][section][field] = value
    anchor = pin_task(server, TaskSpec.from_dict(task))
    assert check_task(server, anchor)["code"] == code


def test_generic_context_is_exact_type_sensitive_and_source_revision_pinned(prepared):
    server, tasks = prepared
    task = tasks[1].to_dict()
    task["requirements"]["context"]["deployment"] = "another-deployment"
    assert check_task(server, pin_task(server, TaskSpec.from_dict(task)))["code"] == "context_mismatch"
    anchor = pin_task(server, tasks[1])
    path = server.workspace / "availability.eal"
    path.write_text(path.read_text().replace("The identified synthetic snapshot", "This identified synthetic snapshot"))
    assert check_task(server, anchor)["code"] == "source_changed"


@pytest.mark.parametrize("mutate", [
    lambda task: task.update(extra=True),
    lambda task: task.update(claims=["duplicate", "duplicate"]),
    lambda task: task.update(claims=[{}]),
    lambda task: task.update(profile="uninstalled/1"),
    lambda task: task["requirements"]["workload"].update(concurrent_clients=True),
    lambda task: task["requirements"]["criteria"].update(maximum_error_rate_percent=float("nan")),
    lambda task: task["requirements"]["criteria"].update(minimum_requests=10**1000),
    lambda task: task["requirements"]["claim_outputs"].update(performance_criteria_met="unproved"),
    lambda task: task["requirements"]["claim_outputs"].update(performance_criteria_met=[]),
    lambda task: task["requirements"].update(now="2026-01-01T00:00:00Z"),
])
def test_closed_task_contract_rejects_coercions_overrides_and_unknown_fields(prepared, mutate):
    _, tasks = prepared
    task = tasks[0].to_dict()
    mutate(task)
    with pytest.raises(ValueError):
        TaskSpec.from_dict(task)


def test_server_paths_are_absolute_frozen_and_closed(tmp_path):
    server = ServerSpec(tmp_path, methods="eal.api_load_methods:registry")
    assert server.database == tmp_path / ".eal" / "runs.sqlite3"
    assert ServerSpec.from_dict(server.to_dict()) == server
    with pytest.raises(ValueError):
        ServerSpec.from_dict({**server.to_dict(), "transport": "http"})
    with pytest.raises(ValueError):
        ServerSpec(tmp_path, methods="arbitrary command")


def test_alternative_api_route_cannot_bypass_requested_output(prepared):
    server, tasks = prepared
    source = server.workspace / "api-load.eal"
    with source.open("a") as target:
        target.write("\nargument unqualified_route = [evidence load_test] via failing_limits => performance_criteria_met\n")
    assert check_task(server, pin_task(server, tasks[0]))["code"] == "criteria_mismatch"


def test_dataclass_replace_preserves_nested_frozen_requirements(prepared):
    _, tasks = prepared
    changed = replace(tasks[0], question="Another operator-authored question")
    assert changed.to_dict()["requirements"] == tasks[0].to_dict()["requirements"]


def test_removed_method_registry_is_a_criterion_change_before_source_refresh(prepared):
    server, tasks = prepared
    anchor = pin_task(server, tasks[0])
    assert check_task(replace(server, methods=None), anchor)["code"] == "criteria_mismatch"
