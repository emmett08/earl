"""Persistent operator invalidation of explicit observation reuse."""

from __future__ import annotations

import json
import os
import stat
import sys
from uuid import uuid4

import pytest

from eal.cli import main as cli_main
from eal.observation_reuse import ObservationRebinder
from eal.parser import parse
from eal.runtime import ReasoningService
from eal.store import RunStore


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; }
evidence measured {
  tool runner; kind test; environment lab; max_age 60;
  input {"value": 7}; require "passed" == true;
}
reasoning observation { method "structured/1"; rationale "The observation supports the claim."; }
claim works { statement "The measured check passes."; environment lab; }
argument result { conclusion works; reasoning observation; evidence measured; }
'''
CONTEXT = {"site": "bench"}


def service_for(tmp_path):
    script = tmp_path / "collector.py"
    script.write_text("import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'value': {'passed': True}}))\n")
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nversion="1"\n'
                        f'argv={json.dumps([sys.executable, str(script)])}\n')
    database = tmp_path / "runs.sqlite3"
    return ReasoningService(tmp_path, registry, database)


def candidates(service, source=SOURCE):
    program = parse(source)
    return ObservationRebinder(service.store).candidates(
        program, CONTEXT, "measured",
        current_binding_digest=service.current_binding_digests(program)["measured"],
        current_execution_digest=service.current_execution_digests(program)["measured"],
    )


def test_origin_event_invalidates_derived_records_across_restart_but_fresh_collection_works(tmp_path):
    service = service_for(tmp_path)
    first = service.collect(SOURCE, CONTEXT)
    original = first["records"]["measured"]
    revised = SOURCE.replace("The observation supports the claim.", "The same observation supports the claim.")
    derived = service.rebind(revised, CONTEXT, first["collection_id"])
    assessed = service.reason(SOURCE, CONTEXT, first["collection_id"])
    assert assessed["claims"]["works"]["status"] == "supported"

    event = service.store.invalidate_reuse(
        kind="event", origin_run_id=original["run_id"], reason="Source revision observed",
    )
    assert event["origin_run_id"] == original["run_id"]
    assert candidates(service) == []
    assert candidates(service, revised) == []
    with pytest.raises(ValueError, match="invalidated"):
        service.rebind(revised, CONTEXT, first["collection_id"])
    with pytest.raises(ValueError, match="invalidated"):
        service.rebind(revised, CONTEXT, derived["collection_id"])
    assert service.store.get(first["collection_id"], kind="collection")["records"]["measured"] == original
    assert service.explain(assessed["assessment_id"])["claims"]["works"]["status"] == "supported"

    restarted = service_for(tmp_path)
    assert candidates(restarted) == []
    fresh = restarted.collect(SOURCE, CONTEXT)
    assert [record["run_id"] for record in candidates(restarted)] == [fresh["records"]["measured"]["run_id"]]
    rebound = restarted.rebind(revised, CONTEXT, fresh["collection_id"])
    assert rebound["records"]["measured"]["origin_run_id"] == fresh["records"]["measured"]["run_id"]


def test_scoped_event_and_global_gap_block_old_measurements_only(tmp_path):
    service = service_for(tmp_path)
    first = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    other_source = SOURCE.replace('"value": 7', '"value": 8')
    other = service.collect(other_source, CONTEXT)["records"]["measured"]

    service.store.invalidate_reuse(
        kind="event", reason="This resource changed",
        tool_binding_digest=first["tool_binding_digest"],
        acquisition_request_digest=first["acquisition_request_digest"],
    )
    assert candidates(service) == []
    assert [record["run_id"] for record in candidates(service, other_source)] == [other["run_id"]]

    service.store.invalidate_reuse(kind="gap", reason="Watch reconnected without complete history")
    assert candidates(service, other_source) == []
    fresh = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    assert [record["run_id"] for record in candidates(service)] == [fresh["run_id"]]


def test_scope_event_blocks_an_in_flight_or_historical_measurement_inserted_later(tmp_path):
    service = service_for(tmp_path)
    first = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    service.store.invalidate_reuse(
        kind="event", reason="Resource changed",
        tool_binding_digest=first["tool_binding_digest"],
        acquisition_request_digest=first["acquisition_request_digest"],
    )
    late_insert = {**first, "run_id": str(uuid4())}
    service.store.put("observation", late_insert, record_id=late_insert["run_id"])
    assert candidates(service) == []
    assert service.store.reuse_invalidated(late_insert)


def test_changed_inherited_process_environment_blocks_command_rebinding(tmp_path, monkeypatch):
    service = service_for(tmp_path)
    original = service.collect(SOURCE, CONTEXT)
    revised = SOURCE.replace("The observation supports the claim.", "The same observation supports the claim.")
    monkeypatch.setenv("EAL_TEST_CLUSTER_ID", "unrelated-cluster")

    assert candidates(service) == []
    with pytest.raises(ValueError, match="process_environment_digest differs"):
        service.rebind(revised, CONTEXT, original["collection_id"])


def test_unversioned_historical_record_can_be_assessed_but_cannot_be_rebound(tmp_path):
    service = service_for(tmp_path)
    first = service.collect(SOURCE, CONTEXT)
    old = {**first["records"]["measured"], "run_id": str(uuid4())}
    del old["schema"]
    service.store.put("observation", old, record_id=old["run_id"])
    historical = {"source_digest": parse(SOURCE).source_digest,
                  "context": CONTEXT, "records": {"measured": old}}
    collection_id = service.store.put("collection", historical)
    assert service.reason(SOURCE, CONTEXT, collection_id)["claims"]["works"]["status"] == "supported"
    assert [record["run_id"] for record in candidates(service)] == [first["records"]["measured"]["run_id"]]
    with pytest.raises(ValueError, match="EAL/observation-record/1"):
        service.rebind(SOURCE, CONTEXT, collection_id)


def test_invalidate_cli_is_an_operator_route(tmp_path, monkeypatch, capsys):
    service = service_for(tmp_path)
    record = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    monkeypatch.setattr(sys, "argv", [
        "eal", "--workspace", str(tmp_path), "--database", str(service.store.path),
        "invalidate", "--kind", "event", "--origin-run-id", record["run_id"],
        "--reason", "Operator-observed source change",
    ])
    cli_main()
    response = json.loads(capsys.readouterr().out)
    assert response["origin_run_id"] == record["run_id"]
    assert candidates(service) == []


def test_database_and_sidecars_are_private_under_normal_umask(tmp_path):
    database = tmp_path / "runs.sqlite3"
    previous = os.umask(0o022)
    try:
        store = RunStore(database)
        store.put("collection", {"records": {}})
    finally:
        os.umask(previous)
    for path in (database, tmp_path / "runs.sqlite3-wal", tmp_path / "runs.sqlite3-shm"):
        if path.exists():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_store_refuses_public_or_symlinked_database_files(tmp_path):
    database = tmp_path / "runs.sqlite3"
    RunStore(database)
    database.chmod(0o644)
    with pytest.raises(PermissionError, match="private regular 0600"):
        RunStore(database)
    database.chmod(0o600)

    sidecar = tmp_path / "runs.sqlite3-wal"
    sidecar.write_text("public")
    sidecar.chmod(0o644)
    with pytest.raises(PermissionError, match="private regular 0600"):
        RunStore(database)
    sidecar.unlink()
    sidecar.symlink_to(database)
    with pytest.raises(OSError):
        RunStore(database)
