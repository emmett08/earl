#!/usr/bin/env python3
"""Pre-terminal census of 32 completed A3 final author products.

Only author source fidelity can be reviewed now. Actual recipient host packets
and the predeclared explanation sample will be appended after A3 terminates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import review_sample_a3 as sample

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    frozen = sample.load(args.run_dir / "freeze.json")
    ledger = sample.load(args.run_dir / "ledger.json")
    pre = sample.load(HERE / "predeclared-review-slots-a3.json")
    protocol = HERE / "postcall-review-protocol-a3.json"
    rubric = HERE / "postcall-review-rubric-a3.json"
    manifest = sample.load(HERE / "manifest.json")
    cases = {c["case_id"]: c for c in frozen["base"]["cases"]}
    roots = {r["id"]: r for r in manifest["roots"]}
    if (frozen["a3_freeze_sha256"] != ledger["a3_freeze_sha256"]
            or pre["a3_freeze_sha256"] != frozen["a3_freeze_sha256"]
            or pre["protocol_sha256"] != sha(protocol)
            or frozen["postcall_review_protocol_sha256"] != sha(protocol)):
        raise ValueError("Author-only review materials do not match A3 freeze")
    author = [c for c in frozen["base"]["cases"] if c["stage"] == "author"]
    if (len(author) != 96 or any(ledger["attempts"].get(c["case_id"], {}).get("status") != "completed"
                              for c in author)):
        raise ValueError("All 96 linked author turns must complete before author-only review")
    packets, links = [], []
    for item in pre["author_products"]:
        final = cases[item["case_id"]]
        group = final["author_group"]
        turns = sorted((c for c in author if c["author_group"] == group), key=lambda c: c["turn"])
        root = roots[final["root_id"]]
        packets.append({"sample_id": item["sample_id"],
                        "review_scope": "final_source_and_three_state_task_fidelity_only; actual recipient host packets pending",
                        "format_visible_in_artifact": final["format"],
                        "reference_by_state": [sample.reference(root, state) for state in root["states"]],
                        "three_linked_turns": [
                            {"turn": c["turn"], "actual_messages": ledger["attempts"][c["case_id"]]["messages"],
                             "response_text": ledger["attempts"][c["case_id"]]["response"]["text"],
                             "attempt_status": ledger["attempts"][c["case_id"]]["status"],
                             "provider_request_count": len(ledger["attempts"][c["case_id"]]["requests"])}
                            for c in turns],
                        "review_questions": [
                            "Does the final source represent the exact claim/scope, two routes, targeted alert and matched resolution?",
                            "Do the three synthetic states warrant the reviewed reference statuses with bounded qualifications?",
                            "Which requirements are missing, changed or invented in the final source?",
                        ]})
        links.append({"sample_id": item["sample_id"], "case_ids": [c["case_id"] for c in turns],
                      "author_model": final["model"], "format": final["format"]})
    if len(packets) != 32:
        raise AssertionError("Author census changed")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    sample.save(args.output_dir / "author-only-review-packet.json", packets)
    sample.save(args.output_dir / "private-author-linkage.json", links)
    summary = {"schema": "eal2-deployment-800-a3-author-only-review-extract/1",
               "a3_freeze_sha256": frozen["a3_freeze_sha256"],
               "ledger_sha256_at_extract": sha(args.run_dir / "ledger.json"),
               "protocol_sha256": sha(protocol), "rubric_sha256": sha(rubric),
               "predeclared_slots_sha256": sha(HERE / "predeclared-review-slots-a3.json"),
               "author_products": 32,
               "pending": "Actual recipient packets and the 48 explanation slots follow after A3 terminal; this packet is not final author-host adjudication.",
               "packet_sha256": sha(args.output_dir / "author-only-review-packet.json")}
    sample.save(args.output_dir / "selection.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
