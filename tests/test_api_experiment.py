"""Experiment controls: real loopback HTTP/MCP, with mocked paid provider calls."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from eal.formatter import semantic_ir
from eal.parser import parse
from eal.responses_provider import ResponsesProvider

from experiments.api_load_test.analysis import decision_interval, paired_interval, summarise
from experiments.api_load_test.api import serve
from experiments.api_load_test.materials import ARMS, PROFILES, prompt_for, source_for
from experiments.api_load_test.oracle import grade, reference
from experiments.api_load_test.routes import TrialTools, child_environment
from experiments.api_load_test.runner import Budget, HERE, run, schedule, trial


PLAN = json.loads((HERE / "plan.json").read_text())
SPEC = json.loads((HERE / "models.json").read_text())["models"][0]


def arguments(api, run_id="unit-test", count=100):
    workload = {"service": "orders-api", "build_id": api["build_id"], "run_id": run_id,
                "concurrent_clients": 10, "request_count": count, "timeout_seconds": 3}
    context = {key: workload[key] for key in ("service", "build_id", "run_id")}
    context["dataset"] = "measured_controlled_api"
    return workload, context


def test_json_represents_the_exact_eal_argument_without_executing_it():
    workload, context = arguments({"build_id": "abc"})
    source = source_for(workload, context)
    prompt = prompt_for("json_prompt", source, workload)
    assert json.loads(prompt.split("\n\n", 1)[1]) == json.loads(json.dumps(semantic_ir(parse(source))))
    assert len({prompt_for(arm, source, workload) for arm in ARMS}) == 5


def test_every_assignment_is_preserved_and_arm_order_is_block_randomised():
    assigned = schedule(SPEC["id"], 3, 42)
    assert assigned == schedule(SPEC["id"], 3, 42)
    assert len(assigned) == 60 == len({row["id"] for row in assigned})
    for block in {row["block"] for row in assigned}:
        assert {row["arm"] for row in assigned if row["block"] == block} == set(ARMS)
    assert assigned != schedule(SPEC["id"], 3, 43)


@pytest.mark.parametrize("arm", ["json_prompt", "eal_mcp"])
def test_real_http_routes_agree_with_independent_reference(tmp_path, arm, monkeypatch):
    with serve(PROFILES["errors"], "unit-test") as api:
        workload, context = arguments(api)
        tools = TrialTools(tmp_path, source_for(workload, context),
                           {"port": api["port"], "input": workload, "context": context})
        if arm == "json_prompt":
            async def forbidden():
                raise AssertionError("JSON must never use MCP")
            monkeypatch.setattr(tools, "_mcp", forbidden)
        packet = asyncio.run(tools.execute(arm))
        report = json.loads(tools.report_path.read_text())
        truth = reference(report, workload, context, tools.assessed_at)
        assert packet["metrics"] == truth["metrics"]
        assert truth["status"] == "unsupported"
        assert packet["metrics"]["error_rate_percent"] == 10
        assert len(api["events"]) == 100
        assert asyncio.run(tools.execute(arm)) == packet
        assert len(api["events"]) == 100  # no favourable rerun
        if arm == "json_prompt":
            assert "status" not in packet and tools.host_status is None
            assert all(row.get("route") != "mcp_stdio" for row in tools.trace)
        else:
            assert tools.host_status == "unsupported"
            assert [row["tool"] for row in tools.trace if "tool" in row] == [
                "eal_validate", "eal_collect", "eal_reason", "eal_explain"]


def test_reference_thresholds_identity_and_freshness():
    workload, context = arguments({"build_id": "abc"})
    rows = [{"request_id": i, "elapsed_ms": 200, "status_code": 500 if i == 99 else 200,
             "identity_matches": True} for i in range(100)]
    report = {"input": workload, "context": context, "requests": rows, "observed_at": "2026-09-25T12:00:00Z"}
    result = reference(report, workload, context, "2026-09-25T12:05:00Z")
    assert result["status"] == "supported"
    assert reference(report, workload, context, "2026-09-25T12:05:01Z")["status"] == "unsupported"
    rows[0]["status_code"] = 0
    assert reference(report, workload, context, report["observed_at"])["status"] == "unsupported"
    rows[0]["status_code"] = 200
    for row in rows[:6]:
        row["elapsed_ms"] = 200.001
    assert reference(report, workload, context, report["observed_at"])["checks"]["latency"] is False
    report["input"] = {**workload, "build_id": "another-build"}
    assert reference(report, workload, context, report["observed_at"])["checks"]["identity"] is False


def test_credentials_do_not_enter_collector_or_mcp_environments(monkeypatch):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-github-secret")
    assert "TOKEN" not in json.dumps(child_environment())


@pytest.mark.parametrize("arm", ["eal_mcp", "json_prompt", "plain_brief"])
def test_native_provider_to_real_tool_to_scored_answer(tmp_path, monkeypatch, arm):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    requests = []

    def response(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["store"] is False
        assert "mcp" not in {tool["type"] for tool in payload["tools"]}
        if len(requests) == 1:
            name = "assess_load_test" if arm == "eal_mcp" else "run_load_test"
            arguments = {}
        else:
            packet = json.loads(payload["input"][-1]["output"])
            assert ("status" in packet) == (arm == "eal_mcp")
            name = "finish"
            arguments = {"status": "unsupported", "request_count": packet["metrics"]["request_count"],
                         "p95_ms": packet["metrics"]["p95_ms"],
                         "error_rate_percent": packet["metrics"]["error_rate_percent"],
                         "explanation": "The measured run has too few requests."}
        return httpx.Response(200, json={"id": f"response-{len(requests)}", "model": SPEC["id"], "status": "completed",
            "output": [{"type": "function_call", "call_id": f"call-{len(requests)}", "name": name,
                        "arguments": json.dumps(arguments)}],
            "usage": {"input_tokens": 300, "output_tokens": 60, "input_tokens_details": {"cached_tokens": 0}}})

    provider = ResponsesProvider(model=SPEC["id"], api_key_env="OPENAI_API_TOKEN",
                                 capabilities={"native_tools": True}, pricing=SPEC["pricing"],
                                 transport=httpx.MockTransport(response))
    plan = {**PLAN, "minimum_call_interval_seconds": 0}
    assignment = {"id": "unit-trial", "model": SPEC["id"], "repeat": 0,
                  "profile": "short_run", "block": "0:short_run", "arm": arm}
    result = asyncio.run(trial(assignment, SPEC, plan, tmp_path, provider, Budget(5)))
    assert result["state"] == "complete"
    assert result["outcome"]["correct"] is True
    assert len(result["model_calls"]) == 2
    assert "unit-test-secret" not in (tmp_path / "trial.json").read_text()


def test_missing_key_keeps_all_assignments_and_has_no_fake_results(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_TOKEN", raising=False)
    output = tmp_path / "missing-key"
    assert asyncio.run(run(output, [SPEC], PLAN, mode="smoke")) is False
    summary = summarise(output)
    assert summary["assigned"] == 20
    assert summary["complete"] is False
    assert all(cell["completed"] == cell["correct"] == cell["model_calls"] == 0 for cell in summary["cells"])


def test_no_collection_or_numeric_fabrication_cannot_pass():
    truth = {"status": "supported", "metrics": {"request_count": 100, "p95_ms": 50, "error_rate_percent": 0}}
    answer = {"status": "supported", **truth["metrics"]}
    assert grade(answer, truth, collected=False)["correct"] is False
    assert grade({**answer, "p95_ms": 0}, truth, collected=True)["correct"] is False
    assert grade(answer, truth, collected=True)["correct"] is True


def test_budget_and_small_sample_analysis_do_not_claim_success():
    budget = Budget(0.000001)
    with pytest.raises(ValueError, match="allowance"):
        budget.reserve([], [], 4096, SPEC["pricing"])
    assert paired_interval([{"profile": key, "difference": 1} for key in PROFILES],
                           alpha=0.05, seed=1, draws=100) is None


def test_decision_bound_preserves_uncertainty_at_ceiling():
    pairs = [{"profile": name, "difference": 0} for name in PROFILES for _ in range(10)]
    bound = decision_interval(pairs, alpha=0.05 / 8)
    assert bound[0] < -0.53 and bound[1] > 0.53
    assert decision_interval(pairs[:4], alpha=0.05) is None


def test_provider_failure_retains_unattempted_assignments(tmp_path, monkeypatch):
    from eal.providers import ProviderError
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")

    class FailingProvider:
        async def complete_request(self, *args, **kwargs):
            raise ProviderError("Synthetic unit-test provider outage")

        def discard_replay_handles(self, handles):
            pass

    output = tmp_path / "outage"
    assert asyncio.run(run(output, [SPEC], PLAN, mode="smoke",
                           provider_factory=lambda *_: FailingProvider())) is False
    records = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert len(records) == 20
    assert sum(row["state"] == "failed" for row in records) == 1
    assert sum(row["state"] == "not_attempted" for row in records) == 19
    assert all(not row["outcome"]["correct"] for row in records)
    assert summarise(output)["complete"] is False
