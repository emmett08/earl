"""Reassess two reviewed prose forms over the same synthetic API fixture."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from eal.argument_host import ArgumentHost
from eal.api_load_methods import registry as api_load_registry
from eal.runtime import ReasoningService


EXAMPLE = Path(__file__).resolve().parent
ROOT = EXAMPLE.parents[1]
FIRST = "Does the bundled synthetic load-test fixture meet its recorded sample criteria?"
LATER = "Is the bundled synthetic fixture still within those recorded sample criteria?"
PARAPHRASE = "Are the recorded sample p95 and error percentage within the bundled synthetic fixture's stated limits?"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="eal-argument-host-") as temporary:
        service = ReasoningService(ROOT, EXAMPLE / "argument-tools.toml",
                                   Path(temporary) / "runs.sqlite3", method_registry=api_load_registry())
        host = ArgumentHost.load(service, EXAMPLE / "argument-schemes.toml",
                                 principal="synthetic-demo", session_id="one-conversation")
        first = host.assess(FIRST)
        if first.get("status") != "supported":
            raise RuntimeError(f"Initial checked sample conclusion failed: {first}")
        host.finish(first["assessment_id"])

        later = host.assess(LATER)
        if later.get("status") != "supported":
            raise RuntimeError(f"Later checked sample conclusion failed: {later}")
        host.finish(later["assessment_id"])
        paraphrase = host.assess(PARAPHRASE)
        if paraphrase.get("status") != "supported":
            raise RuntimeError(f"Reviewed paraphrase did not meet the checked sample contract: {paraphrase}")
        host.finish(paraphrase["assessment_id"])
        unknown = host.assess("Is orders-api reliable in production?")
        if unknown.get("status") != "unresolved" or unknown.get("tool_execution") is not False:
            raise RuntimeError(f"Unreviewed question was not rejected: {unknown}")
        print(json.dumps({
            "dataset": "synthetic",
            "question_1_status": first["status"],
            "question_2_status": later["status"],
            "reviewed_paraphrase_status": paraphrase["status"],
            "same_reviewed_source": first["source_digest"] == later["source_digest"],
            "fresh_collection_for_later_wording": len({first["collection_id"], later["collection_id"],
                                                        paraphrase["collection_id"]}) == 3,
            "later_adequacy": later["adequacy"]["status"],
            "unreviewed_question_status": unknown["status"],
            "unreviewed_question_ran_tools": unknown["tool_execution"],
            "meaning": "current recomputation of a pinned historical synthetic fixture",
        }, indent=2))


if __name__ == "__main__":
    main()
