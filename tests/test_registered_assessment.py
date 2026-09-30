"""One-call registered assessment keeps source, tool and observation identities."""

from __future__ import annotations

import json
import sys

import pytest

from eal.catalogue import WorkspaceKnowledgeCatalogue
from eal.registered_assessment import RegisteredAssessmentHost
from eal.runtime import ReasoningService


SOURCE = '''language "EAL/2"

environment lab {
  require "site" == "bench"
}

tool reader {
  version "1"
}

evidence quick {
  tool reader
  kind test
  environment lab
  max_age 5
  require "ok" == true
}

evidence steady {
  tool reader
  kind test
  environment lab
  max_age 1000
  require "ok" == true
}

reasoning measured {
  method "structured/1"
  rationale "Both observations support this bounded claim."
}

claim works {
  statement "Both checks passed."
  environment lab
}

claim other {
  statement "An unrelated claim."
  environment lab
}

argument result = [evidence quick, steady] via measured => works
'''
AT_FIRST = "2040-01-01T00:00:01Z"
AT_SECOND = "2040-01-01T00:00:07Z"


def _host(tmp_path, *, behaviour="normal"):
    source = tmp_path / "case.eal"
    source.write_text(SOURCE)
    collector = tmp_path / "collector.py"
    collector.write_text(
        "import json, pathlib, sys\n"
        "request = json.load(sys.stdin)\n"
        "name = request['evidence_id']\n"
        "log = pathlib.Path('calls.json')\n"
        "calls = json.loads(log.read_text()) if log.exists() else []\n"
        "calls.append(name)\n"
        "log.write_text(json.dumps(calls))\n"
        f"behaviour = {behaviour!r}\n"
        "if behaviour == 'fail' and len(calls) == 1:\n"
        "    print('not JSON')\n"
        "else:\n"
        "    observed = '2040-01-01T00:00:06Z' if name == 'quick' and calls.count(name) > 1 "
        "else '2040-01-01T00:00:00Z'\n"
        "    print(json.dumps({'value': {'ok': behaviour != 'negative', "
        "'secret': 'collector-secret'}, 'observed_at': observed}))\n"
    )
    registry = tmp_path / "tools.toml"
    registry.write_text(
        '[tools.reader]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(collector)])}\n'
    )
    service = ReasoningService(tmp_path, registry)
    catalogue = WorkspaceKnowledgeCatalogue(service)
    catalogue.register("case.eal", entry_id="demo", context={"site": "bench"}, claims=["works"])
    return RegisteredAssessmentHost(service, catalogue), source


def _calls(tmp_path):
    return json.loads((tmp_path / "calls.json").read_text())


def test_one_call_collects_claim_and_uses_individually_fresh_observations(tmp_path):
    host, source = _host(tmp_path)
    first = host.assess("demo", "works", now=AT_FIRST)
    assert first["status"] == "supported"
    assert first["collected_count"] == 2
    assert first["reused_count"] == 0
    assert set(_calls(tmp_path)) == {"quick", "steady"}
    assert first["packet"]["claims"]["works"]["status"] == "supported"
    assert first["full_explanation"]["assessment_id"] == first["assessment_id"]
    assert "collector-secret" not in json.dumps(first)

    second = host.assess("demo", "works", now=AT_SECOND)
    assert second["status"] == "supported"
    assert second["collected_count"] == 1
    assert second["reused_count"] == 1
    assert _calls(tmp_path).count("quick") == 2
    assert _calls(tmp_path).count("steady") == 1
    collection = host.service.store.get(second["collection_id"], kind="collection")
    assert collection["records"]["steady"]["reused_from_run_id"] == host.service.store.get(
        first["collection_id"], kind="collection")["records"]["steady"]["run_id"]
    assert "reused_from_run_id" not in collection["records"]["quick"]
    assert host.service.explain(second["assessment_id"], "works")["result"]["status"] == "supported"
    assert host.history("demo")["assessments"][0]["assessment_id"] == second["assessment_id"]

    # A source revision changes argument wording but leaves acquisition identity
    # and the stable developer entry name intact.
    source.write_text(SOURCE.replace("Both checks passed.", "Both checks passed at this bench."))
    revised = host.assess("demo", "works", now=AT_SECOND)
    assert revised["source_digest"] != second["source_digest"]
    assert revised["reused_count"] == 2
    assert revised["collected_count"] == 0
    assert len(_calls(tmp_path)) == 3
    assert revised["status"] == "supported"


