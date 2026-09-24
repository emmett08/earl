"""Check that all independently assigned pilot statuses match EAL/2 execution.

This is corpus preflight, not a live model trial or validation of the source's
physical correspondence. The method worker uses multiprocessing spawn, so run
this file as a script rather than through `python -` or an interactive shell.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from eal.runtime import ReasoningService, load_method_registry
from reference_oracle import brief_status


def main():
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "eal2-artifact-live-pilot/1"
    assert len(manifest["roots"]) == 4
    checked = 0
    for root in manifest["roots"]:
        source_path = here / root["source"]
        source = source_path.read_text(encoding="utf-8")
        assert len(root["states"]) == 3
        for state in root["states"]:
            brief_expected, brief_reason = brief_status(root, state)
            assert brief_expected == state["expected"], (root["id"], state["id"], brief_reason)
            with tempfile.TemporaryDirectory(prefix="eal-pilot-preflight-") as temporary:
                service = ReasoningService(
                    source_path.parent, here / state["registry"],
                    Path(temporary) / "runs.sqlite3",
                    method_registry=load_method_registry(root.get("method_factory")),
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
                assert actual == state["expected"], (root["id"], state["id"], state["expected"], actual)
                checked += 1
    print(f"{checked} synthetic state oracles agree with the pinned EAL/2 interpreter")


if __name__ == "__main__":
    main()
