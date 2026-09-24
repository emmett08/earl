#!/usr/bin/env python3
"""Freeze and administer a blinded, staged engineering-decision study.

This creates no participant observations. Administrators must obtain case
review, applicable ethics approval, consent and participants separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys

ARMS = ("conventional_ai", "prose_challenge", "eal_structure", "eal_agent",
        "evidence_only", "no_assistance")
WORDINGS = ("fluent", "plain")
SCHEMA = "eal2-human-decision-manifest/1"
FREEZE_SCHEMA = "eal2-human-decision-allocation/1"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def read(path: Path) -> dict:
    def unique_pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def write_new(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def validate_manifest(data: dict) -> None:
    if data.get("schema") != SCHEMA or not isinstance(data.get("cases"), list) or len(data["cases"]) < 4:
        raise ValueError("At least four independently reviewed cases are required")
    ids, families = set(), set()
    for c in data["cases"]:
        required = {"id", "family", "domain", "question", "evidence", "options",
                    "reference", "review", "assistance"}
        if not isinstance(c, dict) or set(c) != required:
            raise ValueError("Case fields differ from the frozen contract")
        if (not all(isinstance(c[k], str) and c[k].strip()
                    for k in ("id", "family", "domain", "question"))
                or c["id"] in ids or c["family"] in families):
            raise ValueError("Case and family IDs must be unique nonempty strings")
        ids.add(c["id"])
        families.add(c["family"])
        for name in ("evidence", "options"):
            items = c[name]
            if (not isinstance(items, list) or len(items) < 2
                    or any(not isinstance(item, dict) or set(item) != {"id", "text"}
                           or any(not isinstance(v, str) or not v.strip() for v in item.values())
                           for item in items)
                    or len({item["id"] for item in items}) != len(items)):
                raise ValueError("Evidence and options need distinct IDs and text")
        options = {o["id"] for o in c["options"]}
        ref = c["reference"]
        if (not isinstance(ref, dict) or set(ref) != {"correct_option_id", "rationale"}
                or ref["correct_option_id"] not in options
                or not isinstance(ref["rationale"], str) or not ref["rationale"].strip()):
            raise ValueError("Reference decision must select a documented option")
        review = c["review"]
        if (not isinstance(review, dict) or set(review) != {"initial_reviewers", "adjudicator", "approved"}
                or not isinstance(review["initial_reviewers"], list)
                or len(review["initial_reviewers"]) != 2
                or len(set(review["initial_reviewers"])) != 2
                or any(not isinstance(v, str) or not v for v in review["initial_reviewers"])
                or not isinstance(review["adjudicator"], str) or not review["adjudicator"]
                or review["adjudicator"] in review["initial_reviewers"]
                or review["approved"] is not True):
            raise ValueError("Two distinct initial reviewers and an adjudicator must approve")
        aid = c["assistance"]
        if not isinstance(aid, dict) or set(aid) != set(ARMS):
            raise ValueError("All four assistance conditions must be specified")
        for arm, variants in aid.items():
            if not isinstance(variants, dict) or set(variants) != set(WORDINGS):
                raise ValueError("Both wording conditions are required for each arm")
            for value in variants.values():
                if (not isinstance(value, dict) or set(value) != {"text", "recommendation_id"}
                        or not isinstance(value["text"], str)
                        or value["recommendation_id"] not in options | {None}):
                    raise ValueError("Assistance text and recommendation have invalid shape")
                if arm == "no_assistance" and (value["text"] or value["recommendation_id"] is not None):
                    raise ValueError("No-assistance arm must expose no recommendation")
                if arm == "evidence_only" and value["recommendation_id"] is not None:
                    raise ValueError("Evidence-only arm must not recommend an option")
                if arm != "no_assistance" and not value["text"].strip():
                    raise ValueError("Assistance text is missing")
            if variants["fluent"]["recommendation_id"] != variants["plain"]["recommendation_id"]:
                raise ValueError("Wording swap changed the recommended decision")
        if aid["conventional_ai"]["fluent"]["recommendation_id"] is None:
            raise ValueError("Conventional AI advice requires an explicit recommendation")
    correctness = [c["assistance"]["conventional_ai"]["fluent"]["recommendation_id"]
                   == c["reference"]["correct_option_id"] for c in data["cases"]]
    if not (any(correctness) and not all(correctness)):
        raise ValueError("Include both correct and incorrect conventional AI advice")


def allocate(manifest: dict, participants: int, seed: int) -> dict:
    validate_manifest(manifest)
    if not len(ARMS) * len(WORDINGS) <= participants <= 10000 or type(seed) is not int:
        raise ValueError("Invalid participant count or seed")
    rng = random.Random(seed)
    cells = [(arm, wording) for arm in ARMS for wording in WORDINGS]
    assignments = cells * (participants // len(cells)) + cells[:participants % len(cells)]
    rng.shuffle(assignments)
    case_ids = [c["id"] for c in manifest["cases"]]
    allocation = []
    for i, (arm, wording) in enumerate(assignments, 1):
        order = list(case_ids)
        rng.shuffle(order)
        allocation.append({"participant_id": f"P{i:05d}", "arm": arm,
                           "wording": wording, "case_order": order})
    frozen = {"schema": FREEZE_SCHEMA, "manifest_sha256": digest(manifest),
              "seed": seed, "participants": allocation,
              "status": "allocation_only_no_participant_observations"}
    frozen["freeze_sha256"] = digest(frozen)
    return frozen


def validate_freeze(frozen: dict, manifest: dict) -> None:
    validate_manifest(manifest)
    if (frozen.get("schema") != FREEZE_SCHEMA or
            frozen.get("manifest_sha256") != digest(manifest) or
            frozen.get("freeze_sha256") != digest({k: v for k, v in frozen.items()
                                                     if k != "freeze_sha256"})):
        raise ValueError("Trial allocation or case manifest changed")
    expected = allocate(manifest, len(frozen["participants"]), frozen["seed"])
    if frozen != expected:
        raise ValueError("Trial allocation differs from deterministic regeneration")


def _assignment(frozen: dict, manifest: dict, participant_id: str, case_id: str) -> tuple[dict, dict]:
    validate_freeze(frozen, manifest)
    p = next((p for p in frozen["participants"] if p["participant_id"] == participant_id), None)
    c = next((c for c in manifest["cases"] if c["id"] == case_id), None)
    if not p or not c or case_id not in p["case_order"]:
        raise ValueError("Participant/case assignment is absent")
    return p, c


def pre_packet(frozen: dict, manifest: dict, participant_id: str, case_id: str) -> dict:
    p, c = _assignment(frozen, manifest, participant_id, case_id)
    packet = {"phase": "pre", "freeze_sha256": frozen["freeze_sha256"],
              "participant_id": participant_id, "case_id": case_id,
              "task_order": p["case_order"].index(case_id),
              "question": c["question"], "evidence": c["evidence"], "options": c["options"]}
    packet["packet_sha256"] = digest(packet)
    return packet


def validate_answer(answer: dict, packet: dict, options: list[dict]) -> None:
    expected = {"phase", "freeze_sha256", "participant_id", "case_id",
                "packet_sha256", "answer_id", "confidence", "reason", "elapsed_seconds"}
    if (not isinstance(answer, dict) or set(answer) != expected
            or any(answer.get(k) != packet.get(k) for k in
                   ("phase", "freeze_sha256", "participant_id", "case_id", "packet_sha256"))
            or answer["answer_id"] not in {o["id"] for o in options}
            or type(answer["confidence"]) is not int or not 0 <= answer["confidence"] <= 100
            or not isinstance(answer["reason"], str) or not answer["reason"].strip()
            or type(answer["elapsed_seconds"]) not in (int, float)
            or not 0 <= answer["elapsed_seconds"] <= 7200):
        raise ValueError("Response is missing, invalid or bound to a different packet")


def post_packet(frozen: dict, manifest: dict, pre_response: dict) -> dict:
    pid, cid = pre_response.get("participant_id"), pre_response.get("case_id")
    p, c = _assignment(frozen, manifest, pid, cid)
    pre = pre_packet(frozen, manifest, pid, cid)
    validate_answer(pre_response, pre, c["options"])
    packet = {"phase": "post", "freeze_sha256": frozen["freeze_sha256"],
              "participant_id": pid, "case_id": cid,
              "pre_packet_sha256": pre["packet_sha256"],
              "assistance": c["assistance"][p["arm"]][p["wording"]],
              "question": c["question"], "evidence": c["evidence"], "options": c["options"]}
    packet["packet_sha256"] = digest(packet)
    return packet


def score(frozen: dict, manifest: dict, records: list[dict]) -> dict:
    validate_freeze(frozen, manifest)
    indexed, rows = {}, []
    for item in records:
        if not isinstance(item, dict) or set(item) != {"pre", "post"}:
            raise ValueError("Expected paired pre/post response")
        pre = item["pre"]
        pid, cid = pre.get("participant_id"), pre.get("case_id")
        p, c = _assignment(frozen, manifest, pid, cid)
        key = (pid, cid)
        if key in indexed:
            raise ValueError("Duplicate participant/case record")
        indexed[key] = True
        before = pre_packet(frozen, manifest, pid, cid)
        validate_answer(pre, before, c["options"])
        after = post_packet(frozen, manifest, pre)
        validate_answer(item["post"], after, c["options"])
        correct = c["reference"]["correct_option_id"]
        advice = c["assistance"][p["arm"]][p["wording"]]["recommendation_id"]
        rows.append({"participant_id": pid, "case_id": cid, "family": c["family"],
                     "arm": p["arm"], "wording": p["wording"],
                     "pre_correct": pre["answer_id"] == correct,
                     "post_correct": item["post"]["answer_id"] == correct,
                     "wrong_to_right": pre["answer_id"] != correct and item["post"]["answer_id"] == correct,
                     "right_to_wrong": pre["answer_id"] == correct and item["post"]["answer_id"] != correct,
                     "advice_correct": advice == correct if advice is not None else None,
                     "accepted_wrong_advice": advice is not None and advice != correct
                                              and item["post"]["answer_id"] == advice,
                     "switched_to_wrong_advice": advice is not None and advice != correct
                         and pre["answer_id"] != advice and item["post"]["answer_id"] == advice,
                     "pre_seconds": pre["elapsed_seconds"],
                     "post_seconds": item["post"]["elapsed_seconds"]})
    expected = len(frozen["participants"]) * len(manifest["cases"])
    complete = len(rows) == expected
    summary = {}
    for arm in ARMS:
        for wording in WORDINGS:
            subset = [r for r in rows if r["arm"] == arm and r["wording"] == wording]
            summary[arm + "/" + wording] = {
                        "participant_count": len({r["participant_id"] for r in subset}),
                        "task_count": len(subset),
                        "pre_correct": sum(r["pre_correct"] for r in subset),
                        "post_correct": sum(r["post_correct"] for r in subset),
                        "wrong_to_right": sum(r["wrong_to_right"] for r in subset),
                        "right_to_wrong": sum(r["right_to_wrong"] for r in subset),
                        "accepted_wrong_advice": sum(r["accepted_wrong_advice"] for r in subset),
                        "switched_to_wrong_advice": sum(r["switched_to_wrong_advice"] for r in subset),
                        "mean_total_seconds": (sum(r["pre_seconds"] + r["post_seconds"]
                                                   for r in subset) / len(subset) if subset else None)}
    # No confidence interval or winner is inferred from an unreviewed fixture
    # or an incomplete/underpowered participant study.
    return {"schema": "eal2-human-decision-analysis/1",
            "state": "complete" if complete else "partial_or_unrun",
            "assigned_tasks": expected, "recorded_tasks": len(rows),
            "descriptive_only": True, "summary": summary, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("manifest", type=Path)
    f.add_argument("schedule", type=Path)
    f.add_argument("--participants", type=int, required=True)
    f.add_argument("--seed", type=int, default=240925)
    b = sub.add_parser("pre-packet")
    b.add_argument("manifest", type=Path); b.add_argument("schedule", type=Path)
    b.add_argument("participant_id"); b.add_argument("case_id")
    b.add_argument("output", type=Path)
    a = sub.add_parser("post-packet")
    a.add_argument("manifest", type=Path); a.add_argument("schedule", type=Path)
    a.add_argument("pre_response", type=Path); a.add_argument("output", type=Path)
    s = sub.add_parser("score")
    s.add_argument("manifest", type=Path); s.add_argument("schedule", type=Path)
    s.add_argument("responses", type=Path); s.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = read(args.manifest)
        if args.command == "freeze":
            value = allocate(manifest, args.participants, args.seed)
            write_new(args.schedule, value)
            print(json.dumps({"freeze_sha256": value["freeze_sha256"],
                              "participants": args.participants}))
        else:
            frozen = read(args.schedule)
            if args.command == "pre-packet":
                value = pre_packet(frozen, manifest, args.participant_id, args.case_id)
            elif args.command == "post-packet":
                value = post_packet(frozen, manifest, read(args.pre_response))
            else:
                records = [json.loads(line) for line in args.responses.read_text(encoding="utf-8").splitlines()]
                value = score(frozen, manifest, records)
            write_new(args.output, value)
            print(json.dumps({"status": value.get("state", "packet_created"),
                              "sha256": digest(value)}))
        return 0
    except Exception as exc:
        print("Trial stopped: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
