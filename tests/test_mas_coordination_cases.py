"""Real EAL task fixtures and independent answer/delivery outcome checks."""

import json

import pytest

from experiments.mas_coordination.cases import (
    CASE_IDS, CLAIMS, EXAMPLE, FAILED_CLAIM, MET_CLAIM, OBSERVED_AT,
    SOURCE_SCOPE, case_spec, prepare_case, preseed, score_response,
)


def answer(case_id):
    spec = case_spec(case_id)
    return {"statuses": dict(spec.expected_statuses), "scope": spec.requested_scope,
            "assessed_at": spec.assessed_at, "conclusion": spec.expected_conclusion,
            "production_supported": False}


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_real_fixture_assessments_preserve_identity_and_negative_distinctions(tmp_path, case_id):
    original = {name: (EXAMPLE / name).read_bytes()
                for name in ("source.eal", "report.json", "collect_results.py")}
    fixture = prepare_case(case_id, tmp_path / case_id)
    seeded = preseed(fixture)
    assert fixture.context == {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
    assert set(seeded) == set(CLAIMS)
    expected = ({MET_CLAIM: "supported", FAILED_CLAIM: "unsupported"}
                if case_id == "scope_mismatch" else fixture.expected_statuses)
    assert {claim: item["status"] for claim, item in seeded.items()} == expected
    for item in seeded.values():
        assert item["assessed_at"] == fixture.assessed_at
        assert item["entry_id"] == "load_test"
        collection = fixture.knowledge.service.store.get(item["collection_id"], kind="collection")
        assert collection["context"] == fixture.context
        assert collection["records"]["load_test"]["collected_at"] == OBSERVED_AT
        assert item["packet"]["evidence"]["load_test"]["observed_at"] == OBSERVED_AT
    report = json.loads((fixture.workspace / "report.json").read_text())
    assert {key: report[key] for key in SOURCE_SCOPE} == SOURCE_SCOPE
    assert len(report["requests"]) == 100
    assert sum(not 200 <= row["status_code"] < 300 for row in report["requests"]) == (
        2 if case_id == "measured_failure" else 1)
    assert {name: (EXAMPLE / name).read_bytes() for name in original} == original


def test_stale_recollection_preserves_measurement_time(tmp_path):
    fixture = prepare_case("stale", tmp_path)
    seeded = preseed(fixture)
    for item in seeded.values():
        assert item["collected_count"] == 1
        assert item["reused_count"] == 0
        assert item["status"] == "unsupported"
    again = preseed(fixture)
    assert all(item["collected_count"] == 1 for item in again.values())


def test_scope_rejection_is_separate_from_correct_unassessed_answer():
    scored = score_response("scope_mismatch", answer("scope_mismatch"), delivery="rejected")
    assert scored["answer_correct"] is True
    assert scored["justified_unresolved"] is True
    assert scored["resolved"] is False
    wrong = answer("scope_mismatch")
    wrong["statuses"] = {MET_CLAIM: "unsupported", FAILED_CLAIM: "unsupported"}
    assert score_response("scope_mismatch", wrong, delivery="rejected")["answer_correct"] is False
    missing = score_response("scope_mismatch", None, delivery="rejected")
    assert missing["answer_correct"] is None
    assert missing["delivery"] == "rejected"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_scoring_requires_scope_time_and_production_qualification(case_id):
    assert score_response(case_id, answer(case_id))["answer_correct"] is True
    wrong = answer(case_id)
    wrong["scope"]["build_id"] = "another-build"
    assert "wrong_requested_scope" in score_response(case_id, wrong)["errors"]
    wrong = answer(case_id)
    wrong["production_supported"] = True
    assert score_response(case_id, wrong)["answer_correct"] is False
    wrong = answer(case_id)
    wrong["assessed_at"] = "2026-10-12T00:00:00Z"
    assert score_response(case_id, wrong)["answer_correct"] is False


def test_preparation_never_overwrites_existing_run(tmp_path):
    existing = tmp_path / "report.json"
    existing.write_text("user-owned")
    with pytest.raises(FileExistsError, match="empty run workspace"):
        prepare_case("nominal", tmp_path)
    assert existing.read_text() == "user-owned"


def test_case_and_delivery_contracts_reject_unknown_values():
    with pytest.raises(ValueError, match="Unknown coordination case"):
        case_spec("unplanned")
    with pytest.raises(ValueError, match="delivery must"):
        score_response("nominal", answer("nominal"), delivery="silently_repaired")
