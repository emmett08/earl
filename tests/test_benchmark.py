import asyncio
import copy
import json
from pathlib import Path

import pytest

from eal.benchmark import evaluate_models, load_suite, score_answer, source_correspondence, summarise, task_inputs, workflow_score

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
                                        task_ids=["nested-model-observation"], per_mcp_call_usd=0))
    assert len(result["trials"]) == 2
    assert all(trial["score"]["correct"] for trial in result["trials"]), [(t["score"], t["report"]["stop_reason"]) for t in result["trials"]]
    assert result["trials"][0]["inputs"] == result["trials"][1]["inputs"]
    delegated = next(trial for trial in result["trials"] if trial["arm"] == "delegated")
    assert delegated["score"]["source_correspondence"]
    assert delegated["cost"]["mcp_calls"] >= 3
    assert result["summary"]["delegated"]["cost_complete"]
