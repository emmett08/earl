#!/usr/bin/env python3
"""Local, fixture-author retrieval diagnostic; no model or embedding API calls."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from eal.rag import RagCandidateIndex, rag_review_digest
from eal.retrieval import CandidateIndex


HERE = Path(__file__).resolve().parent
QUERIES = HERE / "retrieval_queries.json"
DOCUMENTS = HERE / "retrieval_documents.txt"
_spec = importlib.util.spec_from_file_location("eal2_reviewed_retrieval_fixture", HERE / "run.py")
assert _spec is not None and _spec.loader is not None
study = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(study)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _query_fixture(roots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fixture = json.loads(QUERIES.read_text(encoding="utf-8"))
    if (set(fixture) != {"schema", "review_status", "queries"}
            or fixture["schema"] != "eal2-retrieval-developmental/1"
            or fixture["review_status"] != study.REVIEW_LABEL
            or not isinstance(fixture["queries"], list)
            or len(fixture["queries"]) != 9):
        raise ValueError("Expected nine explicitly unreviewed retrieval queries")
    root_by_id = {root["id"]: root for root in roots}
    seen: set[str] = set()
    resolved = []
    for entry in fixture["queries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] in seen:
            raise ValueError("Retrieval query requires a unique identifier")
        seen.add(entry["id"])
        kind = entry.get("kind")
        target = entry.get("relevant_family")
        if kind == "exact":
            if (set(entry) != {"id", "kind", "brief_root", "relevant_family"}
                    or entry["brief_root"] not in root_by_id
                    or target != entry["brief_root"]):
                raise ValueError("Exact query must name its frozen root")
            query = root_by_id[entry["brief_root"]]["brief"]
        elif kind in {"paraphrase", "decoy", "no_target"}:
            if (set(entry) != {"id", "kind", "text", "relevant_family"}
                    or not isinstance(entry["text"], str) or not entry["text"].strip()
                    or len(entry["text"].encode("utf-8")) > 4096):
                raise ValueError("Query text must be explicit and bounded")
            if (kind == "paraphrase" and target not in root_by_id) or (
                    kind != "paraphrase" and target is not None):
                raise ValueError("Query relevance label conflicts with its kind")
            query = entry["text"]
        else:
            raise ValueError("Unknown retrieval query kind")
        resolved.append({"id": entry["id"], "kind": kind, "query": query,
                         "relevant_family": target})
    if {row["relevant_family"] for row in resolved if row["kind"] == "exact"} != set(root_by_id):
        raise ValueError("Every root needs one exact query")
    return resolved


def build_indexes(workspace: Path) -> tuple[CandidateIndex, RagCandidateIndex, Any, list[dict]]:
    """Give both rankers identical family vocabulary and the same grants."""
    roots = study.corpus()["roots"]
    host, _ = study.prepare(workspace, roots, roots[0], roots[0]["states"][0])
    families = host.families
    expected_lines = [" ".join((study.DESCRIPTIONS[root["id"]][0],
                                *study.DESCRIPTIONS[root["id"]][1]))
                      for root in roots]
    if DOCUMENTS.read_text(encoding="utf-8").splitlines() != expected_lines:
        raise ValueError("BM25 and lexical family vocabularies are no longer the same")
    shutil.copyfile(DOCUMENTS, workspace / DOCUMENTS.name)
    source_sha = _sha(workspace / DOCUMENTS.name)
    lines = ['schema = "eal2-rag-candidates/1"', ""]
    for root, snippet in zip(roots, expected_lines, strict=True):
        family_id = root["id"]
        case = families.families[family_id].cases[0]
        review_sha = rag_review_digest(
            families, family_id, family_id=family_id,
            case_review_contract_sha256=case.review_contract_sha256,
            claim_id=root["claim"], source_path=DOCUMENTS.name,
            source_sha256=source_sha, snippet=snippet)
        values = {
            "family_id": family_id,
            "case_review_contract_sha256": case.review_contract_sha256,
            "claim_id": root["claim"], "source_path": DOCUMENTS.name,
            "source_sha256": source_sha, "snippet": snippet,
            "reviewed_by": study.REVIEW_LABEL, "reviewed_at": study.REVIEW_TIME,
            "review_contract_sha256": review_sha,
        }
        lines.append(f"[documents.{family_id}]")
        lines.extend(f"{key} = {json.dumps(value, ensure_ascii=False)}"
                     for key, value in values.items())
        lines.append("")
    manifest = workspace / "retrieval_manifest.toml"
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return CandidateIndex(families), RagCandidateIndex.load(families, manifest), host, roots


def _summary(rows: list[dict], name: str) -> dict[str, int]:
    targets = [row for row in rows if row["relevant_family"] is not None]
    negatives = [row for row in rows if row["relevant_family"] is None]
    no_target = [row for row in rows if row["kind"] == "no_target"]
    return {
        "target_queries": len(targets),
        "recall_at_1": sum(row["relevant_family"] in row[name][:1] for row in targets),
        "recall_at_3": sum(row["relevant_family"] in row[name][:3] for row in targets),
        "wrong_top_1": sum(bool(row[name]) and row[name][0] != row["relevant_family"]
                           for row in targets),
        "no_target_queries": len(negatives),
        "false_suggestion_no_target": sum(bool(row[name]) for row in negatives),
        "unrelated_abstentions": sum(not row[name] for row in no_target),
    }


def evaluate() -> dict[str, Any]:
    """Report descriptive retrieval results, never promote candidates to tasks."""
    with tempfile.TemporaryDirectory(prefix="eal2-retrieval-diagnostic-") as temporary:
        lexical, bm25, host, roots = build_indexes(Path(temporary))
        queries = _query_fixture(roots)
        family_ids = {root["id"] for root in roots}
        claims = {root["id"]: {root["claim"]} for root in roots}
        service = host.families.artifacts.service
        if service.store.list(kind="collection"):
            raise AssertionError("Retrieval began with an evidence collection")
        rows = []
        for entry in queries:
            query = entry["query"]
            old = lexical.search(query, authorised_families=family_ids, limit=3)
            new = bm25.search(query, authorised_families=family_ids,
                              authorised_artifacts=family_ids,
                              authorised_claims=claims, limit=3)
            rows.append({**entry, "lexical": [item["family_id"] for item in old],
                         "bm25": [item["family_id"] for item in new]})
        if service.store.list(kind="collection"):
            raise AssertionError("Candidate retrieval collected evidence")
        withheld = bm25.search(queries[0]["query"], authorised_families=family_ids,
                               authorised_artifacts=family_ids,
                               authorised_claims={}, limit=3)
        if withheld:
            raise AssertionError("BM25 suggestion escaped an empty claim grant")
        return {
            "schema": "eal2-retrieval-diagnostic/1", "status": study.REVIEW_LABEL,
            "provider_calls": 0, "task_roots": len(roots),
            "fixture_sha256": _sha(QUERIES), "documents_sha256": _sha(DOCUMENTS),
            "corpus_sha256": _sha(study.MANIFEST),
            "shared_vocabulary": True, "embeddings_used": False,
            "query_results": rows,
            "metrics": {name: _summary(rows, name) for name in ("lexical", "bm25")},
            "grant_leak_count": len(withheld),
            "interpretation": (
                "Nine exposed, fixture-author labelled queries over three families. "
                "Candidate ranking is advisory; empty claim grants return no BM25 suggestions. "
                "No model, vector, independent review, held-out retrieval or downstream answer "
                "improvement is measured; these counts have no population inference."
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": result["status"], "provider_calls": 0,
                      "metrics": result["metrics"]}, sort_keys=True))


if __name__ == "__main__":
    main()
