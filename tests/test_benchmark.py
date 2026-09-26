import asyncio
import copy
import json

import pytest

from eal.benchmark import compare_sources, evaluate_models, evidence_trace_score, load_suite, score_answer, source_correspondence, summarise, task_inputs, workflow_score
from _runtime_cases import PRESSURE_SOURCE, write_suite

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
    source = PRESSURE_SOURCE
    assert source_correspondence(source, "// formatting only\n" + source)
    assert not source_correspondence(source, source.replace("evidence e;", ""))
    assert not source_correspondence(source, source.replace('require "revision" == "A";', 'require "revision" == "B";'))
    assert not source_correspondence(source, "invalid")


def test_alpha_equivalence_accepts_consistent_internal_renaming_only():
    source = PRESSURE_SOURCE
    renamed = source.replace("evidence pressure_trial {", "evidence measured_trial {")
    renamed = renamed.replace("e=pressure_trial", "e=measured_trial")
    comparison = compare_sources(source, renamed, anchored_claims=("pressure_increase",))
    assert comparison["equivalent"]
    assert comparison["mapping"]["evidence.pressure_trial"] == "evidence.measured_trial"
    assert not source_correspondence(source, renamed.replace("e=measured_trial", "e=unknown"))
    assert not source_correspondence(source, renamed.replace('valid_until "2026-09-23T11:00:00Z"', 'valid_until "2026-09-24T11:00:00Z"'))
    assert not source_correspondence(source, renamed.replace("pressure_trial_tool", "another_operator_tool"))
    assert not source_correspondence(source, renamed.replace("pressure_increase", "another_claim"), anchored_claims=("pressure_increase",))


def test_alpha_equivalence_handles_declaration_order_and_cycles_without_rewriting_literals():
    source = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool instrument { version "1"; }
evidence measured { tool instrument; kind test; environment lab; max_age 60; require "passed" == true; }
reasoning step { method "structured/1"; rationale "measured means an observation, not a replaceable literal"; }
claim outcome { statement "The trial supports this property."; environment lab; }
argument route { conclusion outcome; reasoning step; evidence measured; }
'''
    renamed = source.replace("environment lab {", "environment place {").replace("environment lab;", "environment place;")
    renamed = renamed.replace("reasoning step {", "reasoning link {").replace("reasoning step;", "reasoning link;")
    renamed = renamed.replace("argument route {", "argument derivation {")
    assert source_correspondence(source, renamed, anchored_claims=("outcome",))
    assert not source_correspondence(source, renamed.replace('"passed" == true', '"passed" == 1'))
    assert not source_correspondence(source, renamed.replace('"measured means', '"different means'))


def test_model_inputs_do_not_disclose_expected_status_or_oracle(tmp_path):
    suite = write_suite(tmp_path)
    task = load_suite(suite)["tasks"][0]
    inputs = task_inputs(task, suite.parent)
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
    suite = load_suite(write_suite(tmp_path))
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


def test_paired_harness_through_actual_mcp_with_explicit_regression_provider(tmp_path):
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

    suite = write_suite(tmp_path)
    result = asyncio.run(evaluate_models(suite, RegressionProvider(), split="development",
                                        task_ids=["pressure-trial"], per_mcp_call_usd=0, host_mode="stateless"))
    assert len(result["trials"]) == 2
    assert all(trial["score"]["correct"] for trial in result["trials"]), [(t["score"], t["report"]["stop_reason"]) for t in result["trials"]]
    assert result["trials"][0]["inputs"] == result["trials"][1]["inputs"]
    delegated = next(trial for trial in result["trials"] if trial["arm"] == "delegated")
    assert delegated["score"]["source_correspondence"]
    collection = next(event["result"] for event in delegated["report"]["tool_calls"]
                      if event["tool"] == "eal_collect" and event["status"] == "ok")
    independent = {"collection": {"records": copy.deepcopy(collection["records"])}}
    independent["collection"]["records"]["pressure_trial"]["tool_binding_digest"] = "f" * 64
    comparison = delegated["score"]["source_comparison"]
    assert evidence_trace_score(delegated["inputs"], independent, comparison,
                                delegated["report"])["verified"]
    altered = copy.deepcopy(delegated["report"])
    altered_collection = next(event["result"] for event in altered["tool_calls"]
                              if event["tool"] == "eal_collect" and event["status"] == "ok")
    altered_collection["records"]["pressure_trial"]["tool_binding_digest"] = "e" * 64
    trace = evidence_trace_score(delegated["inputs"], independent, comparison, altered)
    assert not trace["verified"] and any("local assessed tool binding" in reason for reason in trace["reasons"])
    assert delegated["cost"]["mcp_calls"] >= 3
    assert result["summary"]["delegated"]["cost_complete"]
