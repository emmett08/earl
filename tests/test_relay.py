"""Synthetic counterexamples for relay isolation, charging and restart safety."""
import asyncio
import copy
import json
from pathlib import Path
import sys

import pytest

from eal.benchmark import score_answer
from eal.relay import combine_sequence, freeze_relay, handoff_packet, load_relay_plan, run_relay


def stage_result(task=None, *, correct=True, cost=.01):
    task = task or {"id": "example", "expected": {"claims": {"result": "supported"}}}
    claims = {k: {"status": v if correct else "unresolved"} for k, v in task["expected"]["claims"].items()}
    report = {"provider": {"model": "scripted-not-LLM"}, "status": "completed", "stop_reason": "finished",
              "final": {"claims": claims, "source": "synthetic source"},
              "tool_calls": [{"tool": "eal_reason", "status": "error", "result": {"diagnostic": "retained failure"}}],
              "attempts": [{"response_model": "scripted-not-LLM"}], "repairs": 0, "latency_seconds": 2,
              "conversation": [{"role": "assistant", "content": "visible output"}],
              "usage": {"token_usage_complete": True, "total_tokens": 100}}
    return {"task_id": task["id"], "report": report, "score": score_answer(task["expected"]["claims"], report),
            "expected": {"CANARY_ANSWER_KEY": True}, "oracle": "CANARY_ORACLE", "inputs": {},
            "cost": {"model_usd": cost, "total_usd": cost}}


def plan_file(tmp_path, conditions=None):
    provider = tmp_path / "provider.toml"
    provider.write_text('[provider]\nkind="command"\nmodel="scripted-not-an-LLM"\nmeasurement_kind="interface_only"\nargv=' + json.dumps([sys.executable, "-c", "raise RuntimeError('must not call')"]) + '\n')
    stage = {"provider": str(provider), "model_class": "interface_fixture", "arm": "unaided"}
    protocol = tmp_path / "protocol.json"
    protocol.write_text('{"status":"synthetic_test_only"}')
    plan = {"schema": "EAL/relay-plan/1", "name": "synthetic", "suite": str(Path(__file__).resolve().parents[1] / "benchmarks/engineering-v2/suite.json"),
            "protocol": str(protocol), "split": "held_out", "task_ids": ["registered-rms-velocity"],
            "repetitions": 1, "order_seed": 23, "concurrency": 4, "bootstrap_samples": 10,
            "per_mcp_call_usd": 0, "max_campaign_model_cost_usd": 1, "budget": {"max_model_cost_usd": .05},
            "conditions": conditions or [{"id": "solo", "stages": [stage]},
                                         {"id": "answer", "stages": [stage, {**stage, "handoff": "answer"}]},
                                         {"id": "evidence", "stages": [stage, {**stage, "handoff": "evidence"}]}]}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return path


@pytest.mark.parametrize("mode", ["answer", "evidence", "transcript"])
def test_handoff_excludes_scoring_keys_and_preserves_public_failures(mode):
    trial = stage_result()
    trial["score"]["private"] = "CANARY_SCORE"
    packet = handoff_packet(trial, mode)
    encoded = json.dumps(packet)
    assert "CANARY" not in encoded
    assert "tool_events" in packet if mode != "answer" else "tool_events" not in packet
    if mode != "answer":
        assert packet["tool_events"][0]["status"] == "error"
    if mode == "transcript":
        assert packet["conversation"][0]["content"] == "visible output"
    assert handoff_packet(trial, "none") is None
    assert packet["content_digest"]


def test_three_stage_evidence_retains_earlier_packet_without_shared_mutation():
    first = handoff_packet(stage_result(), "evidence")
    second = stage_result()
    second["inputs"]["prior_stage"] = first
    third = handoff_packet(second, "evidence")
    assert third["prior_stage"] == first
    third["prior_stage"]["claims"].clear()
    assert first["claims"]


