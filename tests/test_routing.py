"""End-to-end claim routing through reviewed cases and a caller grant."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from eal.artifacts import ArtifactRegistry
from eal.families import FamilyRegistry
from eal.retrieval import CandidateIndex
from eal.routing import TaskFamilyHost
from eal.runtime import ReasoningService
from eal.server import create_server
from test_artifacts import SOURCE, setup_artifact
from test_task_families import catalogue, family_catalogue


def routed(tmp_path, *, principal="caller_a", claims=None):
    _, manifest = catalogue(tmp_path)
    collector = tmp_path / "reader.py"
    collector.write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        "print(json.dumps({'value': {'passed': True}, "
        "'observed_at': '2040-01-01T11:59:00Z'}))\n",
        encoding="utf-8",
    )
    tools = tmp_path / "tools.toml"
    tools.write_text(
        '[tools.reader]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(collector)])}\n', encoding="utf-8",
    )
    artifacts = ArtifactRegistry.load(ReasoningService(tmp_path, tools), manifest)
    families = FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts))
    route = TaskFamilyHost(families, principal=principal, authorised_families={"rig"},
                           authorised_claims=claims or {"rig_pilot": {"accepted"}})
    return route, artifacts


def test_retrieval_only_suggests_accessible_family_and_does_not_assess(tmp_path, monkeypatch):
    route, artifacts = routed(tmp_path)
    monkeypatch.setattr(artifacts, "assess_claim", lambda *args: pytest.fail("retrieval assessed a claim"))
    assert route.candidates("rig inspection") == [
        {"family_id": "rig", "score": 2, "matched_terms": ["inspection", "rig"]}
    ]
    assert route.candidates("unrelated") == []
    assert not route._issued


def test_lexical_candidates_obey_artifact_and_claim_grants(tmp_path):
    route, _ = routed(tmp_path)
    index = CandidateIndex(route.families)
    selected = index.search("rig inspection", authorised_families={"rig"},
                            authorised_artifacts={"rig_pilot"},
                            authorised_claims={"rig_pilot": {"accepted"}})
    assert [row["family_id"] for row in selected] == ["rig"]
    assert index.search("rig inspection", authorised_families={"rig"},
                        authorised_artifacts={"rig_pilot"},
                        authorised_claims={"rig_pilot": set()}) == []
    assert index.search("rig inspection", authorised_families={"rig"},
                        authorised_artifacts={"rig_field"},
                        authorised_claims={"rig_pilot": {"accepted"}}) == []


def test_exact_reviewed_case_assesses_and_explains_only_granted_claim(tmp_path):
    route, _ = routed(tmp_path)
    packet = route.assess("rig", {"site": "pilot"}, "accepted")
    assert packet["schema"] == "eal2-claim-packet/2"
    assert packet["artifact_id"] == "rig_pilot"
    assert packet["claim"] == "accepted"
    assert packet["status"] == "supported"
    assert packet["scope"]["status"] == "matched"
    assert len(json.dumps(packet).encode()) <= 3072
    explained = route.explain("rig", {"site": "pilot"}, "accepted", packet["assessment_id"])
    assert explained["packet"] == packet
    assert set(explained["arguments"]) == {"route"}
    assert route.finish("rig", {"site": "pilot"}, "accepted", packet["assessment_id"]) == packet


def test_unreviewed_or_ungranted_route_cannot_infer_from_candidate(tmp_path, monkeypatch):
    route, artifacts = routed(tmp_path)
    calls = []
    monkeypatch.setattr(artifacts, "assess_claim", lambda *args: calls.append(args))
    assert [row["family_id"] for row in route.candidates("rig inspection")] == ["rig"]
    for family, bindings, claim in (
        ("maintenance", {"site": "pilot"}, "accepted"),
        ("rig", {"site": "field"}, "accepted"),
        ("rig", {"site": "unknown"}, "accepted"),
        ("rig", {"site": True}, "accepted"),
        ("rig", {"site": "pilot"}, "other"),
    ):
        with pytest.raises(ValueError):
            route.assess(family, bindings, claim)
    assert calls == []


def test_separate_reviewed_parameter_case_selects_its_own_pinned_scope(tmp_path):
    route, _ = routed(tmp_path, claims={"rig_field": {"accepted"}})
    packet = route.assess("rig", {"site": "field"}, "accepted")
    assert packet["artifact_id"] == "rig_field"
    assert packet["status"] == "supported"
    with pytest.raises(ValueError, match="unauthorised artefact"):
        route.assess("rig", {"site": "pilot"}, "accepted")


def test_same_artifact_grant_does_not_authorise_another_caller_assessment(tmp_path):
    first, _ = routed(tmp_path, principal="caller_a")
    second = TaskFamilyHost(first.families, principal="caller_b", authorised_families={"rig"},
                            authorised_claims={"rig_pilot": {"accepted"}})
    packet = first.assess("rig", {"site": "pilot"}, "accepted")
    with pytest.raises(ValueError, match="not issued for this caller"):
        second.finish("rig", {"site": "pilot"}, "accepted", packet["assessment_id"])
    with pytest.raises(ValueError, match="not issued for this caller"):
        second.explain("rig", {"site": "pilot"}, "accepted", packet["assessment_id"])
    with pytest.raises(ValueError, match="unauthorised artefact"):
        first.finish("rig", {"site": "field"}, "accepted", packet["assessment_id"])


def test_invalid_operator_grants_fail_before_recipient_use(tmp_path):
    route, _ = routed(tmp_path)
    for family_ids, claim_grant in (
        ({"missing"}, {"rig_pilot": {"accepted"}}),
        ({"rig"}, {"absent": {"accepted"}}),
        ({"rig"}, {"rig_pilot": {"other"}}),
    ):
        with pytest.raises(ValueError):
            TaskFamilyHost(route.families, principal="caller_b",
                           authorised_families=family_ids, authorised_claims=claim_grant)
    with pytest.raises(ValueError, match="host-assigned"):
        TaskFamilyHost(route.families, principal="", authorised_families={"rig"},
                       authorised_claims={"rig_pilot": {"accepted"}})


@pytest.mark.parametrize("malformed", ["ab", {"a": True}, ["a", "a"]])
def test_recipient_mcp_rejects_ambiguous_claim_collections(tmp_path, malformed):
    source = (SOURCE.replace("claim works", "claim a")
                    .replace("claim other", "claim b")
                    .replace("conclusion works", "conclusion a"))
    service, manifest, _ = setup_artifact(tmp_path, source=source, claims=("a", "b"))
    artifacts = ArtifactRegistry.load(service, manifest)
    with pytest.raises(ValueError, match="Recipient grant"):
        create_server(service, artifacts, recipient_only=True, principal="caller_a",
                      recipient_grants={"test": malformed})


def test_recipient_mcp_grant_is_snapshot_after_server_construction(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path, claims=("works", "other"))
    artifacts = ArtifactRegistry.load(service, manifest)
    grants = {"test": {"works"}}
    server = create_server(service, artifacts, recipient_only=True, principal="caller_a",
                           recipient_grants=grants)

    async def denied():
        with pytest.raises(ToolError, match="not permitted"):
            await server.call_tool("eal_assess_artifact_claim", {"artifact_id": "test", "claim": "other"})

    asyncio.run(denied())
    grants["test"].add("other")
    asyncio.run(denied())
    grants["test"] = {"other"}
    asyncio.run(denied())
