"""Bounded lexical suggestions for operator-reviewed EAL task families.

Retrieval is deliberately unable to select a case, bind a parameter or run
an assessment. Optional aliases require a separate reviewed, pinned manifest;
even a unique candidate is never a task-applicability decision.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Collection, Mapping

from .evaluator import canonical_digest
from .families import FamilyRegistry, authorised_ids
from .semantics import parse_time


ALIAS_SCHEMA = "eal2-retrieval-aliases/1"
_WORD = re.compile(r"[a-z0-9]+", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _words(value: str) -> set[str]:
    return set(_WORD.findall(value.casefold()))


def alias_review_digest(families: FamilyRegistry, family_id: str,
                        aliases: Collection[str]) -> str:
    """Pin suggested vocabulary to a reviewed family and its case contracts.

    The digest detects changes; the operator authenticates the reviewer. Alias
    words affect candidate recall only and never grant applicability.
    """
    family = families.families[family_id]
    return canonical_digest({
        "schema": ALIAS_SCHEMA, "family_id": family_id,
        "description": family.description, "terms": list(family.terms),
        "cases": [case.review_contract_sha256 for case in family.cases],
        "aliases": list(aliases),
    })


class CandidateIndex:
    def __init__(self, families: FamilyRegistry, *, _aliases: dict[str, tuple[str, ...]] | None = None):
        self.families = families
        aliases = _aliases or {}
        self.index = {name: _words(" ".join((family.description, *family.terms,
                                            *aliases.get(name, ()))))
                      for name, family in families.families.items()}

    @classmethod
    def load(cls, families: FamilyRegistry, path: str | Path) -> "CandidateIndex":
        """Load explicitly reviewed aliases; no guessed synonym expansion."""
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
        if (set(document) != {"schema", "aliases"} or document["schema"] != ALIAS_SCHEMA
                or not isinstance(document["aliases"], dict)
                or len(document["aliases"]) > len(families.families)):
            raise ValueError("Invalid EAL/2 retrieval alias manifest")
        aliases = {}
        for family_id, entry in document["aliases"].items():
            if (family_id not in families.families or not isinstance(entry, dict)
                    or set(entry) != {"terms", "reviewed_by", "reviewed_at", "review_contract_sha256"}):
                raise ValueError("Alias entry requires an existing family and exact review fields")
            terms = entry["terms"]
            if (not isinstance(terms, list) or not 1 <= len(terms) <= 32
                    or any(not isinstance(term, str) or not term.strip()
                           or len(term.encode("utf-8")) > 128 or not 1 <= len(_words(term)) <= 16
                           for term in terms)
                    or len(set(terms)) != len(terms)):
                raise ValueError("Aliases require one to 32 distinct bounded phrases")
            if (not isinstance(entry["reviewed_by"], str) or not entry["reviewed_by"].strip()
                    or len(entry["reviewed_by"].encode("utf-8")) > 128
                    or not isinstance(entry["reviewed_at"], str)
                    or not isinstance(entry["review_contract_sha256"], str)
                    or not _SHA256.fullmatch(entry["review_contract_sha256"])):
                raise ValueError("Alias entry requires bounded reviewer, time and digest")
            parse_time(entry["reviewed_at"])
            if entry["review_contract_sha256"] != alias_review_digest(families, family_id, terms):
                raise ValueError("Alias review contract differs from its family")
            aliases[family_id] = tuple(terms)
        return cls(families, _aliases=aliases)

    def search(self, query: str, *, authorised_families: Collection[str],
               authorised_artifacts: Collection[str] | None = None,
               authorised_claims: Mapping[str, Collection[str]] | None = None,
               limit: int = 8) -> list[dict]:
        """Return possible family IDs with lexical overlap, ordered across ties.

        The score is a ranking aid rather than evidence of applicability.
        The limit may omit tied candidates; a client must never promote the
        highest ranked suggestion into an applicability decision. Empty
        overlap returns no candidate and never guesses a family.
        """
        if not isinstance(query, str) or not 1 <= len(query.encode("utf-8")) <= 4096:
            raise ValueError("Candidate query must be 1 to 4096 UTF-8 bytes")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Candidate limit must be an integer from 1 through 20")
        tokens = _words(query)
        if not tokens or len(tokens) > 128:
            raise ValueError("Candidate query requires one to 128 searchable words")
        allowed = authorised_ids(authorised_families)
        if authorised_artifacts is not None or authorised_claims is not None:
            artifacts = (authorised_ids(authorised_artifacts)
                         if authorised_artifacts is not None else None)
            claims = ({artifact_id: authorised_ids(granted)
                       for artifact_id, granted in authorised_claims.items()}
                      if authorised_claims is not None else None)
            allowed = {family_id for family_id in allowed
                       if family_id in self.families.families and
                       any((artifacts is None or case.artifact_id in artifacts)
                           and (claims is None or bool(
                               set(case.claims) & claims.get(case.artifact_id, set())))
                           for case in self.families.families[family_id].cases)}
        matches = []
        for family_id, words in self.index.items():
            if family_id not in allowed:
                continue
            shared = sorted(tokens & words)
            if shared:
                matches.append({"family_id": family_id, "score": len(shared),
                                "matched_terms": shared})
        matches.sort(key=lambda candidate: (-candidate["score"], candidate["family_id"]))
        return matches[:limit]
