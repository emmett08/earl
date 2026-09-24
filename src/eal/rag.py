"""Reviewed snippet retrieval for candidate suggestions, without assessment authority.

The index uses local BM25 by default. An application may supply query vectors
from any provider; matching reviewed document vectors then add cosine ranking.
Neither ranking signal establishes applicability to a user's question.
"""

from __future__ import annotations

import hashlib
import math
import re
import tomllib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Collection, Sequence

from .evaluator import canonical_digest
from .families import FamilyRegistry, authorised_ids
from .semantics import parse_time


SCHEMA = "eal2-rag-candidates/1"
_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_WORD = re.compile(r"[a-z0-9]+", re.ASCII)
_MAX_DOCUMENT_BYTES = 65536


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def _vector(raw: Any) -> tuple[float, ...]:
    if (not isinstance(raw, (list, tuple)) or not 2 <= len(raw) <= 512
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in raw)):
        raise ValueError("Embedding requires two to 512 finite numeric components")
    values = tuple(float(value) for value in raw)
    if not math.isfinite(math.hypot(*values)) or math.hypot(*values) == 0:
        raise ValueError("Embedding requires a finite nonzero norm")
    return values


def rag_review_digest(families: FamilyRegistry, document_id: str, *, family_id: str,
                      case_review_contract_sha256: str, source_path: str,
                      source_sha256: str, snippet: str, claim_id: str,
                      embedding_model_id: str | None = None,
                      embedding: Sequence[float] | None = None) -> str:
    """Bind reviewed text, source bytes and optional vector to a family case.

    A digest detects changed bytes; the deployment authenticates review and
    controls who may edit the catalogue and its local source files.
    """
    if not isinstance(document_id, str) or not _ID.fullmatch(document_id):
        raise ValueError("Document ID must be an EAL identifier")
    if not isinstance(family_id, str) or family_id not in families.families:
        raise ValueError("RAG document requires an existing family")
    family = families.families[family_id]
    if (not isinstance(case_review_contract_sha256, str)
            or case_review_contract_sha256 not in {
        case.review_contract_sha256 for case in family.cases
    }):
        raise ValueError("RAG document requires a reviewed family case")
    case = next(case for case in family.cases
                if case.review_contract_sha256 == case_review_contract_sha256)
    if not isinstance(claim_id, str) or claim_id not in case.claims:
        raise ValueError("RAG document requires a claim in its reviewed case")
    families._check_case(families.artifacts, family_id, family.parameters,
                         family.context_paths, case)
    if (not isinstance(source_path, str) or not source_path
            or not isinstance(source_sha256, str)
            or not _SHA256.fullmatch(source_sha256)
            or not isinstance(snippet, str) or not snippet.strip()
            or len(source_path.encode("utf-8")) > 256
            or len(snippet.encode("utf-8")) > 2048
            or not 1 <= len(_tokens(snippet)) <= 256):
        raise ValueError("RAG document requires bounded source and snippet")
    if embedding is not None:
        embedding = _vector(embedding)
        if (not isinstance(embedding_model_id, str) or not embedding_model_id.strip()
                or len(embedding_model_id.encode("utf-8")) > 128):
            raise ValueError("Embedding requires one bounded model identity")
    elif embedding_model_id is not None:
        raise ValueError("Embedding model without a vector")
    return canonical_digest({
        "schema": SCHEMA, "document_id": document_id,
        "family_id": family_id, "family_description": family.description,
        "family_terms": list(family.terms),
        "case_review_contract_sha256": case_review_contract_sha256,
        "claim_id": claim_id,
        "source_path": source_path, "source_sha256": source_sha256,
        "snippet": snippet, "embedding_model_id": embedding_model_id,
        "embedding": list(embedding) if embedding is not None else None,
    })


@dataclass(frozen=True)
class _Document:
    document_id: str
    family_id: str
    case_review_contract_sha256: str
    claim_id: str
    source_path: str
    source_sha256: str
    snippet: str
    review_contract_sha256: str
    embedding_model_id: str | None
    embedding: tuple[float, ...] | None


