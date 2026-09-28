"""Identity checks shared by ordinary and formal assessment of stored collections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evaluator import canonical_digest


class CollectionIdentityValidator:
    """Reject a collection whose source or context differs from the assessment."""

    def validate(self, collection: Mapping[str, Any], *, source_digest: str,
                 context: Mapping[str, Any]) -> dict[str, dict]:
        if not isinstance(collection, Mapping):
            raise ValueError("Stored collection must be a JSON object")
        if collection.get("source_digest") != source_digest:
            raise ValueError("Collection differs from the assessment source")
        if canonical_digest(collection.get("context")) != canonical_digest(context):
            raise ValueError("Collection differs from the assessment context")
        records = collection.get("records")
        if not isinstance(records, dict) or any(
            not isinstance(name, str) or not isinstance(record, dict)
            for name, record in records.items()
        ):
            raise ValueError("Collection records must map evidence IDs to observations")
        return records
