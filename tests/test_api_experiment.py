"""Paid adapter contracts with real HTTP/MCP and mocked provider responses."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from eal.responses_provider import ResponsesProvider
from experiments.api_load_test.analysis import summarise
from experiments.api_load_test.cases import build_cases, case_specs
from experiments.api_load_test.materials import ARMS
from experiments.api_load_test.oracle import reference
from experiments.api_load_test.routes import child_environment
from experiments.api_load_test.runner import Budget, HERE, event, run, schedule, trial

PLAN = json.loads((HERE / "plan.json").read_text())
SPEC = json.loads((HERE / "models.json").read_text())["models"][0]


@pytest.fixture(scope="module")
def measured_case(tmp_path_factory):
    selected = next(item for item in case_specs("pilot") if item["family"] == "errors")
    return build_cases(tmp_path_factory.mktemp("measured-cases") / "cases", [selected], PLAN["seed"])[0]


def test_live_progress_shows_usage_without_printing_response_content(tmp_path, capsys):
    event(tmp_path / "events.jsonl", {
        "type": "model_call_completed", "id": "trial-1", "turn": 1,
        "estimated_usd": 0.001, "response": {
            "model": SPEC["id"], "input_tokens": 100, "output_tokens": 20,
            "text": "private-response-body", "metadata": {"id": "resp_123", "private": "hidden"}}})
    line = capsys.readouterr().out
    progress = json.loads(line)
    assert progress["input_tokens"] == 100 and progress["output_tokens"] == 20
    assert progress["response_id"] == "resp_123"
    assert "private-response-body" not in line and "hidden" not in line


def test_every_assignment_is_preserved_and_case_order_is_randomised():
    cases = case_specs("pilot")
    assigned = schedule(SPEC["id"], cases, 42)
    assert assigned == schedule(SPEC["id"], cases, 42)
    assert len(assigned) == 240 == len({row["id"] for row in assigned})
    assert len({row["case_id"] for row in assigned}) == 40
    for block in {row["block"] for row in assigned}:
        assert {row["arm"] for row in assigned if row["block"] == block} == set(ARMS)
    assert assigned != schedule(SPEC["id"], cases, 43)
    assert {row["id"] for row in assigned}.isdisjoint(row["id"] for row in schedule(SPEC["id"], cases, 42, "native"))


def test_credentials_do_not_enter_collector_or_mcp_environments(monkeypatch):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-github-secret")
    assert "TOKEN" not in json.dumps(child_environment())


@pytest.mark.parametrize("arm", ["eal_mcp", "json_prompt", "plain_brief", "plain_validator"])
@pytest.mark.parametrize("transport", ["text", "native"])
def test_provider_to_real_tool_to_scored_answer(tmp_path, monkeypatch, arm, transport, measured_case):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    requests = []
    truth = reference(measured_case)
    report_id = truth["report_id"]

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["store"] is False
        assert ("tools" in payload) == (transport == "native")
        assert "text" not in payload  # text route needs no provider JSON mode
        if len(requests) == 1:
            name = "assess_load_test" if arm == "eal_mcp" else "inspect_report"
            arguments = {"report_id": report_id}
        else:
            if transport == "native":
                packet = json.loads(payload["input"][-1]["output"])
            else:
                packet = json.loads(payload["input"][-1]["content"].split("\n", 1)[1])
            assert "error" not in packet
            assert packet["report_id"] == report_id
            name = "finish"
            arguments = {key: truth[key] for key in ("status", "report_id", "scope", "failed_checks", "unknown_checks", "metrics")}
            arguments["explanation"] = "The selected run has measured errors beyond the inclusive limit."
        if transport == "native":
            output = [{"type": "function_call", "call_id": f"call-{len(requests)}", "name": name,
                       "arguments": json.dumps(arguments)}]
        else:
            output = [{"type": "message", "role": "assistant", "status": "completed", "content": [
                {"type": "output_text", "text": json.dumps({"operation": name, **arguments})}]}]
        # Exercise continuation replay for reasoning-capable text models too.
        output.insert(0, {"type": "reasoning", "id": f"reasoning-{len(requests)}",
                          "encrypted_content": "opaque-test-content", "summary": []})
        if len(requests) > 1:
            assert any(item.get("type") == "reasoning" for item in payload["input"])
        return httpx.Response(200, json={"id": f"response-{len(requests)}", "model": SPEC["id"],
            "status": "completed", "output": output,
            "usage": {"input_tokens": 300, "output_tokens": 60, "input_tokens_details": {"cached_tokens": 0}}})

    provider = ResponsesProvider(model=SPEC["id"], api_key_env="OPENAI_API_TOKEN",
                                 capabilities={"native_tools": transport == "native"}, pricing=SPEC["pricing"],
                                 transport=httpx.MockTransport(respond))
    plan = {**PLAN, "minimum_call_interval_seconds": 0, "transport": transport}
    assignment = {"id": "unit-trial", "model": SPEC["id"], "repeat": 0, "transport": transport,
                  "case_id": measured_case["id"], "case_family": measured_case["family"],
                  "block": measured_case["id"], "arm": arm}
    result = asyncio.run(trial(assignment, SPEC, plan, tmp_path, provider, Budget(5), measured_case))
    assert result["state"] == "complete", result
    assert result["outcome"]["correct"] is True, result
    assert len(result["model_calls"]) == 2
    assert "unit-test-secret" not in (tmp_path / "trial.json").read_text()
    assert not provider._replay_items


def test_missing_key_keeps_all_assignments_and_has_no_fake_results(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_TOKEN", raising=False)
    output = tmp_path / "missing-key"
    assert asyncio.run(run(output, [SPEC], PLAN, mode="smoke")) is False
    summary = summarise(output)
    assert summary["assigned"] == 24
    assert summary["complete"] is False
    assert all(cell["completed"] == cell["correct"] == cell["model_calls"] == 0 for cell in summary["cells"])


def test_budget_cannot_spend_past_allowance():
    with pytest.raises(ValueError, match="allowance"):
        Budget(0.000001).reserve([], [], 4096, SPEC["pricing"])


def test_internal_tool_failure_stops_model_instead_of_requesting_model_repair(
        tmp_path, monkeypatch, measured_case):
    from eal.providers import ModelResponse
    from experiments.api_load_test.routes import ToolExecutionError, TrialTools
    calls = []

    class SelectingProvider:
        def identity(self):
            return {"pricing": SPEC["pricing"]}

        async def complete_request(self, *args, **kwargs):
            calls.append(1)
            return ModelResponse(json.dumps({"operation": "inspect_report",
                                 "report_id": measured_case["expected_report_id"]}),
                                 input_tokens=100, output_tokens=20, model=SPEC["id"], metadata={})

        def discard_replay_handles(self, handles):
            pass

    async def failed_host(*args):
        raise ToolExecutionError("Synthetic collector integrity failure")

    monkeypatch.setattr(TrialTools, "execute", failed_host)
    assignment = {"id": "host-failure", "model": SPEC["id"], "repeat": 0, "transport": "text",
                  "case_id": measured_case["id"], "case_family": measured_case["family"],
                  "block": measured_case["id"], "arm": "json_prompt"}
    result = asyncio.run(trial(assignment, SPEC, {**PLAN, "minimum_call_interval_seconds": 0},
                               tmp_path, SelectingProvider(), Budget(5), measured_case))
    assert result["state"] == "failed" and result["stop_model"]
    assert result["failure"] == "host_error:ToolExecutionError"
    assert len(calls) == 1 and not result["protocol_errors"]
    assert not result["outcome"]["correct"]


def test_provider_failure_retains_unattempted_assignments(tmp_path, monkeypatch, measured_case):
    from eal.providers import ProviderError
    import experiments.api_load_test.runner as runner
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setattr(runner, "case_specs", lambda mode: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])

    class FailingProvider:
        async def complete_request(self, *args, **kwargs):
            raise ProviderError("Synthetic unit-test provider outage")

        def discard_replay_handles(self, handles):
            pass

    output = tmp_path / "outage"
    assert asyncio.run(run(output, [SPEC], PLAN, mode="smoke",
                           provider_factory=lambda *_: FailingProvider())) is False
    records = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert len(records) == 6
    assert sum(row["state"] == "failed" for row in records) == 1
    assert sum(row["state"] == "not_attempted" for row in records) == 5
    assert all(not row["outcome"]["correct"] for row in records)
    assert summarise(output)["complete"] is False


def test_provider_setup_failure_does_not_cancel_other_model_ledger(tmp_path, monkeypatch, measured_case):
    import experiments.api_load_test.runner as runner
    from eal.providers import ProviderError
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setattr(runner, "case_specs", lambda mode: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])
    second = {**SPEC, "id": "second-pinned-test-model"}

    class Outage:
        async def complete_request(self, *args, **kwargs):
            raise ProviderError("Test provider outage")

        def discard_replay_handles(self, handles):
            pass

    def factory(spec, plan):
        if spec["id"] == SPEC["id"]:
            raise ValueError("Test setup failure")
        return Outage()

    output = tmp_path / "setup-failure"
    assert asyncio.run(run(output, [SPEC, second], PLAN, mode="smoke", provider_factory=factory)) is False
    records = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert len(records) == 12
    assert {row["model"] for row in records if row["state"] == "failed"} == {SPEC["id"], second["id"]}
    assert sum(row["state"] == "not_attempted" for row in records) == 10
    assert json.loads((output / "completion.json").read_text())["trials"] == 12


def test_calibration_freezes_small_selected_design_without_paid_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_TOKEN", raising=False)
    output = tmp_path / "calibration"
    assert asyncio.run(run(output, [SPEC], PLAN, mode="calibration")) is False
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["schema"] == "eal-api-experiment-run/3"
    assert len(manifest["assignments"]) == 9
    assert {row["family"] for row in manifest["case_specs"]} == {"healthy", "corrupt", "stale"}
    assert all(row["variant"] == 0 for row in manifest["case_specs"])
    assert manifest["plan"]["arms"] == ["eal_mcp", "json_prompt", "plain_validator"]
    assert manifest["plan"]["max_model_calls_per_trial"] == 3
    assert manifest["plan"]["max_output_tokens_per_call"] == 4096
    assert manifest["plan"]["calibration_max_usd_per_model"] == 0.5
    assert PLAN["arms"] == list(ARMS)  # selected manifest cannot mutate full plan
    assert PLAN["max_model_calls_per_trial"] == 6
    assert len(summarise(output)["contrasts"]) == 2


@pytest.mark.parametrize("category,usage,identity,continues", [
    ("output_truncated", True, True, True),
    ("multiple_messages", True, True, True),
    ("output_incomplete", True, True, True),
    ("missing_message", True, True, True),
    ("invalid_operation", True, True, True),
    ("output_filtered", True, True, True),
    ("output_truncated", False, True, False),
    ("output_truncated", True, False, False),
    ("http_account", True, True, False),
    ("provider_error", True, True, False),
])
def test_reply_failures_are_trial_local_only_with_verified_cost_and_identity(
        tmp_path, monkeypatch, measured_case, category, usage, identity, continues):
    from eal.providers import ModelResponse, ProviderError
    import experiments.api_load_test.runner as runner
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setattr(runner, "case_specs", lambda mode: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])
    calls = []
    metadata = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                "visible_output": []}

    class MeasuredFailure:
        def identity(self):
            return {"pricing": SPEC["pricing"]}

        async def complete_request(self, *args, **kwargs):
            calls.append(1)
            response = ModelResponse("", input_tokens=100 if usage else None,
                                     output_tokens=4096 if usage else None,
                                     model=SPEC["id"] if identity else "unexpected-snapshot",
                                     metadata=metadata)
            raise ProviderError("Measured synthetic failure", category=category,
                                response=response, diagnostics=metadata)

        def discard_replay_handles(self, handles):
            pass

    output = tmp_path / "measured-failure"
    assert asyncio.run(run(output, [SPEC], PLAN, mode="calibration",
                           provider_factory=lambda *_: MeasuredFailure())) is False
    records = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert len(records) == 3
    assert len(calls) == (3 if continues else 1)  # no repeat of a failed attempt
    assert sum(row["state"] == "not_attempted" for row in records) == (0 if continues else 2)
    attempted = [row for row in records if row["state"] == "failed"]
    assert all(row["stop_model"] is not continues for row in attempted)
    assert all(row["model_calls"][0]["category"] == category for row in attempted)
    assert all(row["model_calls"][0]["diagnostics"] == metadata for row in attempted)
    budget = json.loads((output / f"budget-{SPEC['id']}.json").read_text())
    assert (budget["unknown_charge_reserve_usd"] > 0) is (not usage)
    summary = summarise(output)
    assert sum(row["model_calls"] for row in summary["cells"]) == len(calls)
