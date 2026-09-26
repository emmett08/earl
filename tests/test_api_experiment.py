"""Paid adapter contracts with real HTTP/MCP and mocked provider responses."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from eal.responses_provider import ResponsesProvider
from experiments.api_load_test.analysis import summarise
from experiments.api_load_test.cases import build_cases, case_specs
from experiments.api_load_test.collector import collect
from experiments.api_load_test.materials import ARMS, source_for
from experiments.api_load_test.oracle import reference
from experiments.api_load_test.routes import (TrialTools, checked_decision,
                                               child_environment, eal_decision)
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


def test_eal_projection_uses_checked_claim_status_and_refuses_conflicts():
    packet = {"measurement_facts": {"report_valid": True, "identity_matches": True,
        "complete_records": True, "consistent_records": True, "age_seconds": 12},
        "metrics": {"request_count": 100, "p95_ms": 4.2, "error_rate_percent": 0.0}}
    assert checked_decision(packet)["status"] == "supported"
    assert eal_decision(packet, "unsupported")["status"] == "unsupported"
    assert eal_decision(packet, "supported") == checked_decision(packet)
    with pytest.raises(ValueError, match="unambiguous"):
        eal_decision(packet, "contested")
    packet["measurement_facts"]["age_seconds"] = 301
    assert eal_decision(packet, "unsupported")["status"] == "unavailable"
    with pytest.raises(ValueError, match="conflicts"):
        eal_decision(packet, "supported")


def test_experiment_collector_requires_the_mode_free_acquisition_request(tmp_path, measured_case):
    source = source_for(measured_case["target"]["input"], measured_case["target"]["context"])
    tools = TrialTools(tmp_path / "trial", source, {"case": measured_case})
    report_id = next(iter(measured_case["reports"]))
    request = tools._request(report_id)
    assert set(request) == {"evidence_id", "environment", "tool", "tool_version", "input", "context"}
    output = tmp_path / "report.json"
    with pytest.raises(ValueError, match="Collection request differs"):
        collect({**request, "mode": "deterministic"}, {"case": measured_case}, output)
    assert not output.exists()


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
    assert manifest["schema"] == "eal-api-experiment-run/4"
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
    assert (budget["unknown_charge_reserve_usd"] > 0) is (not usage or not identity)
    summary = summarise(output)
    assert sum(row["model_calls"] for row in summary["cells"]) == len(calls)


def _assignment(case, *, identity="durability-test"):
    return {"id": identity, "model": SPEC["id"], "repeat": 0, "transport": "text",
            "case_id": case["id"], "case_family": case["family"],
            "block": case["id"], "arm": "json_prompt"}


@pytest.mark.parametrize("dispatched", [False, True])
def test_cancellation_retains_only_dispatched_unknown_cost_calls(tmp_path, measured_case, dispatched):
    class WaitingProvider:
        def __init__(self):
            self.entered = asyncio.Event()

        async def complete_request(self, *args, **kwargs):
            self.entered.set()
            await asyncio.Event().wait()

        def discard_replay_handles(self, handles):
            pass

    async def exercise():
        provider, budget = WaitingProvider(), Budget(5)
        task = asyncio.create_task(trial(_assignment(measured_case), SPEC, PLAN, tmp_path,
                                         provider, budget, measured_case,
                                         call_slots=asyncio.Semaphore(1 if dispatched else 0)))
        if dispatched:
            await provider.entered.wait()
        else:
            await asyncio.sleep(0)  # reaches semaphore admission without a dispatch
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return budget

    budget = asyncio.run(exercise())
    result = json.loads((tmp_path / "trial.json").read_text())
    assert result["state"] == "failed" and result["failure"] == "interrupted"
    assert result["stop_model"] is True
    assert len(result["model_calls"]) == int(dispatched)
    assert (budget.unknown_reserve > 0) is dispatched
    if dispatched:
        call = result["model_calls"][0]
        assert call["state"] == "interrupted" and call["estimated_usd"] is None
        assert call["response"] is None and call["reserved_usd"] == budget.unknown_reserve
    else:
        assert not (tmp_path / "events.jsonl").exists()


def test_completed_and_pending_calls_are_durable_before_trial_finishes(tmp_path, measured_case):
    from eal.providers import ModelResponse

    class TwoReplies:
        def __init__(self):
            self.calls, self.pending = 0, asyncio.Event()

        def identity(self):
            return {"pricing": SPEC["pricing"]}

        async def complete_request(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse("{}", 100, 20, SPEC["id"])
            self.pending.set()
            await asyncio.Event().wait()

        def discard_replay_handles(self, handles):
            pass

    async def exercise():
        provider = TwoReplies()
        task = asyncio.create_task(trial(_assignment(measured_case), SPEC,
                                         {**PLAN, "minimum_call_interval_seconds": 0}, tmp_path,
                                         provider, Budget(5), measured_case))
        await provider.pending.wait()
        snapshot = json.loads((tmp_path / "trial.json").read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return snapshot

    snapshot = asyncio.run(exercise())
    assert snapshot["state"] == "running"
    assert [call["state"] for call in snapshot["model_calls"]] == ["complete", "in_flight"]
    assert snapshot["model_calls"][0]["estimated_usd"] > 0
    assert snapshot["model_calls"][1]["estimated_usd"] is None


@pytest.mark.parametrize("failure_stage", ["provider", "finalizer"])
def test_host_failures_preserve_dispatched_call_accounting(tmp_path, measured_case, failure_stage):
    from eal.providers import ModelResponse

    class BrokenHost:
        def identity(self):
            return {"pricing": SPEC["pricing"]}

        async def complete_request(self, *args, **kwargs):
            if failure_stage == "provider":
                raise RuntimeError("unexpected adapter failure after dispatch")
            return ModelResponse("{}", 100, 20, SPEC["id"])

        def discard_replay_handles(self, handles):
            if failure_stage == "finalizer":
                raise RuntimeError("cleanup failure")

    result = asyncio.run(trial(_assignment(measured_case), SPEC,
                               {**PLAN, "max_model_calls_per_trial": 1, "minimum_call_interval_seconds": 0},
                               tmp_path, BrokenHost(), Budget(5), measured_case))
    retained = json.loads((tmp_path / "trial.json").read_text())
    assert result == retained and retained["state"] == "failed" and retained["stop_model"]
    assert len(retained["model_calls"]) == 1
    call = retained["model_calls"][0]
    assert (call["estimated_usd"] is not None) is (failure_stage == "finalizer")
    assert call["state"] == ("complete" if failure_stage == "finalizer" else "failed")


def test_worker_fallback_preserves_checkpoint_after_scoring_exception(tmp_path, monkeypatch, measured_case):
    import experiments.api_load_test.runner as runner
    from eal.providers import ModelResponse
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setattr(runner, "case_specs", lambda mode: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])
    original_grade = runner.grade

    def failed_grading(answer, truth, **kwargs):
        if truth is not None:
            raise RuntimeError("synthetic scoring failure after measured response")
        return original_grade(answer, truth, **kwargs)

    class Reply:
        def identity(self):
            return {"pricing": SPEC["pricing"]}

        async def complete_request(self, *args, **kwargs):
            return ModelResponse("{}", 100, 20, SPEC["id"])

        def discard_replay_handles(self, handles):
            pass

    monkeypatch.setattr(runner, "grade", failed_grading)
    output = tmp_path / "scoring-failure"
    assert not asyncio.run(run(output, [SPEC],
                               {**PLAN, "calibration_max_model_calls_per_trial": 1,
                                "minimum_call_interval_seconds": 0},
                               mode="calibration", provider_factory=lambda *_: Reply()))
    rows = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    failed = next(row for row in rows if row["state"] == "failed")
    assert failed["failure"] == "host_setup_error:RuntimeError"
    assert len(failed["model_calls"]) == 1
    assert failed["model_calls"][0]["estimated_usd"] > 0
    assert sum(row["state"] == "not_attempted" for row in rows) == 2
    summary = summarise(output)
    assert sum(cell["model_calls"] for cell in summary["cells"]) == 1
    assert sum(cell["estimated_usd_known"] for cell in summary["cells"]) > 0


@pytest.mark.parametrize("verified_identity", [False, True])
def test_unverified_reply_keeps_unknown_cost_and_discards_private_replay(
        tmp_path, monkeypatch, measured_case, verified_identity):
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")

    def respond(request):
        return httpx.Response(200, json={"id": "reply-unverified", "status": "completed",
            "model": SPEC["id"] if verified_identity else "unexpected-model",
            "usage": {"input_tokens": None if verified_identity else 100, "output_tokens": 20},
            "output": [{"type": "reasoning", "encrypted_content": "private-test-replay"},
                       {"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": "{}"}]}]})

    provider = ResponsesProvider(model=SPEC["id"], api_key_env="OPENAI_API_TOKEN",
                                 pricing=SPEC["pricing"], transport=httpx.MockTransport(respond))
    budget = Budget(5)
    result = asyncio.run(trial(_assignment(measured_case), SPEC, PLAN, tmp_path,
                               provider, budget, measured_case))
    assert result["failure"] == "model_identity_or_usage_unverified"
    assert result["model_calls"][0]["estimated_usd"] is None
    assert budget.estimated_usd == 0 and budget.unknown_reserve > 0
    assert not provider._replay_items
    assert "private-test-replay" not in (tmp_path / "trial.json").read_text()


def test_run_cancellation_finalizes_assignment_ledger_and_budget(tmp_path, monkeypatch, measured_case):
    import experiments.api_load_test.runner as runner
    monkeypatch.setenv("OPENAI_API_TOKEN", "unit-test-secret")
    monkeypatch.setattr(runner, "case_specs", lambda mode: [measured_case])
    monkeypatch.setattr(runner, "build_cases", lambda *_: [measured_case])
    output = tmp_path / "interrupted-run"

    class WaitingProvider:
        async def complete_request(self, *args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        def discard_replay_handles(self, handles):
            pass

    async def exercise():
        nonlocal entered
        entered = asyncio.Event()
        task = asyncio.create_task(run(output, [SPEC], PLAN, mode="calibration",
                                       provider_factory=lambda *_: WaitingProvider()))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    entered = None
    asyncio.run(exercise())
    rows = [json.loads(path.read_text()) for path in output.glob("trials/*/trial.json")]
    assert len(rows) == 3
    assert sum(row["state"] == "failed" and row["failure"] == "interrupted" for row in rows) == 1
    assert sum(row["state"] == "not_attempted" and row["failure"] == "run_interrupted" for row in rows) == 2
    budget = json.loads((output / f"budget-{SPEC['id']}.json").read_text())
    assert budget["estimated_usd"] == 0 and budget["unknown_charge_reserve_usd"] > 0
    completion = json.loads((output / "completion.json").read_text())
    assert completion["interrupted"] and not completion["complete"]
    assert completion["model_calls"] == 1
    summary = summarise(output)
    assert sum(cell["model_calls"] for cell in summary["cells"]) == 1
    assert sum(cell["unknown_cost_calls"] for cell in summary["cells"]) == 1


def test_cli_summarises_interrupted_run_without_retry(tmp_path, monkeypatch, measured_case):
    import experiments.api_load_test.__main__ as cli
    import experiments.api_load_test.runner as runner
    monkeypatch.delenv("OPENAI_API_TOKEN", raising=False)
    monkeypatch.setattr(runner, "case_specs", lambda mode: [measured_case])
    output = tmp_path / "cli-interrupted"
    invocations = []

    async def interrupted(output, specs, plan, *, mode):
        invocations.append(1)
        await run(output, specs, plan, mode=mode)
        raise asyncio.CancelledError

    monkeypatch.setattr(cli, "run", interrupted)
    monkeypatch.setattr("sys.argv", ["api_load_test", "run", "--output", str(output), "--model", SPEC["id"]])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1 and invocations == [1]
    assert json.loads((output / "summary.json").read_text())["complete"] is False
    assert (output / "summary.md").exists()


@pytest.mark.parametrize("arm", ["json_prompt", "plain_validator", "eal_mcp"])
def test_trial_rejects_incorrect_or_missing_tool_results_privately(tmp_path, monkeypatch, measured_case, arm):
    from eal.providers import ModelResponse
    from experiments.api_load_test.routes import TrialTools
    truth = reference(measured_case)
    original = TrialTools.execute

    async def corrupted_packet(self, selected_arm, report_id):
        packet = await original(self, selected_arm, report_id)
        if selected_arm == "json_prompt":
            packet["measurement_facts"]["identity_matches"] = False
            assert "status" not in packet  # the audit supplies no verdict to this arm
        else:
            for key in ("status", "failed_checks", "unknown_checks"):
                packet.pop(key)
        return packet

    class Replies:
        calls = 0

        def identity(self):
            return {"pricing": SPEC["pricing"]}

        async def complete_request(self, *args, **kwargs):
            self.calls += 1
            operation = ({"operation": "assess_load_test" if arm == "eal_mcp" else "inspect_report",
                          "report_id": truth["report_id"]} if self.calls == 1 else
                         {"operation": "finish", **{key: truth[key] for key in
                          ("status", "report_id", "scope", "failed_checks", "unknown_checks", "metrics")},
                          "explanation": "The model's answer is correct independently of the broken tool packet."})
            return ModelResponse(json.dumps(operation), input_tokens=100, output_tokens=100, model=SPEC["id"])

        def discard_replay_handles(self, handles):
            pass

    monkeypatch.setattr(TrialTools, "execute", corrupted_packet)
    assignment = {"id": "packet-integrity", "model": SPEC["id"], "repeat": 0, "transport": "text",
                  "case_id": measured_case["id"], "case_family": measured_case["family"],
                  "block": measured_case["id"], "arm": arm}
    result = asyncio.run(trial(assignment, SPEC, {**PLAN, "minimum_call_interval_seconds": 0},
                               tmp_path, Replies(), Budget(5), measured_case))
    assert result["failure"] == "host_reference_disagreement" and result["stop_model"]
    assert not result["outcome"]["correct"]
    if arm == "json_prompt":
        assert result["outcome"]["status_correct"] and len(result["model_calls"]) == 2
    else:
        # The checked packet cannot supply a final-answer template. Stop before
        # asking the model to repair missing host output or paying another call.
        assert result["answer"] is None and len(result["model_calls"]) == 1
    expected = ["measurement_facts"] if arm == "json_prompt" else ["status", "failed_checks", "unknown_checks"]
    assert result["host_checks"][0]["mismatches"] == expected
