"""Scripted clients test the interaction boundary, not language-model capability."""
import asyncio
import json
import os
import sys

import pytest
from mcp import StdioServerParameters

from eal.agent import AgentBudget, run_agent, run_unaided
from eal.providers import ModelResponse, ProviderError


SOURCE = '''language "EAL/0.1";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence measured { tool runner; kind test; environment lab; max_age 60; require "passed" == true; }
reasoning measurement { mode structured; rationale "The bounded observation supplies support."; }
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
    report = asyncio.run(run_agent("Check works from actual observation", provider, server(tmp_path), required_claims=("works",)))
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
                                   initial_data={"source": SOURCE, "context": {"site": "bench"}, "now": now}))
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
    report = asyncio.run(run_agent("Check works", provider, server(tmp_path)))
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
