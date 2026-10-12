"""Current-time fixtures for two genuine registered EAL task profiles."""

from datetime import datetime, timezone
import hashlib
import json

import pytest

from eal.api_load_methods import registry
from eal.knowledge import EALKnowledgeBase
from eal.semantics import parse_time
from experiments.mas_coordination.coordinator_demo import (
    API_CLAIMS, EXAMPLE, GENERIC_CLAIMS, prepare_demo,
)


def knowledge(spec):
    server = spec["server"]
    return EALKnowledgeBase(server["workspace"], server["registry"], server["database"],
                            method_registry=registry())


def test_prepare_registers_both_profiles_without_assessment_or_overwriting_example(tmp_path):
    original = {name: (EXAMPLE / name).read_bytes()
                for name in ("source.eal", "report.json", "collect_results.py")}
    before = datetime.now(timezone.utc)
    spec = prepare_demo(tmp_path)
    after = datetime.now(timezone.utc)
    assert before.replace(microsecond=0) <= parse_time(spec["created_at"]) <= after
    assert spec["dataset"] == "synthetic"
    assert {task["profile"] for task in spec["tasks"]} == {"api_load/1", "registered_claims/1"}
    assert all(len(task["claims"]) >= 2 for task in spec["tasks"])
    kb = knowledge(spec)
    assert {entry["entry_id"] for entry in kb.sources()} == {"api_sample", "availability_sample"}
    assert all(kb.history(task["entry_id"])["assessments"] == [] for task in spec["tasks"])
    assert {name: (EXAMPLE / name).read_bytes() for name in original} == original
    # Each source pins its identified synthetic bytes, not merely their names.
    for fixture, source in (("report.json", "api-load.eal"), ("availability.json", "availability.eal")):
        data = (tmp_path / fixture).read_bytes()
        assert json.loads(data)["observed_at"] == spec["created_at"]
        assert hashlib.sha256(data).hexdigest() in (tmp_path / source).read_text()
    text = json.dumps(spec)
    assert "expected_statuses" not in text and "binding_key" not in text


def test_actual_current_time_eal_distinguishes_supported_contested_and_negative_claims(tmp_path):
    spec = prepare_demo(tmp_path)
    kb = knowledge(spec)
    api = {claim: kb.assess("api_sample", claim) for claim in API_CLAIMS}
    assert {claim: item["status"] for claim, item in api.items()} == {
        "performance_criteria_met": "supported", "performance_criteria_failed": "unsupported",
    }
    generic = {claim: kb.assess("availability_sample", claim) for claim in GENERIC_CLAIMS}
    assert {claim: item["status"] for claim, item in generic.items()} == {
        "sample_endpoint_available": "contested", "sample_quorum_present": "supported",
    }
    assert generic["sample_endpoint_available"]["packet"]["objections"]["recorded_outage"]["status"] == "active"
    for item in [*api.values(), *generic.values()]:
        assert parse_time(item["assessed_at"]) >= parse_time(spec["created_at"])
        for evidence in item["packet"]["evidence"].values():
            assert evidence["observed_at"] == spec["created_at"]
    # A later session obtains compatible recorded observations, without
    # repeating collector effects or changing their original timestamps.
    later = knowledge(spec)
    for task in spec["tasks"]:
        item = later.assess(task["entry_id"], task["claims"][0])
        assert item["collected_count"] == 0 and item["reused_count"] > 0


def test_demo_refuses_to_replace_prior_runs_or_non_directory_paths(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "retained.json").write_text("retained")
    with pytest.raises(FileExistsError, match="empty output directory"):
        prepare_demo(existing)
    assert (existing / "retained.json").read_text() == "retained"
    file = tmp_path / "file"
    file.write_text("retained")
    with pytest.raises(FileExistsError):
        prepare_demo(file)


def test_changed_snapshot_is_not_admitted_as_the_pinned_synthetic_observation(tmp_path):
    spec = prepare_demo(tmp_path)
    path = tmp_path / "availability.json"
    snapshot = json.loads(path.read_bytes())
    snapshot["value"]["outage_count"] = 0
    path.write_text(json.dumps(snapshot))
    kb = knowledge(spec)
    result = kb.assess("availability_sample", "sample_endpoint_available")
    assert result["status"] == "unsupported"
    assert all(row["status"] == "unavailable" for row in result["packet"]["evidence"].values())
