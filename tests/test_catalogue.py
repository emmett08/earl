"""Registered EAL sources and historical run identities survive sessions."""

from pathlib import Path

import pytest

from eal.catalogue import WorkspaceKnowledgeCatalogue
from eal.evaluator import canonical_digest
from eal.extensions import example_registry
from eal.runtime import ReasoningService


SOURCE = '''language "EAL/2"

environment lab {
  require "site" == "bench"
}

tool reader {
  version "1"
}

evidence observation {
  tool reader
  kind test
  environment lab
  max_age 60
  require "ok" == true
}

reasoning authored {
  method "structured/1"
  rationale "The measurement supports this claim."
}

claim ready {
  statement "The service is ready."
  environment lab
}

argument route = [evidence observation] via authored => ready
'''
CONTEXT = {"site": "bench"}


def catalogue(tmp_path, *, source=SOURCE, path="source.eal"):
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    service = ReasoningService(tmp_path)
    return service, WorkspaceKnowledgeCatalogue(service)


def test_register_list_find_and_reload_have_stable_source_identity(tmp_path):
    service, first = catalogue(tmp_path)
    entry = first.register("source.eal", context=CONTEXT, claims=["ready"], label="Readiness")
    assert entry["entry_id"] == "source.eal"
    assert entry["context"] == CONTEXT
    assert entry["claims"] == ["ready"]
    assert "source" not in entry
    assert first.register("source.eal", context=CONTEXT, claims=["ready"], label="Readiness") == entry
    second = WorkspaceKnowledgeCatalogue(ReasoningService(tmp_path))
    assert second.get("source.eal", include_source=True)["source"] == SOURCE
    assert second.list() == [entry]
    assert second.find("readiness", claim="ready", context=CONTEXT) == [entry]
    assert second.find("service is ready") == [entry]
    assert second.find(claim="missing") == []
    assert second.find(context={"site": "elsewhere"}) == []


def test_file_edit_adds_revision_while_stable_name_and_history_remain(tmp_path):
    _, index = catalogue(tmp_path)
    original = index.register("source.eal", context=CONTEXT, claims=["ready"])
    changed_source = SOURCE.replace("The service is ready.", "The service is ready after the second check.")
    (tmp_path / "source.eal").write_text(changed_source)
    changed = index.get("source.eal", include_source=True)
    assert changed["entry_id"] == original["entry_id"]
    assert changed["source_digest"] != original["source_digest"]
    assert changed["source"] == changed_source
    previous = index.get_revision("source.eal", original["source_digest"], include_source=True)
    assert previous["current"] is False
    assert previous["source"] == SOURCE
    assert {item["source_digest"] for item in index.revisions("source.eal")} == {
        original["source_digest"], changed["source_digest"]}
    assert len(index.list()) == 1


def test_invalid_edit_does_not_replace_last_valid_revision(tmp_path):
    _, index = catalogue(tmp_path)
    original = index.register("source.eal", context=CONTEXT, claims=["ready"])
    (tmp_path / "source.eal").write_text(
        SOURCE.replace("claim ready", "claim gone").replace("=> ready", "=> gone")
    )
    with pytest.raises(ValueError, match="Selected claims are absent"):
        index.get("source.eal")
    assert index.get_revision("source.eal", original["source_digest"])["current"] is True
    (tmp_path / "source.eal").write_text("invalid source")
    with pytest.raises(ValueError, match="EAL validation"):
        index.get("source.eal")
    (tmp_path / "source.eal").unlink()
    with pytest.raises(FileNotFoundError):
        index.get("source.eal")
    assert index.get_revision("source.eal", original["source_digest"], include_source=True)["source"] == SOURCE


def test_same_source_retains_distinct_method_registry_revisions(tmp_path):
    service, index = catalogue(tmp_path)
    original = index.register("source.eal", context=CONTEXT)
    service.method_registry = example_registry()
    revised = index.get("source.eal")
    assert revised["entry_id"] == original["entry_id"]
    assert revised["source_digest"] == original["source_digest"]
    assert revised["method_registry_fingerprint"] != original["method_registry_fingerprint"]
    previous = index.get_revision(
        "source.eal", original["source_digest"],
        method_registry_fingerprint=original["method_registry_fingerprint"],
    )
    assert previous["current"] is False
    assert previous["method_registry_fingerprint"] == original["method_registry_fingerprint"]
    assert index.find(claim="ready") == [revised]


def test_prior_runs_are_found_by_source_and_context_without_copying_values(tmp_path):
    service, index = catalogue(tmp_path)
    entry = index.register("source.eal", context=CONTEXT)
    digest = entry["source_digest"]
    earlier_collection = service.store.put("collection", {
        "source_digest": digest, "context": CONTEXT,
        "records": {"observation": {"value": {"ok": True, "secret": "not catalogue metadata"}}},
    })
    service.store.put("collection", {"source_digest": digest, "context": {"site": "elsewhere"},
                                     "records": {}})
    earlier_assessment = service.store.put("assessment", {
        "source_digest": digest, "context_fingerprint": canonical_digest(CONTEXT),
        "method_registry_fingerprint": service.method_registry.fingerprint,
        "collection_id": earlier_collection, "assessed_at": "2040-01-01T00:00:00Z",
        "claims": {"ready": {"status": "supported"}},
    })
    service.store.put("assessment", {
        "source_digest": digest, "context_fingerprint": canonical_digest({"site": "elsewhere"}),
        "claims": {"ready": {"status": "unsupported"}},
    })
    history = WorkspaceKnowledgeCatalogue(ReasoningService(tmp_path)).runs("source.eal")
    assert [item["collection_id"] for item in history["collections"]] == [earlier_collection]
    assert [item["assessment_id"] for item in history["assessments"]] == [earlier_assessment]
    assert history["assessments"][0]["claim_statuses"] == {"ready": "supported"}
    assert "secret" not in str(history)


def test_register_tree_reports_invalid_files_and_bounds_discovery(tmp_path):
    _, index = catalogue(tmp_path, path="nested/good.eal")
    (tmp_path / "nested" / "bad.eal").write_text("invalid source")
    result = index.register_tree("nested", context=CONTEXT)
    assert [item["path"] for item in result["registered"]] == ["nested/good.eal"]
    assert [item["path"] for item in result["rejected"]] == ["nested/bad.eal"]
    with pytest.raises(ValueError, match="discovery limit"):
        index.register_tree("nested", limit=1)
    with pytest.raises(ValueError, match="outside the workspace"):
        index.register("../outside.eal")
    with pytest.raises(ValueError, match="finite UTF-8 JSON"):
        index.register("nested/good.eal", context={"bad": float("nan")})