def test_negative_measurement_is_reused_and_forcing_fresh_recollects(tmp_path):
    host, _ = _host(tmp_path, behaviour="negative")
    first = host.assess("demo", "works", now=AT_FIRST)
    assert first["status"] == "unsupported"
    assert "predicate_not_met" in first["packet"]["evidence"]["quick"]["availability_issues"]
    second = host.assess("demo", "works", now=AT_FIRST)
    assert second["status"] == "unsupported"
    assert second["reused_count"] == 2
    assert second["collected_count"] == 0
    assert len(_calls(tmp_path)) == 2
    third = host.assess("demo", "works", now=AT_FIRST, reuse="fresh")
    assert third["reused_count"] == 0
    assert third["collected_count"] == 2
    assert len(_calls(tmp_path)) == 4


def test_assumption_interval_changes_support_without_expiring_tool_output(tmp_path):
    host, source = _host(tmp_path)
    source.write_text(SOURCE.replace(
        'reasoning measured {',
        'assumption stable {\n'
        '  statement "The bench is stable."\n'
        '  environment lab\n'
        '  validate steady\n'
        '  valid_from "2040-01-01T00:00:00Z"\n'
        '  valid_until "2040-01-01T00:00:10Z"\n'
        '}\nreasoning measured {',
    ).replace('[evidence quick, steady]', '[evidence quick, assumptions stable]'))
    first = host.assess("demo", "works", now=AT_FIRST)
    assert first["status"] == "supported"
    second = host.assess("demo", "works", now=AT_SECOND)
    assert second["status"] == "supported"
    assert second["reused_count"] == 1
    ended = host.assess("demo", "works", now="2040-01-01T00:00:10Z")
    assert ended["status"] == "unsupported"
    assert ended["reused_count"] == 2
    assert ended["collected_count"] == 0
    assert ended["packet"]["assumptions"]["stable"]["status"] == "unsupported"
    assert _calls(tmp_path).count("steady") == 1


def test_failed_tool_is_retried_and_unselected_claim_is_rejected_before_collection(tmp_path):
    host, _ = _host(tmp_path, behaviour="fail")
    with pytest.raises(ValueError, match="not selected"):
        host.assess("demo", "other", now=AT_FIRST)
    assert not (tmp_path / "calls.json").exists()
    first = host.assess("demo", "works", now=AT_FIRST)
    assert first["status"] == "unsupported"
    assert first["collected_count"] == 2
    second = host.assess("demo", "works", now=AT_SECOND)
    assert second["status"] == "supported"
    assert second["reused_count"] == 1
    assert second["collected_count"] == 1
    assert len(_calls(tmp_path)) == 3


def test_context_change_blocks_reuse(tmp_path):
    host, _ = _host(tmp_path)
    first = host.assess("demo", "works", now=AT_FIRST)
    context_changed = host.assess("demo", "works", context={"site": "elsewhere"}, now=AT_FIRST)
    assert context_changed["status"] == "out_of_scope"
    assert context_changed["reused_count"] == 0
    assert context_changed["collected_count"] == 2

    final = host.assess("demo", "works", now=AT_FIRST)
    assert final["reused_count"] == 2
    assert final["collected_count"] == 0
    assert _calls(tmp_path).count("quick") == 2


def test_reading_expiring_during_other_collection_is_recollected(tmp_path, monkeypatch):
    host, _ = _host(tmp_path)
    host.assess("demo", "works", now=AT_FIRST)
    # The quick reading has expired when collection begins; the steady reading
    # expires while quick is collected. Both need fresh records by assessment.
    after_steady_expiry = "2040-01-01T00:16:41Z"
    times = iter((AT_SECOND, after_steady_expiry, after_steady_expiry))
    monkeypatch.setattr("eal.registered_assessment.utc_now", lambda: next(times))
    second = host.assess("demo", "works")
    assert second["status"] == "unsupported"
    assert second["reused_count"] == 0
    assert second["collected_count"] == 2
    assert _calls(tmp_path).count("quick") == 2
    assert _calls(tmp_path).count("steady") == 2
    combined = host.service.store.get(second["collection_id"], kind="collection")
    assert set(combined["records"]) == {"quick", "steady"}
