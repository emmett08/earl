"""Bounded lexical suggestions for operator-reviewed EAL task families.

Retrieval is deliberately unable to select a case, bind a parameter or run
an assessment. Every returned candidate still requires exact authorisation
and binding through FamilyRegistry.resolve.
"""

from __future__ import annotations

import re
from typing import Collection

from .families import FamilyRegistry, authorised_ids


_WORD = re.compile(r"[a-z0-9_]+", re.ASCII)


def _words(value: str) -> set[str]:
    return set(_WORD.findall(value.casefold()))


class CandidateIndex:
    def __init__(self, families: FamilyRegistry):
        self.families = families
        self.index = {name: _words(" ".join((family.description, *family.terms)))
                      for name, family in families.families.items()}

    def search(self, query: str, *, authorised_families: Collection[str],
               limit: int = 8) -> list[dict]:
        """Return possible family IDs with lexical overlap, including ties.

        The score is a ranking aid rather than evidence of applicability.
        Empty overlap returns no candidate and never guesses a family.
        """
        if not isinstance(query, str) or not 1 <= len(query.encode("utf-8")) <= 4096:
            raise ValueError("Candidate query must be 1 to 4096 UTF-8 bytes")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Candidate limit must be an integer from 1 through 20")
        tokens = _words(query)
        if not tokens or len(tokens) > 128:
            raise ValueError("Candidate query requires one to 128 searchable words")
        allowed = authorised_ids(authorised_families)
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
