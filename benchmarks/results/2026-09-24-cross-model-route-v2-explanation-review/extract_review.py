#!/usr/bin/env python3
"""Freeze an all-case, model-blind route-v2 explanation review packet.

Run only after both pinned ledgers report complete. Does not alter campaign files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
RUNS = (
    (
        "pilot",
        "paid-route-v2-pilot-final",
        "78e859ece4e05dcffcc0594d12f39b08356087a3fa18e55cadf4463951db468d",
        "paid-pilot-alias-v2",
        "3d6a33d88720772f63255a1fac1210c05717b08fe4b49d7900a176920939529d",
        36,
    ),
    (
        "cohort",
        "paid-route-v2-cohort-final",
        "0aed399243f68d420eaa07ebcd063909e7d4899bdaf91ccfabb9ed2102de2640",
        "paid-cohort-alias-v2",
        "b8f9cf8fa03ac03c446c94d4e32287edbc0f45fcf4360c00195046375b8e13ef",
        27,
    ),
)
PREFIX = "Host assessment result (the status remains authoritative):\n"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse_raw_prompt(case: dict) -> tuple[str, str]:
    user = next(m["content"] for m in case["messages"] if m["role"] == "user")
    task = user.split("Task: ", 1)[1].split("\nClaim ID: ", 1)[0]
    source = user.split("Argument source:\n", 1)[1].split("\nAcquired observations:\n", 1)[0]
    return task, source


def semantic_records(snapshot: dict) -> list:
    return sorted(
        (
            x["evidence_id"],
            x["imported_envelope"]["context"],
            x["imported_envelope"]["observed_at"],
            x["imported_envelope"]["value"],
        )
        for x in snapshot["raw_records"]
    )


def delivered_packet(attempt: dict) -> dict | None:
    """Return exactly the host JSON delivered in the second recipient call."""
    for call in attempt.get("calls", [])[1:]:
        for message in call.get("messages", []):
            if message["role"] != "user" or not message["content"].startswith(PREFIX):
                continue
            text = message["content"][len(PREFIX):]
            packet, _ = json.JSONDecoder().raw_decode(text)
            if not isinstance(packet, dict):
                raise ValueError("Delivered host packet is not an object")
            return packet
    return None


def load_checked_run(spec: tuple, require_terminal: bool) -> tuple[dict, dict, dict, dict]:
    name, route_dir, route_sha, original_dir, original_sha, n = spec
    route = read_json(BASE / route_dir / "freeze.json")
    original = read_json(BASE / original_dir / "freeze.json")
    ledger = read_json(BASE / route_dir / "ledger.json")
    assert route["freeze_sha256"] == route_sha and original["freeze_sha256"] == original_sha, name
    assert route["routing_revision"] == "skill-route-second-turn/2", name
    assert len(route["cases"]) == n and len(original["cases"]) >= n, name
    assert ledger["freeze_sha256"] == route_sha, name
    assert set(route["snapshots"]) == set(original["snapshots"]), name
    for key, snap in route["snapshots"].items():
        src = original["snapshots"][key]
        assert (snap["expected"], snap["revision"], snap["collection"]["source_digest"]) == (
            src["expected"], src["revision"], src["collection"]["source_digest"]
        ), (name, key)
        assert semantic_records(snap) == semantic_records(src), (name, key)
    if require_terminal:
        assert ledger["status"] == "complete", (name, ledger["status"])
        assert len(ledger["attempts"]) == n, (name, len(ledger["attempts"]), n)
        assert sorted(a["index"] for a in ledger["attempts"]) == list(range(n)), name
    return route, original, ledger, {x["index"]: x for x in ledger["attempts"]}


def build() -> tuple[dict, dict]:
    dossiers: dict[str, dict] = {}
    items: list[dict] = []
    linkage: list[dict] = []
    for spec in RUNS:
        name, _, route_sha, _, original_sha, n = spec
        route, original, _, attempts = load_checked_run(spec, require_terminal=True)
        raw_by_key: dict[str, list[dict]] = {}
        for c in original["cases"]:
            if c["arm"] == "raw":
                raw_by_key.setdefault(c["root_id"] + "/" + c["state_id"], []).append(c)
        assert set(raw_by_key) == set(original["snapshots"]), name
        models = {x["id"]: x["model_class"] for x in route["plan"]["conditions"]}
        for c in route["cases"]:
            a = attempts[c["index"]]
            assert a["case_id"] == c["case_id"] and a["prompt_sha256"] == c["prompt_sha256"], (name, c["index"])
            assert c["arm"] == "skill_route", (name, c["index"])
            key = c["root_id"] + "/" + c["state_id"]
            raws = raw_by_key[key]
            task, source = parse_raw_prompt(raws[0])
            assert all(parse_raw_prompt(x) == (task, source) for x in raws), (name, key)
            snap = original["snapshots"][key]
            dossier_id = hashlib.sha256(("route-v2-dossier/" + route_sha + "/" + key).encode()).hexdigest()[:24]
            if dossier_id not in dossiers:
                dossiers[dossier_id] = {
                    "dossier_id": dossier_id,
                    "claim": c["claim"],
                    "task": task,
                    "argument_source": source,
                    "acquired_observations": snap["raw_records"],
                    "author_supplied_oracle_status": snap["expected"],
                    "scope": snap["eal"]["scope"],
                    "reference_limit": "Agent-authored synthetic oracle and observations; no independent human adjudication",
                }
            assert dossiers[dossier_id]["claim"] == c["claim"] and dossiers[dossier_id]["author_supplied_oracle_status"] == c["expected"]
            item_id = hashlib.sha256(("route-v2-item/" + route_sha + "/" + c["case_id"]).encode()).hexdigest()[:24]
            packet = delivered_packet(a)
            if packet is not None:
                assert packet["claim"] == c["claim"] and packet["status"] == c["host_status"], (name, c["index"])
                assert packet["scope"] == route["snapshots"][key]["eal"]["scope"], (name, c["index"])
            recipient = a.get("recipient") or {}
            response = a.get("response") or {}
            items.append({
                "item_id": item_id,
                "dossier_id": dossier_id,
                "host_packet_delivered": packet,
                "raw_final_recipient_text": response.get("text"),
                "recipient_json_status": recipient.get("status"),
                "recipient_explanation": recipient.get("explanation"),
                "recipient_format_valid": recipient.get("format_valid", False),
                "final_call_failure": a.get("status") != "completed",
            })
            linkage.append({
                "item_id": item_id,
                "dossier_id": dossier_id,
                "run": name,
                "case_id": c["case_id"],
                "index": c["index"],
                "root_id": c["root_id"],
                "state_id": c["state_id"],
                "condition_id": c["condition_id"],
                "model_class": models[c["condition_id"]],
                "recipient_model": response.get("model"),
                "accepted_status": a.get("accepted_status"),
                "route_requested": a.get("route_requested"),
                "routing_status": a.get("route_reason"),
            })
    assert len(items) == len(linkage) == 63 and len({x["item_id"] for x in items}) == 63
    assert len(dossiers) == 21, len(dossiers)
    # Fixed hash shuffle, independent of recipient response contents and labels.
    items.sort(key=lambda x: hashlib.sha256(("route-v2-review-order/" + x["item_id"]).encode()).hexdigest())
    packet = {
        "schema": "route_v2_explanation_review_items_v1",
        "sampling_rule": "All 36+27 frozen route-v2 cases; order by SHA-256 of route-v2-review-order/<opaque item ID>.",
        "reference_limit": "Developmental synthetic authored cases; no human adjudication or population inference.",
        "sources": {spec[0]: {"route_freeze_sha256": spec[2], "original_freeze_sha256": spec[4]} for spec in RUNS},
        "dossiers": sorted(dossiers.values(), key=lambda x: x["dossier_id"]),
        "items": items,
    }
    link = {"schema": "route_v2_review_hidden_linkage_v1", "items": linkage}
    return packet, link


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--preflight", action="store_true", help="Check pins and semantic parity; make no reviewer files")
    args = p.parse_args()
    if args.preflight:
        for spec in RUNS:
            _, _, ledger, _ = load_checked_run(spec, require_terminal=False)
            print(f"{spec[0]}: {ledger['status']}, {len(ledger['attempts'])}/{spec[5]} attempts")
        return
    packet, linkage = build()
    review = OUT / "reviewer_items.json"
    hidden = OUT / "arm_model_linkage.json"
    assert not review.exists() and not hidden.exists(), "Packet already frozen; do not overwrite"
    review.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n")
    hidden.write_text(json.dumps(linkage, indent=2, ensure_ascii=False) + "\n")
    (OUT / "packet_manifest.json").write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer_items_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "hidden_linkage_sha256": hashlib.sha256(hidden.read_bytes()).hexdigest(),
        "item_count": len(packet["items"]),
        "dossier_count": len(packet["dossiers"]),
        "reviewer_packet_semantic_digest": digest(packet),
    }, indent=2) + "\n")
    print(f"Frozen reviewer packet: {len(packet['items'])} items, {len(packet['dossiers'])} dossiers")


if __name__ == "__main__":
    main()
