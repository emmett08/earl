#!/usr/bin/env python3
"""Audit and unblind a small exploratory, non-human explanation review.

Run only after both reviewers have finished their de-identified files. A
category-only disagreement is retained explicitly; binary fidelity is not
extrapolated to the unsampled campaign or used to calculate total cost.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


DISPUTED = "93ada1ab2f9ffdac0f8b0d52"
CATEGORIES = {"faithful", "incomplete_but_nonmisleading", "materially_false", "malformed_or_absent"}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarise(directory: Path) -> dict:
    paths = {key: directory / filename for key, filename in {
        "sample": "reviewer_items.json", "linkage": "arm_model_linkage.json",
        "reviewer_a": "reviewer_a.json", "reviewer_b": "reviewer_b.json",
    }.items()}
    sample, linkage, a, b = (read(paths[key]) for key in paths)
    items = {item["item_id"]: item for item in sample["items"]}
    links = {item["item_id"]: item for item in linkage["items"]}
    left = {item["item_id"]: item for item in a["entries"]}
    right = {item["item_id"]: item for item in b["items"]}
    if (len(items), len(links), len(left), len(right)) != (105, 105, 105, 105) or not (
            set(items) == set(links) == set(left) == set(right)):
        raise ValueError("The preselected 105 items need both complete reviews and exact linkage")
    canonical_sample = json.dumps(sample, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False).encode("utf-8")
    if (len(sample["dossiers"]) != 7 or linkage.get("reviewer_sample_sha256") !=
            hashlib.sha256(canonical_sample).hexdigest()):
        raise ValueError("The linkage does not address this seven-dossier reviewer sample")
    if any(item["category"] not in CATEGORIES or item["faithful"] != (item["category"] == "faithful")
           for item in [*left.values(), *right.values()]):
        raise ValueError("Reviewer category and binary judgement disagree")
    binary_differences = [key for key in items if left[key]["faithful"] != right[key]["faithful"]]
    category_differences = [key for key in items if left[key]["category"] != right[key]["category"]]
    if binary_differences or category_differences != [DISPUTED]:
        raise ValueError("Unresolved review disagreement; adjudicate before summarising")
    categories = Counter()
    by_arm = defaultdict(lambda: [0, 0])
    by_condition = defaultdict(lambda: [0, 0])
    reconciled = []
    for key in items:
        category = ("incomplete_but_nonmisleading" if key == DISPUTED else left[key]["category"])
        faithful = category == "faithful"
        categories[category] += 1
        arm, condition = links[key]["arm"], links[key]["condition_id"]
        by_arm[arm][0] += int(faithful)
        by_arm[arm][1] += 1
        by_condition[condition][0] += int(faithful)
        by_condition[condition][1] += 1
        reconciled.append({"item_id": key, "adjudicated_category": category, "faithful": faithful,
                           "reviewer_a_category": left[key]["category"],
                           "reviewer_b_category": right[key]["category"]})
    return {
        "schema": "eal2-cross-model-exploratory-agent-review/1",
        "input_sha256": {key: sha(path) for key, path in paths.items()},
        "sampled_items": len(items), "dossiers": len(sample["dossiers"]),
        "reviewers": "two separate AI agents, blinded to arm/model linkage until both files were complete",
        "binary_agreement": 105, "category_agreement": 104,
        "category_disagreement": {"item_id": DISPUTED,
            "a": left[DISPUTED]["category"], "b": right[DISPUTED]["category"],
            "adjudicated": "incomplete_but_nonmisleading",
            "reason": "The answer omits the decisive basis; 'supplied excerpt' may refer to a compact recipient view absent from the reviewer dossier. Its factual falsity cannot be established from the blinded file."},
        "categories": dict(categories),
        "faithful_total": categories["faithful"],
        "by_arm": {key: {"faithful": value[0], "sampled": value[1]}
                   for key, value in sorted(by_arm.items())},
        "by_condition": {key: {"faithful": value[0], "sampled": value[1]}
                         for key, value in sorted(by_condition.items())},
        "reported_review_seconds": {
            "a": round(a["elapsed_minutes"] * 60, 3), "b": b["elapsed_seconds"]},
        "human_adjudication": "none",
        "full_campaign_fidelity": None,
        "all_in_cost_per_correct_accepted_decision": None,
        "limitations": [
            "Seven author-supplied synthetic dossiers and selected states; no independent human source oracle.",
            "Reviewer packet gave the full dossier but omitted each recipient's exact exposed prompt; a statement about a supplied excerpt cannot always be verified.",
            "Agent judgements are exploratory, not validated human fidelity labels; binary agreement includes 39 malformed or absent explanations.",
            "The 105 outputs are a balanced subset of 315 first-call cases and cannot establish full-campaign faithful acceptance or author/review cost.",
        ],
        "items": reconciled,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarise(args.directory)
    formatted = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(formatted, encoding="utf-8")
    else:
        print(formatted, end="")


if __name__ == "__main__":
    main()
