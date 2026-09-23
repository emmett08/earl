import asyncio
import copy
import json
from pathlib import Path

import pytest

from eal.benchmark import check_task, compare_sources, evaluate_models, evidence_trace_score, load_suite, prepare_task, score_answer, source_correspondence, summarise, task_inputs, workflow_score

SUITE = Path(__file__).resolve().parents[1] / "benchmarks/engineering-v1/suite.json"


def report(claims, status="completed"):
    return {"status": status, "final": {"claims": claims}}


def test_scoring_distinguishes_justified_unresolved_and_unjustified_answers():
    expected = {"result": "unsupported"}
    correct = score_answer(expected, report({"result": "unsupported"}))
    assert correct["correct"] and correct["justified_unresolved"] and not correct["correctly_resolved"]
    positive = score_answer(expected, report({"result": {"status": "supported"}}))
    assert positive["unjustified"] and not positive["correct"]
    unresolved = score_answer({"result": "supported"}, report({"result": "unresolved"}))
    assert unresolved["unresolved"] and not unresolved["unjustified"]


def test_empty_failed_extra_or_malformed_answers_receive_no_credit():
    expected = {"result": "supported"}
    for answer in ({}, {"result": []}, {"result": "supported", "unasked": "supported"}):
        assert not score_answer(expected, report(answer))["correct"]
    assert not score_answer(expected, report({"result": "supported"}, "incomplete"))["correct"]


def test_repaired_source_must_retain_full_reference_meaning():
    source = (SUITE.parent / "sources/nested-model.eal").read_text()
    assert source_correspondence(source, "// formatting only\n" + source)
    assert not source_correspondence(source, source.replace("premises model_result, model_applies;", "premises model_result;"))
    assert not source_correspondence(source, source.replace('require "revision" == "A";', 'require "revision" == "B";'))
    assert not source_correspondence(source, "invalid")


def test_alpha_equivalence_accepts_consistent_internal_renaming_only():
    source = (SUITE.parent / "sources/calibration-interval.eal").read_text()
    renamed = source.replace("assumption calibrated {", "assumption calibration_valid {").replace("assumptions calibrated;", "assumptions calibration_valid;")
    comparison = compare_sources(source, renamed, anchored_claims=("reading_usable",))
    assert comparison["equivalent"]
    assert comparison["mapping"]["assumptions.calibrated"] == "assumptions.calibration_valid"
    assert not source_correspondence(source, renamed.replace("assumptions calibration_valid;", ""))
    assert not source_correspondence(source, renamed.replace('valid_until "2026-09-23T11:00:00Z"', 'valid_until "2026-09-24T11:00:00Z"'))
    assert not source_correspondence(source, renamed.replace("calibration_check_tool", "another_operator_tool"))
    assert not source_correspondence(source, renamed.replace("reading_usable", "another_claim"), anchored_claims=("reading_usable",))


def test_alpha_equivalence_handles_declaration_order_and_cycles_without_rewriting_literals():
    source = '''language "EAL/0.1";
environment lab { require "site" == "bench"; }
tool instrument { version "1"; mode deterministic; }
evidence measured { tool instrument; kind test; environment lab; max_age 60; require "passed" == true; }
reasoning step { mode structured; rationale "measured means an observation, not a replaceable literal"; }
claim outcome { statement "The trial supports this property."; environment lab; }
argument route { conclusion outcome; reasoning step; evidence measured; }
'''
    renamed = source.replace("environment lab {", "environment place {").replace("environment lab;", "environment place;")
    renamed = renamed.replace("reasoning step {", "reasoning link {").replace("reasoning step;", "reasoning link;")
    renamed = renamed.replace("argument route {", "argument derivation {")
    assert source_correspondence(source, renamed, anchored_claims=("outcome",))
    assert not source_correspondence(source, renamed.replace('"passed" == true', '"passed" == 1'))
    assert not source_correspondence(source, renamed.replace('"measured means', '"different means'))


def test_model_inputs_do_not_disclose_expected_status_or_oracle():
    task = load_suite(SUITE)["tasks"][0]
    inputs = task_inputs(task, SUITE.parent)
    assert set(inputs) == {"source", "observations", "context", "now"}
    assert task["oracle"] not in json.dumps(inputs)


