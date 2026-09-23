"""Scripted clients test the interaction boundary, not language-model capability."""
import asyncio
import json
import os
import sys

import pytest
from mcp import StdioServerParameters

from eal.agent import AgentBudget, run_agent, run_unaided
from eal.providers import ModelResponse, ProviderError


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence measured { tool runner; kind test; environment lab; max_age 60; require "passed" == true; }
reasoning measurement { method "structured/1"; rationale "The bounded observation supplies support."; }
claim works { statement "The requested check passes."; environment lab; }
argument result { conclusion works; reasoning measurement; evidence measured; }
'''


class ScriptedProvider:
    def __init__(self, replies, *, measured=True):
        self.replies = iter(replies)
        self.measured = measured

    def identity(self):
        return {"provider": "scripted-interface", "model": "no-language-model", "measurement_kind": "interface_only",
                "sampling": {}, "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2}}

    async def complete(self, messages, max_output_tokens):
        reply = next(self.replies)
        if callable(reply):
            reply = reply(messages)
        if isinstance(reply, Exception):
            raise reply
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return ModelResponse(text, 100 if self.measured else None, 10 if self.measured else None, model="no-language-model")


def feedback_result(messages, operation):
    for message in reversed(messages):
        if message["role"] == "user":
            value = json.loads(message["content"])
            feedback = value.get("host_feedback", {})
            if feedback.get("operation") == operation:
                return feedback["result"]
    raise AssertionError(f"No {operation} feedback")


def finish(messages):
    return {"operation": "finish", "assessment_id": feedback_result(messages, "reason")["assessment_id"], "claims": ["works"]}


def server(tmp_path, *, observation=True):
    args = ["-m", "eal.server", "--workspace", str(tmp_path)]
    if observation:
        script = tmp_path / "tool.py"
        script.write_text("import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'value':{'passed':True}}))\n")
        registry = tmp_path / "tools.toml"
        registry.write_text('[tools.runner]\nkind="command"\nmode="deterministic"\nversion="1"\nargv=' + json.dumps([sys.executable, str(script)]) + '\n')
        args += ["--registry", str(registry)]
    return StdioServerParameters(command=sys.executable, args=args, env=dict(os.environ))


def reason(messages):
    return {"operation": "reason", "source": SOURCE, "context": {"site": "bench"},
            "collection_id": feedback_result(messages, "collect")["collection_id"]}


def test_real_persistent_mcp_loop_repairs_collects_reasons_explains_and_finishes(tmp_path):
    provider = ScriptedProvider([
        "not JSON",
        {"operation": "validate", "source": SOURCE.replace("conclusion works", "conclusion absent")},
        {"operation": "validate", "source": SOURCE},
        {"operation": "collect", "source": SOURCE, "context": {"site": "bench"}},
        reason,
        lambda messages: {"operation": "explain", "assessment_id": feedback_result(messages, "reason")["assessment_id"], "claim": "works"},
        finish,
    ])
    report = asyncio.run(run_agent("Check works from actual observation", provider, server(tmp_path), required_claims=("works",), host_mode="stateless"))
    assert report["status"] == "completed", report
    assert report["final"]["claims"]["works"]["status"] == "supported"
    assert report["final"]["verification"] == "server_assessment"
    assert report["task_correspondence"] == "unverified"
    assert report["repairs"] == 2
    assert len(report["attempts"]) == 7
    assert report["usage"]["total_tokens"] == 770
    assert report["usage"]["model_cost_usd"] == pytest.approx(0.00084)
    assert report["usage"]["total_cost_usd"] is None
    tools = [event["tool"] for event in report["tool_calls"]]
    assert tools.count("eal_collect") == 1 and tools.count("eal_reason") == 1 and tools.count("eal_explain") == 1
    assert report["protocol_version"] == "2025-11-25"


def test_model_discovery_uses_exact_host_operations_and_deduplicates_identical_reference(tmp_path):
    from eal.discovery import describe_language

    def inspect_prompt(messages):
        system = messages[0]["content"]
        assert "eal_validate" not in system
        assert '"operation":"validate"' in system
        assert '"const":"validate"' in system
        assert '"operation":"collect"' in system
        assert '"operation":"reason"' in system
        assert '"operation":"explain"' in system
        assert '"operation":"assess"' in system
        assert '"operation":"finish"' in system
        assert "Correct that request yourself" in system
        description = feedback_result(messages, "describe")
        assert description["language_reference_verified"] is True
        assert description["reference"] == "initial_data.language_reference"
        assert "grammar" not in description
        return {"operation": "stop", "reason": "Interface inspection complete"}

    report = asyncio.run(run_agent("Inspect the operation contract", ScriptedProvider([inspect_prompt]), server(tmp_path),
                                   initial_data={"language_reference": describe_language()}))
    assert report["stop_reason"] == "model_stopped", report
    assert "eal_validate" in {tool["name"] for tool in report["discovered_tools"]}
    assert "validate" in {tool["operation"] for tool in report["host_operations"]}
    assert report["tool_calls"][0]["tool"] == "eal_describe"
    assert report["tool_calls"][0]["result"] == describe_language()


def test_fixed_task_source_context_and_time_cannot_be_replaced(tmp_path):
    now = "2026-09-23T12:00:00Z"
    provider = ScriptedProvider([
        {"operation": "reason", "source": SOURCE.replace("requested check", "different check"), "context": {"site": "bench"}, "now": now},
        {"operation": "reason", "source": SOURCE, "context": {"site": "other"}, "now": now},
        {"operation": "reason", "source": SOURCE, "context": {"site": "bench"}},
        {"operation": "reason", "source": SOURCE, "context": {"site": "bench"}, "now": now},
        finish,
    ])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path, observation=False), required_claims=("works",),
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}, "now": now}, host_mode="stateless"))
    assert report["status"] == "completed", report
    assert report["repairs"] == 3
    assert report["task_correspondence"] == "source_anchored"
    assert report["final"]["claims"]["works"]["status"] == "unsupported"
    assert report["final"]["source"] == SOURCE
    assert report["final"]["assessed_at"] == now


def test_final_status_cannot_be_asserted_and_old_assessment_cannot_be_reused(tmp_path):
    saved = {}

    def invent_status(messages):
        request = finish(messages)
        saved.update(request)
        return {**request, "status": "supported"}

    provider = ScriptedProvider([
        {"operation": "reason", "source": SOURCE, "context": {"site": "bench"}}, invent_status,
        {"operation": "collect", "source": SOURCE, "context": {"site": "bench"}},
        lambda _: saved,
        {"operation": "stop", "reason": "Need a new assessment"},
    ])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), host_mode="stateless"))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == "model_stopped", report
    assert report["final"] is None
    assert report["repairs"] == 2


def test_unknown_provider_usage_is_not_zero_and_blocks_unbounded_retries(tmp_path):
    provider = ScriptedProvider([ProviderError("temporary failure")])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path)))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == "token_usage_unavailable", report
    assert report["usage"]["total_tokens"] is None
    assert report["usage"]["model_cost_usd"] is None
    assert report["attempts"][0]["status"] == "provider_error"


@pytest.mark.parametrize("budget,replies,expected", [
    (AgentBudget(max_iterations=1), ["bad"], "iteration_budget_exhausted"),
    (AgentBudget(max_repairs=0), ["bad"], "repair_budget_exhausted"),
    (AgentBudget(max_total_tokens=20), ["bad"], "token_budget_exhausted"),
    (AgentBudget(max_response_bytes=2), ["bad"], "repair_budget_exhausted"),
])
def test_budget_exhaustion_is_explicit(tmp_path, budget, replies, expected):
    if budget.max_response_bytes == 2:
        budget = AgentBudget(max_response_bytes=2, max_repairs=0)
    report = asyncio.run(run_agent("Check works", ScriptedProvider(replies), server(tmp_path), budget=budget))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == expected, report


def test_unaided_comparison_has_same_usage_accounting_but_unverified_answer():
    provider = ScriptedProvider(["bad", {"claims": {"works": "supported"}}])
    report = asyncio.run(run_unaided("Check works", provider, required_claims=("works",)))
    assert report["status"] == "completed"
    assert report["final"]["verification"] == "unverified_model_answer"
    assert report["usage"]["total_tokens"] == 220
    assert report["repairs"] == 1
    assert report["tool_calls"] == []


def test_elapsed_deadline_cancels_generation_and_records_attempt():
    class Slow(ScriptedProvider):
        async def complete(self, messages, max_output_tokens):
            await asyncio.sleep(10)
            raise AssertionError("deadline failed")

    report = asyncio.run(run_unaided("Check works", Slow([]), budget=AgentBudget(max_elapsed_seconds=0.02)))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == "elapsed_time_budget_exhausted", report
    assert report["attempts"][0]["status"] == "cancelled"


def test_stateful_workflow_preserves_exact_source_without_copying_source_or_ids(tmp_path):
    provider = ScriptedProvider([{"operation": op} for op in ("validate", "collect", "reason", "explain", "finish")])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["host_mode"] == "stateful" and report["repairs"] == 0
    assert report["final"]["source"] == SOURCE and report["final"]["source"].endswith("\n")
    assert report["final"]["claims"]["works"]["status"] == "supported"
    calls = {entry["tool"]: entry for entry in report["tool_calls"]}
    assert calls["eal_reason"]["arguments"]["collection_id"] == calls["eal_collect"]["result"]["collection_id"]
    assert calls["eal_explain"]["arguments"]["assessment_id"] == report["final"]["assessment_id"]
    assert all("source" not in json.loads(attempt["text"]) for attempt in report["attempts"])


def test_stateful_explicit_null_collection_differs_from_omission(tmp_path):
    provider = ScriptedProvider([
        {"operation": "collect"}, {"operation": "reason", "collection_id": None},
        {"operation": "reason"}, {"operation": "finish"},
    ])
    report = asyncio.run(run_agent("Check observation use", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}}))
    assessments = [entry for entry in report["tool_calls"] if entry["tool"] == "eal_reason"]
    assert report["status"] == "completed", report
    assert assessments[0]["arguments"]["collection_id"] is None
    assert assessments[0]["result"]["claims"]["works"]["status"] == "unsupported"
    assert isinstance(assessments[1]["arguments"]["collection_id"], str)
    assert assessments[1]["result"]["claims"]["works"]["status"] == "supported"


def test_stateful_draft_repair_is_explicit_and_revalidates(tmp_path):
    draft = SOURCE.replace("conclusion works", "conclusion absent")
    provider = ScriptedProvider([
        {"operation": "validate"},
        {"operation": "revise", "replacements": [{"old": "conclusion absent", "new": "conclusion works"}]},
        {"operation": "validate"}, {"operation": "collect"}, {"operation": "reason"}, {"operation": "finish"},
    ])
    report = asyncio.run(run_agent("Repair the missing conclusion reference", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"draft_source": draft, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["final"]["source"] == SOURCE
    assert report["repairs"] == 1 and report["task_correspondence"] == "unverified"
    assert report["source_revisions"][0]["replacements"] == [{"old": "conclusion absent", "new": "conclusion works"}]


def test_stateful_revision_invalidates_old_observations_and_assessment(tmp_path):
    provider = ScriptedProvider([
        {"operation": "collect"}, {"operation": "reason"},
        {"operation": "revise", "replacements": [{"old": "requested check", "new": "specified check"}]},
        {"operation": "finish"}, {"operation": "reason"}, {"operation": "finish"},
    ])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"draft_source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["repairs"] == 1
    reasons = [entry for entry in report["tool_calls"] if entry["tool"] == "eal_reason"]
    assert reasons[0]["result"]["claims"]["works"]["status"] == "supported"
    assert "collection_id" not in reasons[1]["arguments"]
    assert report["final"]["claims"]["works"]["status"] == "unsupported"


def test_stateful_replacements_are_atomic_and_fixed_source_is_immutable(tmp_path):
    for anchored in (True, False):
        provider = ScriptedProvider([
            {"operation": "revise", "replacements": [{"old": "requested check", "new": "changed claim"}, {"old": "does not occur", "new": "replacement"}]},
            {"operation": "stop", "reason": "End interface test"},
        ])
        report = asyncio.run(run_agent("Preserve the original", provider, server(tmp_path),
                                       initial_data={"source" if anchored else "draft_source": SOURCE}))
        assert report["source_revisions"] == []
        assert report["repairs"] == 1
        import hashlib
        assert report["active_state"]["source_digest"] == hashlib.sha256(SOURCE.encode()).hexdigest()


def test_native_function_calls_use_same_state_and_real_mcp(tmp_path):
    import httpx
    from eal.providers import ChatCompletionsProvider

    operations = iter(("validate", "collect", "reason", "explain", "finish"))
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        operation = next(operations)
        if calls:
            assert payload["messages"][-1]["role"] == "tool"
            assert payload["messages"][-1]["tool_call_id"] == f"call-{len(calls)}"
            assert payload["messages"][-2]["tool_calls"][0]["id"] == f"call-{len(calls)}"
        functions = {entry["function"]["name"]: entry["function"] for entry in payload["tools"]}
        assert "operation" not in functions[operation]["parameters"]["properties"]
        assert payload["parallel_tool_calls"] is False and payload["tool_choice"] == "required"
        calls.append(operation)
        return httpx.Response(200, json={"model": "native-interface-fixture", "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            "choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": f"call-{len(calls)}", "type": "function", "function": {"name": operation, "arguments": "{}"}}]}}]})

    provider = ChatCompletionsProvider(model="native-interface-fixture", api_key_env=None, capabilities={"native_tools": True},
                                      transport=httpx.MockTransport(respond))
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",), interaction_mode="native",
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["final"]["claims"]["works"]["status"] == "supported"
    assert calls == ["validate", "collect", "reason", "explain", "finish"]
    assert report["conversation"][-1]["role"] == "tool"
    assert report["usage"]["total_tokens"] == 550


def test_native_interaction_requires_configured_capability(tmp_path):
    report = asyncio.run(run_agent("Check works", ScriptedProvider([]), server(tmp_path), interaction_mode="native"))
    assert report["stop_reason"] == "native_tool_capability_unavailable"
    assert report["attempts"] == []


def test_compact_feedback_preserves_conflict_missing_assumptions_and_bound_results():
    from eal.agent import _compact_feedback

    proposition = {"subject": "pipe", "quantity": "pressure", "unit": "kPa", "result": {"expected": 20}}
    original = {"operation": "reason", "is_error": False, "result": {
        "claims": {"pressure": {"status": "contested", "reasons": ["Active objection"], "proposition": proposition}},
        "assumptions": {"calibration": {"status": "unsupported", "reasons": ["Validation expired"]}},
        "objections": {"sensor_fault": {"status": "active", "target": "pressure"}},
        "arguments": {"derivation": {"status": "contested", "conclusion": "pressure", "dependencies": {"assumptions": ["calibration"]},
            "reasoning_result": {"status": "supported", "reasons": ["Model-conditional computation"],
                "method_contract": {"identifier": "causal/test", "input_schema": {"large": "schema"}, "quantity_interpretation": "model-conditional"},
                "binding": {"actual": 12, "output_unit": "kPa", "status": "supported", "proposition": proposition,
                            "formal_query": {"large": "input"}, "method_contract": {"duplicate": "schema"}},
                "details": {"assumptions_verified": False, "counterexample": {"A": False}, "samples": list(range(3000))}}}},
        "dialectic": {"nodes": {"derivation": "rejected"}, "trace": [{"round": 1}]},
    }}
    compact = _compact_feedback(original)
    result = compact["result"]
    assert result["claims"] == original["result"]["claims"]
    assert result["assumptions"] == original["result"]["assumptions"]
    assert result["objections"] == original["result"]["objections"]
    calculation = result["arguments"]["derivation"]["reasoning_result"]
    assert calculation["binding"]["actual"] == 12 and calculation["binding"]["output_unit"] == "kPa"
    assert calculation["details"]["assumptions_verified"] is False
    assert calculation["details"]["counterexample"] == {"A": False}
    assert calculation["detail_fields_available_in_full_explanation"] == ["samples"]
    assert "method_contract" not in calculation and "formal_query" not in calculation["binding"]
    assert result["full_explanation"] == {"operation": "explain", "detail": "full"}
    assert "trace" in original["result"]["dialectic"]  # Raw persisted result remains intact.


def test_full_explanation_is_retrieved_on_explicit_request(tmp_path):
    provider = ScriptedProvider([
        {"operation": "collect"}, {"operation": "reason"}, {"operation": "explain", "detail": "full"}, {"operation": "finish"},
    ])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    feedback = [json.loads(m["content"])["host_feedback"] for m in report["conversation"] if m["role"] == "user" and "host_feedback" in json.loads(m["content"])]
    assert next(item for item in feedback if item.get("operation") == "reason")["feedback_detail"] == "summary"
    assert "feedback_detail" not in next(item for item in feedback if item.get("operation") == "explain")
    assert "detail" not in next(call for call in report["tool_calls"] if call["tool"] == "eal_explain")["arguments"]


def test_assess_delegates_complete_workflow_and_finish_uses_exact_checked_result(tmp_path):
    provider = ScriptedProvider([{"operation": "assess"}, {"operation": "finish"}])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["final"]["source"] == SOURCE
    assert report["final"]["claims"]["works"]["status"] == "supported"
    assert [call["tool"] for call in report["tool_calls"] if call["tool"] != "eal_describe"] == [
        "eal_validate", "eal_collect", "eal_reason", "eal_explain"]
    assert len(report["attempts"]) == 2
    for entry in report["host_operations"]:
        if entry["operation"] in {"collect", "reason", "explain", "finish"}:
            assert not {"source", "context", "assessment_id"} & entry["input_schema"]["properties"].keys()
    feedback = feedback_result(report["conversation"], "assess")
    assert feedback["claims"]["works"]["status"] == "supported"
    assess_message = next(json.loads(m["content"])["host_feedback"] for m in report["conversation"]
                          if m["role"] == "user" and json.loads(m["content"]).get("host_feedback", {}).get("operation") == "assess")
    assert assess_message["next_request"] == {"operation": "finish"}


def test_assess_invalid_source_stops_before_collection_and_reports_diagnostics(tmp_path):
    provider = ScriptedProvider([{"operation": "assess"}, {"operation": "stop", "reason": "Invalid draft needs explicit repair"}])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",),
        initial_data={"draft_source": SOURCE.replace("conclusion works", "conclusion absent"), "context": {"site": "bench"}}))
    assert report["status"] == "incomplete" and report["repairs"] == 1
    assert [call["tool"] for call in report["tool_calls"] if call["tool"] != "eal_describe"] == ["eal_validate"]
    assert report["tool_calls"][-1]["result"]["diagnostics"]
    assert report["active_state"]["assessment_available"] is False


def test_assess_observation_failure_stays_unsupported(tmp_path):
    provider = ScriptedProvider([{"operation": "assess"}, {"operation": "finish"}])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path, observation=False), required_claims=("works",),
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["final"]["claims"]["works"]["status"] == "unsupported"
    collected = next(call["result"] for call in report["tool_calls"] if call["tool"] == "eal_collect")
    assert collected["records"]["measured"]["status"] == "error"


def test_assess_counts_every_call_against_budget_and_cannot_reuse_old_assessment(tmp_path):
    provider = ScriptedProvider([{"operation": "assess"}, {"operation": "assess"}])
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path), required_claims=("works",),
        initial_data={"source": SOURCE, "context": {"site": "bench"}}, budget=AgentBudget(max_tool_calls=6)))
    assert report["status"] == "incomplete" and report["stop_reason"] == "tool_call_budget_exhausted"
    assert len(report["tool_calls"]) == 6  # describe + first workflow + second validation
    assert report["active_state"]["assessment_available"] is False


def test_metadata_cannot_replace_active_draft_and_invalid_candidate_is_transactional(tmp_path):
    import hashlib
    digest = hashlib.sha256(SOURCE.encode()).hexdigest()
    provider = ScriptedProvider([
        {"operation": "validate", "source": digest},
        {"operation": "collect", "source": "initial_data"},
        {"operation": "reason", "source": digest},
        {"operation": "assess"}, {"operation": "finish"},
    ])
    report = asyncio.run(run_agent("Preserve this draft", provider, server(tmp_path), required_claims=("works",),
                                   initial_data={"draft_source": SOURCE, "context": {"site": "bench"}}))
    assert report["status"] == "completed", report
    assert report["final"]["source"] == SOURCE and report["repairs"] == 3
    assert report["source_revisions"] == []
    failures = [json.loads(message["content"])["host_feedback"] for message in report["conversation"]
                if message["role"] == "user" and json.loads(message["content"]).get("host_feedback", {}).get("is_error")]
    assert all(failure["active_state"]["source_digest"] == digest for failure in failures)
    assert all(failure["next_request"] == {"operation": "assess"} for failure in failures)
    assert all("hashes are metadata" in failure["next_action"] for failure in failures)