def test_actual_mcp_stage_receives_packet_without_changing_task_anchors():
    from eal.benchmark import evaluate_task, load_suite
    from eal.providers import ModelResponse
    suite_path = Path(__file__).resolve().parents[1] / "benchmarks/engineering-v2/suite.json"
    task = next(t for t in load_suite(suite_path)["tasks"] if t["id"] == "registered-rms-velocity")
    packet = handoff_packet(stage_result(), "evidence")
    class Scripted:
        def __init__(self): self.calls = 0
        def identity(self):
            return {"model": "scripted-not-an-LLM", "measurement_kind": "interface_only",
                    "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 1}}
        async def complete(self, messages, max_output_tokens):
            data = json.loads(messages[1]["content"])["initial_data"]
            assert data["prior_stage"] == packet
            assert data["source"] != packet["source"]
            assert "CANARY" not in json.dumps(messages)
            self.calls += 1
            return ModelResponse(json.dumps({"operation": "assess" if self.calls == 1 else "finish"}), 100, 10, "scripted-not-an-LLM")
    result = asyncio.run(evaluate_task(task, suite_path.parent, Scripted(), arm="delegated", prior_stage=packet,
                                      per_mcp_call_usd=0, budget=__import__('eal.agent', fromlist=['AgentBudget']).AgentBudget()))
    assert result["score"]["correct"]
    assert result["score"]["evidence_trace"]["verified"]


def test_common_endpoint_score_and_all_stage_costs():
    task = {"id": "example", "family": "fixture", "expected": {"claims": {"result": "supported"}}}
    failed, final = stage_result(correct=False), stage_result(cost=.03)
    final["score"]["correct"] = False  # strict operational check failed
    condition = {"stages": [{"arm": "unaided", "model_class": "s"}, {"arm": "delegated", "model_class": "l"}]}
    combined = combine_sequence(task, condition, [failed, final], ["first", "last"])
    assert combined["score"]["correct"]
    assert not combined["endpoint_operational_score"]["correct"]
    assert combined["stage_endpoint_correct"] == [False, True]
    assert combined["cost"]["model_usd"] == .04
    assert combined["report"]["latency_seconds"] == 4
    failed["cost"]["model_usd"] = None
    failed["cost"]["total_usd"] = None
    assert combine_sequence(task, condition, [failed, final], ["first", "last"])["cost"]["total_usd"] is None


def test_shared_prefix_is_called_once_and_resume_never_replays_paid_requests(tmp_path, monkeypatch):
    from eal import relay
    calls = []
    async def measured(task, root, provider, **kwargs):
        calls.append(copy.deepcopy(kwargs["prior_stage"]))
        await asyncio.sleep(0)
        result = stage_result(task)
        result["inputs"]["prior_stage"] = kwargs["prior_stage"]
        return result
    monkeypatch.setattr(relay, "evaluate_task", measured)
    plan = plan_file(tmp_path)
    output = tmp_path / "run"
    report = asyncio.run(run_relay(plan, output))
    assert len(calls) == 3 and calls.count(None) == 1
    assert report["unique_stages"] == 3
    assert report["stage_uses"] == 5
    assert report["unique_model_cost_usd"] == pytest.approx(.03)
    assert report["aggregate"]["conditions"]["evidence"]["total_cost_usd"] == .02
    assert asyncio.run(run_relay(plan, output, resume=True))["completed_trials"] == 3
    assert len(calls) == 3
    raw = json.loads(plan.read_text());raw["notes"] = "changed"
    plan.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Resume refused"):
        asyncio.run(run_relay(plan, output, resume=True))


def test_orphan_request_blocks_further_billing_and_is_not_retried(tmp_path, monkeypatch):
    from eal import relay
    plan = plan_file(tmp_path)
    output = tmp_path / "run"
    asyncio.run(run_relay(plan, output, freeze_only=True))
    (output / "stages" / "unknown.inflight.json").write_text('{}')
    async def must_not_run(*args, **kwargs):
        raise AssertionError("No call may be made with unknown prior charges")
    monkeypatch.setattr(relay, "evaluate_task", must_not_run)
    report = asyncio.run(run_relay(plan, output, resume=True))
    assert report["unique_model_cost_usd"] is None
    assert report["unique_stages"] == 0
    assert all(c["correct"] == 0 for c in report["aggregate"]["conditions"].values())


def test_changed_checkpoint_is_detected(tmp_path, monkeypatch):
    from eal import relay
    async def measured(task, *args, **kwargs):
        return stage_result(task)
    monkeypatch.setattr(relay, "evaluate_task", measured)
    path=plan_file(tmp_path);output=tmp_path/'run'
    asyncio.run(run_relay(path, output))
    checkpoint=next((output/'stages').glob('*.json'))
    record=json.loads(checkpoint.read_text());record['trial']['cost']['model_usd']=0
    checkpoint.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="integrity"):
        asyncio.run(run_relay(path,output,resume=True))


def test_partial_known_charges_survive_later_usage_failure(tmp_path, monkeypatch):
    from eal import relay
    async def measured(task, *args, **kwargs):
        result = stage_result(task)
        result['report']['usage'].update(known_model_cost_usd=.013, model_cost_complete=False)
        result['cost'].update(model_usd=None, total_usd=None)
        return result
    monkeypatch.setattr(relay, 'evaluate_task', measured)
    path = plan_file(tmp_path)
    plan = json.loads(path.read_text())
    plan['concurrency'] = 1
    path.write_text(json.dumps(plan))
    output = tmp_path / 'run'
    report = asyncio.run(run_relay(path, output))
    assert report['unique_model_cost_usd'] is None
    assert report['known_unique_model_cost_usd'] == .013
    resumed = asyncio.run(run_relay(path, output, resume=True))
    assert resumed['known_unique_model_cost_usd'] == .013


@pytest.mark.parametrize("change", ["first_handoff", "native_unaided", "negative_cost", "extra_field"])
def test_invalid_design_fails_before_requests(tmp_path, change):
    path=plan_file(tmp_path);p=json.loads(path.read_text())
    if change=='first_handoff': p['conditions'][0]['stages'][0]['handoff']='evidence'
    elif change=='native_unaided': p['conditions'][0]['stages'][0]['interaction_mode']='native'
    elif change=='negative_cost': p['max_campaign_model_cost_usd']=-1
    else: p['conditions'][0]['stages'][0]['oracle']='not allowed'
    path.write_text(json.dumps(p))
    with pytest.raises(ValueError): load_relay_plan(path)
