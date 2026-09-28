"""One claim can be planned, collected, assessed and carried across sessions."""

from __future__ import annotations

import json
import sys

import pytest

from eal.runtime import ReasoningService
from eal.knowledge import EALKnowledgeBase


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool reader { version "1"; }
tool unrelated_reader { version "1"; }
evidence reading { tool reader; kind test; environment lab; max_age 60; require "ok" == true; }
evidence unrelated { tool unrelated_reader; kind test; environment lab; max_age 60; require "ok" == true; }
reasoning measured { method "structured/1"; rationale "The check supports this bounded claim."; }
claim works { statement "The check passed."; environment lab; }
claim separate { statement "A separate check passed."; environment lab; }
argument result { conclusion works; reasoning measured; evidence reading; }
argument other { conclusion separate; reasoning measured; evidence unrelated; }
'''
CONTEXT = {"site": "bench"}


def test_claim_workflow_rebinds_without_recollecting_and_packet_is_scoped(tmp_path):
    collector = tmp_path / "reader.py"
    collector.write_text(
        "import json, pathlib, sys\n"
        "request = json.load(sys.stdin)\n"
        "path = pathlib.Path('calls.txt')\n"
        "path.write_text(path.read_text() + 'x' if path.exists() else 'x')\n"
        "print(json.dumps({'value': {'ok': True}}))\n"
    )
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.reader]\nkind="command"\nversion="1"\n'
                        f'argv={json.dumps([sys.executable, str(collector)])}\n'
                        '[tools.unrelated_reader]\nkind="command"\nversion="1"\n'
                        f'argv={json.dumps([sys.executable, str(collector)])}\n')
    service = ReasoningService(tmp_path, registry)
    plan = service.plan(SOURCE, "works")
    assert plan["evidence_ids"] == ["reading"]
    assert plan["estimated_calls"] == 1
    collection = service.collect_claim(SOURCE, CONTEXT, "works")
    assert list(collection["records"]) == ["reading"]
    assert (tmp_path / "calls.txt").read_text() == "x"
    assessment = service.reason(SOURCE, CONTEXT, collection["collection_id"])
    assert assessment["claims"]["works"]["status"] == "supported"
    packet = service.packet(assessment["assessment_id"], "works")
    assert list(packet["claims"]) == ["works"]
    assert "unrelated" not in json.dumps(packet)
    assert packet["full_explanation"]["assessment_id"] == assessment["assessment_id"]

    revised = SOURCE.replace("The check passed.", "The check passed in this lab.")
    with pytest.raises(ValueError, match="assessment source"):
        service.reason(revised, CONTEXT, collection["collection_id"])
    (tmp_path / "revised.eal").write_text(revised)
    restarted = EALKnowledgeBase(tmp_path, registry)
    restarted.register("revised.eal", context=CONTEXT, claims=["works"])
    rebound = restarted.assess("revised.eal", "works")
    assert rebound["reused_count"] == 1
    derived = restarted.service.store.get(rebound["collection_id"], kind="collection")
    assert derived["records"]["reading"]["collected_at"] == collection["records"]["reading"]["collected_at"]
    assert (tmp_path / "calls.txt").read_text() == "x"
    assert rebound["status"] == "supported"


def test_packet_rejects_current_method_registry_contract_drift(tmp_path):
    service = ReasoningService(tmp_path)
    assessment_id = service.store.put("assessment", {
        "valid": True, "method_registry_fingerprint": "a" * 64,
        "claims": {}, "collection_id": None,
    })
    with pytest.raises(ValueError, match="method registry differs"):
        service.packet(assessment_id)
