"""Offline safety and accounting checks for the paired model campaign."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyse_cross_model_campaign import analyse  # noqa: E402
from run_cross_model_campaign import _run_route_case, prepare, run, verify_freeze  # noqa: E402
from eal.providers import ModelResponse  # noqa: E402

PLAN = ROOT / "benchmarks" / "experiments" / "cross-model-developmental.json"
CONFIRMATORY = ROOT / "benchmarks" / "experiments" / "cross-model-confirmatory.json"


class FakeProvider:
    def __init__(self, model: str, *, no_usage: bool = False):
        self.model = model
        self.no_usage = no_usage
        self.calls = 0

    def identity(self):
        return {"provider": "offline-fake", "adapter": "fake", "model": self.model,
                "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2},
                "capabilities": {"reasoning_effort": "high" if self.model == "gpt-6-sol" else "none"}}

    async def complete(self, messages, max_output_tokens):
        self.calls += 1
        content = messages[-1]["content"]
        if "Routing skill:" in messages[0]["content"] and "Host assessment result" not in content:
            candidates = json.loads(content.split("Candidates:\n", 1)[1])
            brief = content.split("Task: ", 1)[1].split("\nCandidates:", 1)[0]
            selected = next(c for c in candidates if brief.startswith(c["description"][:50]))
            answer = {"operation": "assess", "artifact_id": selected["artifact_id"], "claim": selected["claim"]}
        else:
            # A completed response can be wrong; the host must keep its status.
            claim = next(c for c in ("recorded_direction", "intervention_within_limit",
                                     "bounded_dosing_error", "continuation_preconditions")
                         if c in content)
            answer = {"claims": {claim: "supported"}, "explanation": "A plausible but unreviewed explanation."}
        # The frozen live plan permits the dated identity returned for nano,
        # while provider.identity() remains the configured model alias.
        response_model = "gpt-4.1-nano-2025-04-14" if self.model == "gpt-4.1-nano" else self.model
        return ModelResponse(json.dumps(answer), None if self.no_usage else 100,
                             None if self.no_usage else 10, response_model)


def providers():
    models = {"nano": "gpt-4.1-nano", "luna": "gpt-6-luna", "sol": "gpt-6-sol"}
    return {f"{short}_{arm}": FakeProvider(model) for short, model in models.items()
            for arm in ("raw", "skill", "route", "eal", "equal")}


def test_freeze_is_paired_and_checks_comparator_tamper_offline():
    conditions = providers()
    frozen = prepare(PLAN, conditions)
    verify_freeze(frozen)
    assert len(frozen["cases"]) == 180
    assert frozen["comparator_checks"]["cases_total"] == 12
    assert frozen["comparator_checks"]["tamper_pass"] == 60
    assert len({(c["root_id"], c["state_id"], c["condition_id"]) for c in frozen["cases"]}) == 180
    assert all(p.calls == 0 for p in conditions.values())
    assert not any("expected" in str(c["messages"]) for c in frozen["cases"])
    assert str(ROOT / "scripts" / "run_cross_model_campaign.py") in frozen["materials"]
    assert str(ROOT / "scripts" / "analyse_cross_model_campaign.py") in frozen["materials"]


def test_routed_calls_and_final_host_status_are_retained(tmp_path):
    conditions = providers()
    result = asyncio.run(run(PLAN, tmp_path / "run", providers=conditions))
    assert result["status"] == "complete" and result["attempts"] == 180
    assert sum(p.calls for p in conditions.values()) == 216
    ledger = json.loads((tmp_path / "run" / "ledger.json").read_text())
    routed = [row for row in ledger["attempts"] if "route_requested" in row]
    assert len(routed) == 36 and all(row["route_requested"] for row in routed)
    assert all(len(row["calls"]) == 2 for row in routed)
    assert all(row["retry_count"] == 0 for row in ledger["attempts"])
    summary = analyse(tmp_path / "run")
    assert summary["root_count"] == 4
    assert summary["conditions"]["nano_route"]["model_calls"] == 24
    assert summary["conditions"]["nano_eal"]["final_false_support"] == 0
    assert summary["conditions"]["nano_eal"]["recipient_contradictions"] > 0
    assert summary["conditions"]["nano_route"]["total_cost_per_correct_accepted_usd"] is None


def test_unknown_billing_stops_before_retry(tmp_path):
    conditions = providers()
    conditions["nano_raw"].no_usage = True
    # Whichever seeded condition is first, force an unknown usage response.
    for provider in conditions.values():
        provider.no_usage = True
    output = tmp_path / "failed"
    first = asyncio.run(run(PLAN, output, providers=conditions))
    assert first["status"] in {"stopped_provider_failure", "stopped_unknown_usage"}
    assert first["attempts"] == 1
    total = sum(provider.calls for provider in conditions.values())
    with pytest.raises(ValueError, match="reconcile manually"):
        asyncio.run(run(PLAN, output, resume=True, providers=conditions))
    assert sum(provider.calls for provider in conditions.values()) == total


def test_confirmatory_freeze_requires_actual_independent_review(tmp_path):
    with pytest.raises(ValueError, match="Required file is absent"):
        asyncio.run(run(CONFIRMATORY, tmp_path / "confirmatory", freeze_only=True,
                        providers=providers()))


def test_second_model_call_is_stopped_by_actual_prompt_budget(tmp_path):
    conditions = providers()
    frozen = prepare(PLAN, conditions)
    case = next(item for item in frozen["cases"] if item["condition_id"] == "nano_route")
    provider = conditions["nano_route"]
    plan = {**frozen["plan"], "max_cost_usd": 0.001}
    row = {"status": "pending", "retry_count": 0}
    ledger = {"status": "running", "attempts": [row]}
    spent = asyncio.run(_run_route_case(case, row, ledger, tmp_path / "ledger.json", provider,
                                        provider.identity(), plan, PLAN, 0))
    assert spent > 0 and provider.calls == 1
    assert ledger["status"] == "stopped_budget_after_route"
    assert row["status"] == "failed" and row["route_requested"]
    assert len(row["calls"]) == 1
