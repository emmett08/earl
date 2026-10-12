"""Software-only recording checks against real prepared EAL/MCP fixtures.

No response below represents a host-agent execution or a MAS Protocol Lab run.
"""

import copy
import json
from pathlib import Path
import shutil

import pytest

from experiments.mas_coordination import pilot
from experiments.mas_coordination.cases import CLAIMS, case_spec


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    output = tmp_path_factory.mktemp("pilot-template") / "run"
    pilot.prepare(output, ["mcp_json"], None)
    return output


@pytest.fixture
def run_copy(prepared, tmp_path):
    def copy_case(case_id="nominal"):
        for run_id in pilot.read(prepared / "manifest.json")["prepared_runs"]:
            candidate = prepared / run_id
            if pilot.read(candidate / "state.json")["case_id"] == case_id:
                destination = tmp_path / run_id
                shutil.copytree(candidate, destination)
                return destination
        raise AssertionError("Prepared case absent")
    return copy_case


def response_file(run, actor, value):
    path = run / f"software-{actor}.json"
    pilot.write(path, value)
    return path


def assessor_output(run):
    context = pilot.read(run / "assessor-context.json")
    return {"proposals": context["proposal_templates"],
            "consumed_message_ids": [message["message_id"] for message in context["received_messages"]]}


def reviewer_output(run):
    state = pilot.read(run / "state.json")
    context = pilot.read(run / "reviewer-context.json")
    spec = case_spec(state["case_id"])
    return {"answer": {"statuses": dict(spec.expected_statuses), "scope": spec.requested_scope,
                       "assessed_at": spec.assessed_at, "conclusion": spec.expected_conclusion,
                       "production_supported": False},
            "reviews": context["review_templates"],
            "consumed_message_ids": [message["message_id"] for message in context["received_messages"]]}


def record_software(run, actor, value, execution_id=None):
    return pilot.record(run, actor, response_file(run, actor, value),
                        execution_id or f"software-only-{actor}",
                        execution_mode="software_test")


def test_canonical_first_attempts_are_recorded_as_software_only(run_copy):
    run = run_copy()
    first = record_software(run, "assessor", assessor_output(run))
    assert first["delivery"] == "accepted"
    context = pilot.read(run / "reviewer-context.json")
    assert set(context["trusted_packets"]) == set(CLAIMS)
    final = record_software(run, "reviewer", reviewer_output(run))
    assert final["score"]["answer_correct"] is True
    assert final["score"]["response_admitted"] is True
    state = pilot.read(run / "state.json")
    assert all(row["execution_mode"] == "software_test" for row in state["executions"])
    assert all(row["model_tokens"] is None and row["model_cost_usd"] is None
               and row["elapsed_seconds"] is None for row in state["executions"])
    assert len(state["accepted_messages"]) == 6
    assert state["executions"][0]["durable_transport"]["status"] == "not_applicable"
    with pytest.raises(ValueError, match="First-attempt"):
        record_software(run, "assessor", assessor_output(run), execution_id="software-second-turn")


def test_scope_rejection_permits_empty_reviews_and_correct_unassessed_answer(run_copy):
    run = run_copy("scope_mismatch")
    first = record_software(run, "assessor", assessor_output(run))
    assert first["delivery"] == "rejected"
    context = pilot.read(run / "reviewer-context.json")
    assert context["received_messages"] == []
    assert context["trusted_packets"] == {}
    assert context["review_templates"] == []
    final = record_software(run, "reviewer", reviewer_output(run))
    assert final["recorded"]["first_attempt_outcome"] == "accepted"
    assert final["score"]["answer_correct"] is True
    assert final["score"]["justified_unresolved"] is True
    assert final["score"]["delivery"] == "rejected"
    assert len(pilot.read(run / "state.json")["accepted_messages"]) == 2


def test_wrong_consumption_cannot_commit_valid_proposals(run_copy):
    run = run_copy()
    value = assessor_output(run)
    value["consumed_message_ids"] = []
    result = record_software(run, "assessor", value)
    assert result["delivery"] == "rejected"
    assert "attest inspection" in result["recorded"]["admission_errors"][0]
    assert len(pilot.read(run / "state.json")["accepted_messages"]) == 2
    assert pilot.read(run / "reviewer-context.json")["trusted_packets"] == {}


