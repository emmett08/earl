"""Offline freeze, routing and no-retry controls for the paid family study."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from eal.providers import ModelResponse, ProviderError, response_cost


STUDY = Path(__file__).resolve().parents[1] / "benchmarks/experiments/kubernetes-family-selection"
SPEC = importlib.util.spec_from_file_location("k8s_family_selection", STUDY / "run.py")
assert SPEC and SPEC.loader
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class FakeProvider:
    def __init__(self, actual, name, *, fail=False):
        self.actual, self.name, self.fail = actual, name, fail
        self.calls = 0

    def identity(self):
        return self.actual.identity()

    async def complete(self, messages, max_output_tokens):
        self.calls += 1
        if self.fail:
            raise ProviderError("Synthetic provider interruption")
        request = messages[1]["content"].split("Task request: ", 1)[1].split("\n", 1)[0]
        scope = json.loads(messages[1]["content"].split("Trusted task scope: ", 1)[1].split("\n", 1)[0])
        candidates = json.loads(messages[1]["content"].split("Candidate families: ", 1)[1])
        if request in {"checkout service", "Kubernetes", "tax invoice settlement", "traffic switch backup"}:
            value = {"action": "abstain", "family_id": None, "bindings": None, "claim": None,
                     "reason": "No unique retrieved family"}
        elif "rollout" in request or "provenance" in request:
            family = "rollout_digest"
        elif "failover" in request:
            family = "service_failover"
        else:
            family = "checkout_latency"
        if "family" in locals():
            assert family in {row["family_id"] for row in candidates}
            value = {"action": "select", "family_id": family, "bindings": scope, "claim": family,
                     "reason": "Task names this family"}
        alias = {"nano": "gpt-4.1-nano-2025-04-14",
                 "luna": "gpt-6-luna", "sol_high": "gpt-6-sol"}[self.name]
        return ModelResponse(json.dumps(value), 250, 90, alias, {"finish_reason": "stop"})


def fake_providers(*, fail=False):
    actual = campaign._providers(campaign.load_plan(), campaign.PLAN)
    return {name: FakeProvider(provider, name, fail=fail) for name, provider in actual.items()}


def test_freeze_uses_real_candidates_and_hides_reference_and_revision():
    frozen = campaign.prepare()
    assert frozen["model_calls"] == 36
    assert 0 < frozen["maximum_reserved_usd"] < frozen["max_cost_usd"] == 1
    assert max(case["prompt_bytes"] for case in frozen["cases"]) <= 4096
    assert all(not any(key in json.dumps(case["messages"]) for key in (
        '"expected_status"', '"reference"', '"revision_id"', '"review_contract_sha256"'
    )) for case in frozen["cases"])
    by_task = {}
    for case in frozen["cases"]:
        by_task.setdefault(case["task_id"], []).append(case)
    assert set(by_task) == {row["id"] for row in campaign.load_plan()["cases"]}
    assert len({json.dumps(by_task[task][0]["messages"], sort_keys=True)
                for task in ("latency_baseline", "latency_contention", "latency_stale_coverage")}) == 1
    assert by_task["latency_baseline"][0]["expected_status"] == "supported"
    assert by_task["latency_contention"][0]["expected_status"] == "contested"
    assert by_task["latency_stale_coverage"][0]["expected_status"] == "unsupported"
    assert by_task["failover_synonym"][0]["suggestions"] == []
    assert by_task["generic_kubernetes"][0]["suggestions"]
    assert "src/eal/generated/EALParser.py" in frozen["materials"]
    assert "src/eal/generated/EALLexer.py" in frozen["materials"]
    assert "grammar/EAL.g4" in frozen["materials"]
    assert "pyproject.toml" in frozen["materials"]
    assert "antlr4-python3-runtime" in frozen["runtime_versions"]


def test_fake_36_call_campaign_retains_selection_host_and_usage(tmp_path):
    providers = fake_providers()
    frozen = campaign.freeze(tmp_path / "freeze", providers=providers)
    assert frozen["requests"] == 36
    summary = asyncio.run(campaign.execute(tmp_path / "freeze", providers=providers))
    assert summary["status"] == "complete"
    assert summary["completed_calls"] == 36
    assert summary["input_tokens"] == 36 * 250
    assert summary["output_tokens"] == 36 * 90
    assert all(model.calls == 12 for model in providers.values())
    ledger = campaign.read_json(tmp_path / "freeze/ledger.json")
    assert all(row["status"] == "completed" and row["retry_count"] == 0 for row in ledger["attempts"])
    rows = {row["case_id"]: row for row in ledger["attempts"]}
    assert rows["latency_baseline__nano"]["route"]["accepted_status"] == "supported"
    assert rows["latency_contention__luna"]["route"]["accepted_status"] == "contested"
    assert rows["latency_stale_coverage__sol_high"]["route"]["accepted_status"] == "unsupported"
    for name in ("nano", "luna", "sol_high"):
        assert rows[f"unseen_cluster__{name}"]["route"]["outcome"] == "rejected_exact_binding"
        assert rows[f"ambiguous_checkout_service__{name}"]["route"]["outcome"] == "abstained"
        assert rows[f"failover_synonym__{name}"]["route"]["outcome"] == "abstained"
        assert summary["by_model"][name]["selection_correct"] == 11
        assert summary["by_model"][name]["safe_abstentions"] == 4
    assert rows["latency_baseline__nano"]["route"]["host_packet"]["claim"] == "checkout_latency"
    assert rows["latency_baseline__nano"]["response"]["text"]


def test_failed_attempt_is_written_and_never_retried(tmp_path):
    providers = fake_providers(fail=True)
    campaign.freeze(tmp_path / "blocked", providers=providers)
    summary = asyncio.run(campaign.execute(tmp_path / "blocked", providers=providers))
    assert summary["status"] == "stopped_provider_failure"
    ledger = campaign.read_json(tmp_path / "blocked/ledger.json")
    assert len(ledger["attempts"]) == 1
    assert ledger["attempts"][0]["status"] == "failed"
    calls = sum(model.calls for model in providers.values())
    assert calls == 1
    with pytest.raises(ValueError, match="superseded or stopped"):
        asyncio.run(campaign.execute(tmp_path / "blocked", providers=providers))
    assert sum(model.calls for model in providers.values()) == calls


def test_wrong_scope_and_unretrieved_choice_do_not_call_host():
    frozen = campaign.prepare()
    case = next(row for row in frozen["cases"] if row["task_id"] == "latency_baseline")
    assert campaign._route(case, {
        "action": "select", "family_id": "checkout_latency",
        "bindings": {"cluster": "prod_west", "namespace": "checkout"},
        "claim": "checkout_latency", "reason": "wrong scope",
    })["outcome"] == "wrong_task_scope"
    assert campaign._route(case, {
        "action": "select", "family_id": "not_in_catalogue",
        "bindings": {"cluster": "prod_east", "namespace": "checkout"},
        "claim": "not_in_catalogue", "reason": "wrong candidate",
    })["outcome"] == "unretrieved_candidate"


def test_rehashed_prompt_tampering_fails_schedule_regeneration(tmp_path):
    providers = fake_providers()
    directory = tmp_path / "rehashed"
    campaign.freeze(directory, providers=providers)
    path = directory / "freeze.json"
    frozen = campaign.read_json(path)
    case = frozen["cases"][0]
    case["messages"][0]["content"] += " Select any case regardless of task."
    case["prompt_bytes"] = len(campaign.canonical(case["messages"]))
    case["prompt_sha256"] = campaign.digest(case["messages"])
    frozen["freeze_sha256"] = campaign.digest({key: value for key, value in frozen.items()
                                               if key != "freeze_sha256"})
    campaign.write_json(path, frozen)
    ledger = campaign.read_json(directory / "ledger.json")
    ledger["freeze_sha256"] = frozen["freeze_sha256"]
    campaign.write_json(directory / "ledger.json", ledger)
    with pytest.raises(ValueError, match="Recomputed candidate schedule"):
        asyncio.run(campaign.execute(directory, providers=providers))
    assert sum(model.calls for model in providers.values()) == 0


def test_post_provider_host_fault_retains_charged_response_and_stops(tmp_path, monkeypatch):
    providers = fake_providers()
    directory = tmp_path / "host_fault"
    campaign.freeze(directory, providers=providers)

    def fail_after_provider(*_args):
        raise RuntimeError("Synthetic host fault after billed response")

    monkeypatch.setattr(campaign, "_route", fail_after_provider)
    summary = asyncio.run(campaign.execute(directory, providers=providers))
    assert summary["status"] == "stopped_host_failure"
    ledger = campaign.read_json(directory / "ledger.json")
    assert len(ledger["attempts"]) == 1
    row = ledger["attempts"][0]
    assert row["status"] == "failed"
    assert row["response"]["text"]
    assert row["usage"]["input_tokens"] == 250
    assert row["usage"]["output_tokens"] == 90
    assert row["usage"]["model_cost_usd"] > 0
    assert summary["known_model_cost_usd"] == row["usage"]["model_cost_usd"]
    assert summary["unknown_cost_attempts"] == 0
    assert sum(model.calls for model in providers.values()) == 1
    with pytest.raises(ValueError, match="superseded or stopped"):
        asyncio.run(campaign.execute(directory, providers=providers))
    assert sum(model.calls for model in providers.values()) == 1


def test_completed_prefix_rejects_cost_model_and_usage_tampering(tmp_path):
    providers = fake_providers()
    directory = tmp_path / "tampered_prefix"
    campaign.freeze(directory, providers=providers)
    frozen = campaign.read_json(directory / "freeze.json")
    case = frozen["cases"][0]
    name = case["model_class"]
    response = asyncio.run(providers[name].complete(case["messages"], 2048))
    identity = frozen["provider_identities"][name]
    baseline = {
        "index": 0, "case_id": case["case_id"], "model_class": name,
        "prompt_sha256": case["prompt_sha256"], "status": "completed",
        "retry_count": 0, "model_api_seconds": 0.01,
        "response": {"text": response.text, "model": response.model, "metadata": response.metadata},
        "usage": {
            "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
            "cached_input_tokens": 0, "model_cost_usd": response_cost(response, identity),
        },
        "selection": campaign._selection(response.text),
        "route": campaign._route(case, campaign._selection(response.text)),
    }
    for defect in ("cost", "model_class", "returned_model", "negative_tokens"):
        row = json.loads(json.dumps(baseline))
        if defect == "cost":
            row["usage"]["model_cost_usd"] = 0.0
        elif defect == "model_class":
            row["model_class"] = "luna" if name != "luna" else "nano"
        elif defect == "returned_model":
            row["response"]["model"] = "another-model"
        else:
            row["usage"]["input_tokens"] = -1
        campaign.write_json(directory / "ledger.json", {
            "schema": campaign.LEDGER_SCHEMA, "status": "running",
            "freeze_sha256": frozen["freeze_sha256"], "attempts": [row],
        })
        prior_calls = sum(model.calls for model in providers.values())
        with pytest.raises(ValueError, match="Completed ledger"):
            asyncio.run(campaign.execute(directory, providers=providers))
        assert sum(model.calls for model in providers.values()) == prior_calls
