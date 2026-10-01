"""Exercise shared arguments, separate observations and scope-safe reuse."""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path

from eal.knowledge import EALKnowledgeBase


EXAMPLE = Path(__file__).resolve().parent
ROOT = EXAMPLE.parents[1]
SOURCE_PATH = "examples/multi-environment/source.eal"
ASSESS_AT = "2026-09-30T10:00:30Z"
CONTEXT = {"$environments": {
    name: {"dataset": "synthetic", "deployment": name, "sensor": "controller-A", "scenario": "safe"}
    for name in ("staging", "production")
}}
CLAIMS = {name: f"{name}_check.within_limit" for name in ("staging", "production")}


def demonstrate(database: Path) -> dict:
    knowledge = EALKnowledgeBase(ROOT, EXAMPLE / "tools.toml", database)
    service = knowledge.service
    source = (EXAMPLE / "source.eal").read_text()
    validated = service.validate(source)
    assert validated["valid"], validated
    assert service.validate(service.format(source)["source"])["valid"]
    knowledge.register(SOURCE_PATH, entry_id="multi-environment", context=CONTEXT)

    first = {name: knowledge.assess("multi-environment", claim, now=ASSESS_AT)
             for name, claim in CLAIMS.items()}
    assert all(result["status"] == "supported" for result in first.values()), first
    assert all((result["collected_count"], result["reused_count"]) == (1, 0)
               for result in first.values()), first

    # Reopen the persistent host to demonstrate reuse across sessions.
    next_session = EALKnowledgeBase(ROOT, EXAMPLE / "tools.toml", database)
    reused = {name: next_session.assess("multi-environment", claim, now=ASSESS_AT)
              for name, claim in CLAIMS.items()}
    assert all((result["status"], result["collected_count"], result["reused_count"])
               == ("supported", 0, 1) for result in reused.values()), reused

    overheated = deepcopy(CONTEXT)
    overheated["$environments"]["production"]["scenario"] = "overheat"
    negative = next_session.assess("multi-environment", CLAIMS["production"],
                                   context=overheated, now=ASSESS_AT)
    assert (negative["status"], negative["collected_count"], negative["reused_count"]) == (
        "unsupported", 1, 0), negative

    missing = {"$environments": {"staging": CONTEXT["$environments"]["staging"]}}
    isolated = next_session.assess("multi-environment", CLAIMS["production"],
                                  context=missing, now=ASSESS_AT)
    assert isolated["status"] == "out_of_scope" and isolated["reused_count"] == 0, isolated

    def concise(result: dict) -> dict:
        return {key: result[key] for key in ("status", "collected_count", "reused_count")}

    return {"dataset": "synthetic", "source_language": "EAL/3", "assessed_at": ASSESS_AT,
            "first_session": {name: concise(result) for name, result in first.items()},
            "second_session": {name: concise(result) for name, result in reused.items()},
            "production_overheat": concise(negative), "production_context_missing": concise(isolated)}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="eal-multiple-environments-") as temporary:
        print(json.dumps(demonstrate(Path(temporary) / "records.sqlite3"), indent=2))


if __name__ == "__main__":
    main()