def test_second_invalid_message_rolls_back_whole_domain_admission(run_copy):
    run = run_copy()
    value = copy.deepcopy(assessor_output(run))
    value["proposals"][1]["assessment_id"] = "invented-assessment"
    result = record_software(run, "assessor", value)
    assert result["recorded"]["first_attempt_outcome"] == "rejected"
    assert len(pilot.read(run / "state.json")["accepted_messages"]) == 2


@pytest.mark.parametrize("mutation", [
    lambda body: {**body, "debug": "extra"},
    lambda body: {"proposals": body["proposals"]},
    lambda body: {**body, "consumed_message_ids": ["request-0", "request-0"]},
])
def test_exact_top_level_contract_and_message_consumption(run_copy, mutation):
    run = run_copy()
    result = record_software(run, "assessor", mutation(assessor_output(run)))
    assert result["delivery"] == "rejected"
    assert len(pilot.read(run / "state.json")["accepted_messages"]) == 2


def test_duplicate_nested_body_field_is_rejected_and_raw_attempt_retained(run_copy):
    run = run_copy()
    path = response_file(run, "assessor", assessor_output(run))
    raw = path.read_text().replace('"status": "supported"',
                                  '"status": "supported", "status": "unsupported"', 1)
    path.write_text(raw)
    result = pilot.record(run, "assessor", path, "software-only-duplicate",
                          execution_mode="software_test")
    assert result["delivery"] == "rejected"
    assert "Duplicate JSON field" in result["recorded"]["admission_errors"][0]
    assert (run / "assessor-response.raw.json").read_text() == raw
    assert pilot.read(run / "assessor-response.json") is None


def test_missing_first_attempt_response_remains_unknown(run_copy):
    run = run_copy()
    result = pilot.record(run, "assessor", run / "absent-response.json", "software-missing-output",
                          execution_mode="software_test")
    assert result["recorded"]["first_attempt_outcome"] == "unknown"
    assert result["recorded"]["response_sha256"] is None
    assert result["delivery"] == "unresolved"
    reviewer = pilot.record(run, "reviewer", run / "absent-reviewer.json", "software-missing-reviewer",
                            execution_mode="software_test")
    assert reviewer["score"]["answer_correct"] is None
    assert reviewer["score"]["response_admitted"] is False


def test_correct_task_fields_do_not_imply_response_admission(run_copy):
    run = run_copy()
    record_software(run, "assessor", assessor_output(run))
    value = reviewer_output(run)
    value["debug"] = "forbidden extra response field"
    result = record_software(run, "reviewer", value)
    assert result["recorded"]["first_attempt_outcome"] == "rejected"
    assert result["score"]["answer_correct"] is True
    assert result["score"]["response_admitted"] is False


def test_execution_identity_mode_and_elapsed_are_explicit(run_copy):
    run = run_copy()
    response = response_file(run, "assessor", assessor_output(run))
    with pytest.raises(TypeError, match="execution_mode"):
        pilot.record(run, "assessor", response, "software-test")
    for execution_id, mode, elapsed in [("  ", "software_test", None),
                                        ("test", "unverified_role_label", None),
                                        ("test", "software_test", float("nan"))]:
        with pytest.raises(ValueError):
            pilot.record(run, "assessor", response, execution_id, elapsed, execution_mode=mode)
    assert pilot.read(run / "state.json")["executions"] == []


def test_invalid_initialization_arguments_do_not_mutate_output(tmp_path):
    for arms, runtime in [([], None), (["invented"], None), (["mcp_json", "mcp_json"], None),
                          (["eal_protocol"], None), (["eal_protocol"], tmp_path / "no-runtime")]:
        output = tmp_path / "never-created"
        with pytest.raises((ValueError, FileNotFoundError)):
            pilot.prepare(output, arms, runtime)
        assert not output.exists()


def test_model_visible_case_id_and_anchors_are_opaque(prepared):
    for run_id in pilot.read(prepared / "manifest.json")["prepared_runs"]:
        context = pilot.read(prepared / run_id / "assessor-context.json")
        assert "case_id" not in context["task"]
        assert context["task"]["task_id"].startswith("task")
        assert all(message["task_id"] == context["task"]["task_id"]
                   for message in context["received_messages"])
        assert all(case_id not in run_id for case_id in ("nominal", "stale", "scope_mismatch", "measured_failure"))


def test_frozen_plan_matches_first_attempt_cli():
    plan = pilot.read(pilot.PLAN)
    assert plan["role_execution"]["roles"] == ["assessor", "reviewer"]
    assert plan["role_execution"]["maximum_repair_turns_total"] == 0
    assert plan["role_execution"]["maximum_role_turns_total"] == 16
