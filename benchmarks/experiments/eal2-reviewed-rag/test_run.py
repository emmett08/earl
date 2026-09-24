"""Offline contract and scripted provider checks; no OpenAI request is made."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from eal.providers import ModelResponse, ProviderError
from eal.responses_provider import ResponsesProvider


RUN = Path(__file__).with_name("run.py")
spec = importlib.util.spec_from_file_location("reviewed_rag_run", RUN)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ScriptedProvider:
    """Tests orchestration and ledger, never model capability."""

    def identity(self):
        return {"provider": "scripted_test", "model": "scripted_test"}

    async def complete(self, messages, max_output_tokens):
        user = messages[-1]["content"]
        if user.startswith("{"):
            payload = json.loads(user)
            if "checked_result" in payload:
                status = payload["checked_result"]["status"]
            elif "checked_assessment" in payload:
                answer = {"operation": "answer", "text": "The checked status concerns submitted records."}
                return ModelResponse(json.dumps(answer), 10, 20, "scripted_test",
                                     {"id": "synthetic-only"})
            else:
                status = "supported"
            answer = {"status": status, "reason_code": "matching_digest", "records_only": True}
        else:
            answer = {"operation": "assess_bound_task"}
        return ModelResponse(json.dumps(answer), 10, 20, "scripted_test",
                             {"id": "synthetic-only"})


class FailedProvider(ScriptedProvider):
    async def complete(self, messages, max_output_tokens):
        raise ProviderError("incomplete model output", response=ModelResponse(
            "partial", 8, 3, "scripted_test", {"id": "failed-response"}))


class ExplainingProvider(ScriptedProvider):
    def __init__(self):
        self.turns = 0

    async def complete(self, messages, max_output_tokens):
        self.turns += 1
        if self.turns == 1:
            text = '{"operation":"explain"}'
        else:
            assert "host_feedback" in messages[-1]["content"]
            text = '{"operation":"answer","text":"The checked claim concerns submitted records."}'
        return ModelResponse(text, 10, 20, "scripted_test", {"id": f"synthetic-{self.turns}"})


def test_preflight_preserves_original_oracle_disagreement():
    report = runner.preflight()
    assert report["passed"] is True
    assert report["total"] == 14
    assert report["parity"] == 14
    assert report["recipient_reference_match"] == 14
    assert report["original_raw_label_match"] == 10
    refused = {(row["root"], row["state"]) for row in report["pairs"]
               if row["eal"]["status"] == "refused"}
    assert refused == runner.EXPECTED_REFUSALS
    assert all(row["review_status"] == "pending_independent_human_review"
               for row in report["pairs"])


def test_bound_question_rejects_wrong_nomination_before_collection(tmp_path):
    roots = runner.corpus()["roots"]
    root = roots[0]
    host, _ = runner.prepare(tmp_path, roots, root, root["states"][0])
    with pytest.raises(ValueError):
        host.assess_task(roots[1]["id"])
    assert host.families.artifacts.service.store.list(kind="collection") == []
    packet = host.assess_bound_task()
    assert packet["claim"] == root["claim"]
    assert host.finish_bound_task(packet["assessment_id"]) == packet


def test_scripted_study_retains_each_attempt_and_separates_metrics(tmp_path):
    journal = tmp_path / "attempts.jsonl"
    report = asyncio.run(runner.run_live(
        model="scripted_test", provider=ScriptedProvider(), max_calls=18,
        max_cost_usd=1.0, input_rate=1.0, output_rate=1.0,
        max_output_tokens=256, api_key_env="OPENAI_API_KEY", seed=7,
        states_per_root=1, journal=journal,
    ))
    assert report["status"] == "developmental_unreviewed"
    assert report["actual_provider_calls"] == 18
    assert len(report["results"]) == 3
    assert all(row["bound_tool_adherence"] for row in report["results"])
    assert all(set(row["delivery"]) == {"eal", "json"}
               and set(row["raw"]) == {"raw_eal", "raw_json"}
               and row["real_recipient"]["status"] == "completed"
               and row["real_recipient"]["status_match_offline"]
               for row in report["results"])
    events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 36
    assert [item["phase"] for item in events] == ["before", "after"] * 18
    assert "Authorization" not in journal.read_text(encoding="utf-8")


def test_real_recipient_can_request_explanation_then_finish(tmp_path):
    provider = ExplainingProvider()
    calls = runner.BoundedCalls(provider, max_calls=2, max_cost_usd=1,
                                input_usd_per_million=1, output_usd_per_million=1,
                                max_output_tokens=256,
                                journal=tmp_path / "explain.jsonl",
                                frozen_materials=runner.material_hashes())
    roots = runner.corpus()["roots"]
    report = asyncio.run(runner.real_recipient(roots[0], roots[0]["states"][0], roots, calls))
    assert report["status"] == "completed"
    assert report["status_match_offline"]
    assert report["explanation"]["packet"] == report["checked_answer"]
    assert [item["tool"] for item in report["tool_calls"]][-2:] == [
        "eal_explain_bound_task", "eal_finish_bound_task"]
    assert calls.calls == 2
    assert len((tmp_path / "explain.jsonl").read_text().splitlines()) == 4


def test_real_recipient_replays_responses_reasoning_without_logging_handle(tmp_path):
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            output = [
                {"type": "reasoning", "id": "rs-1", "encrypted_content": "opaque-private-reasoning"},
                {"type": "message", "status": "completed", "content": [
                    {"type": "output_text", "text": '{"operation":"explain"}'}]},
            ]
        else:
            assert any(item.get("id") == "rs-1" for item in payload["input"])
            assert any(item.get("type") == "message" and item.get("content", [{}])[0].get("text")
                       == '{"operation":"explain"}' for item in payload["input"])
            assert "host_feedback" in json.dumps(payload["input"])
            output = [{"type": "message", "status": "completed", "content": [
                {"type": "output_text", "text":
                 '{"operation":"answer","text":"The checked claim is bounded to submitted records."}'}]}]
        return httpx.Response(200, json={"id": f"resp-{len(requests)}",
                                          "model": "scripted_test", "status": "completed",
                                          "output": output,
                                          "usage": {"input_tokens": 10, "output_tokens": 20}})

    provider = ResponsesProvider(model="scripted_test", api_key_env=None,
                                 capabilities={"reasoning_effort": "none"},
                                 transport=httpx.MockTransport(handler))
    journal = tmp_path / "responses-attempts.jsonl"
    calls = runner.BoundedCalls(provider, max_calls=2, max_cost_usd=1,
                                input_usd_per_million=1, output_usd_per_million=1,
                                max_output_tokens=256, journal=journal,
                                frozen_materials=runner.material_hashes())
    roots = runner.corpus()["roots"]
    report = asyncio.run(runner.real_recipient(roots[0], roots[0]["states"][0], roots, calls))
    assert report["status"] == "completed", report
    assert report["explanation"] is not None
    assert report["status_match_offline"]
    assert len(requests) == calls.calls == 2
    assert provider._replay_items == {}
    retained = journal.read_text(encoding="utf-8")
    assert len(retained.splitlines()) == 4
    assert "opaque-private-reasoning" not in retained
    assert "responses_replay_handle" not in retained


def test_real_recipient_refusal_issues_no_model_attempt(tmp_path):
    provider = ScriptedProvider()
    calls = runner.BoundedCalls(provider, max_calls=1, max_cost_usd=1,
                                input_usd_per_million=1, output_usd_per_million=1,
                                max_output_tokens=256, journal=tmp_path / "refused.jsonl",
                                frozen_materials=runner.material_hashes())
    roots = runner.corpus()["roots"]
    report = asyncio.run(runner.real_recipient(roots[1], roots[1]["states"][1], roots, calls))
    assert report["expected_recipient_refusal"]
    assert report["refusal_as_expected"]
    assert report["status_match_offline"] is None
    assert report["checked_answer"] is None
    assert calls.calls == 0
    assert not (tmp_path / "refused.jsonl").exists()


def test_missing_credential_stops_before_live_call(monkeypatch):
    monkeypatch.delenv("EAL2_STUDY_MISSING_CREDENTIAL", raising=False)
    with pytest.raises(RuntimeError, match="no provider call was attempted"):
        asyncio.run(runner.run_live(
            model="explicit-model", max_calls=15, max_cost_usd=1,
            input_rate=1, output_rate=1, max_output_tokens=256,
            api_key_env="EAL2_STUDY_MISSING_CREDENTIAL", seed=7, states_per_root=1,
        ))


def test_provider_partial_response_is_journalled_and_stops(tmp_path):
    journal = tmp_path / "failed.jsonl"
    report = asyncio.run(runner.run_live(
        model="scripted_test", provider=FailedProvider(), max_calls=18,
        max_cost_usd=1.0, input_rate=1.0, output_rate=1.0,
        max_output_tokens=256, api_key_env="OPENAI_API_KEY", seed=7,
        states_per_root=1, journal=journal,
    ))
    assert report["status"] == "stopped_partial"
    assert report["actual_provider_calls"] == 1
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [event["phase"] for event in events] == ["before", "after"]
    assert events[1]["provider_response"]["input_tokens"] == 8
    assert events[1]["provider_response"]["model"] == "scripted_test"
    assert events[1]["provider_response"]["text"] == "partial"


def test_material_drift_prevents_next_paid_call(monkeypatch, tmp_path):
    snapshot = runner.material_hashes()
    provider = ScriptedProvider()
    calls = runner.BoundedCalls(provider, max_calls=2, max_cost_usd=1,
                                input_usd_per_million=1, output_usd_per_million=1,
                                max_output_tokens=256, journal=tmp_path / "drift.jsonl",
                                frozen_materials=snapshot)
    monkeypatch.setattr(runner, "material_hashes", lambda: {**snapshot, "synthetic_drift": "0" * 64})
    with pytest.raises(RuntimeError, match="materials changed"):
        asyncio.run(calls.complete([{"role": "user", "content": "task"}]))
    assert calls.calls == 0
    assert json.loads((tmp_path / "drift.jsonl").read_text())["phase"] == "material_drift"
