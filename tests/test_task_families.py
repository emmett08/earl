"""Finite reviewed binding and candidate-only retrieval boundaries."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from eal.artifacts import ArtifactRegistry
from eal.families import FamilyRegistry, Parameter, review_binding_digest
from eal.retrieval import CandidateIndex
from eal.runtime import ReasoningService


def source(site: str) -> str:
    return f'''language "EAL/2";
environment rig {{ require "site" == "{site}"; }}
tool reader {{ version "1"; mode deterministic; }}
evidence result {{ tool reader; kind test; environment rig; max_age 3600; require "passed" == true; }}
reasoning relation {{ method "structured/1"; rationale "A scoped record supplies provisional support."; }}
claim accepted {{ statement "The {site} rig test passed."; environment rig; }}
argument route {{ conclusion accepted; reasoning relation; evidence result; }}
'''


def catalogue(tmp_path: Path, *, mismatched_source_scope: bool = False) -> tuple[ArtifactRegistry, Path]:
    service = ReasoningService(tmp_path, database_path=tmp_path / "runs.sqlite3")
    entries = []
    for artifact_id, site in (("rig_pilot", "pilot"), ("rig_field", "field")):
        data = source("pilot" if site == "field" and mismatched_source_scope else site).encode()
        (tmp_path / f"{artifact_id}.eal").write_bytes(data)
        entries.append(f'''[artifacts.{artifact_id}]
path = "{artifact_id}.eal"
sha256 = "{hashlib.sha256(data).hexdigest()}"
method_registry_fingerprint = "{service.method_registry.fingerprint}"
claims = ["accepted"]
context = {{ site = "{site}" }}
now = "2040-01-01T12:00:00Z"
''')
    path = tmp_path / "artifacts.toml"
    path.write_text("\n".join(entries), encoding="utf-8")
    return ArtifactRegistry.load(service, path), path


def family_catalogue(tmp_path: Path, artifacts: ArtifactRegistry, *,
                     wrong_context: bool = False, duplicate: bool = False) -> Path:
    params = {"site": Parameter("string", ("pilot", "field"))}
    rows = []
    for site, artifact_id in (("pilot", "rig_pilot"), ("field", "rig_field")):
        declared = site
        if site == "field" and wrong_context:
            artifact_id = "rig_pilot"
        binding = {"site": declared}
        digest = review_binding_digest("rig", params, {"site": "site"}, binding,
                                       artifact_id, artifacts.definitions[artifact_id], ["accepted"])
        rows.append(f'''[[families.rig.cases]]
bindings = {{ site = "{declared}" }}
artifact_id = "{artifact_id}"
claims = ["accepted"]
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "{digest}"
''')
    if duplicate:
        rows.append(rows[0])
    # This second family deliberately has the same lexical search terms. Its
    # identical artefact still requires a separate family permission and review.
    pilot_digest = review_binding_digest("maintenance", {"site": Parameter("string", ("pilot",))},
                                         {"site": "site"}, {"site": "pilot"}, "rig_pilot",
                                         artifacts.definitions["rig_pilot"], ["accepted"])
    path = tmp_path / "families.toml"
    path.write_text(f'''schema = "eal2-task-families/1"

[families.rig]
description = "Rig inspection by reviewed site"
terms = ["rig", "inspection"]
context_paths = {{ site = "site" }}

[families.rig.parameters.site]
type = "string"
values = ["pilot", "field"]

{''.join(rows)}
[families.maintenance]
description = "Rig inspection maintenance"
terms = ["rig", "inspection"]
context_paths = {{ site = "site" }}

[families.maintenance.parameters.site]
type = "string"
values = ["pilot"]

[[families.maintenance.cases]]
bindings = {{ site = "pilot" }}
artifact_id = "rig_pilot"
claims = ["accepted"]
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "{pilot_digest}"
''', encoding="utf-8")
    return path


def resolve(registry: FamilyRegistry, site: str, *, authorised_families=("rig",),
            authorised_artifacts=("rig_pilot", "rig_field")) -> dict:
    return registry.resolve("rig", {"site": site}, authorised_families=authorised_families,
                            authorised_artifacts=authorised_artifacts)


def test_resolves_reviewed_changed_scope_without_runtime_source_substitution(tmp_path):
    artifacts, _ = catalogue(tmp_path)
    families = FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts))
    assert resolve(families, "pilot") == {"artifact_id": "rig_pilot", "claims": ["accepted"]}
    assert resolve(families, "field") == {"artifact_id": "rig_field", "claims": ["accepted"]}
    with pytest.raises(ValueError, match="allowed typed value"):
        resolve(families, "unreviewed")
    with pytest.raises(ValueError, match="unauthorised family"):
        resolve(families, "pilot", authorised_families=())
    with pytest.raises(ValueError, match="unauthorised artefact"):
        resolve(families, "field", authorised_artifacts=("rig_pilot",))
    with pytest.raises(ValueError, match="bounded collection"):
        resolve(families, "pilot", authorised_artifacts="rig_pilot")


def test_reviewed_binding_must_match_context_and_claim_scope(tmp_path):
    artifacts, _ = catalogue(tmp_path)
    with pytest.raises(ValueError, match="differs from artefact context"):
        FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts, wrong_context=True))
    second = tmp_path / "second"
    second.mkdir()
    artifacts, _ = catalogue(second, mismatched_source_scope=True)
    with pytest.raises(ValueError, match="does not constrain family binding"):
        FamilyRegistry.load(artifacts, family_catalogue(second, artifacts))


def test_source_drift_after_load_blocks_resolution(tmp_path):
    artifacts, _ = catalogue(tmp_path)
    families = FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts))
    (tmp_path / "rig_field.eal").write_text(source("field") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source differs"):
        resolve(families, "field")


def test_changed_assessment_time_invalidates_review_contract(tmp_path):
    artifacts, _ = catalogue(tmp_path)
    families = FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts))
    artifacts.definitions["rig_pilot"] = replace(artifacts.definitions["rig_pilot"],
                                                   now="2040-01-02T12:00:00Z")
    with pytest.raises(ValueError, match="review contract differs"):
        resolve(families, "pilot")


def test_duplicate_binding_fails_closed(tmp_path):
    artifacts, _ = catalogue(tmp_path)
    with pytest.raises(ValueError, match="ambiguous duplicate"):
        FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts, duplicate=True))


def test_retrieval_returns_ambiguous_candidates_without_execution(tmp_path, monkeypatch):
    artifacts, _ = catalogue(tmp_path)
    families = FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts))
    def cannot_assess(*args, **kwargs):
        raise AssertionError("retrieval attempted assessment")
    monkeypatch.setattr(artifacts, "assess", cannot_assess)
    candidates = CandidateIndex(families).search("rig inspection", authorised_families={"rig", "maintenance"})
    assert [entry["family_id"] for entry in candidates] == ["maintenance", "rig"]
    assert all(entry["score"] == 2 for entry in candidates)
    assert CandidateIndex(families).search("rig inspection", authorised_families={"rig"}) == [
        {"family_id": "rig", "score": 2, "matched_terms": ["inspection", "rig"]}
    ]
    assert CandidateIndex(families).search("unrelated", authorised_families={"rig"}) == []
