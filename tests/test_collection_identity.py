"""Stored collections are usable only under their exact source and context."""

import pytest

from eal.parser import parse
from eal.runtime import ReasoningService


SOURCE = '''language "EAL/3"

environment lab {
  require "site" == "bench"
}

tool runner {
  version "1"
}

evidence measured {
  tool runner
  kind test
  environment lab
  max_age 60
  require "passed" == true
}

reasoning observation {
  method "structured/1"
  rationale "The declared observation supports the bounded claim."
}

claim works {
  statement "The test passes."
  environment lab
}

argument result = [evidence measured] via observation => works
'''


def test_reason_rejects_collection_for_different_source_even_without_records(tmp_path):
    service = ReasoningService(tmp_path)
    collection_id = service.store.put("collection", {
        "source_digest": parse(SOURCE).source_digest, "context": {"site": "bench"}, "records": {},
    })
    changed = SOURCE.replace("The test passes.", "The test passes in production.")
    with pytest.raises(ValueError, match="assessment source"):
        service.reason(changed, {"site": "bench"}, collection_id)


def test_reason_and_aspic_share_context_validation(tmp_path):
    service = ReasoningService(tmp_path)
    collection_id = service.store.put("collection", {
        "source_digest": parse(SOURCE).source_digest, "context": {"site": "bench"}, "records": {},
    })
    with pytest.raises(ValueError, match="assessment context"):
        service.reason(SOURCE, {"site": "other"}, collection_id)
    with pytest.raises(ValueError, match="assessment context"):
        service.compile_aspic(SOURCE, {"site": "other"}, collection_id, "works")


def test_reason_rejects_malformed_collection_records(tmp_path):
    service = ReasoningService(tmp_path)
    collection_id = service.store.put("collection", {
        "source_digest": parse(SOURCE).source_digest, "context": {"site": "bench"},
        "records": {"measured": "not an observation"},
    })
    with pytest.raises(ValueError, match="Collection records"):
        service.reason(SOURCE, {"site": "bench"}, collection_id)
