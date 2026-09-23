"""Scientific-control and record-integrity tests, using no live model calls."""
import asyncio
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import notation_transfer_experiment as study
from analyse_relay_transitions import analyse, DEFAULT
from check_reasoning_argument import check
from eal.providers import ModelResponse


@pytest.fixture(scope="module")
def frozen():
    return study.freeze(ROOT / "benchmarks/experiments/eal2-notation-transfer-diagnostic.json")


def test_same_meaning_and_only_surface_changes(frozen):
    assert len(frozen["schedule"]) == 180
    for task in frozen["tasks"].values():
        assert study.semantic_view(task["representations"]["eal"]) == task["representations"]["json"]
        a = {"notation": "eal", "candidate_quality": "absent", "information": "raw_only"}
        b = {**a, "notation": "json"}
        left = study.messages_for(task, a, 0, frozen["common_reference"])
        right = study.messages_for(task, b, 0, frozen["common_reference"])
        assert left[0] == right[0]
        left, right = json.loads(left[1]["content"]), json.loads(right[1]["content"])
        left.pop("argument")
        right.pop("argument")
        assert left == right


def test_raw_data_and_injected_proposal_do_not_smuggle_scores(frozen):
    for task in frozen["tasks"].values():
        for repetition in (0, 1):
            common = {"notation": "eal", "candidate_quality": "incorrect"}
            packets = {}
            for information in study.INFORMATION:
                messages = study.messages_for(task, {**common, "information": information}, repetition, "")
                packets[information] = json.loads(messages[1]["content"])
            proposal = packets["answer"]["proposed_answer"]["claims"]
            assert all(proposal[k] != v for k, v in task["expected"].items())
            for information, packet in packets.items():
                assert packet["proposed_answer"]["claims"] == proposal
                assert not {"expected", "oracle", "score", "candidate_quality", "semantic_digest"} & packet.keys()
                assert ("interpreter_conclusions" in packet) == (information == "answer_assessed")
            assert "observations" not in packets["answer"]
            raw = packets["answer_raw"]["observations"]
            irrelevant = packets["answer_irrelevant"]["observations"]
            for name in raw:
                assert raw[name]["value"] == irrelevant[name]["value"]
                assert irrelevant[name]["context"]["assembly"] != task["inputs"]["context"]["assembly"]


def test_shared_prefix_audit_and_missing_correction_denominator():
    result = analyse(DEFAULT)
    assert result["endpoints"] == 324
    assert all(c["shared_producer_checked"] for c in result["comparisons"])
    primary = result["conditions"]["l_tool_n_evidence"]["counts"]
    assert primary.get("producer_incorrect", 0) == 0
    # Two failed producer outcomes are different scientific categories.
    mixed = result["conditions"]["n_tool_r_evidence"]["counts"]
    assert mixed["corrected"] == 1
    assert mixed["recovered_incomplete"] == 1


def test_duplicate_endpoint_rejected(tmp_path):
    for name in ("complete-block-endpoints.csv", "complete-block-stages.csv"):
        (tmp_path / name).write_bytes((DEFAULT / name).read_bytes())
    p = tmp_path / "complete-block-endpoints.csv"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines + [lines[1]]) + "\n")
    with pytest.raises(ValueError, match="Duplicate endpoint"):
        analyse(tmp_path)


def test_argument_does_not_promote_pending_study():
    report = check()
    assert report["claims"]["requested_contribution_established"] == "unsupported"
    assert report["claims"]["whole_system_correction_observed"] == "supported"


