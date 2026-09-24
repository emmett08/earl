#!/usr/bin/env python3
"""Extract a blinded 105-response developmental review sample without scoring it.

Input ledgers remain untouched. The reviewer file hides condition and model
metadata; raw prose may still reveal that a host or checker was used. Keep the
separate linkage key away from reviewers until both reviews are locked.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from analyse_cross_model_campaign import _audit
from run_cross_model_campaign import digest, read_json, write_json


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_and_evidence(raw_case: dict) -> tuple[str, str, list[dict]]:
    content = raw_case["messages"][1]["content"]
    task, remainder = content.split("\nClaim ID: ", 1)
    _, remainder = remainder.split("\nArgument source:\n", 1)
    source, observations = remainder.split("\nAcquired observations:\n", 1)
    return task.removeprefix("Task: "), source, json.loads(observations)


def _load(run_directory: Path) -> tuple[dict, dict, list[dict]]:
    frozen = read_json(run_directory / "freeze.json")
    ledger = read_json(run_directory / "ledger.json")
    rows = _audit(frozen, ledger)
    if (ledger["status"] != "complete" or len(rows) != len(frozen["cases"])
            or any(row["attempt"]["status"] != "completed" for row in rows)
            or {case["arm"] for case in frozen["cases"]} !=
            {"raw", "skill", "skill_route", "eal_host", "equal_checker"}):
        raise ValueError("Review extraction requires a complete five-arm developmental run")
    return frozen, ledger, rows


def extract(pilot: Path, cohort: Path) -> tuple[dict, dict]:
    runs = [("pilot", *_load(pilot)), ("cohort", *_load(cohort))]
    if [len(frozen["cases"]) for _, frozen, _, _ in runs] != [180, 135]:
        raise ValueError("Expected the exact original 180- and 135-case developmental schedules")
    by_root = {}
    case_lookup = {}
    for run_name, frozen, ledger, rows in runs:
        for row in rows:
            root = (run_name, row["root_id"])
            by_root.setdefault(root, {"freeze_sha256": frozen["freeze_sha256"], "states": {}})
            by_root[root]["states"][row["state_id"]] = row["expected"]
            case_lookup[(run_name, row["root_id"], row["state_id"], row["condition_id"])] = row
    contested_roots = sorted(root for root, data in by_root.items()
                             if "contested" in data["states"].values())
    if len(by_root) != 7 or len(contested_roots) != 2:
        raise ValueError("Review strata differ from the documented seven-root design")
    selected: dict[tuple[str, str], str] = {}
    for root in contested_roots:
        states = [state for state, status in by_root[root]["states"].items() if status == "contested"]
        selected[root] = min(states, key=lambda state: _hash("explanation-v1/"
            + by_root[root]["freeze_sha256"] + "/" + root[1] + "/" + state))
    unsupported_roots = [root for root, data in by_root.items()
                         if root not in selected and "unsupported" in data["states"].values()]
    unsupported_roots.sort(key=lambda root: _hash("explanation-v1/"
                           + by_root[root]["freeze_sha256"] + "/" + root[1]))
    for root in unsupported_roots[:2]:
        states = [state for state, status in by_root[root]["states"].items() if status == "unsupported"]
        selected[root] = min(states, key=lambda state: _hash("explanation-v1/"
            + by_root[root]["freeze_sha256"] + "/" + root[1] + "/" + state))
    for root, data in by_root.items():
        if root in selected:
            continue
        states = [state for state, status in data["states"].items() if status == "supported"]
        selected[root] = min(states, key=lambda state: _hash("explanation-v1/"
            + data["freeze_sha256"] + "/" + root[1] + "/" + state))
    if Counter(by_root[root]["states"][state] for root, state in selected.items()) != {
            "supported": 3, "unsupported": 2, "contested": 2}:
        raise ValueError("Review sample lost the declared oracle balance")

    dossiers = []
    items = []
    linkage = []
    for run_name, frozen, ledger, rows in runs:
        conditions = {condition["id"]: condition for condition in frozen["plan"]["conditions"]}
        for (selected_run, root), state in sorted(selected.items()):
            if selected_run != run_name:
                continue
            cells = [row for row in rows if row["root_id"] == root and row["state_id"] == state]
            if len(cells) != 15 or {row["condition_id"] for row in cells} != set(conditions):
                raise ValueError("Selected state is missing a condition cell")
            raw = next(row for row in cells if row["arm"] == "raw")
            brief, source, observations = _source_and_evidence(raw)
            key = root + "/" + state
            dossier_id = _hash("review-dossier-v1/" + frozen["freeze_sha256"] + "/" + key)[:20]
            dossiers.append({
                "dossier_id": dossier_id,
                "task": brief,
                "claim": raw["claim"],
                "scope": frozen["snapshots"][key]["eal"]["scope"],
                "author_supplied_oracle_status": raw["expected"],
                "argument_source": source,
                "acquired_observations": observations,
                "reference_limit": "Synthetic authored oracle and observations; not independently human reviewed",
            })
            for row in cells:
                case_id = row["case_id"]
                item_id = _hash("review-item-v1/" + frozen["freeze_sha256"] + "/" + case_id)[:24]
                attempt = row["attempt"]
                items.append({
                    "item_id": item_id,
                    "dossier_id": dossier_id,
                    "raw_recipient_text": attempt["response"]["text"],
                    "recipient_json_status": attempt["recipient"]["status"],
                    "recipient_explanation": attempt["recipient"]["explanation"],
                    "recipient_format_valid": attempt["recipient"]["format_valid"],
                    "parse_error": attempt["recipient"].get("error"),
                })
                linkage.append({
                    "item_id": item_id, "dossier_id": dossier_id,
                    "run": run_name, "case_id": case_id, "root_id": root, "state_id": state,
                    "condition_id": row["condition_id"], "arm": row["arm"],
                    "model_class": conditions[row["condition_id"]]["model_class"],
                    "configured_model": frozen["provider_identities"][row["condition_id"]]["model"],
                    "accepted_status": attempt["accepted_status"],
                    "oracle_status": row["expected"],
                })
    items.sort(key=lambda item: item["item_id"])
    linkage.sort(key=lambda item: item["item_id"])
    if len(dossiers) != 7 or len(items) != 105 or len({x["item_id"] for x in items}) != 105:
        raise ValueError("Sample is not the intended seven-block, 105-response design")
    reviewer = {
        "schema": "eal2-developmental-explanation-review-sample/1",
        "review_status": "unreviewed",
        "sampling_rule": "docs/cross-model-explanation-review-proposal-20260924.md",
        "limits": "Arm and model fields hidden; prose may reveal route. The reference oracle requires independent human check.",
        "sources": [{"run": name, "freeze_sha256": frozen["freeze_sha256"],
                     "ledger_sha256": digest(ledger)} for name, frozen, ledger, _ in runs],
        "dossiers": sorted(dossiers, key=lambda item: item["dossier_id"]),
        "items": items,
    }
    key = {"schema": "eal2-developmental-explanation-review-linkage/1",
           "reviewer_sample_sha256": digest(reviewer), "items": linkage}
    return reviewer, key


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pilot_directory", type=Path)
    parser.add_argument("cohort_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    reviewer, key = extract(args.pilot_directory, args.cohort_directory)
    args.output_directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_json(args.output_directory / "reviewer_items.json", reviewer)
    write_json(args.output_directory / "arm_model_linkage.json", key)
    print(json.dumps({"sample_size": len(reviewer["items"]), "root_state_dossiers": len(reviewer["dossiers"]),
                      "reviewer_sha256": digest(reviewer), "review_status": "unreviewed"}, sort_keys=True))
