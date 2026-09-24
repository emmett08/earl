"""Candidate suggestions and exact task applicability are separate boundaries."""

from __future__ import annotations

from dataclasses import replace

import pytest

from eal.applicability import (AmbiguousTask, NoApplicableTask,
                               TaskApplicabilityRegistry, review_applicability_digest)
from eal.families import FamilyRegistry
from eal.retrieval import CandidateIndex, alias_review_digest
from test_task_families import catalogue, family_catalogue


def _families(tmp_path):
    artifacts, _ = catalogue(tmp_path)
    return FamilyRegistry.load(artifacts, family_catalogue(tmp_path, artifacts))


def _aliases(tmp_path, families, *, digest=None):
    terms = ["traffic switch backup", "k8s"]
    digest = digest or alias_review_digest(families, "rig", terms)
    path = tmp_path / "aliases.toml"
    path.write_text(f'''schema = "eal2-retrieval-aliases/1"

[aliases.rig]
terms = ["traffic switch backup", "k8s"]
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "{digest}"
''', encoding="utf-8")
    return path


def _tasks(tmp_path, families, *, duplicate=False, bad_digest=False):
    question = "Can the field rig proceed?"
    digest = review_applicability_digest(families, "field_rig", question, "rig",
                                          {"site": "field"}, "accepted")
    if bad_digest:
        digest = "0" * 64
    text = f'''schema = "eal2-task-applicability/1"

[tasks.field_rig]
question = "{question}"
family_id = "rig"
bindings = {{ site = "field" }}
claim = "accepted"
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "{digest}"
'''
    if duplicate:
        second = review_applicability_digest(families, "maintenance_rig", question,
                                               "maintenance", {"site": "pilot"}, "accepted")
        text += f'''
[tasks.maintenance_rig]
question = "{question}"
family_id = "maintenance"
bindings = {{ site = "pilot" }}
claim = "accepted"
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "{second}"
'''
    path = tmp_path / "tasks.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _resolve(registry, question="Can the field rig proceed?", *, task_id="field_rig",
             tasks=("field_rig",), families=("rig", "maintenance"),
             artifacts=("rig_field", "rig_pilot")):
    return registry.resolve(question, task_id=task_id, authorised_tasks=tasks,
                            authorised_families=families, authorised_artifacts=artifacts)


def test_reviewed_alias_recovers_synonym_only_as_candidate(tmp_path, monkeypatch):
    families = _families(tmp_path)
    monkeypatch.setattr(families, "resolve", lambda *args, **kwargs:
                        (_ for _ in ()).throw(AssertionError("candidate executed")))
    assert CandidateIndex(families).search("k8s switch", authorised_families={"rig"}) == []
    index = CandidateIndex.load(families, _aliases(tmp_path, families))
    assert [row["family_id"] for row in index.search(
        "k8s traffic switch", authorised_families={"rig", "maintenance"})] == ["rig"]
    assert index.search("k8s traffic switch", authorised_families={"maintenance"}) == []
    # An ordinary shared description stays ambiguous: rank is not selection.
    assert len(index.search("rig inspection", authorised_families={"rig", "maintenance"})) == 2


def test_alias_review_rejects_changed_vocabulary_and_case_contract(tmp_path):
    families = _families(tmp_path)
    manifest = _aliases(tmp_path, families)
    manifest.write_text(manifest.read_text().replace("k8s", "kubernetes"), encoding="utf-8")
    with pytest.raises(ValueError, match="review contract differs"):
        CandidateIndex.load(families, manifest)
    manifest = _aliases(tmp_path, families)
    row = families.families["rig"].cases[0]
    families.families["rig"] = replace(families.families["rig"],
                                       cases=(replace(row, review_contract_sha256="0" * 64),
                                              *families.families["rig"].cases[1:]))
    with pytest.raises(ValueError, match="review contract differs"):
        CandidateIndex.load(families, manifest)


def test_exact_reviewed_question_resolves_correct_case_and_blocks_irrelevant_task(tmp_path):
    families = _families(tmp_path)
    registry = TaskApplicabilityRegistry.load(families, _tasks(tmp_path, families))
    selected = _resolve(registry)
    assert selected["artifact_id"] == "rig_field"
    assert selected["claim"] == "accepted"
    assert selected["review_contract_sha256"] == registry.tasks["field_rig"].review_contract_sha256
    for question, task_id in (("Can the pilot rig proceed?", "field_rig"),
                              ("Can the field rig proceed?", "maintenance_rig")):
        with pytest.raises(NoApplicableTask):
            _resolve(registry, question, task_id=task_id)
    with pytest.raises(NoApplicableTask):
        _resolve(registry, tasks=())
    with pytest.raises(ValueError, match="unauthorised family"):
        _resolve(registry, families=("maintenance",))
    with pytest.raises(ValueError, match="unauthorised artefact"):
        _resolve(registry, artifacts=("rig_pilot",))


def test_duplicate_question_refuses_ambiguous_route_even_when_bindings_are_reviewed(tmp_path):
    families = _families(tmp_path)
    with pytest.raises(AmbiguousTask, match="Duplicate exact question"):
        TaskApplicabilityRegistry.load(families, _tasks(tmp_path, families, duplicate=True))


def test_task_review_rejects_changed_question_and_source_contract(tmp_path):
    families = _families(tmp_path)
    with pytest.raises(ValueError, match="review contract differs"):
        TaskApplicabilityRegistry.load(families, _tasks(tmp_path, families, bad_digest=True))
    registry = TaskApplicabilityRegistry.load(families, _tasks(tmp_path, families))
    (tmp_path / "rig_field.eal").write_text("changed source", encoding="utf-8")
    with pytest.raises(ValueError, match="source differs"):
        _resolve(registry)
