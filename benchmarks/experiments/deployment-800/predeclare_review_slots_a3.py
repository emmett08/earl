#!/usr/bin/env python3
"""Freeze outcome-independent A3 review IDs before any A3 API request."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = ("initial", "adverse", "restored")
EXPOSURES = ("fixed_direct", "fixed_host_owned", "authored_recipient")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exposure(case: dict) -> str | None:
    if case["stage"] == "recipient":
        return "authored_recipient"
    if case["stage"] == "fixed" and case["delivery"] in ("direct", "host_owned"):
        return "fixed_" + case["delivery"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("freeze", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    frozen = json.loads(args.freeze.read_text())
    protocol_path = HERE / "postcall-review-protocol-a3.json"
    if digest(protocol_path) != frozen["postcall_review_protocol_sha256"]:
        raise ValueError("A3 review protocol not bound to freeze")
    cases = frozen["base"]["cases"]
    roots = sorted({c["root_id"] for c in cases})
    author = [{"sample_id": f"A{i + 1:02d}", "case_id": c["case_id"]}
              for i, c in enumerate(c for c in cases if c["stage"] == "author" and c["turn"] == 2)]
    explanations = []
    for root_index, root in enumerate(roots):
        for state_index, state in enumerate(STATES):
            block_index = 3 * root_index + state_index
            for arm_index, arm in enumerate(EXPOSURES):
                if arm_index == block_index % 3:
                    continue
                eligible = [c for c in cases if c["root_id"] == root
                            and c["state_id"] == state and exposure(c) == arm]
                if not eligible:
                    raise ValueError("A selected block has no frozen eligible case")
                chosen = min(eligible, key=lambda c: (
                    hashlib.sha256(("240924801|" + c["case_id"]).encode()).hexdigest(),
                    c["case_id"]))
                explanations.append({"sample_id": f"E{len(explanations) + 1:02d}",
                                     "case_id": chosen["case_id"],
                                     "root_id": root, "state_id": state,
                                     "exposure": arm})
    if len(author) != 32 or len(explanations) != 48:
        raise ValueError("A3 predeclared sample count changed")
    result = {"schema": "eal2-deployment-800-a3-predeclared-review-slots/1",
              "a3_freeze_sha256": frozen["a3_freeze_sha256"],
              "protocol_sha256": digest(protocol_path),
              "author_products": author, "explanations": explanations,
              "disclosure": "Case IDs and exposures were selected before any A3 model response; A1/A2/C1 operational outcomes were visible."}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"authors": len(author), "explanations": len(explanations),
                      "output_sha256": digest(args.output)}))


if __name__ == "__main__":
    main()
