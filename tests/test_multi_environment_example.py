"""One reusable route retains separate environment and observation identities."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from eal.formatter import semantic_ir
from eal.runtime import ReasoningService


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/multi-environment"
SOURCE = (EXAMPLE / "source.eal").read_text()
CONTEXT = {"$environments": {
    name: {"dataset": "synthetic", "deployment": name, "sensor": "controller-A", "scenario": "safe"}
    for name in ("staging", "production")
}}
NOW = "2026-09-30T10:00:30Z"


def service(tmp_path: Path) -> ReasoningService:
    return ReasoningService(ROOT, EXAMPLE / "tools.toml", tmp_path / "records.sqlite3")


def test_pattern_expansion_and_formatting_preserve_shared_reasoning_and_separate_scopes(tmp_path):
    host = service(tmp_path)
    assert host.validate(SOURCE)["valid"]
    original = host.parse(SOURCE)
    formatted = host.parse(host.format(SOURCE)["source"])
    assert semantic_ir(original) == semantic_ir(formatted)
    assert len(original.patterns) == 1
    for name in ("staging", "production"):
        argument = original.arguments[f"{name}_check.assess"]
        assert argument.reasoning == "sample_criterion"
        assert argument.evidence == (f"{name}_check.readings",)
        assert original.claims[argument.conclusion].environment == name
        assert original.evidence[argument.evidence[0]].environment == name


def test_collector_records_bind_distinct_samples_to_each_environment(tmp_path):
    host = service(tmp_path)
    collected = host.collect(SOURCE, CONTEXT)
    records = collected["records"]
    first, second = (records[f"{name}_check.readings"] for name in ("staging", "production"))
    assert first["status"] == second["status"] == "ok"
    assert first["run_id"] != second["run_id"]
    assert first["environment_fingerprint"] != second["environment_fingerprint"]
    assert first["value"]["samples"] == [60, 64, 68]
    assert second["value"]["samples"] == [72, 75, 78]
    for record in (first, second):
        assert record["environment"] == record["context"]["deployment"]
        assert "$environments" not in record["acquisition_request"]["context"]
    assessed = host.reason(SOURCE, CONTEXT, collected["collection_id"], now=NOW)
    assert {claim["status"] for claim in assessed["claims"].values()} == {"supported"}


def test_changed_context_cannot_reassess_an_old_collection(tmp_path):
    host = service(tmp_path)
    collected = host.collect(SOURCE, CONTEXT)
    changed = deepcopy(CONTEXT)
    changed["$environments"]["production"]["scenario"] = "overheat"
    with pytest.raises(ValueError, match="context"):
        host.reason(SOURCE, changed, collected["collection_id"], now=NOW)
    current = host.collect(SOURCE, changed)
    assessed = host.reason(SOURCE, changed, current["collection_id"], now=NOW)
    assert assessed["claims"]["staging_check.within_limit"]["status"] == "supported"
    assert assessed["claims"]["production_check.within_limit"]["status"] == "unsupported"
    assert current["records"]["production_check.readings"]["status"] == "ok"


def test_missing_scope_and_expired_samples_supply_no_production_support(tmp_path):
    host = service(tmp_path)
    missing = {"$environments": {"staging": CONTEXT["$environments"]["staging"]}}
    collected = host.collect(SOURCE, missing)
    assessed = host.reason(SOURCE, missing, collected["collection_id"], now=NOW)
    assert collected["records"]["production_check.readings"]["status"] == "error"
    assert assessed["claims"]["staging_check.within_limit"]["status"] == "supported"
    assert assessed["claims"]["production_check.within_limit"]["status"] == "out_of_scope"
    current = host.collect(SOURCE, CONTEXT)
    expired = host.reason(SOURCE, CONTEXT, current["collection_id"], now="2026-09-30T10:01:01Z")
    assert {claim["status"] for claim in expired["claims"].values()} == {"unsupported"}


def test_runnable_example_reuses_only_compatible_scoped_observations(tmp_path):
    spec = importlib.util.spec_from_file_location("multi_environment_example", EXAMPLE / "run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    result = runner.demonstrate(tmp_path / "records.sqlite3")
    assert result["first_session"] == {
        name: {"status": "supported", "collected_count": 1, "reused_count": 0}
        for name in ("staging", "production")
    }
    assert result["second_session"] == {
        name: {"status": "supported", "collected_count": 0, "reused_count": 1}
        for name in ("staging", "production")
    }
    assert result["production_overheat"] == {
        "status": "unsupported", "collected_count": 1, "reused_count": 0}
    assert result["production_context_missing"]["status"] == "out_of_scope"
