"""A scripted provider checks the recipient loop's real MCP boundary."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import StdioServerParameters

from eal.providers import ModelResponse, ProviderError
from eal.applicability import review_applicability_digest
from eal.recipient import RecipientBudget, run_reviewed_recipient
from eal.responses_provider import ResponsesProvider
from test_reviewed_task_route import OTHER, QUESTION, reviewed


_SOURCE_ENV = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")
               + os.pathsep + os.environ.get("PYTHONPATH", "")}


class ScriptedProvider:
    def __init__(self, replies, *, native=False, measured=True):
        self.replies = iter(replies)
        self.native = native
        self.measured = measured
        self.calls = []

    def identity(self):
        return {"provider": "scripted", "model": "no-language-model",
                "measurement_kind": "interface_only", "sampling": {},
                "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2},
                "capabilities": {"native_tools": self.native, "structured_output": "none"}}

    async def complete(self, messages, max_output_tokens):
        return await self.complete_request(messages, max_output_tokens, operations=[], native_tools=False)

    async def complete_request(self, messages, max_output_tokens, *, operations, native_tools=False):
        self.calls.append({"messages": messages, "operations": operations,
                           "native_tools": native_tools, "max_output_tokens": max_output_tokens})
        reply = next(self.replies)
        if callable(reply):
            reply = reply(messages)
        if isinstance(reply, Exception):
            raise reply
        value = reply if isinstance(reply, str) else json.dumps(reply)
        metadata = {}
        if native_tools:
            request = json.loads(value)
            metadata["native_tool_call"] = {
                "id": f"call_{len(self.calls)}", "type": "function",
                "function": {"name": request["operation"],
                             "arguments": json.dumps({key: item for key, item in request.items()
                                                      if key != "operation"})},
            }
        return ModelResponse(value, 60 if self.measured else None,
                             12 if self.measured else None,
                             model="scripted-model", metadata=metadata)


def bound_server(tmp_path, *, question=QUESTION, prepare=True):
    if prepare:
        reviewed(tmp_path)
    task_file = tmp_path / "question.txt"
    task_file.write_text(question, encoding="utf-8")
    arguments = ["-m", "eal.server", "--workspace", str(tmp_path),
                 "--registry", str(tmp_path / "tools.toml"),
                 "--artifacts", str(tmp_path / "artifacts.toml"),
                 "--families", str(tmp_path / "families.toml"),
                 "--tasks", str(tmp_path / "tasks.toml"),
                 "--recipient-task-file", str(task_file),
                 "--recipient-only", "--recipient-principal", "caller_a",
                 "--recipient-family-grant", "rig", "--recipient-task-grant", "pilot_task",
                 "--recipient-grant", "rig_pilot:accepted"]
    return StdioServerParameters(command=sys.executable, args=arguments, env=_SOURCE_ENV)


def run(question, provider, server, **kw):
    return asyncio.run(run_reviewed_recipient(question, provider, server, **kw))


def test_real_subprocess_binds_question_and_final_status_despite_false_model_prose(tmp_path):
    provider = ScriptedProvider([{"operation": "answer", "text": "The rig inspection is unsupported."}])
    report = run(QUESTION, provider, bound_server(tmp_path))
    assert report["status"] == "completed", report
    assert report["checked_answer"]["status"] == "supported"
    assert report["recipient_output_unverified"] == "The rig inspection is unsupported."
    assert report["assessment"] == report["checked_answer"]
    assert report["usage"]["total_tokens"] == 72
    assert report["usage"]["model_cost_usd"] == 0.000084
    assert report["discovered_tools"] == sorted({
        "eal_bound_task", "eal_task_candidates", "eal_assess_bound_task",
        "eal_explain_bound_task", "eal_finish_bound_task"})
    assert [event["tool"] for event in report["tool_calls"]] == [
        "eal_bound_task", "eal_task_candidates", "eal_assess_bound_task", "eal_finish_bound_task"]
    assert all("question" not in event["arguments"] and "task_id" not in event["arguments"]
               for event in report["tool_calls"])


def test_explanation_is_addressed_by_host_and_returned_to_text_model(tmp_path):
    def answer(messages):
        feedback = json.loads(messages[-1]["content"])["host_feedback"]
        assert feedback["operation"] == "explain"
        assert feedback["result"]["packet"]["status"] == "supported"
        assert "route" in feedback["result"]["arguments"]
        return {"operation": "answer", "text": "The observed test supports the scoped claim."}

    provider = ScriptedProvider([{"operation": "explain"}, answer])
    report = run(QUESTION, provider, bound_server(tmp_path))
    assert report["status"] == "completed", report
    assert report["explanation"]["packet"] == report["checked_answer"]
    assert [event["tool"] for event in report["tool_calls"]][-2:] == [
        "eal_explain_bound_task", "eal_finish_bound_task"]
    assert report["usage"]["total_tokens"] == 144


def test_original_question_mismatch_never_assesses_or_calls_model(tmp_path):
    provider = ScriptedProvider([])
    report = run(OTHER, provider, bound_server(tmp_path))
    assert report["stop_reason"] == "bound_question_or_review_mismatch", report
    assert report["assessment"] is None and provider.calls == []
    assert [event["tool"] for event in report["tool_calls"]] == ["eal_bound_task"]


def test_advisory_candidate_failure_does_not_block_exact_reviewed_task(tmp_path):
    host, _ = reviewed(tmp_path)
    question = "机组检验？"
    original = review_applicability_digest(host.families, "pilot_task", QUESTION,
                                            "rig", {"site": "pilot"}, "accepted")
    revised = review_applicability_digest(host.families, "pilot_task", question,
                                           "rig", {"site": "pilot"}, "accepted")
    manifest = tmp_path / "tasks.toml"
    manifest.write_text(manifest.read_text().replace(json.dumps(QUESTION), json.dumps(question))
                        .replace(original, revised))
    provider = ScriptedProvider([{"operation": "answer", "text": "The checked result is supported."}])
    report = run(question, provider, bound_server(tmp_path, question=question, prepare=False))
    assert report["status"] == "completed", report
    assert report["candidate_error"] == "reviewed_mcp_tool_failed"
    assert report["checked_answer"]["status"] == "supported"


def test_model_cannot_supply_new_task_or_status_fields(tmp_path):
    provider = ScriptedProvider([{"operation": "answer", "text": "Yes", "task_id": "maintenance_task",
                                  "status": "supported"}])
    report = run(QUESTION, provider, bound_server(tmp_path), budget=RecipientBudget(max_repairs=0))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == "repair_budget_exhausted"
    assert report["recipient_output_unverified"] is None
    assert report["checked_answer"]["status"] == "supported"
    assert sum(event["tool"] == "eal_assess_bound_task" for event in report["tool_calls"]) == 1


def test_native_function_call_feedback_preserves_call_id_and_bound_status(tmp_path):
    def answer(messages):
        assert messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == "call_1"
        feedback = json.loads(messages[-1]["content"])
        assert feedback["result"]["packet"]["status"] == "supported"
        return {"operation": "answer", "text": "A checked observation supports the claim."}

    provider = ScriptedProvider([{"operation": "explain"}, answer], native=True)
    report = run(QUESTION, provider, bound_server(tmp_path), interaction_mode="native")
    assert report["status"] == "completed", report
    assert report["checked_answer"]["status"] == "supported"
    assert all(call["native_tools"] for call in provider.calls)


def test_responses_provider_native_replays_reasoning_and_bound_explanation(tmp_path):
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["store"] is False and payload["tool_choice"] == "required"
        assert {tool["name"] for tool in payload["tools"]} == {"answer", "explain", "stop"}
        assert all("operation" not in tool["parameters"]["properties"] for tool in payload["tools"])
        if len(requests) == 1:
            output = [
                {"type": "reasoning", "id": "rs-1", "encrypted_content": "opaque"},
                {"type": "function_call", "id": "fc-1", "call_id": "call-1",
                 "name": "explain", "arguments": "{}"},
            ]
        else:
            previous = payload["input"][-3:]
            assert previous[0] == {"type": "reasoning", "id": "rs-1", "encrypted_content": "opaque"}
            assert previous[1]["type"] == "function_call" and previous[1]["call_id"] == "call-1"
            assert previous[2]["type"] == "function_call_output"
            assert previous[2]["call_id"] == "call-1"
            feedback = json.loads(previous[2]["output"])
            assert feedback["operation"] == "explain"
            assert feedback["result"]["packet"]["status"] == "supported"
            output = [{"type": "function_call", "id": "fc-2", "call_id": "call-2",
                       "name": "answer", "arguments": '{"text":"The checked test supports the scoped claim."}'}]
        return httpx.Response(200, json={
            "id": f"resp-{len(requests)}", "model": "mock-responses-model", "status": "completed",
            "output": output, "usage": {"input_tokens": 60, "output_tokens": 12},
        })

    provider = ResponsesProvider(model="mock-responses-model", api_key_env=None,
                                 capabilities={"native_tools": True},
                                 pricing={"input_usd_per_million": 1, "output_usd_per_million": 2},
                                 transport=httpx.MockTransport(handler))
    report = run(QUESTION, provider, bound_server(tmp_path), interaction_mode="native",
                 budget=RecipientBudget(max_model_turns=2, max_total_tokens=150))
    assert report["status"] == "completed", report
    assert report["recipient_output_unverified"] == "The checked test supports the scoped claim."
    assert report["checked_answer"]["status"] == "supported"
    assert report["usage"]["total_tokens"] == 144
    assert len(requests) == 2
    assert "responses_replay_handle" not in json.dumps(report)
    assert "_responses_replay_handle" not in json.dumps(report)
    assert "opaque" not in json.dumps(report)
    assert provider._replay_items == {}


def test_model_token_budget_stops_after_explanation_and_still_finalises(tmp_path):
    provider = ScriptedProvider([{"operation": "explain"},
                                 {"operation": "answer", "text": "Should not be called"}])
    report = run(QUESTION, provider, bound_server(tmp_path),
                 budget=RecipientBudget(max_total_tokens=72))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == "token_budget_exhausted"
    assert report["explanation"]["packet"] == report["checked_answer"]
    assert len(provider.calls) == 1


def test_provider_failure_retains_checked_status_and_unknown_usage(tmp_path):
    provider = ScriptedProvider([ProviderError("provider failed")])
    report = run(QUESTION, provider, bound_server(tmp_path))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == "provider_error"
    assert report["checked_answer"]["status"] == "supported"
    assert report["usage"]["total_tokens"] is None
    assert report["usage"]["model_cost_usd"] is None


def test_shared_or_legacy_endpoint_is_rejected_before_assessment(tmp_path):
    reviewed(tmp_path)
    server = StdioServerParameters(command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path),
              "--registry", str(tmp_path / "tools.toml"),
              "--artifacts", str(tmp_path / "artifacts.toml"),
              "--recipient-only", "--recipient-principal", "caller_a",
              "--recipient-grant", "rig_pilot:accepted"], env=_SOURCE_ENV)
    provider = ScriptedProvider([])
    report = run(QUESTION, provider, server)
    assert report["stop_reason"] == "dedicated_reviewed_endpoint_required"
    assert report["tool_calls"] == [] and provider.calls == []