def test_summary_counts_failed_attempt_cost_and_never_fills_unknown_cost_with_zero():
    def trial(arm, correct, cost, tokens=40):
        return {"arm": arm, "score": {"correct": correct, "correctly_resolved": correct,
                "justified_unresolved": False, "unjustified": False, "unresolved": not correct},
                "report": {"repairs": 1, "attempts": [{}, {}], "latency_seconds": 2,
                           "usage": {"total_tokens": tokens, "token_usage_complete": tokens is not None}},
                "cost": {"total_usd": cost}}
    trials = [trial("unaided", False, .03), trial("unaided", True, .01),
              trial("delegated", True, .02), trial("delegated", False, None, None)]
    result = summarise(trials)
    assert result["unaided"]["cost_per_correct_task_usd"] == .04
    assert result["unaided"]["attempts"] == 4
    assert result["unaided"]["total_tokens"] == 80
    assert result["delegated"]["total_cost_usd"] is None
    assert result["delegated"]["cost_per_correct_task_usd"] is None
    assert result["delegated"]["total_tokens"] is None


def test_suite_rejects_duplicate_identifiers_and_unbounded_file_paths(tmp_path):
    suite = load_suite(SUITE)
    task = copy.deepcopy(suite["tasks"][0])
    task["source"] = "source.eal"
    task["observations"] = "observations.json"
    (tmp_path / "source.eal").write_text("example")
    (tmp_path / "observations.json").write_text("{}")
    filename = tmp_path / "suite.json"
    filename.write_text(json.dumps({**suite, "tasks": [task, task]}))
    with pytest.raises(ValueError, match="unique"):
        load_suite(filename)
    task["source"] = "../outside.eal"
    filename.write_text(json.dumps({**suite, "tasks": [task]}))
    with pytest.raises(ValueError, match="outside"):
        load_suite(filename)


def test_workflow_requires_the_explanation_of_the_final_assessment():
    report = {"final": {"assessment_id": "latest"}, "tool_calls": [
        {"tool": "eal_explain", "status": "ok", "arguments": {"assessment_id": "old"}},
        {"tool": "eal_validate", "status": "ok", "result": {"valid": False}}]}
    assert workflow_score(["validate", "explain"], report)["missing_operations"] == ["explain", "validate"]