class RagCandidateIndex:
    """Rank operator-reviewed snippets and return advisory family suggestions."""

    def __init__(self, families: FamilyRegistry, root: Path,
                 documents: tuple[_Document, ...], *,
                 embedder: Callable[[str], tuple[str, Sequence[float]]] | None = None):
        self.families = families
        self.root = root
        self.documents = documents
        self.embedder = embedder
        self._terms = {d.document_id: Counter(_tokens(d.snippet)) for d in documents}
        self._lengths = {name: sum(words.values()) for name, words in self._terms.items()}

    @classmethod
    def load(cls, families: FamilyRegistry, path: str | Path, *,
             embedder: Callable[[str], tuple[str, Sequence[float]]] | None = None
             ) -> "RagCandidateIndex":
        """Load a bounded catalogue and verify local source bytes and reviews."""
        manifest = Path(path)
        if manifest.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("RAG catalogue exceeds four MiB")
        root = manifest.resolve().parent
        with manifest.open("rb") as stream:
            document = tomllib.load(stream)
        if (set(document) != {"schema", "documents"} or document["schema"] != SCHEMA
                or not isinstance(document["documents"], dict)
                or not 1 <= len(document["documents"]) <= 128):
            raise ValueError("Expected a bounded eal2-rag-candidates/1 catalogue")
        rows = []
        model_dimensions: dict[str, int] = {}
        required = {"family_id", "case_review_contract_sha256", "claim_id", "source_path",
                    "source_sha256", "snippet", "reviewed_by", "reviewed_at",
                    "review_contract_sha256"}
        for document_id, entry in document["documents"].items():
            if not isinstance(entry, dict) or set(entry) not in (
                    required, required | {"embedding_model_id", "embedding"}):
                raise ValueError("RAG entry requires exact source and review fields")
            if (not isinstance(entry["reviewed_by"], str)
                    or not entry["reviewed_by"].strip()
                    or len(entry["reviewed_by"].encode("utf-8")) > 128
                    or not isinstance(entry["reviewed_at"], str)
                    or not isinstance(entry["review_contract_sha256"], str)
                    or not _SHA256.fullmatch(entry["review_contract_sha256"])):
                raise ValueError("RAG entry requires bounded reviewer, time and digest")
            parse_time(entry["reviewed_at"])
            family_id = entry["family_id"]
            case_digest = entry["case_review_contract_sha256"]
            claim_id = entry["claim_id"]
            source_path = entry["source_path"]
            source_sha = entry["source_sha256"]
            snippet = entry["snippet"]
            vector = (entry.get("embedding") if "embedding" in entry else None)
            model = entry.get("embedding_model_id")
            digest = rag_review_digest(families, document_id, family_id=family_id,
                                       case_review_contract_sha256=case_digest,
                                       claim_id=claim_id,
                                       source_path=source_path, source_sha256=source_sha,
                                       snippet=snippet, embedding_model_id=model,
                                       embedding=vector)
            if entry["review_contract_sha256"] != digest:
                raise ValueError(f"RAG document {document_id!r} review contract differs")
            row = _Document(document_id, family_id, case_digest, claim_id, source_path,
                            source_sha, snippet, digest, model,
                            _vector(vector) if vector is not None else None)
            cls._check_source(root, row)
            if row.embedding is not None:
                assert model is not None
                if model in model_dimensions and model_dimensions[model] != len(row.embedding):
                    raise ValueError("Embedding model has inconsistent dimensions")
                model_dimensions[model] = len(row.embedding)
            rows.append(row)
        return cls(families, root, tuple(rows), embedder=embedder)

    @staticmethod
    def _check_source(root: Path, document: _Document) -> None:
        path = Path(document.source_path)
        if (path.is_absolute() or not path.parts
                or any(part in (".", "..") for part in path.parts)):
            raise ValueError("RAG source must be a local relative file")
        source = (root / path).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("RAG source is outside the local reviewed corpus")
        with source.open("rb") as stream:
            data = stream.read(_MAX_DOCUMENT_BYTES + 1)
        if len(data) > _MAX_DOCUMENT_BYTES:
            raise ValueError("RAG source exceeds the document size bound")
        if hashlib.sha256(data).hexdigest() != document.source_sha256:
            raise ValueError("RAG source differs from reviewed bytes")
        if document.snippet not in data.decode("utf-8"):
            raise ValueError("RAG snippet is absent from reviewed source")

    def search(self, query: str, *, authorised_families: Collection[str],
               authorised_artifacts: Collection[str],
               authorised_claims: Mapping[str, Collection[str]],
               limit: int = 8, query_embedding: tuple[str, Sequence[float]] | None = None
               ) -> list[dict[str, Any]]:
        """Return deterministic suggestions; similarity grants no case authority.

        A caller may supply `(model_id, vector)` or configure an embedder.
        A request never triggers collection or family assessment here.
        """
        if (not isinstance(query, str) or not query.strip()
                or not 1 <= len(query.encode("utf-8")) <= 4096):
            raise ValueError("Candidate query must be 1 to 4096 UTF-8 bytes")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Candidate limit must be an integer from 1 through 20")
        terms = set(_tokens(query))
        if not terms or len(terms) > 128:
            raise ValueError("Candidate query requires one to 128 searchable words")
        allowed = authorised_ids(authorised_families)
        allowed_artifacts = authorised_ids(authorised_artifacts)
        if not isinstance(authorised_claims, Mapping):
            raise ValueError("Claim permissions require an artifact-to-claim mapping")
        authorised_ids(list(authorised_claims))
        allowed_claims = {artifact: authorised_ids(claims)
                          for artifact, claims in authorised_claims.items()}
        if query_embedding is not None and self.embedder is not None:
            raise ValueError("Supply query vectors through one source only")
        # Recheck on every request: changing corpus bytes or case contracts
        # invalidates retrieval, even when the index object is long-lived.
        eligible = []
        for document in self.documents:
            if document.family_id not in allowed:
                continue
            family = self.families.families[document.family_id]
            case = next((case for case in family.cases
                         if case.review_contract_sha256 == document.case_review_contract_sha256), None)
            if (case is None or case.artifact_id not in allowed_artifacts
                    or document.claim_id not in allowed_claims.get(case.artifact_id, ())):
                continue
            self._check_source(self.root, document)
            expected = rag_review_digest(
                self.families, document.document_id, family_id=document.family_id,
                case_review_contract_sha256=document.case_review_contract_sha256,
                claim_id=document.claim_id,
                source_path=document.source_path, source_sha256=document.source_sha256,
                snippet=document.snippet, embedding_model_id=document.embedding_model_id,
                embedding=document.embedding)
            if expected != document.review_contract_sha256:
                raise ValueError("RAG review contract changed after load")
            eligible.append(document)
        if not eligible:
            return []
        if query_embedding is None and self.embedder is not None and any(
                document.embedding is not None for document in eligible):
            query_embedding = self.embedder(query)
        model: str | None = None
        vector: tuple[float, ...] | None = None
        if query_embedding is not None:
            if (not isinstance(query_embedding, (tuple, list))
                    or len(query_embedding) != 2
                    or not isinstance(query_embedding[0], str)
                    or not query_embedding[0].strip()
                    or len(query_embedding[0].encode("utf-8")) > 128):
                raise ValueError("Query embedding requires model identity and vector")
            model, vector = query_embedding[0], _vector(query_embedding[1])
        df = Counter(term for document in eligible for term in self._terms[document.document_id])
        avg = sum(self._lengths[d.document_id] for d in eligible) / len(eligible)
        lexical: dict[str, float] = {}
        semantic: dict[str, float] = {}
        for document in eligible:
            words = self._terms[document.document_id]
            length = self._lengths[document.document_id]
            score = 0.0
            for term in sorted(terms & words.keys()):
                tf = words[term]
                idf = math.log1p((len(eligible) - df[term] + .5) / (df[term] + .5))
                score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * length / avg))
            if score > 0:
                lexical[document.document_id] = score
            if (vector is not None and document.embedding is not None
                    and document.embedding_model_id == model):
                if len(vector) != len(document.embedding):
                    raise ValueError("Query embedding dimension differs from reviewed model")
                query_norm = math.hypot(*vector)
                document_norm = math.hypot(*document.embedding)
                similarity = sum((a / query_norm) * (b / document_norm)
                                 for a, b in zip(vector, document.embedding))
                if similarity > 0:
                    semantic[document.document_id] = similarity
        # Reciprocal rank fusion avoids comparing BM25 and cosine magnitudes.
        lexical_rank = {name: rank for rank, (name, _) in enumerate(
            sorted(lexical.items(), key=lambda item: (-item[1], item[0])), 1)}
        semantic_rank = {name: rank for rank, (name, _) in enumerate(
            sorted(semantic.items(), key=lambda item: (-item[1], item[0])), 1)}
        best: dict[str, dict[str, Any]] = {}
        for document in eligible:
            name = document.document_id
            if name not in lexical_rank and name not in semantic_rank:
                continue
            score = ((1 / (60 + lexical_rank[name]) if name in lexical_rank else 0)
                     + (1 / (60 + semantic_rank[name]) if name in semantic_rank else 0))
            candidate = {
                "family_id": document.family_id, "score": score,
                "document_id": name, "source_path": document.source_path,
                "case_review_contract_sha256": document.case_review_contract_sha256,
                "claim_id": document.claim_id,
                "reviewed_snippet": document.snippet,
                "signals": {"bm25": lexical.get(name), "cosine": semantic.get(name)},
            }
            current = best.get(document.family_id)
            if current is None or (-score, name) < (-current["score"], current["document_id"]):
                best[document.family_id] = candidate
        return sorted(best.values(), key=lambda row: (-row["score"], row["family_id"]))[:limit]
