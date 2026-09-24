#!/usr/bin/env python3
"""Compare independently sealed post-call AI ratings without adjudicating them."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIRST = ROOT / "docs/reviews/deployment-800-a3-explanation-grammar-ai-review.json"
SECOND = ROOT / "docs/reviews/deployment-800-a3-explanation-second-ai-review.json"
PACKET = HERE / "postcall-review-rubric-a3.json"
CRITERIA = ("target_scope", "status", "decisive_evidence",
            "challenge_handling", "qualification", "recipient_format")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare() -> dict:
    first, second = (json.loads(p.read_text(encoding="utf-8"))
                     for p in (FIRST, SECOND))
    frame = json.loads((HERE / "predeclared-review-slots-a3.json").read_text())
    expected_ids = [f"E{i:02d}" for i in range(1, 49)]
    a = {v["sample_id"]: v for v in first["items"]}
    b = {v["sample_id"]: v for v in second["items"]}
    if (len(a) != 48 or len(b) != 48 or set(a) != set(expected_ids)
            or set(b) != set(expected_ids)
            or len(frame["explanations"]) != 48
            or first["material"]["rubric_sha256"] != sha(PACKET)
            or second["rubric_file_sha256"] != sha(PACKET)
            or first["material"]["explanation_packet_sha256"]
            != second["packet_file_sha256"]):
        raise ValueError("Review identity, sample frame, packet or rubric mismatch")
    disagreement = {c: [] for c in CRITERIA}
    rating_disagreement = []
    response_mismatch = []
    faithful = {"first": [], "second": []}
    by_id = {}
    for sample_id in expected_ids:
        one, two = a[sample_id], b[sample_id]
        if one["response_sha256"] != two["response_sha256"]:
            response_mismatch.append(sample_id)
        for criterion in CRITERIA:
            if (type(one["criteria"][criterion]) is not bool
                    or type(two["criteria"][criterion]) is not bool):
                raise ValueError(f"Nonboolean criterion {sample_id}/{criterion}")
            if one["criteria"][criterion] != two["criteria"][criterion]:
                disagreement[criterion].append(sample_id)
        if one["rating"] != two["rating"]:
            rating_disagreement.append(sample_id)
        for side, item in (("first", one), ("second", two)):
            if item["rating"] == "faithful":
                faithful[side].append(sample_id)
        by_id[sample_id] = {"first_rating": one["rating"],
                            "second_rating": two["rating"],
                            "first_criteria": one["criteria"],
                            "second_criteria": two["criteria"]}
    return {"schema": "eal2-deployment-800-a3-explanation-review-comparison/1",
            "review_scope": "48 predeclared exploratory explanations; independent unmasked AI ratings, no forced adjudication",
            "first_review_sha256": sha(FIRST), "second_review_sha256": sha(SECOND),
            "packet_sha256": first["material"]["explanation_packet_sha256"],
            "rubric_sha256": sha(PACKET),
            "rating_agreement": 48 - len(rating_disagreement),
            "rating_disagreement": rating_disagreement,
            "criterion_disagreements": disagreement,
            "response_hash_disagreement": response_mismatch,
            "faithful_ids": faithful,
            "by_id": by_id,
            "limitations": ["Both reviewers are AI agents and saw actual prompts that can reveal exposure",
                            "Predeclared 48-case sample is exploratory, not a population estimate for assigned explanations",
                            "All 32 authored sources violate the executable contract; host-unavailable recipient failures are upstream"]}


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, sort_keys=True))
