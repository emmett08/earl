"""Automatic observation reuse across source revisions and sessions."""

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


SOURCE = '''language "EAL/2"

environment lab {
  require "site" == "bench"
}

tool runner {
  version "1"
}

evidence measured {
  tool runner
  kind test
  environment lab
  max_age 60
  input {"value": 7}
  require "passed" == true
}

reasoning observation {
  method "structured/1"
  rationale "Measurement supports the bounded claim."
}

claim works {
  statement "The configured measurement passes."
  environment lab
}

argument result = [evidence measured] via observation => works
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


def _prepare(service, source, record, *, context=CONTEXT, evidence_id="measured"):
    program = parse(source)
    return ObservationRebinder(service.store).prepare_record(
        program, context, evidence_id, record,
        current_binding_digest=service.current_binding_digests(program).get(evidence_id),
        current_execution_digest=service.current_execution_digests(program).get(evidence_id),
    )


def test_reuse_preserves_measurement_and_origin_without_tool_call(tmp_path):
    service = _service(tmp_path)
    old = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    revised = SOURCE.replace("Measurement supports the bounded claim.",
                             "The same measurement supports this scoped claim.")
    new = _prepare(service, revised, old)
    assert (tmp_path / "calls.txt").read_text() == "x"
    assert new["run_id"] != old["run_id"]
    assert new["source_digest"] == parse(revised).source_digest
    assert new["collected_at"] == old["collected_at"]
    assert new["started_at"] == old["started_at"]
    assert new["origin_run_id"] == old["run_id"]
    assert new["reused_from_run_id"] == old["run_id"]
    collection = {"source_digest": parse(revised).source_digest,
                  "context": CONTEXT, "records": {"measured": new}}
    collection_id = service.store.put_batch([
        ("observation", new, new["run_id"]), ("collection", collection, None)
    ])[-1]
    assert service.store.get(old["run_id"], kind="observation") == old
    assert service.store.get(new["run_id"], kind="observation") == new
    assert service.reason(revised, CONTEXT, collection_id)["claims"]["works"]["status"] == "supported"
    next_record = _prepare(service, revised, new)
    assert next_record["origin_run_id"] == old["run_id"]
    assert next_record["reused_from_run_id"] == new["run_id"]


def test_reuse_rechecks_request_identity_and_distinct_evidence_ids(tmp_path):
    service = _service(tmp_path)
    old = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    rebinder = ObservationRebinder(service.store)
    program = parse(SOURCE)
    assert [r["run_id"] for r in rebinder.candidates(
        program, CONTEXT, "measured", current_binding_digest=old["tool_binding_digest"],
        current_execution_digest=service.current_execution_digests(program)["measured"],
    )] == [old["run_id"]]
    renamed = SOURCE.replace("measured", "another_id")
    different = parse(renamed)
    assert rebinder.candidates(
        different, CONTEXT, "another_id",
        current_binding_digest=old["tool_binding_digest"],
        current_execution_digest=service.current_execution_digests(different)["another_id"],
    ) == []
    with pytest.raises(ValueError, match="evidence_id differs"):
        _prepare(service, renamed, old, evidence_id="another_id")
    with pytest.raises(ValueError, match="environment_fingerprint differs"):
        _prepare(service, SOURCE, old, context={"site": "other"})
    changed_env = SOURCE.replace('environment lab\n  max_age', 'environment altered\n  max_age')
    changed_env = changed_env.replace("tool runner {", '''environment altered { require "site" == "bench"
 }
tool runner {''')
    with pytest.raises(ValueError, match="environment differs"):
        _prepare(service, changed_env, old)
    with pytest.raises(ValueError, match="tool_binding_digest differs"):
        rebinder.prepare_record(
            program, CONTEXT, "measured", old,
            current_binding_digest="0" * 64,
            current_execution_digest=service.current_execution_digests(program)["measured"],
        )
    assert (tmp_path / "calls.txt").read_text() == "x"


def test_import_time_is_preserved_and_freshness_checked_at_assessment(tmp_path):
    observed = datetime.now(timezone.utc) - timedelta(hours=2)
    envelope = {"observed_at": observed.isoformat(), "context": CONTEXT,
                "request": acquisition_request(parse(SOURCE), "measured", CONTEXT),
                "value": {"passed": True}}
    (tmp_path / "input.json").write_text(json.dumps(envelope))
    (tmp_path / "tools.toml").write_text(
        '[tools.runner]\nkind="json_file"\nversion="1"\npath="input.json"\n'
    )
    service = ReasoningService(tmp_path, tmp_path / "tools.toml", tmp_path / "runs.sqlite3")
    old = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    revised = SOURCE.replace("Measurement supports the bounded claim.", "Revised rationale.")
    new = _prepare(service, revised, old)
    assert new["collected_at"] == observed.isoformat() == old["collected_at"]
    collection_id = service.store.put("collection", {
        "source_digest": parse(revised).source_digest,
        "context": CONTEXT, "records": {"measured": new},
    })
    result = service.reason(revised, CONTEXT, collection_id)
    assert result["claims"]["works"]["status"] == "unsupported"
    assert "stale_observation" in result["evidence"]["measured"]["availability_issues"]


def test_failed_records_are_not_reused_and_index_survives_restart(tmp_path):
    service = _service(tmp_path)
    missing = SOURCE.replace('version "1"', 'version "2"')
    failed = service.collect(missing, CONTEXT)["records"]["measured"]
    with pytest.raises(ValueError, match="No current tool binding"):
        _prepare(service, missing, failed)
    assert service.store.find_observations(evidence_id="measured", environment="lab",
                                           request_digest="0" * 64,
                                           tool_binding_digest="0" * 64) == []
    old = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    with sqlite3.connect(service.store.path) as connection:
        connection.execute("DELETE FROM observation_index")
        connection.execute("DELETE FROM store_metadata WHERE key = 'observation-index-version'")
    restarted = RunStore(service.store.path)
    program = parse(SOURCE)
    assert [r["run_id"] for r in ObservationRebinder(restarted).candidates(
        program, CONTEXT, "measured", current_binding_digest=old["tool_binding_digest"],
        current_execution_digest=service.current_execution_digests(program)["measured"],
    )] == [old["run_id"]]


def test_reuse_discards_legacy_raw_process_output(tmp_path):
    service = _service(tmp_path)
    old = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    legacy = {**old, "run_id": str(uuid4()),
              "stdout": "legacy sensitive output", "stderr": "legacy sensitive diagnostic"}
    service.store.put("observation", legacy, record_id=legacy["run_id"])
    current = _prepare(service, SOURCE, legacy)
    assert "stdout" not in current and "stderr" not in current
    assert current["stdout_digest"] == old["stdout_digest"]
    assert current["stderr_bytes"] == old["stderr_bytes"]
    assert service.store.get(legacy["run_id"], kind="observation") == legacy


def test_batch_write_rolls_back_if_a_record_id_conflicts(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    with pytest.raises(sqlite3.IntegrityError):
        store.put_batch([("observation", {"status": "ok"}, "duplicate"),
                         ("collection", {"records": {}}, "duplicate")])
    with pytest.raises(KeyError):
        store.get("duplicate")