def test_paired_harness_through_actual_mcp_with_explicit_regression_provider():
    """This scripted provider tests wiring; its answers are not empirical model data."""
    from eal.providers import ModelResponse

    class RegressionProvider:
        def identity(self):
            return {"provider": "scripted-regression-only", "model": "not-an-LLM", "sampling": {},
                    "measurement_kind": "interface_only",
                    "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2}}

        async def complete(self, messages, max_output_tokens):
            initial = json.loads(messages[1]["content"])
            claim_ids = initial["required_claims"]
            if "no tool access" in messages[0]["content"]:
                value = {"claims": {claim: "supported" for claim in claim_ids}}
            else:
                inputs = initial["initial_data"]
                events = []
                for message in messages[2:]:
                    if message["role"] != "user":
                        continue
                    try:
                        feedback = json.loads(message["content"])
                    except ValueError:
                        continue
                    feedback = feedback.get("host_feedback", feedback)
                    if isinstance(feedback, dict) and feedback.get("operation"):
                        events.append(feedback)
                collected = next((e["result"] for e in events if e["operation"] == "collect"), None)
                reasoned = next((e["result"] for e in events if e["operation"] == "reason"), None)
                if reasoned:
                    value = {"operation": "finish", "assessment_id": reasoned["assessment_id"], "claims": claim_ids}
                elif collected:
                    value = {"operation": "reason", "source": inputs["source"], "context": inputs["context"],
                             "now": inputs["now"], "collection_id": collected["collection_id"]}
                else:
                    value = {"operation": "collect", "source": inputs["source"], "context": inputs["context"]}
            return ModelResponse(json.dumps(value), input_tokens=100, output_tokens=30, model="not-an-LLM")

    result = asyncio.run(evaluate_models(SUITE, RegressionProvider(), split="development",
                                        task_ids=["nested-model-observation"], per_mcp_call_usd=0, host_mode="legacy"))
    assert len(result["trials"]) == 2
    assert all(trial["score"]["correct"] for trial in result["trials"]), [(t["score"], t["report"]["stop_reason"]) for t in result["trials"]]
    assert result["trials"][0]["inputs"] == result["trials"][1]["inputs"]
    delegated = next(trial for trial in result["trials"] if trial["arm"] == "delegated")
    assert delegated["score"]["source_correspondence"]
    assert delegated["cost"]["mcp_calls"] >= 3
    assert result["summary"]["delegated"]["cost_complete"]


def test_unsupported_answer_requires_the_provided_observation_to_be_assessed(tmp_path):
    fresh = SUITE.parents[1] / "engineering-v2/suite.json"
    task = next(task for task in load_suite(fresh)["tasks"] if task["id"] == "registered-rms-wrong-origin")
    reference = check_task(task, fresh.parent, tmp_path)
    inputs = task_inputs(task, fresh.parent)
    source = inputs["source"]
    comparison = compare_sources(source, source, anchored_claims=tuple(task["expected"]["claims"]))
    collection = reference["collection"]
    assessment = reference["assessment"]
    final = {"assessment_id": assessment["assessment_id"], "source": source, "claims": assessment["claims"]}
    validation = {"tool": "eal_validate", "status": "ok", "arguments": {"source": source},
                  "result": {"valid": True, "source_digest": assessment["source_digest"]}}
    collection_event = {"tool": "eal_collect", "status": "ok", "arguments": {"source": source, "context": inputs["context"]}, "result": collection}
    reason_event = {"tool": "eal_reason", "status": "ok", "arguments": {"source": source, "context": inputs["context"], "now": inputs["now"], "collection_id": collection["collection_id"]}, "result": assessment}
    valid = {"final": final, "tool_calls": [validation, collection_event, reason_event]}
    assert evidence_trace_score(inputs, reference, comparison, valid)["verified"]
    skipped_collection = {"final": final, "tool_calls": [validation, reason_event]}
    assert not evidence_trace_score(inputs, reference, comparison, skipped_collection)["verified"]
    wrong_data = copy.deepcopy(valid)
    wrong_data["tool_calls"][1]["result"]["records"] = {}
    assert not evidence_trace_score(inputs, reference, comparison, wrong_data)["verified"]
    wrong_time = copy.deepcopy(valid)
    wrong_time["tool_calls"][2]["arguments"]["now"] = "2041-01-31T08:20:00Z"
    assert not evidence_trace_score(inputs, reference, comparison, wrong_time)["verified"]
    wrong_collection = copy.deepcopy(valid)
    wrong_collection["tool_calls"][2]["arguments"]["collection_id"] = "another-collection"
    assert not evidence_trace_score(inputs, reference, comparison, wrong_collection)["verified"]


@pytest.mark.parametrize("task_id", ["nested-outside-environment", "nested-missing-measurement"])
def test_intentional_missing_or_out_of_scope_observations_are_not_scoring_errors(task_id, tmp_path):
    task = next(task for task in load_suite(SUITE)["tasks"] if task["id"] == task_id)
    reference = check_task(task, SUITE.parent, tmp_path)
    inputs = task_inputs(task, SUITE.parent)
    source = inputs["source"]
    comparison = compare_sources(source, source, anchored_claims=tuple(task["expected"]["claims"]))
    collection, assessment = reference["collection"], reference["assessment"]
    report = {"final": {"assessment_id": assessment["assessment_id"], "source": source}, "tool_calls": [
        {"tool": "eal_validate", "status": "ok", "arguments": {"source": source}, "result": {"valid": True, "source_digest": assessment["source_digest"]}},
        {"tool": "eal_collect", "status": "ok", "arguments": {"source": source, "context": inputs["context"]}, "result": collection},
        {"tool": "eal_reason", "status": "ok", "arguments": {"source": source, "context": inputs["context"], "now": inputs["now"], "collection_id": collection["collection_id"]}, "result": assessment}]}
    assert evidence_trace_score(inputs, reference, comparison, report)["verified"]


def test_evidence_trace_accepts_a_consistently_renamed_evidence_and_assumption(tmp_path):
    task = next(task for task in load_suite(SUITE)["tasks"] if task["id"] == "calibration-historical-valid")
    reference = check_task(task, SUITE.parent, tmp_path / "reference")
    service, inputs = prepare_task(task, SUITE.parent, tmp_path / "actual")
    source = inputs["source"].replace("assumption calibrated {", "assumption calibration_valid {").replace("assumptions calibrated;", "assumptions calibration_valid;")
    source = source.replace("evidence calibration_check {", "evidence calibration_observation {").replace("validate calibration_check;", "validate calibration_observation;")
    comparison = compare_sources(inputs["source"], source, anchored_claims=tuple(task["expected"]["claims"]))
    validation = service.validate(source)
    collection = service.collect(source, inputs["context"])
    assessment = service.reason(source, inputs["context"], collection["collection_id"], inputs["now"])
    report = {"final": {"assessment_id": assessment["assessment_id"], "source": source}, "tool_calls": [
        {"tool": "eal_validate", "status": "ok", "arguments": {"source": source}, "result": validation},
        {"tool": "eal_collect", "status": "ok", "arguments": {"source": source, "context": inputs["context"]}, "result": collection},
        {"tool": "eal_reason", "status": "ok", "arguments": {"source": source, "context": inputs["context"], "now": inputs["now"], "collection_id": collection["collection_id"]}, "result": assessment}]}
    assert comparison["equivalent"]
    assert evidence_trace_score(inputs, reference, comparison, report)["verified"]
