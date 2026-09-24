"""The revised route handoff yields a single flat claim answer without touching v1."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_cross_model_campaign as legacy  # noqa: E402
from audit_cross_model_ledger import ROUTE_V2_SYSTEM, inspect  # noqa: E402
from analyse_cross_model_campaign_v2 import analyse as analyse_v2  # noqa: E402
from run_cross_model_route_v2 import FINAL_SYSTEM, prepare, run, verify_freeze  # noqa: E402
from eal.providers import ModelResponse  # noqa: E402


PLANS = (
    ROOT / "benchmarks/experiments/cross-model-route-v2-pilot-developmental.json",
    ROOT / "benchmarks/experiments/cross-model-route-v2-cohort-developmental.json",
)


class FakeRecipient:
    def __init__(self, model: str):
        self.model = model
        self.calls = 0

    def identity(self):
        return {"provider": "offline", "model": self.model,
                "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2},
                "capabilities": {"reasoning_effort": "high" if self.model == "gpt-6-sol" else "none"}}

    async def complete(self, messages, max_output_tokens):
        self.calls += 1
        content = messages[-1]["content"]
        if "Host assessment result (the status remains authoritative):" in content:
            assert messages[0]["content"] == FINAL_SYSTEM
            packet = json.loads(content.split("Host assessment result (the status remains authoritative):\n", 1)[1]
                                .split("\nReturn one JSON object", 1)[0])
            answer = {"claims": {packet["claim"]: packet["status"]},
                      "explanation": "The host packet gives this claim and status for the declared scope."}
        else:
            candidates = json.loads(content.split("Candidates:\n", 1)[1])
            brief = content.split("Task: ", 1)[1].split("\nCandidates:", 1)[0]
            selected = next(item for item in candidates if brief.startswith(item["description"]))
            answer = {"operation": "assess", "artifact_id": selected["artifact_id"],
                      "claim": selected["claim"]}
        response_model = "gpt-4.1-nano-2025-04-14" if self.model == "gpt-4.1-nano" else self.model
        return ModelResponse(json.dumps(answer), 100, 20, response_model)


def _providers():
    return {prefix + "_route": FakeRecipient(model) for prefix, model in (
        ("nano", "gpt-4.1-nano"), ("luna", "gpt-6-luna"), ("sol", "gpt-6-sol"))}


def test_route_v2_both_corpora_are_bounded_and_reviewed_only_as_developmental(tmp_path):
    assert FINAL_SYSTEM == ROUTE_V2_SYSTEM
    old_builder = legacy._route_second_messages
    for plan, count in zip(PLANS, (36, 27)):
        providers = _providers()
        freeze = prepare(plan, providers)
        verify_freeze(freeze)
        with pytest.raises(ValueError, match="Frozen schedule"):
            legacy.verify_freeze(freeze)
        assert len(freeze["cases"]) == count
        assert freeze["routing_revision"] == "skill-route-second-turn/2"
        assert freeze["study_kind"] == "developmental"
        result = asyncio.run(run(plan, tmp_path / plan.stem, providers=providers))
        assert result["status"] == "complete" and result["attempts"] == count
        assert sum(provider.calls for provider in providers.values()) == count * 2
        audit = inspect(tmp_path / plan.stem)
        assert all(row.get("malformed_or_declined", 0) == 0 for row in
                   audit["recipient_status_consistency_by_condition"].values())
        assert all(row.get("recipient_final_status_disagreement", 0) == 0 for row in
                   audit["recipient_status_consistency_by_condition"].values())
        summary = analyse_v2(tmp_path / plan.stem)
        assert summary["schema"] == "eal2-cross-model-analysis/2"
        assert sum(c["oracle_matching_and_recipient_consistent_before_explanation_review"]
                   for c in summary["conditions"].values()) == count
        assert all(c["consistent_faithful_accepted_decisions"] is None for c in
                   summary["conditions"].values())
    assert legacy._route_second_messages is old_builder


def test_versions_reject_cross_resume_and_forged_completed_prefix(tmp_path):
    plan = PLANS[0]
    v1_directory = tmp_path / "v1"
    v2_directory = tmp_path / "v2"
    asyncio.run(legacy.run(plan, v1_directory, freeze_only=True, providers=_providers()))
    with pytest.raises(ValueError, match="route-v2 developmental freeze"):
        asyncio.run(run(plan, v1_directory, resume=True, providers=_providers()))

    asyncio.run(run(plan, v2_directory, providers=_providers()))
    with pytest.raises(ValueError, match="Frozen schedule"):
        asyncio.run(legacy.run(plan, v2_directory, resume=True, providers=_providers()))

    zero_prefix = tmp_path / "zero_prefix"
    asyncio.run(run(plan, zero_prefix, freeze_only=True, providers=_providers()))
    zero_providers = _providers()
    assert asyncio.run(run(plan, zero_prefix, resume=True, providers=zero_providers))["status"] == "complete"
    assert sum(provider.calls for provider in zero_providers.values()) == 72

    one_prefix = tmp_path / "one_prefix"
    one_prefix.mkdir()
    (one_prefix / "freeze.json").write_bytes((v2_directory / "freeze.json").read_bytes())
    ledger = json.loads((v2_directory / "ledger.json").read_text())
    ledger["attempts"] = ledger["attempts"][:1]
    ledger["status"] = "running"
    (one_prefix / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    one_providers = _providers()
    assert asyncio.run(run(plan, one_prefix, resume=True, providers=one_providers))["status"] == "complete"
    assert sum(provider.calls for provider in one_providers.values()) == 70

    ledger_path = v2_directory / "ledger.json"
    ledger = json.loads(ledger_path.read_text())
    ledger["attempts"][0]["calls"][0]["usage"]["model_cost_usd"] += 0.01
    ledger["attempts"][0]["usage"]["model_cost_usd"] += 0.01
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="Configured rate, tokens, and retained call cost disagree"):
        asyncio.run(run(plan, v2_directory, resume=True, providers=_providers()))

    ledger["attempts"][0]["calls"][0]["usage"]["model_cost_usd"] -= 0.01
    ledger["attempts"][0]["usage"]["model_cost_usd"] -= 0.01
    ledger["attempts"][0]["calls"][0]["response"]["model"] = "wrong-model"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="Completed routed subcall used a different model"):
        asyncio.run(run(plan, v2_directory, resume=True, providers=_providers()))


def test_charged_first_call_survives_failed_host_in_v2_analysis(tmp_path):
    source = tmp_path / "complete"
    partial = tmp_path / "failed_host"
    asyncio.run(run(PLANS[0], source, providers=_providers()))
    partial.mkdir()
    (partial / "freeze.json").write_bytes((source / "freeze.json").read_bytes())
    ledger = json.loads((source / "ledger.json").read_text())
    attempt = ledger["attempts"][0]
    billed_first = attempt["calls"][0]["usage"]["model_cost_usd"]
    attempt.update(status="failed", usage=None, calls=attempt["calls"][:1],
                   error="simulated host failure")
    ledger.update(status="stopped_host_failure", attempts=[attempt])
    (partial / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    result = analyse_v2(partial)
    condition_id = json.loads((partial / "freeze.json").read_text())["cases"][0]["condition_id"]
    condition = result["conditions"][condition_id]
    assert condition["known_configured_rate_model_cost_usd_lower_bound"] == pytest.approx(billed_first)
    assert condition["configured_rate_model_cost_usd"] == pytest.approx(billed_first)
    assert condition["full_cost_usd"] is None
