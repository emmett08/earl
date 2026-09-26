"""Adversarial tests for typed argument recognition and persistent execution."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import pytest

import eal.argument_host as module
from eal.argument_host import ArgumentHost
from eal.evaluator import canonical_digest
from eal.parser import parse
from test_argument_host_integration import _host


HELD_OUT = json.loads((Path(__file__).parent / "fixtures" / "argument-host-heldout.json").read_text())


@pytest.mark.parametrize("punctuation", ["?", ".", "?!"])
def test_reviewed_form_normalises_case_spacing_and_terminal_punctuation(tmp_path, punctuation):
    host, _, _, _ = _host(tmp_path)
    result = host.resolve("  CHECK   THE ERROR LIMIT FOR payments" + punctuation + "  ")
    assert result["status"] == "resolved"
    assert result["bindings"] == {"service": "payments"}
    assert result["correspondence"]["profile"] == "typed_templates/1"


def test_same_phrase_matching_two_argument_schemes_is_ambiguous_before_collection(tmp_path, monkeypatch):
    host, service, _, _ = _host(tmp_path)
    scheme = host.schemes["error_probability"]
    ambiguous = ArgumentHost(service, {"one": scheme, "two": scheme}, principal="engineer", session_id="ambiguous")
    monkeypatch.setattr(service, "collect", lambda *args: pytest.fail("ambiguous request executed a tool"))
    result = ambiguous.assess("check the error limit for payments")
    assert result["status"] == "ambiguous"
    assert result["candidate_schemes"] == ["one", "two"]


def test_context_conflict_cannot_silently_change_requested_subject(tmp_path, monkeypatch):
    host, service, _, _ = _host(tmp_path)
    monkeypatch.setattr(service, "collect", lambda *args: pytest.fail("conflicting subject collected"))
    result = host.assess("check the error limit for payments", {"service": "orders"})
    assert result["status"] == "unresolved"
    assert any("conflicts" in reason for reason in result["reasons"])


def test_parameters_are_substituted_as_literals_not_source_text(tmp_path):
    host, service, _, _ = _host(tmp_path)
    original = host.schemes["error_probability"]
    parameter = replace(original.parameters["service"], values=None)
    scheme = replace(original, parameters={"service": parameter})
    instance = ArgumentHost(service, {"test": scheme}, principal="engineer", session_id="quoted")
    injected = 'x"; } claim injected { statement "yes'
    source = instance.instantiate("test", {"service": injected}, {"service": injected})
    program = parse(source)
    assert set(program.claims) == {"error_limit"}
    assert program.claims["error_limit"].proposition.subject == injected
    assert program.evidence["sample"].input["subject"] == injected


def test_unrecognised_prose_invalidates_prior_action_packet_and_followup_context(tmp_path):
    host, _, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    assert host.resolve("Use the same test for every production service")["status"] == "unresolved"
    with pytest.raises(ValueError, match="active request"):
        host.finish(packet["assessment_id"])
    assert host.resolve("check the error limit again")["status"] == "unresolved"


def _candidate(prose):
    return {"scheme_id": "error_probability", "bindings": {"service": "payments"},
            "task_kind": "claim", "spans": [{"role": "conclusion", "start": 0,
                                             "end": len(prose), "text": prose}]}


def test_model_argument_proposal_requires_independent_correspondence(tmp_path, monkeypatch):
    host, service, _, _ = _host(tmp_path)
    prose = "Would the payments sample support the specified upper error bound?"
    monkeypatch.setattr(service, "collect", lambda *args: pytest.fail("unverified interpretation executed"))
    result = host.assess(prose, routing_candidate=_candidate(prose))
    assert result["status"] == "unresolved"
    assert any("independent correspondence" in reason for reason in result["reasons"])


@pytest.mark.parametrize("case", HELD_OUT["cases"], ids=lambda item: item["category"])
def test_heldout_wording_is_not_silently_promoted_to_a_reviewed_claim(tmp_path, monkeypatch, case):
    host, service, _, _ = _host(tmp_path)
    monkeypatch.setattr(service, "collect", lambda *args: pytest.fail("Unreviewed wording collected evidence"))
    result = host.assess(case["request"])
    assert result["status"] == "unresolved"
    assert result["tool_execution"] is False


def test_independent_correspondence_admits_only_the_reviewed_heldout_paraphrase(tmp_path):
    host, service, _, _ = _host(tmp_path)
    approved = HELD_OUT["cases"][0]["request"]

    class Reviewer:
        def validate(self, prose, scheme_id, bindings, context, candidate):
            assert scheme_id == "error_probability"
            return ({"status": "satisfied", "method": "reviewed-heldout/1"}
                    if prose == approved and bindings == {"service": "payments"}
                    and context == {"service": "payments"} else {"status": "unresolved"})

    route = ArgumentHost(service, host.schemes, principal="engineer", session_id="heldout",
                         correspondence_validator=Reviewer())
    packet = route.assess(approved, routing_candidate=_candidate(approved))
    assert packet["status"] == "supported" and packet["adequacy"]["status"] == "adequate"
    assert route.finish(packet["assessment_id"])["status"] == "supported"
    for case in HELD_OUT["cases"][1:]:
        prose = case["request"]
        result = route.assess(prose, routing_candidate=_candidate(prose))
        assert result["status"] == "unresolved" and result["tool_execution"] is False


def test_an_action_proposal_never_functions_as_a_routing_proposal(tmp_path):
    host, _, _, _ = _host(tmp_path)
    prose = "A request with no reviewed form"
    result = host.resolve(prose, proposal=_candidate(prose))
    assert result["status"] == "unresolved"
    assert result["candidates"] == []


def test_installed_validator_receives_exact_prose_and_typed_candidate(tmp_path):
    host, service, _, _ = _host(tmp_path)
    prose = "Would the payments sample support the specified upper error bound?"
    candidate = _candidate(prose)
    calls = []

    class Validator:
        def validate(self, original, scheme_id, bindings, context, proposal):
            calls.append((original, scheme_id, bindings, context, proposal))
            return {"status": "satisfied", "method": "fixture-reviewed-interpretation/1"}

    route = ArgumentHost(service, host.schemes, principal="engineer", session_id="validator",
                         correspondence_validator=Validator())
    result = route.assess(prose, routing_candidate=candidate)
    assert result["status"] == "supported"
    assert calls == [(prose, "error_probability", {"service": "payments"}, {"service": "payments"}, candidate)]
    assert result["correspondence"]["profile"] == "installed_validator/1"


@pytest.mark.parametrize("mutation", ["span", "task_kind", "binding_type", "unknown_scheme"])
def test_malformed_role_or_binding_proposals_never_reach_validator(tmp_path, mutation):
    host, service, _, _ = _host(tmp_path)
    prose = "Would the payments sample support the specified upper error bound?"
    candidate = _candidate(prose)
    if mutation == "span":
        candidate["spans"][0]["text"] = "replacement question"
    elif mutation == "task_kind":
        candidate["task_kind"] = "action"
    elif mutation == "binding_type":
        candidate["bindings"]["service"] = True
    else:
        candidate["scheme_id"] = "unregistered"

    class Validator:
        def validate(self, *args):
            pytest.fail("Malformed candidate reached semantic validation")

    route = ArgumentHost(service, host.schemes, principal="engineer", session_id="bad",
                         correspondence_validator=Validator())
    assert route.resolve(prose, routing_candidate=candidate)["status"] == "unresolved"


def test_action_identity_and_rendered_result_survive_checked_finish(tmp_path):
    host, _, _, _ = _host(tmp_path)
    prose = "check the error limit for payments"
    proposal = {"schema": "eal2-file-change/1", "path": "settings.json", "prior_sha256": "1" * 64,
                "replacement_sha256": "2" * 64, "replacement_size": 3,
                "task_sha256": hashlib.sha256(prose.encode()).hexdigest()}
    packet = host.assess(prose, proposal=proposal)
    assert packet["prose_digest"] == proposal["task_sha256"]
    assert packet["proposal_digest"] == canonical_digest(proposal)
    assert packet["checked_answer"]["status"] == "supported"
    assert "recorded scope" in packet["checked_answer"]["text"]
    assert host.finish(packet["assessment_id"]) == packet


def test_finish_cannot_reuse_expired_observations(tmp_path, monkeypatch):
    host, _, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    assessed = datetime.fromisoformat(packet["assessed_at"].replace("Z", "+00:00"))
    monkeypatch.setattr(module, "utc_now", lambda: (assessed + timedelta(seconds=120)).isoformat())
    with pytest.raises(ValueError, match="freshness"):
        host.finish(packet["assessment_id"])


def test_finish_rejects_same_version_tool_binding_configuration_drift(tmp_path):
    host, _, _, tools = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    tools.write_text(tools.read_text() + 'max_output_bytes=2048\n')
    with pytest.raises(ValueError, match="identity|binding|reassess"):
        host.finish(packet["assessment_id"])


def test_new_principal_cannot_retrieve_another_principals_result(tmp_path):
    host, service, manifest, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    another = ArgumentHost.load(service, manifest, principal="different", session_id=host.session_id)
    with pytest.raises(ValueError, match="principal"):
        another.finish(packet["assessment_id"])


def test_bad_adequacy_contract_fails_before_any_collection(tmp_path, monkeypatch):
    host, service, _, _ = _host(tmp_path)
    original = host.schemes["error_probability"]
    invalid = replace(original, adequacy={"correspondence": "reviewed_source", "obligations": [{"id": "incomplete"}]})
    route = ArgumentHost(service, {"invalid": invalid}, principal="engineer", session_id="invalid")
    monkeypatch.setattr(service, "collect", lambda *args: pytest.fail("invalid contract executed"))
    with pytest.raises(ValueError, match="obligation"):
        route.assess("check the error limit for payments")


def test_same_literal_cannot_bind_two_parameters(tmp_path):
    _, service, manifest, _ = _host(tmp_path)
    manifest.write_text(manifest.read_text() + '\n[schemes.error_probability.parameters.second]\n'
        'kind="string"\ncontext_path="second"\nsource_literal="$service"\n')
    with pytest.raises(ValueError, match="distinct source literals"):
        ArgumentHost.load(service, manifest, principal="engineer", session_id="duplicate")


def test_method_selector_cannot_be_a_parameter(tmp_path):
    host, service, _, _ = _host(tmp_path)
    original = host.schemes["error_probability"]
    marker = replace(original.parameters["service"], source_literal="inductive/1", values=None)
    scheme = replace(original, parameters={"service": marker})
    route = ArgumentHost(service, {"method": scheme}, principal="engineer", session_id="method")
    with pytest.raises(ValueError, match="tool or method"):
        route.instantiate("method", {"service": "structured/1"}, {"service": "structured/1"})


def test_pending_resolution_cannot_finish_an_earlier_assessment(tmp_path):
    host, _, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    assert host.resolve("assess request failures for orders")["status"] == "resolved"
    with pytest.raises(ValueError, match="active request"):
        host.finish(packet["assessment_id"])


def test_finish_rechecks_session_after_slow_evaluation(tmp_path, monkeypatch):
    host, _, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    original_evaluate = module.evaluate

    def superseded_during_evaluation(*args, **kwargs):
        result = original_evaluate(*args, **kwargs)
        assert host.resolve("assess request failures for orders")["status"] == "resolved"
        return result

    monkeypatch.setattr(module, "evaluate", superseded_during_evaluation)
    with pytest.raises(ValueError, match="active request"):
        host.finish(packet["assessment_id"])
