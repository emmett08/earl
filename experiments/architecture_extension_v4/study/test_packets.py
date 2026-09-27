"""Matched exposure and source-backed attack tests for the v4 packets."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from experiments.architecture_extension_v4.study.packets import generate
from experiments.architecture_extension_v4.study.runner_capture import tree_digest, tree_entries


HERE = Path(__file__).resolve().parents[1]
ENTITLEMENT = HERE / "systems" / "entitlement" / "source"
LOOKUP = {"target": {"path": "service.py", "class": "InMemoryIssuer", "method": "lookup"},
          "statement": "The public issuer declares a lookup that can be inspected for reconciliation.",
          "guidance": "Inspect issuer effects and verify issue retries under acknowledgement loss.",
          "action_if_supported": "Inspect lookup results before deciding whether to issue again.",
          "action_if_contested": "Implement the stubbed lookup and verify it before issue retries.",
          "action_if_unknown": "Determine whether lookup exists before relying on reconciliation."}
TIMEOUT = {"mode": "effect_before_timeout", "effect_attribute": "issued",
           "target": {"path": "service.py", "class": "InMemoryIssuer", "method": "issue"},
           "statement": "Source-order patterns in the issuer bear on the disputed no-issue-after-timeout premise.",
           "guidance": "Treat issuer timeouts as uncertain until reconciled against source and tests.",
           "action_if_supported": "Reconcile with lookup before any retry; a token may have been appended.",
           "action_if_contested": "Inspect both timeout branches and reconcile each before deciding on a retry.",
           "action_if_unknown": "Establish effect timing and reconciliation before a retry."}


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "candidate"
    shutil.copytree(ENTITLEMENT, target)
    return target


def test_real_source_plain_formal_parity_and_compiled_route():
    p1 = generate(ENTITLEMENT, "entitlement", "D", "P1", LOOKUP)
    p2 = generate(ENTITLEMENT, "entitlement", "D", "P2", LOOKUP)
    for field in ("facts", "guidance", "status", "plain_conclusion", "selected_action",
                  "source_tree_sha256", "shared_material_digest"):
        assert p1[field] == p2[field], field
    assert p1["status"] == "supported"
    assert p1["selected_action"] == LOOKUP["action_if_supported"]
    assert "formal" not in p1
    assert p2["formal"]["language"] == "EAL/2"
    assert p2["formal"]["authored_status"] == "supported"
    assert p2["formal"]["grounded_status"] == "accepted"
    assert p2["formal"]["routes"] == [{"id": "declared_route", "status": "accepted"}]
    assert p2["formal"]["objections"] == [{"id": "stubbed_route", "status": "inactive"}]
    assert p2["packet_text"].splitlines()[:2] == p1["packet_text"].splitlines()[:2]
    assert "argument declared_route" in p2["packet_text"]
    assert len(p2["evidence_provenance"]["evidence_record_digest"]) == 64
    assert p1["source_tree_sha256"] == tree_digest(tree_entries(ENTITLEMENT))
    json.dumps(p1)
    json.dumps(p2)


def test_direct_source_stub_defeats_route_and_changes_selected_action(tmp_path):
    source = _copy(tmp_path)
    service = source / "service.py"
    original = service.read_text()
    assert "return tuple(r for r in self.issued" in original
    service.write_text(original.replace(
        "return tuple(r for r in self.issued if r.account_id == account_id and r.request_id == request_id)",
        "raise NotImplementedError('lookup is not implemented')"))
    p1 = generate(source, "entitlement", "D", "P1", LOOKUP)
    p2 = generate(source, "entitlement", "D", "P2", LOOKUP)
    assert p1["status"] == p2["status"] == "contested"
    assert p1["facts"]["direct_stub"] is True
    assert p1["selected_action"] == p2["selected_action"] == LOOKUP["action_if_contested"]
    assert p1["shared_material_digest"] == p2["shared_material_digest"]
    assert p2["formal"]["grounded_status"] == "rejected"
    assert p2["formal"]["routes"] == [{"id": "declared_route", "status": "rejected"}]
    assert p2["formal"]["defeats"]
    assert "stub" in p1["plain_conclusion"]


def test_public_effect_order_and_counterexample_change_decision(tmp_path):
    # The committed public issuer now contains both before- and after-effect
    # timeout branches. This contested status is actually exposed in the live
    # experiment; the clean derivative checks the positive route separately.
    contested = generate(ENTITLEMENT, "entitlement", "D", "P1", TIMEOUT)
    assert contested["status"] == "contested"
    assert contested["selected_action"] == TIMEOUT["action_if_contested"]
    assert contested["facts"]["effect_order"]["after_effect_timeout_lines"]
    assert contested["facts"]["effect_order"]["before_effect_timeout_lines"]
    source = _copy(tmp_path)
    service = source / "service.py"
    original = service.read_text()
    pre_effect_branch = (
        "        if self.fail_before_issue:\n"
        "            self.fail_before_issue = False\n"
        "            raise TimeoutError(\"issuer timed out before applying request\")\n")
    assert pre_effect_branch in original
    service.write_text(original.replace(pre_effect_branch, "", 1))
    clean = generate(source, "entitlement", "D", "P1", TIMEOUT)
    assert clean["status"] == "supported"
    assert clean["selected_action"] == TIMEOUT["action_if_supported"]
    assert not clean["facts"]["effect_order"]["before_effect_timeout_lines"]

    # A second bounded source variant again introduces a pre-effect branch;
    # it must recover the same formal status and action as the live fixture.
    service.write_text(original.replace(
        'raise TimeoutError("issuer timed out before applying request")',
        'raise TimeoutError("issuer timed out before applying request; retained case")', 1))
    plain = generate(source, "entitlement", "D", "P1", TIMEOUT)
    formal = generate(source, "entitlement", "D", "P2", TIMEOUT)
    assert plain["status"] == formal["status"] == "contested"
    assert plain["selected_action"] == formal["selected_action"] == TIMEOUT["action_if_contested"]
    assert plain["selected_action"] != clean["selected_action"]
    assert plain["facts"]["effect_order"]["after_effect_timeout_lines"]
    assert plain["facts"]["effect_order"]["before_effect_timeout_lines"]
    assert formal["formal"]["grounded_status"] == "rejected"
    assert formal["formal"]["defeats"]
    assert plain["shared_material_digest"] == formal["shared_material_digest"]
    assert "external durability remain unverified" in plain["facts"]["scope"]


def test_missing_or_unknown_source_does_not_become_false_or_true(tmp_path):
    source = _copy(tmp_path)
    assert generate(source, "entitlement", "D", "P1", {})["status"] == "unsupported"
    absent = {**LOOKUP, "target": {**LOOKUP["target"], "method": "not_declared"}}
    packet = generate(source, "entitlement", "D", "P2", absent)
    assert packet["status"] == "unsupported"
    assert packet["formal"]["grounded_status"] == "unconstructed"
    assert packet["facts"]["present"] is False
    assert "does not verify runtime behaviour" in packet["facts"]["scope"]


def test_p0_has_no_packet_and_invalid_paths_are_rejected():
    packet = generate(ENTITLEMENT, "entitlement", "D", "P0", LOOKUP)
    assert packet["packet_text"] is None
    assert packet["shared_material_digest"] is None
    with pytest.raises(ValueError, match="canonical relative"):
        generate(ENTITLEMENT, "entitlement", "D", "P1",
                 {"target": {**LOOKUP["target"], "path": "../service.py"}})
