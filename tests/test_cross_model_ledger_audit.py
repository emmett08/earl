"""The read-only forensic audit catches omissions that basic ledger scoring misses."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_cross_model_ledger import inspect  # noqa: E402
from run_cross_model_campaign import digest, prepare  # noqa: E402
from eal.providers import ModelResponse, response_cost  # noqa: E402


PLAN = ROOT / "benchmarks" / "experiments" / "cross-model-developmental.json"


@pytest.fixture(scope="module")
def frozen():
    # Offline only. No credential, network connection or model call is made.
    return prepare(PLAN)


def _write(tmp_path: Path, frozen: dict, attempts: list[dict]) -> Path:
    (tmp_path / "freeze.json").write_text(json.dumps(frozen), encoding="utf-8")
    (tmp_path / "ledger.json").write_text(json.dumps({
        "schema": "eal2-cross-model-ledger/1", "freeze_sha256": frozen["freeze_sha256"],
        "status": "running", "attempts": attempts,
    }), encoding="utf-8")
    return tmp_path


def _pending(frozen: dict, index: int) -> dict:
    case = frozen["cases"][index]
    return {"index": index, "case_id": case["case_id"], "prompt_sha256": case["prompt_sha256"],
            "status": "pending", "retry_count": 0, "usage": None}


def test_route_first_prompt_must_equal_frozen_prompt(tmp_path, frozen):
    index = next(i for i, case in enumerate(frozen["cases"]) if case["arm"] == "skill_route")
    attempts = [_pending(frozen, i) for i in range(index + 1)]
    case = frozen["cases"][index]
    altered = json.loads(json.dumps(case["messages"]))
    altered[1]["content"] = altered[1]["content"].replace("Task: ", "Different task: ", 1)
    attempts[-1]["calls"] = [{"index": 0, "status": "pending", "prompt_sha256": digest(altered),
                              "messages": altered, "usage": None}]
    with pytest.raises(ValueError, match="Routed first prompt differs from freeze"):
        inspect(_write(tmp_path, frozen, attempts))


def test_failed_route_retains_known_paid_first_call_cost(tmp_path, frozen):
    index = next(i for i, case in enumerate(frozen["cases"]) if case["arm"] == "skill_route")
    attempts = [_pending(frozen, i) for i in range(index + 1)]
    case = frozen["cases"][index]
    identity = frozen["provider_identities"][case["condition_id"]]
    actual_model = frozen["plan"].get("response_model_aliases", {}).get(case["condition_id"], identity["model"])
    response = ModelResponse('{"operation":"decline"}', 100, 10, actual_model)
    cost = response_cost(response, identity)
    attempts[-1].update(status="failed", error="second call did not return billed usage", calls=[{
        "index": 0, "status": "completed", "prompt_sha256": case["prompt_sha256"],
        "messages": case["messages"], "response": {"text": response.text, "model": response.model,
                                              "metadata": response.metadata},
        "usage": {"input_tokens": 100, "output_tokens": 10, "model_cost_usd": cost},
        "duration_seconds": 0.1,
    }])
    report = inspect(_write(tmp_path, frozen, attempts))
    assert report["failed_route_subcall_cost_missing_from_standard_analyser_usd"] == pytest.approx(cost)
    assert report["known_configured_rate_model_cost_usd_lower_bound"] == pytest.approx(cost)