def test_credential_absence_creates_no_attempts(frozen, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = asyncio.run(study.execute(frozen, tmp_path))
    assert report["status"] == "blocked_before_execution"
    assert report["attempted"] == 0 and report["live_results"] is False
    assert not (tmp_path / "trials").exists()


def test_unknown_usage_stops_and_is_not_retried(frozen, tmp_path, monkeypatch):
    class UnpricedProvider:
        calls = 0

        async def complete(self, messages, max_output_tokens):
            self.calls += 1
            return ModelResponse('{"claims": {}, "basis": []}')

    provider = UnpricedProvider()
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-never-sent")
    monkeypatch.setattr(study, "provider_from_config", lambda config: provider)
    report = asyncio.run(study.execute(frozen, tmp_path))
    assert report["attempted"] == 1 and provider.calls == 1
    assert report["status"] == "provider_failure_or_unknown_usage"
    resumed = asyncio.run(study.execute(frozen, tmp_path))
    assert resumed["attempted"] == 1 and provider.calls == 1
    assert resumed["status"] == "prior_provider_failure_not_retried"


def test_uncertain_attempt_kept_separate_from_unexecuted(frozen, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-never-sent")
    row = frozen["schedule"][0]
    study.write(tmp_path / "trials" / (row["trial_id"] + ".json"),
                {**row, "freeze_digest": frozen["freeze_digest"], "state": "attempt_started"})
    report = asyncio.run(study.execute(frozen, tmp_path))
    assert report["attempted"] == 0 and report["uncertain_attempts"] == 1
    assert report["unexecuted"] == 179


def test_freeze_change_rejected(frozen, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    asyncio.run(study.execute(frozen, tmp_path))
    changed = copy.deepcopy(frozen)
    changed["plan"]["repetitions"] += 1
    with pytest.raises(ValueError, match="different freeze"):
        asyncio.run(study.execute(changed, tmp_path))


def test_partial_pairs_cannot_appear_as_full_comparison(frozen):
    raw = next(x for x in frozen["schedule"] if x["condition"]["id"] == "eal_raw_only")
    record = {**raw, "score": {"correct": True, "unjustified": False},
              "available_information_score": {"correct": True, "unjustified": False}, "cost_usd": 0.001}
    report = study.summarise([record], 180)
    assert report["paired_comparisons"][0]["coverage_complete"] is False
    assert report["paired_comparisons"][0]["task_weighted_difference"] is None


def test_complete_synthetic_pipeline_and_resume(frozen, tmp_path, monkeypatch):
    class FixedLabelProvider:
        calls = 0

        async def complete(self, messages, max_output_tokens):
            self.calls += 1
            packet = json.loads(messages[1]["content"])
            response = {"claims": {name: "supported" for name in packet["requested_claims"]}, "basis": []}
            return ModelResponse(json.dumps(response), 100, 20, frozen["provider_identity"]["model"])

    provider = FixedLabelProvider()
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-never-sent")
    monkeypatch.setattr(study, "provider_from_config", lambda config: provider)
    result = asyncio.run(study.execute(frozen, tmp_path))
    assert result["status"] == "completed" and result["attempted"] == 180
    assert sum(g["correct"] for g in result["conditions"].values()) == 108
    assert all(x["coverage_complete"] for x in result["paired_comparisons"])
    assert result["paired_comparisons"][0]["task_weighted_difference"] == 0
    asyncio.run(study.execute(frozen, tmp_path))
    assert provider.calls == 180  # Reuse saved synthetic responses, never recharge.


def test_missing_or_wrong_scope_evidence_has_its_own_reference(frozen):
    task = frozen["tasks"]["registered-rms-velocity"]
    refs = task["available_information_references"]
    assert refs["answer_raw"] == {"vibration_within_limit": "supported"}
    assert refs["answer"] == {"vibration_within_limit": "unsupported"}
    assert refs["answer_irrelevant"] == {"vibration_within_limit": "unsupported"}
    assert task["expected"] == refs["answer_raw"]


def test_valid_perfect_response_scores_correct(frozen, tmp_path, monkeypatch):
    one = copy.deepcopy(frozen)
    one["schedule"] = [one["schedule"][0]]
    row = one["schedule"][0]
    expected = one["tasks"][row["task_id"]]["expected"]

    class KnownAnswerProvider:
        async def complete(self, messages, max_output_tokens):
            return ModelResponse(json.dumps({"claims": expected, "basis": []}), 100, 20,
                                 one["provider_identity"]["model"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-never-sent")
    monkeypatch.setattr(study, "provider_from_config", lambda config: KnownAnswerProvider())
    result = asyncio.run(study.execute(one, tmp_path))
    assert result["conditions"][row["condition"]["id"]]["correct"] == 1
