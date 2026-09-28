from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from eal.observation_reuse import ObservationRebinder
from eal.parser import parse
from eal.runtime import ReasoningService, acquisition_request
from eal.store import RunStore


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; }
evidence measured {
  tool runner; kind test; environment lab; max_age 60;
  input {"value": 7}; require "passed" == true;
}
reasoning observation { method "structured/1"; rationale "Measurement supports the bounded claim."; }
claim works { statement "The configured measurement passes."; environment lab; }
argument result { conclusion works; reasoning observation; evidence measured; }
'''
CONTEXT = {"site": "bench"}


def _service(tmp_path):
    script = tmp_path / "collector.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "request = json.load(sys.stdin)\n"
        "counter = pathlib.Path(__file__).with_name('calls.txt')\n"
        "counter.write_text(counter.read_text() + 'x' if counter.exists() else 'x')\n"
        "print(json.dumps({'value': {'passed': request['input']['value'] == 7}}))\n"
    )
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nversion="1"\n'
                        f'argv={json.dumps([sys.executable, str(script)])}\n')
    return ReasoningService(tmp_path, registry, tmp_path / "runs.sqlite3")


def _rebind(service, source, collection, *, context=CONTEXT, evidence_ids=None):
    program = parse(source)
    return ObservationRebinder(service.store).rebind_collection(
        program, context, from_collection_id=collection["collection_id"],
        current_binding_digests=service.current_binding_digests(program),
        current_execution_digests=service.current_execution_digests(program),
        evidence_ids=evidence_ids,
    )


def test_explicit_rebinding_preserves_measurement_and_origin_without_tool_call(tmp_path):
    service = _service(tmp_path)
    original = service.collect(SOURCE, CONTEXT)
    old = original["records"]["measured"]
    revised = SOURCE.replace("Measurement supports the bounded claim.",
                             "The same measurement supports this scoped claim.")
    rebound = _rebind(service, revised, original)
    new = rebound["records"]["measured"]
    assert (tmp_path / "calls.txt").read_text() == "x"
    assert original["collection_id"] != rebound["collection_id"]
    assert new["run_id"] != old["run_id"]
    assert new["source_digest"] == parse(revised).source_digest
    assert new["collected_at"] == old["collected_at"]
    assert new["started_at"] == old["started_at"]
    assert new["origin_run_id"] == old["run_id"]
    assert new["reused_from_run_id"] == old["run_id"]
    assert new["reused_from_collection_id"] == original["collection_id"]
    assert service.store.get(old["run_id"], kind="observation") == old
    assert service.store.get(new["run_id"], kind="observation") == new
    assert service.reason(revised, CONTEXT, rebound["collection_id"])["claims"]["works"]["status"] == "supported"
    next_rebound = _rebind(service, revised, rebound)
    assert next_rebound["records"]["measured"]["origin_run_id"] == old["run_id"]
    assert next_rebound["records"]["measured"]["reused_from_run_id"] == new["run_id"]


def test_rebinding_rechecks_identity_and_never_coalesces_distinct_ids(tmp_path):
    service = _service(tmp_path)
    original = service.collect(SOURCE, CONTEXT)
    rebinder = ObservationRebinder(service.store)
    program = parse(SOURCE)
    digest = service.current_binding_digests(program)["measured"]
    assert [r["run_id"] for r in rebinder.candidates(program, CONTEXT, "measured",
                                                     current_binding_digest=digest,
                                                     current_execution_digest=service.current_execution_digests(program)["measured"])] == [
        original["records"]["measured"]["run_id"]]
    renamed = SOURCE.replace("measured", "another_id")
    different = parse(renamed)
    assert rebinder.candidates(different, CONTEXT, "another_id",
                               current_binding_digest=digest,
                               current_execution_digest=service.current_execution_digests(different)["another_id"]) == []
    with pytest.raises(ValueError, match="no observation"):
        _rebind(service, renamed, original, evidence_ids=["another_id"])
    with pytest.raises(ValueError, match="context differs"):
        _rebind(service, SOURCE, original, context={"site": "other"})
    changed_env = SOURCE.replace("environment lab; max_age", "environment altered; max_age")
    changed_env = changed_env.replace("tool runner {", "environment altered { require \"site\" == \"bench\"; }\ntool runner {")
    with pytest.raises(ValueError, match="environment differs"):
        _rebind(service, changed_env, original)
    with pytest.raises(ValueError, match="tool_binding_digest differs"):
        rebinder.rebind_collection(program, CONTEXT, from_collection_id=original["collection_id"],
                                  current_binding_digests={"measured": "0" * 64},
                                  current_execution_digests=service.current_execution_digests(program))
    assert (tmp_path / "calls.txt").read_text() == "x"


def test_preserves_import_time_and_rechecks_freshness_at_assessment(tmp_path):
    observed = datetime.now(timezone.utc) - timedelta(hours=2)
    source = SOURCE.replace("max_age 60", "max_age 60")
    envelope = {"observed_at": observed.isoformat(), "context": CONTEXT,
                "request": acquisition_request(parse(source), "measured", CONTEXT),
                "value": {"passed": True}}
    (tmp_path / "input.json").write_text(json.dumps(envelope))
    (tmp_path / "tools.toml").write_text(
        '[tools.runner]\nkind="json_file"\nversion="1"\npath="input.json"\n'
    )
    service = ReasoningService(tmp_path, tmp_path / "tools.toml", tmp_path / "runs.sqlite3")
    original = service.collect(source, CONTEXT)
    assert original["records"]["measured"]["status"] == "ok"
    revised = source.replace("Measurement supports the bounded claim.", "Revised rationale.")
    rebound = _rebind(service, revised, original)
    old = original["records"]["measured"]
    new = rebound["records"]["measured"]
    assert new["collected_at"] == observed.isoformat() == old["collected_at"]
    assert service.reason(revised, CONTEXT, rebound["collection_id"])["claims"]["works"]["status"] == "unsupported"
    assert "stale_observation" in service.reason(revised, CONTEXT, rebound["collection_id"])["evidence"]["measured"]["availability_issues"]


def test_error_records_are_not_indexed_or_rebound(tmp_path):
    service = _service(tmp_path)
    missing = SOURCE.replace('version "1"', 'version "2"')
    failed = service.collect(missing, CONTEXT)
    program = parse(missing)
    with pytest.raises(ValueError, match="No current tool binding"):
        _rebind(service, missing, failed)
    assert service.store.find_observations(evidence_id="measured", environment="lab",
                                           request_digest="0" * 64,
                                           tool_binding_digest="0" * 64) == []


def test_index_survives_restart_and_rebuilds_old_entries(tmp_path):
    service = _service(tmp_path)
    original = service.collect(SOURCE, CONTEXT)
    with sqlite3.connect(service.store.path) as connection:
        connection.execute("DELETE FROM observation_index")
        connection.execute("DELETE FROM store_metadata WHERE key = 'observation-index-version'")
    restarted = RunStore(service.store.path)
    program = parse(SOURCE)
    record = original["records"]["measured"]
    assert [r["run_id"] for r in ObservationRebinder(restarted).candidates(
        program, CONTEXT, "measured",
        current_binding_digest=record["tool_binding_digest"],
        current_execution_digest=service.current_execution_digests(program)["measured"])] == [record["run_id"]]


def test_rebinding_discards_legacy_raw_process_output(tmp_path):
    service = _service(tmp_path)
    original = service.collect(SOURCE, CONTEXT)
    old = {**original["records"]["measured"], "run_id": str(uuid4()),
           "stdout": "legacy sensitive output", "stderr": "legacy sensitive diagnostic"}
    service.store.put("observation", old, record_id=old["run_id"])
    collection = {"source_digest": parse(SOURCE).source_digest,
                  "context": CONTEXT, "records": {"measured": old}}
    collection_id = service.store.put("collection", collection)
    rebound = _rebind(service, SOURCE, {"collection_id": collection_id})
    current = rebound["records"]["measured"]
    assert "stdout" not in current and "stderr" not in current
    assert current["stdout_digest"] == old["stdout_digest"]
    assert current["stderr_bytes"] == old["stderr_bytes"]
    assert service.store.get(old["run_id"], kind="observation") == old


def test_batch_rebind_rolls_back_if_a_record_id_conflicts(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    with pytest.raises(sqlite3.IntegrityError):
        store.put_batch([("observation", {"status": "ok"}, "duplicate"),
                         ("collection", {"records": {}}, "duplicate")])
    with pytest.raises(KeyError):
        store.get("duplicate")
