"""Bounded provider recovery and checked finalisation through the real runner."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from eal.providers import ModelResponse, ProviderError
from eal.responses_provider import ResponsesProvider
from experiments.api_load_test import runner
from experiments.api_load_test.cases import build_cases, case_specs
from experiments.api_load_test.oracle import reference


PLAN = {**json.loads((runner.HERE / "plan.json").read_text()),
        "finalisation": "model", "max_provider_retries_per_trial": 2,
        "provider_retry_delays_seconds": [0, 0], "max_consecutive_transient_failures": 3,
        "minimum_call_interval_seconds": 0}
SPEC = json.loads((runner.HERE / "models.json").read_text())["models"][0]


@pytest.fixture(scope="module")
def measured_case(tmp_path_factory):
    selected = next(row for row in case_specs("pilot") if row["family"] == "errors")
    return build_cases(tmp_path_factory.mktemp("recovery-cases") / "cases", [selected], PLAN["seed"])[0]


def assignment(case, arm="plain_validator"):
    return {"id": "recovery", "model": SPEC["id"], "repeat": 0, "transport": "text",
            "case_id": case["id"], "case_family": case["family"], "block": case["id"], "arm": arm}


def model_response(operation):
    return ModelResponse(json.dumps(operation), 100, 20, SPEC["id"])


class Replies:
    def __init__(self, replies):
        self.replies, self.calls = iter(replies), 0

    def identity(self):
        return {"pricing": SPEC["pricing"]}

    async def complete_request(self, *args, **kwargs):
        self.calls += 1
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return model_response(reply)

    def discard_replay_handles(self, handles):
        pass


def finish(case):
    truth = reference(case)
    return {"operation": "finish", **{key: truth[key] for key in
            ("status", "metrics", "failed_checks", "unknown_checks")}}


@pytest.mark.parametrize("failed_call", [1, 2])
def test_http_503_then_success_keeps_unknown_charge_and_retries_same_request(
        tmp_path, monkeypatch, measured_case, failed_call):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unused-mock-secret")
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == failed_call:
            return httpx.Response(503, json={"error": {"message": "synthetic outage"}})
        successful_calls = len(requests) - (len(requests) > failed_call)
        operation = ({"operation": "inspect_report", "report_id": measured_case["expected_report_id"]}
                     if successful_calls == 1 else finish(measured_case))
        return httpx.Response(200, json={
            "id": f"test-{len(requests)}", "model": SPEC["id"], "status": "completed",
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": json.dumps(operation)}]}],
            "usage": {"input_tokens": 100, "output_tokens": 20}})

    provider = ResponsesProvider(model=SPEC["id"], api_key_env="OPENAI_API_TOKEN",
                                 pricing=SPEC["pricing"], transport=httpx.MockTransport(respond))
    budget = runner.Budget(5)
    result = asyncio.run(runner.trial(assignment(measured_case), SPEC, PLAN, tmp_path,
                                     provider, budget, measured_case))
    assert result["state"] == "complete" and result["outcome"]["correct"]
    assert result["protocol_complete"] and result["answer_complete"]
    assert result["answer_origin"] == "model" and not result["explanation_present"]
    assert result["provider_retries"] == 1 and not result["transient_failure"]
    assert requests[failed_call - 1] == requests[failed_call]
    assert len(result["model_calls"]) == 3
    assert result["model_calls"][failed_call - 1]["category"] == "http_server"
    assert result["model_calls"][failed_call]["retry_of_turn"] == failed_call - 1
    assert budget.unknown_reserve == pytest.approx(result["model_calls"][failed_call - 1]["reserved_usd"])
    assert budget.estimated_usd > 0
    trace = json.loads((tmp_path / "tool-trace.json").read_text())
    assert len([item for item in trace if item["route"] == "direct_command"]) == 1


@pytest.mark.parametrize("category", ["http_server", "timeout", "transport"])
def test_retry_exhaustion_is_trial_local_and_uses_existing_call_cap(tmp_path, measured_case, category):
    outage = ProviderError("Synthetic transient failure", category=category, retryable=True)
    provider, budget = Replies([outage] * 3), runner.Budget(5)
    result = asyncio.run(runner.trial(assignment(measured_case), SPEC,
                                     {**PLAN, "max_model_calls_per_trial": 2}, tmp_path,
                                     provider, budget, measured_case))
    assert provider.calls == 2 and result["provider_retries"] == 1
    assert result["failure"] == "transient_provider_exhausted"
    assert result["transient_failure"] and not result["stop_model"]
    assert not result["outcome"]["correct"] and not result["answer_complete"]
    assert budget.unknown_reserve == pytest.approx(sum(call["reserved_usd"] for call in result["model_calls"]))


def test_repeated_outage_opens_circuit_after_three_failed_trials(tmp_path, monkeypatch, measured_case):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unused-mock-secret")
    monkeypatch.setattr(runner, "case_specs", lambda _: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])
    providers = []

    def factory(*_):
        provider = Replies([ProviderError("outage", category="http_server", retryable=True)] * 3)
        providers.append(provider)
        return provider

    output = tmp_path / "outage"
    assert not asyncio.run(runner.run(output, [SPEC], PLAN, mode="smoke", provider_factory=factory))
    rows = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert sum(row["state"] == "failed" for row in rows) == 3
    assert sum(row["state"] == "not_attempted" for row in rows) == 3
    assert sum(provider.calls for provider in providers) == 9
    assert sum(row.get("stop_model", False) for row in rows) == 1
    assert {row["stop_reason"] for row in rows if row["state"] == "not_attempted"} == {
        "transient_provider_circuit_open"}
    budget = json.loads((output / f"budget-{SPEC['id']}.json").read_text())
    assert budget["estimated_usd"] == 0 and budget["unknown_charge_reserve_usd"] > 0


def test_unknown_reservation_can_stop_recovery_before_dispatch(tmp_path, measured_case):
    budget = runner.Budget(5)

    class Exhausting(Replies):
        async def complete_request(self, *args, **kwargs):
            # The first admitted charge remains unknown. An allowance that
            # covers it but cannot cover another identical request must stop.
            budget.limit = budget.unknown_reserve * 1.5
            return await super().complete_request(*args, **kwargs)

    provider = Exhausting([ProviderError("outage", category="http_server", retryable=True)])
    result = asyncio.run(runner.trial(assignment(measured_case), SPEC, PLAN, tmp_path,
                                     provider, budget, measured_case))
    assert provider.calls == len(result["model_calls"]) == 1
    assert result["provider_retries"] == 0
    assert result["failure"] == "cost_allowance_exhausted" and result["stop_model"]
    assert budget.unknown_reserve == result["model_calls"][0]["reserved_usd"]


@pytest.mark.parametrize("error", [
    ProviderError("account", category="http_account", retryable=True),
    ProviderError("unclassified", category="provider_error", retryable=True),
    ProviderError("fatal server classification", category="http_server", retryable=False),
    ProviderError("bad identity", category="http_server", retryable=True,
                  response=ModelResponse("", 100, 20, "unexpected-model")),
    ProviderError("missing usage", category="http_server", retryable=True,
                  response=ModelResponse("", model=SPEC["id"])),
])
def test_fatal_or_unverified_errors_are_never_retried(tmp_path, measured_case, error):
    provider = Replies([error])
    result = asyncio.run(runner.trial(assignment(measured_case), SPEC, PLAN, tmp_path,
                                     provider, runner.Budget(5), measured_case))
    assert provider.calls == 1 and result["stop_model"]
    assert not result["transient_failure"] and result["provider_retries"] == 0


@pytest.mark.parametrize("arm", ["eal_mcp", "plain_validator"])
def test_checked_finalisation_retains_tool_decision_without_model_rewrite(tmp_path, measured_case, arm):
    operation = "assess_load_test" if arm == "eal_mcp" else "inspect_report"
    provider = Replies([{"operation": operation, "report_id": measured_case["expected_report_id"]}])
    result = asyncio.run(runner.trial(assignment(measured_case, arm), SPEC,
                                     {**PLAN, "finalisation": "checked"}, tmp_path,
                                     provider, runner.Budget(5), measured_case))
    truth = reference(measured_case)
    assert provider.calls == 1 and result["state"] == "complete"
    assert result["outcome"]["correct"] and result["outcome"]["host_agrees_with_reference"]
    assert result["answer_origin"] == "checked_host" and result["answer_complete"]
    assert not result["protocol_complete"] and not result["explanation_present"]
    assert result["answer"] == {key: truth[key] for key in
                                 ("status", "report_id", "scope", "failed_checks", "unknown_checks", "metrics")} | {
                                     "explanation": ""}


def test_model_finalisation_preserves_wrong_status_and_valid_protocol(tmp_path, measured_case):
    answer = {**finish(measured_case), "status": "supported"}
    assert reference(measured_case)["status"] == "unsupported"
    provider = Replies([{"operation": "inspect_report", "report_id": measured_case["expected_report_id"]}, answer])
    result = asyncio.run(runner.trial(assignment(measured_case), SPEC, PLAN, tmp_path,
                                     provider, runner.Budget(5), measured_case))
    assert result["state"] == "complete" and result["protocol_complete"]
    assert result["answer"]["status"] == "supported" and not result["outcome"]["correct"]
    assert result["outcome"]["host_agrees_with_reference"]


def test_checked_run_freezes_distinct_assignments_and_only_checking_arms(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_TOKEN", raising=False)
    output = tmp_path / "checked"
    assert not asyncio.run(runner.run(output, [SPEC], {**PLAN, "finalisation": "checked"}, mode="calibration"))
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["schema"] == "eal-api-experiment-run/4"
    assert manifest["finalisation"] == "checked"
    assert manifest["plan"]["arms"] == ["eal_mcp", "plain_validator"]
    model_ids = {row["id"] for row in runner.schedule(SPEC["id"], manifest["case_specs"], PLAN["seed"])}
    assert model_ids.isdisjoint(row["id"] for row in manifest["assignments"])
    assert all(row["finalisation"] == "checked" for row in manifest["assignments"])


def test_later_success_resets_transient_circuit_count(tmp_path, monkeypatch, measured_case):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unused-mock-secret")
    monkeypatch.setattr(runner, "case_specs", lambda _: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])
    providers = []

    class Successful(Replies):
        def __init__(self):
            self.calls = 0

        async def complete_request(self, messages, output_limit, *, operations, native_tools):
            self.calls += 1
            if self.calls == 1:
                return model_response({"operation": operations[0]["operation"],
                                       "report_id": measured_case["expected_report_id"]})
            return model_response(finish(measured_case))

    def factory(*_):
        provider = (Replies([ProviderError("outage", category="http_server", retryable=True)] * 3)
                    if len(providers) in {0, 2, 4} else Successful())
        providers.append(provider)
        return provider

    output = tmp_path / "intermittent"
    assert not asyncio.run(runner.run(output, [SPEC], PLAN, mode="smoke", provider_factory=factory))
    rows = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert sum(row["state"] == "complete" for row in rows) == 3
    assert sum(row["state"] == "failed" for row in rows) == 3
    assert not any(row["stop_model"] for row in rows)
    assert {row["consecutive_transient_failures"] for row in rows} == {0, 1}


@pytest.mark.parametrize("repair", [False, True])
def test_native_model_can_submit_returned_template_arguments_verbatim(
        tmp_path, monkeypatch, measured_case, repair):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unused-mock-secret")
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            name, arguments = "inspect_report", {"report_id": measured_case["expected_report_id"]}
        else:
            packet = json.loads(payload["input"][-1]["output"])
            template = packet["answer_contract"]["finish_template"]
            assert template["name"] == "finish" and "operation" not in template["arguments"]
            name, arguments = template["name"], template["arguments"]
            if repair and len(requests) == 2:
                arguments = {key: value for key, value in arguments.items() if key != "status"}
            elif repair:
                assert packet["fields"] == ["status"] and packet["evidence_changed"] is False
        return httpx.Response(200, json={
            "id": f"native-{len(requests)}", "model": SPEC["id"], "status": "completed",
            "output": [{"type": "function_call", "call_id": f"call-{len(requests)}",
                        "name": name, "arguments": json.dumps(arguments)}],
            "usage": {"input_tokens": 100, "output_tokens": 20}})

    provider = ResponsesProvider(model=SPEC["id"], api_key_env="OPENAI_API_TOKEN",
                                 pricing=SPEC["pricing"], capabilities={"native_tools": True},
                                 transport=httpx.MockTransport(respond))
    result = asyncio.run(runner.trial({**assignment(measured_case), "transport": "native"}, SPEC,
                                     {**PLAN, "transport": "native"}, tmp_path,
                                     provider, runner.Budget(5), measured_case))
    assert result["state"] == "complete" and result["outcome"]["correct"]
    assert result["protocol_complete"] and result["answer_origin"] == "model"
    assert len(result["model_calls"]) == 2 + repair
    assert len(result["protocol_errors"]) == int(repair)
    assert not provider._replay_items


def test_interrupted_retry_has_durable_count_and_unknown_reservations(tmp_path, measured_case):
    class WaitingRetry(Replies):
        def __init__(self):
            self.calls, self.retried = 0, asyncio.Event()

        async def complete_request(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError("outage", category="http_server", retryable=True)
            self.retried.set()
            await asyncio.Event().wait()

    async def exercise():
        provider, budget = WaitingRetry(), runner.Budget(5)
        task = asyncio.create_task(runner.trial(assignment(measured_case), SPEC, PLAN,
                                               tmp_path, provider, budget, measured_case))
        await provider.retried.wait()
        snapshot = json.loads((tmp_path / "trial.json").read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return snapshot, budget

    snapshot, budget = asyncio.run(exercise())
    assert snapshot["state"] == "running" and snapshot["provider_retries"] == 1
    assert snapshot["model_calls"][1]["retry_of_turn"] == 0
    assert snapshot["model_calls"][1]["state"] == "in_flight"
    retained = json.loads((tmp_path / "trial.json").read_text())
    assert retained["failure"] == "interrupted" and retained["provider_retries"] == 1
    assert budget.unknown_reserve == pytest.approx(sum(call["reserved_usd"] for call in retained["model_calls"]))
