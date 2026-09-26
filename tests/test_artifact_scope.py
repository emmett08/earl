"""A checked recipient route acquires the selected claim's complete evidence closure."""

import hashlib
import json
import sys
from dataclasses import replace

import pytest

from eal.artifacts import ArtifactRegistry
from eal import evaluator
from eal.runtime import ReasoningService


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
environment field { require "site" == "field"; }
tool runner { version "1"; }
evidence leaf_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }
evidence calibration_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }
evidence backing_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }
evidence challenge_record { tool runner; kind test; environment lab; max_age 3600; require "finding" == true; }
evidence defence_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }
evidence attacker_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }
evidence irrelevant_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }
evidence foreign_record { tool runner; kind test; environment field; max_age 3600; require "passed" == true; }
assumption calibrated { statement "The test is calibrated."; environment lab; validate calibration_record; }
reasoning checked { method "structured/1"; rationale "The calibrated test supports this claim."; backing backing_record; }
reasoning inferred { method "structured/1"; rationale "The premise supports this bounded decision."; }
claim leaf { statement "The leaf test passes."; environment lab; }
claim middle { statement "The leaf result supplies a premise."; environment lab; }
claim decision { statement "The bounded decision is supported."; environment lab; }
claim attacker { statement "A potential counterclaim applies."; environment lab; }
claim irrelevant { statement "An unrelated claim holds."; environment lab; }
claim foreign { statement "A different scope has a distinct claim."; environment field; }
argument leaf_route { conclusion leaf; reasoning checked; evidence leaf_record; assumptions calibrated; }
argument middle_route { conclusion middle; reasoning inferred; premises leaf; }
argument decision_route { conclusion decision; reasoning inferred; premises middle; }
argument attacker_route { conclusion attacker; reasoning inferred; evidence attacker_record; }
argument irrelevant_route { conclusion irrelevant; reasoning inferred; evidence irrelevant_record; }
argument foreign_route { conclusion foreign; reasoning inferred; evidence foreign_record; }
objection challenge { target assumption calibrated; evidence challenge_record; }
objection answer { target objection challenge; evidence defence_record; }
objection alternative_attack { target claim decision; premises attacker; }
objection alternative_answer { target objection alternative_attack; evidence defence_record; }
objection foreign_method { target reasoning inferred; evidence foreign_record; }
'''

NEEDED = {"leaf_record", "calibration_record", "backing_record", "challenge_record",
          "defence_record", "attacker_record"}


def setup_registry(tmp_path, *, source=SOURCE):
    (tmp_path / "checked.eal").write_text(source)
    collector = tmp_path / "collector.py"
    collector.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "request=json.load(sys.stdin)\nname=request['evidence_id']\n"
        "with Path('calls.txt').open('a') as log: log.write(name+'\\n')\n"
        "if Path('broken.txt').exists() and name==Path('broken.txt').read_text(): sys.exit(2)\n"
        "value={'finding':False} if name=='challenge_record' else {'passed':True}\n"
        "date='2039-01-31T08:30:00Z' if Path('stale.txt').exists() and name==Path('stale.txt').read_text() else '2040-01-31T08:30:00Z'\n"
        "print(json.dumps({'value':value,'observed_at':date}))\n")
    tools = tmp_path / "tools.toml"
    tools.write_text('[tools.runner]\nkind="command"\nversion="1"\nargv='
                     + json.dumps([sys.executable, str(collector)]) + "\n")
    service = ReasoningService(tmp_path, tools)
    manifest = tmp_path / "artifacts.toml"
    manifest.write_text(
        '[artifacts.reviewed]\npath="checked.eal"\n'
        f'sha256="{hashlib.sha256(source.encode()).hexdigest()}"\n'
        f'method_registry_fingerprint="{service.method_registry.fingerprint}"\n'
        'claims=["decision","irrelevant"]\nnow="2040-01-31T08:30:00Z"\n'
        '[artifacts.reviewed.context]\nsite="bench"\n')
    return service, ArtifactRegistry.load(service, manifest)


def test_claim_collection_and_explanation_cover_premises_attacks_and_defences(tmp_path):
    service, registry = setup_registry(tmp_path)
    packet = registry.assess_claim("reviewed", "decision")
    assert packet["status"] == "supported"
    assert packet["verification"] == "server_assessment"
    collection = service.store.get(packet["collection_id"], kind="collection")
    assert set(collection["records"]) == NEEDED
    assert set((tmp_path / "calls.txt").read_text().splitlines()) == NEEDED
    explanation = registry.explain_claim("reviewed", packet["assessment_id"], "decision")
    assert set(explanation["premises"]) == {"leaf", "middle", "attacker"}
    assert set(explanation["arguments"]) == {
        "leaf_route", "middle_route", "decision_route", "attacker_route"}
    assert set(explanation["evidence"]) == NEEDED
    assert set(explanation["assumptions"]) == {"calibrated"}
    assert set(explanation["reasoning"]) == {"checked", "inferred"}
    assert set(explanation["objections"]) == {
        "challenge", "answer", "alternative_attack", "alternative_answer"}
    assert explanation["premises"]["leaf"]["status"] == "supported"
    assert explanation["objections"]["alternative_attack"]["status"] == "defeated"
    assert "irrelevant" not in json.dumps(explanation)
    assert "foreign" not in json.dumps(explanation)
    assert registry.finish_claim("reviewed", packet["assessment_id"], "decision") == packet


def test_false_adverse_monitor_remains_checkable_after_diagnostic_wording_changes(tmp_path, monkeypatch):
    original = evaluator._check_predicate

    def differently_worded(predicate, value):
        checked = original(predicate, value)
        return replace(checked, reason=f"Measured {predicate.path}: {checked.holds}")

    monkeypatch.setattr(evaluator, "_check_predicate", differently_worded)
    service, registry = setup_registry(tmp_path)
    packet = registry.assess_claim("reviewed", "decision")
    assert packet["status"] == "supported"
    assessment = service.store.get(packet["assessment_id"], kind="assessment")
    assert assessment["evidence"]["challenge_record"]["status"] == "unavailable"
    assert assessment["evidence"]["challenge_record"]["reasons"] == ["Measured finding: False"]
    assert registry.finish_claim("reviewed", packet["assessment_id"], "decision") == packet


@pytest.mark.parametrize("failure_file", ["broken.txt", "stale.txt"])
def test_failed_adverse_monitor_never_issues_false_support_packet(tmp_path, failure_file):
    service, registry = setup_registry(tmp_path)
    (tmp_path / failure_file).write_text("challenge_record")
    with pytest.raises(ValueError, match="Claim assessment unresolved: required evidence 'challenge_record'"):
        registry.assess_claim("reviewed", "decision")
    assert not service.store.list(kind="artifact_packet")
    assert not service.store.list(kind="artifact_claim_packet")
    collection_id = service.store.list(kind="collection")[0]["id"]
    collection = service.store.get(collection_id, kind="collection")
    assert set(collection["records"]) == NEEDED
    assert "irrelevant_record" not in (tmp_path / "calls.txt").read_text()
    if failure_file == "broken.txt":
        assert collection["records"]["challenge_record"]["status"] == "error"
    else:
        assert collection["records"]["challenge_record"]["status"] == "ok"
        assessment_id = service.store.list(kind="assessment")[0]["id"]
        raw_assessment = service.store.get(assessment_id, kind="assessment")
        assert raw_assessment["claims"]["decision"]["status"] == "supported"
        assert raw_assessment["evidence"]["challenge_record"]["status"] == "unavailable"


def test_complete_collection_gate_also_requires_optional_alternative(tmp_path):
    source = SOURCE.replace(
        'assumption calibrated {',
        'evidence backup_record { tool runner; kind test; environment lab; max_age 3600; require "passed" == true; }\n'
        'assumption calibrated {').replace(
        'argument middle_route {',
        'argument backup_route { conclusion leaf; reasoning inferred; evidence backup_record; }\n'
        'argument middle_route {')
    service, registry = setup_registry(tmp_path, source=source)
    (tmp_path / "broken.txt").write_text("backup_record")
    with pytest.raises(ValueError, match="Claim assessment unresolved: required evidence 'backup_record'"):
        registry.assess_claim("reviewed", "decision")
    assert not service.store.list(kind="artifact_packet")
    collection_id = service.store.list(kind="collection")[0]["id"]
    raw = service.reason(source, {"site": "bench"}, collection_id, "2040-01-31T08:30:00Z")
    assert raw["claims"]["decision"]["status"] == "supported"


def test_frozen_historical_evaluator_is_explicit_and_cannot_cross_recipient_boundary(tmp_path):
    from eal.server import create_server

    service, strict = setup_registry(tmp_path)
    (tmp_path / "stale.txt").write_text("challenge_record")
    historical = ArtifactRegistry.load(service, tmp_path / "artifacts.toml",
                                       historical_evaluator=True)
    packet = historical.assess_claim("reviewed", "decision")
    assert packet["status"] == "supported"
    assert packet["historical_evaluator"] is True
    assert historical.finish_claim("reviewed", packet["assessment_id"], "decision") == packet
    with pytest.raises(ValueError, match="different evidence collection policy"):
        strict.finish_claim("reviewed", packet["assessment_id"], "decision")
    with pytest.raises(ValueError, match="Historical evaluator cannot serve recipient"):
        create_server(service, historical, recipient_only=True, principal="reviewer",
                      recipient_grants={"reviewed": {"decision"}})
