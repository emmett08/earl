#!/usr/bin/env python3
"""Compare two sealed independent author-only A3 review files by item ID."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(first: Path, second: Path, packet: Path) -> dict:
    a, b, source = (json.loads(p.read_text()) for p in (first, second, packet))
    rows_a = {r["sample_id"]: r for r in a["items"]}
    rows_b = {r["sample_id"]: r for r in b["items"]}
    packet_rows = {r["sample_id"]: r for r in source}
    if (len(rows_a) != 32 or set(rows_a) != set(rows_b) or set(rows_a) != set(packet_rows)):
        raise ValueError("Independent reviews differ in the assigned 32-product census")
    for key in rows_a:
        actual_text = packet_rows[key]["three_linked_turns"][2]["response_text"]
        actual_sha = hashlib.sha256(actual_text.encode()).hexdigest()
        if (rows_a[key]["response_sha256"] != actual_sha
                or rows_b[key]["final_response_sha256"] != actual_sha):
            raise ValueError("Reviewer response hash does not bind exact packet product")
    criteria = tuple(rows_a["A01"]["criteria"])
    differences = {name: [key for key in sorted(rows_a)
                          if rows_a[key]["criteria"][name] != rows_b[key]["criteria"][name]]
                   for name in criteria}
    item_ratings = {key: {"first": rows_a[key]["rating"], "second": rows_b[key]["rating"],
                          "first_executable": rows_a[key]["candidate_executable_under_exposed_contract"],
                          "second_executable": rows_b[key]["executable_format_valid"]}
                    for key in sorted(rows_a)}
    return {"schema": "eal2-deployment-800-a3-author-review-comparison/1",
            "scope": "Author source fidelity only; actual recipient host-packet review follows after terminal",
            "first_review_sha256": sha(first), "second_review_sha256": sha(second),
            "author_packet_sha256": sha(packet),
            "independence": "Both files sealed before comparison; no peer aggregate was supplied during review",
            "rating_agreement": sum(x["first"] == x["second"] for x in item_ratings.values()),
            "both_unfaithful": sum(x["first"] == x["second"] == "unfaithful"
                                    for x in item_ratings.values()),
            "executable_agreement": sum(x["first_executable"] == x["second_executable"]
                                        for x in item_ratings.values()),
            "both_nonexecutable": sum(x["first_executable"] is False and x["second_executable"] is False
                                      for x in item_ratings.values()),
            "criterion_disagreements": differences,
            "ratings_by_sample": item_ratings,
            "interpretation": "Shared invalidity of all 32 final source contracts is an exploratory synthetic-model finding. Criterion disagreements in readable intent remain unresolved and do not change executable-source fidelity. AI review is not human adjudication."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("packet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args.first, args.second, args.packet),
                                      indent=2, sort_keys=True) + "\n")
    print(sha(args.output))


if __name__ == "__main__":
    main()
