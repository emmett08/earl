"""Executable controls for the synthetic Kubernetes host/retrieval study."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from eal.artifacts import ArtifactRegistry
from eal.families import FamilyRegistry
from eal.runtime import ReasoningService


STUDY = Path(__file__).resolve().parents[1] / "benchmarks/experiments/kubernetes-host-revisions"
SPEC = importlib.util.spec_from_file_location("k8s_host_revision_study", STUDY / "run.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_frozen_revisions_and_candidate_reference_are_executed():
    result = module.run(repetitions=1)
    assert result["schema"] == "eal2-kubernetes-host-revisions-result/2"
    assert result["revision_count"] == result["raw_statuses_correct"] == 7
    assert result["statuses_correct"] == result["issued_count"] == 5
    assert result["refused_count"] == 2
    assert result["record_statuses_correct"] == 7
    assert {row["id"]: row["raw_assessment_status"] for row in result["revisions"]} == {
        "baseline": "supported",
        "new_batch_contention": "contested",
        "stale_load_record": "unsupported",
        "failed_current_test": "unsupported",
        "current_separate_reservation": "supported",
        "wrong_deployment": "unsupported",
        "stale_pressure_gap": "unsupported",
    }
    assert {row["id"] for row in result["revisions"] if row["host_outcome"] == "refused_unresolved"} == {
        "stale_load_record", "stale_pressure_gap"}
    assert all(row["observed_status"] is None and row["packet_bytes"] is None
               and row["direct_trace_bytes"] is None and row["refusal"]
               for row in result["revisions"] if row["host_outcome"] == "refused_unresolved")
    assert all("pinned_digest" not in json.dumps(row["refusal"])
               and "routed_failover" not in json.dumps(row["refusal"])
               for row in result["revisions"] if row["host_outcome"] == "refused_unresolved")
    assert {row["id"]: row["observed_record_status"] for row in result["revisions"]} == {
        "baseline": "supported",
        "new_batch_contention": "supported",
        "stale_load_record": "supported",
        "failed_current_test": "unsupported",
        "current_separate_reservation": "supported",
        "wrong_deployment": "unsupported",
        "stale_pressure_gap": "supported",
    }
    retrieval = result["retrieval"]
    assert retrieval["counts"] == {
        "tp": 8, "fp": 6, "fn": 1,
        "zero_target": 2, "zero_target_abstentions": 1,
    }
    assert result["rejected_routes"]["unreviewed_cluster"] == (
        "No reviewed case exists for these family bindings"
    )
    issued = [row for row in result["revisions"] if row["host_outcome"] == "issued"]
    assert all(row["packet_bytes"] <= 3072 for row in issued)
    assert all(row["packet_bytes"] < row["direct_trace_bytes"] for row in issued)
    assert all(row["evidence_integrity"] == "consistency_checked_not_authenticated"
               for row in issued)


def test_packet_cause_tracks_contention_staleness_and_separate_record_status(tmp_path):
    manifest = json.loads((STUDY / "manifest.json").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in manifest["revisions"]}
    for revision_id, expected in (
        ("new_batch_contention", ("pressure_challenge", "batch_pressure")),
        ("failed_current_test", ("bounded_load", "observed 278")),
        ("current_separate_reservation", ("reservation_response", "separate_reservation")),
    ):
        directory = tmp_path / revision_id
        module._workspace(directory, rows[revision_id])
        host = module._host(directory)
        packet = host.assess("checkout_latency", module.CONTEXT, "checkout_latency")
        reason = json.dumps(packet["decisive"], sort_keys=True)
        assert all(piece in reason for piece in expected)
        explanation = host.explain("checkout_latency", module.CONTEXT, "checkout_latency",
                                   packet["assessment_id"])
        assert set(explanation["arguments"]) == {"load_route", "record_route"}
        assert set(explanation["premises"]) == {"checkout_test_record"}
        assert "recorded_load" in explanation["evidence"]
        assert "digest_route" not in json.dumps(explanation)
        assert "failover_route" not in json.dumps(explanation)

    for revision_id, failed_evidence, expected_age in (
        ("stale_load_record", "bounded_load", "1200s exceeds max_age 600s"),
        ("stale_pressure_gap", "batch_pressure", "1200s exceeds max_age 300s"),
    ):
        directory = tmp_path / revision_id
        module._workspace(directory, rows[revision_id])
        host = module._host(directory)
        with pytest.raises(ValueError, match=f"Claim assessment unresolved: required evidence '{failed_evidence}'"):
            host.assess("checkout_latency", module.CONTEXT, "checkout_latency")
        store = host.families.artifacts.service.store
        assert not store.list(kind="artifact_packet")
        assert not store.list(kind="artifact_claim_packet")
        retained_id = store.list(kind="assessment")[0]["id"]
        raw = store.get(retained_id, kind="assessment")
        assert raw["claims"]["checkout_latency"]["status"] == "unsupported"
        assert raw["claims"]["checkout_test_record"]["status"] == "supported"
        assert any(expected_age in reason for reason in raw["evidence"][failed_evidence]["reasons"])
        if revision_id == "stale_pressure_gap":
            assert raw["evidence"]["monitor_complete"]["status"] == "unavailable"


def test_review_contract_rejects_changed_source_or_clock(tmp_path):
    manifest = json.loads((STUDY / "manifest.json").read_text(encoding="utf-8"))
    module._workspace(tmp_path / "case", manifest["revisions"][0])
    directory = tmp_path / "case"
    service = ReasoningService(directory, directory / "tools.toml",
                               database_path=directory / "runs.sqlite3")
    artifacts = ArtifactRegistry.load(service, directory / "artifacts.toml")
    FamilyRegistry.load(artifacts, directory / "families.toml")
    # The contract pins source identity before any case is resolved.
    (directory / "source.eal").write_text(
        (directory / "source.eal").read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="source differs"):
        FamilyRegistry.load(artifacts, directory / "families.toml")
