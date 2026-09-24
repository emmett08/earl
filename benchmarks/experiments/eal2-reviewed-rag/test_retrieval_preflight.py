"""Small local regression for advisory retrieval; no provider request."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_path = Path(__file__).with_name("retrieval_preflight.py")
_spec = importlib.util.spec_from_file_location("eal2_retrieval_preflight_test", _path)
assert _spec is not None and _spec.loader is not None
study = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(study)


def test_fixture_author_queries_report_both_hits_and_false_suggestions():
    report = study.evaluate()
    assert report["provider_calls"] == 0
    assert report["embeddings_used"] is False
    assert report["shared_vocabulary"] is True
    assert len(report["query_results"]) == 9
    assert report["grant_leak_count"] == 0
    for method in ("lexical", "bm25"):
        assert report["metrics"][method] == {
            "target_queries": 6, "recall_at_1": 6, "recall_at_3": 6,
            "wrong_top_1": 0, "no_target_queries": 3,
            "false_suggestion_no_target": 2, "unrelated_abstentions": 1,
        }
    assert report["query_results"][-1]["lexical"] == []
    assert report["query_results"][-1]["bm25"] == []


def test_changed_snippet_source_refuses_retrieval(tmp_path):
    _, bm25, host, roots = study.build_indexes(tmp_path)
    question = roots[0]["brief"]
    grants = {root["id"] for root in roots}
    claims = {root["id"]: {root["claim"]} for root in roots}
    assert bm25.search(question, authorised_families=grants,
                       authorised_artifacts=grants,
                       authorised_claims=claims)
    assert host.families.artifacts.service.store.list(kind="collection") == []
    source = tmp_path / study.DOCUMENTS.name
    source.write_text(source.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source differs from reviewed bytes"):
        bm25.search(question, authorised_families=grants,
                    authorised_artifacts=grants, authorised_claims=claims)
    assert host.families.artifacts.service.store.list(kind="collection") == []


def test_claim_grants_filter_before_suggestions(tmp_path):
    _, bm25, _, roots = study.build_indexes(tmp_path)
    question = roots[0]["brief"]
    grants = {root["id"] for root in roots}
    assert bm25.search(question, authorised_families=grants,
                       authorised_artifacts=grants, authorised_claims={}) == []
    only_network = {"network_failover": {"bounded_failover"}}
    candidates = bm25.search(question, authorised_families=grants,
                             authorised_artifacts=grants,
                             authorised_claims=only_network)
    assert all(row["family_id"] == "network_failover" for row in candidates)
