"""Offline controls for the developmental 960-case schedule and billing gate."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_mechanisms_960 as study
from eal.providers import ModelResponse


@pytest.fixture(scope="module")
def frozen():
    return study.freeze(ROOT / "benchmarks/experiments/mechanisms-960/plan.json")


def test_24_new_roots_full_schedule_and_192_separate_executions(frozen):
    assert len(frozen["roots"]) == 24
    assert len(frozen["schedule"]) == 960 == len({case["id"] for case in frozen["schedule"]})
    assert frozen["deterministic_parity"]["executions"] == 192
    assert frozen["deterministic_parity"]["discordance"] == 0
    assert frozen["deterministic_parity"]["tampered_accepted"] == 0
    assert frozen["reserve_usd"] <= frozen["plan"]["max_configured_model_cost_usd"]
    for root in frozen["roots"]:
        selected = [case for case in frozen["schedule"] if case["root_id"] == root["id"]]
        assert len(selected) == 40
        assert {case["arm"] for case in selected} == set(study.ARMS)
        assert {case["notation"] for case in selected} == {"eal", "json"}
        assert {case["reference"] for case in selected} == {"compact", "historical_length"}


def test_prompt_contents_prevent_oracle_leakage_and_preserve_checked_identity(frozen):
    for case in frozen["schedule"]:
        packet = json.loads(case["messages"][1]["content"])
        assert set(packet).isdisjoint({"reference_rule", "valid_status", "invalid_status", "absent_status",
                                      "wrong_proposal", "oracle", "score"})
        assert case["messages"][0]["content"].endswith(frozen["references"][case["reference"]])
        assert ("observations" in packet) == (case["arm"] != "wrong_proposal_only")
        assert ("eligibility_memo" in packet) == (case["arm"] == "wrong_proposal_valid_raw_eligibility")
        assert ("registered_method_result" in packet) == (case["arm"] == "wrong_proposal_valid_raw_method")
        assert ("checked_assessment" in packet) == (case["arm"] == "wrong_proposal_valid_raw_status")
        assert ("unvalidated_earlier_verdict" in packet) == (case["arm"] == "wrong_proposal_invalid_raw_forged_status")
        if "checked_assessment" in packet:
            root = next(item for item in frozen["roots"] if item["id"] == case["root_id"])
            assert packet["checked_assessment"]["source_sha256"] == study.digest(
                root["representations"]["eal"].encode("utf-8"))
            assert packet["checked_assessment"]["semantic_sha256"] == study.digest(root["representations"]["json"])
        if "unvalidated_earlier_verdict" in packet:
            assert "disposition" not in packet["unvalidated_earlier_verdict"]
            assert packet["unvalidated_earlier_verdict"]["status"] != case["available_reference"]


def test_review_gate_is_separate_from_dry_freeze(frozen, tmp_path):
    assert frozen["review_class"] == "pending_independent_human_review"
    with pytest.raises(ValueError, match="review attestation"):
        study.verify_review(frozen, tmp_path)
    review = {"schema": "eal2-mechanisms-review/2", "status": "developmental_ai_review_accepted",
              "freeze_sha256": frozen["freeze_sha256"],
              "manifest_sha256": frozen["materials_sha256"]["benchmarks/experiments/mechanisms-960/fixtures/manifest.json"],
              "reviewers": [{"id": "masked_fixture_review", "report_sha256": "a" * 64},
                            {"id": "unmasked_prompt_audit", "report_sha256": "b" * 64}],
              "masked_packet_sha256": "c" * 64,
              "limitations": ["AI review, synthetic data, no authenticated physical acquisition"]}
    study.write(tmp_path / "review-attestation.json", review)
    assert study.verify_review(frozen, tmp_path) == review
    review["freeze_sha256"] = "0" * 64
    study.write(tmp_path / "review-attestation.json", review)
    with pytest.raises(ValueError, match="did not accept"):
        study.verify_review(frozen, tmp_path)


def test_model_mismatch_is_retained_as_billed_failure():
    class WrongSnapshot:
        async def complete(self, messages, limit):
            return ModelResponse('{"claims":{"claim":"supported"},"basis":[]}', 100, 20, "wrong-model")

    case = {"id": "root:arm:eal:compact", "messages": [{"role": "user", "content": "synthetic"}],
            "prompt_sha256": "0" * 64, "claim": "claim", "available_reference": "unsupported",
            "full_information_reference": "supported", "proposal": "contested"}
    identity = {"pricing": {"input_usd_per_million": 0.10, "output_usd_per_million": 0.40}}
    row = asyncio.run(study.one_case(0, case, WrongSnapshot(), identity, {"expected-model"}, 768))
    assert row["state"] == "failed" and row["error_kind"] == "response_model_mismatch"
    assert row["usage"]["input_tokens"] == 100 and row["cost_usd"] > 0
