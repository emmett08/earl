"""Preflight source fidelity against brief rules for synthetic inputs only.

This executes no model calls and cannot substitute for masked human review.
The method worker uses multiprocessing spawn; run this module as a script.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from eal.runtime import ReasoningService
from reference_oracle import brief_status


def main() -> None:
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "eal2-cross-model-delivery/1"
    assert len(manifest["roots"]) == 3
    assert len({root["id"] for root in manifest["roots"]}) == 3
    checked = 0
    for root in manifest["roots"]:
        source_path = here / root["source"]
        source = source_path.read_text(encoding="utf-8")
        assert len(root["states"]) == 3
        assert len(root["tamper"]) >= 1
        for state in (*root["states"], *root["tamper"]):
            assert state["review"]["status"] == "pending_independent_human_review"
            expected, reason = brief_status(root, state)
            assert expected == state["expected"], (root["id"], state["id"], reason)
            with tempfile.TemporaryDirectory(prefix="eal-delivery-fixture-") as temporary:
                service = ReasoningService(
                    source_path.parent, here / state["registry"],
                    Path(temporary) / "runs.sqlite3",
                )
                validity = service.validate(source)
                assert validity["valid"], (root["id"], validity["diagnostics"])
                assert all(binding.kind == "json_file" for binding in service.runtime.registry.bindings.values())
                collection = service.collect(source, root["context"])
                assert all(record["status"] == "ok" for record in collection["records"].values()), (
                    root["id"], state["id"], collection["records"]
                )
                result = service.reason(source, root["context"], collection["collection_id"], root["now"])
                actual = result["claims"][root["claim"]]["status"]
                assert actual == expected, (root["id"], state["id"], expected, actual)
                checked += 1
    print(f"{checked} state/tamper oracles agree with pinned EAL/2 execution; human review remains pending")


if __name__ == "__main__":
    main()
