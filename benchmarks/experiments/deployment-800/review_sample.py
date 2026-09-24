#!/usr/bin/env python3
"""Extract the fixed exploratory 32-product and 48-explanation review frames.

This extractor is deliberately post-freeze code. Its selection rule lives in
postcall-review-protocol.json, recorded and hashed before A2 terminated. Never
replace a selected failed, missing or malformed call with a successful one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = ("initial", "adverse", "restored")
EXPOSURES = ("fixed_direct", "fixed_host_owned", "authored_recipient")
SEED = "240924801"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")


def exposure(case: dict) -> str | None:
    if case["stage"] == "recipient":
        return "authored_recipient"
    if case["stage"] == "fixed" and case["delivery"] in ("direct", "host_owned"):
        return "fixed_" + case["delivery"]
    return None


def records(root: dict, state: dict) -> dict:
    return {name: load(HERE / path) for name, path in state["checker_evidence"].items()}


def reference(root: dict, state: dict) -> dict:
    return {"root_id": root["id"], "state_id": state["id"],
            "brief": root["brief"], "claim": root["claim"],
            "scope": root["context"], "now": root["now"],
            "expected_status": state["expected"],
            "synthetic_acquisition_records": records(root, state),
            "reviewed_reference_eal_source": (HERE / root["source"]).read_text(encoding="utf-8"),
            "reviewed_reference_generic_graph": load(HERE / root["graph"])}


def run(freeze_dir: Path, output: Path) -> dict:
    protocol_path = HERE / "postcall-review-protocol.json"
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    frozen = load(freeze_dir / "freeze.json")
    ledger_path = freeze_dir / "ledger.json"
    ledger_bytes = ledger_path.read_bytes()
    ledger = json.loads(ledger_bytes)
    manifest = load(HERE / "manifest.json")
    if (protocol["freeze_sha256"] != frozen["freeze_sha256"]
            or ledger["freeze_sha256"] != frozen["freeze_sha256"]
            or ledger["status"] not in ("complete", "complete_with_recorded_failures")
            or len(frozen["cases"]) != 800):
        raise ValueError("A complete, matching A2 ledger is required")
    roots = {root["id"]: root for root in manifest["roots"]}
    cases = frozen["cases"]
    attempts = ledger["attempts"]

    authored = sorted((case for case in cases
                       if case["stage"] == "author" and case["turn"] == 2),
                      key=lambda c: c["index"])
    if len(authored) != 32:
        raise ValueError("Expected exactly 32 assigned final author products")
    candidates = []
    author_link = []
    for i, final in enumerate(authored):
        group = final["author_group"]
        turns = sorted((case for case in cases if case["stage"] == "author"
                        and case["author_group"] == group), key=lambda c: c["turn"])
        if [c["turn"] for c in turns] != [0, 1, 2]:
            raise ValueError("Broken linked author group")
        root = roots[final["root_id"]]
        recipient_packets = {}
        for state in STATES:
            recipients = [case for case in cases if case["stage"] == "recipient"
                          and case["author_group"] == group and case["state_id"] == state]
            packets = [attempts.get(c["case_id"], {}).get("host_packet") for c in recipients]
            distinct = {json.dumps(p, sort_keys=True) for p in packets}
            if len(distinct) > 1:
                raise ValueError("A group/state received inconsistent host packets")
            recipient_packets[state] = packets[0] if packets else None
        sample_id = f"A{i + 1:02d}"
        candidates.append({
            "sample_id": sample_id,
            "format_visible_in_artifact": final["format"],
            "reference_by_state": [reference(root, s) for s in root["states"]],
            "three_linked_turns": [{"turn": c["turn"], "actual_messages":
                                    attempts.get(c["case_id"], {}).get("messages"),
                                    "response_text": attempts.get(c["case_id"], {})
                                    .get("response", {}).get("text") if isinstance(
                                        attempts.get(c["case_id"], {}).get("response"), dict)
                                    else None,
                                    "attempt_status": attempts.get(c["case_id"], {}).get("status", "missing"),
                                    "error": attempts.get(c["case_id"], {}).get("error")}
                                   for c in turns],
            "actual_recipient_host_packet_by_state": recipient_packets,
            "review_questions": [
                "Does the authored final source represent the specified scope, positive routes, alert target and matched resolution?",
                "For each state, does its actual recipient packet warrant the expected bounded status?",
                "Does it preserve separate acquisitions and their temporal/identity qualifications?",
                "Which task claims or necessary qualifications are missing, changed or invented?",
            ],
        })
        author_link.append({"sample_id": sample_id, "author_group": group,
                            "case_ids": [c["case_id"] for c in turns],
                            "author_model": final["model"], "format": final["format"]})

    selected = []
    for b, root_id in enumerate(sorted(roots)):
        for state_index, state_id in enumerate(STATES):
            block = 3 * b + state_index
            for arm_index, arm in enumerate(EXPOSURES):
                if arm_index == block % 3:
                    continue
                eligible = [c for c in cases if c["root_id"] == root_id
                            and c["state_id"] == state_id and exposure(c) == arm]
                if not eligible:
                    raise ValueError(f"No assigned cases in {root_id}/{state_id}/{arm}")
                chosen = min(eligible, key=lambda c: (sha((SEED + "|" + c["case_id"]).encode()),
                                                      c["case_id"]))
                selected.append((chosen, arm))
    if len(selected) != 48 or {e: sum(arm == e for _, arm in selected)
                               for e in EXPOSURES} != dict.fromkeys(EXPOSURES, 16):
        raise AssertionError("Fixed stratified sample changed")
    explanations = []
    explanation_link = []
    for i, (case, arm) in enumerate(selected):
        row = attempts.get(case["case_id"])
        root = roots[case["root_id"]]
        state = next(s for s in root["states"] if s["id"] == case["state_id"])
        sample_id = f"E{i + 1:02d}"
        response = row.get("response") if row else None
        explanations.append({
            "sample_id": sample_id,
            "reference": reference(root, state),
            "actual_recipient_messages": row.get("messages") if row else case.get("messages"),
            "actual_host_packet": row.get("host_packet") if row else None,
            "response_text": response.get("text") if isinstance(response, dict) else None,
            "attempt_status": row.get("status", "missing") if row else "missing",
            "recorded_accepted_status": row.get("accepted_status") if row else None,
            "recorded_format_valid": (row.get("recipient") or {}).get("format_valid") if row else None,
            "error": row.get("error") if row else None,
            "review_questions": [
                "Does the explanation faithfully state the bounded claim and actual decisive observations?",
                "Does it distinguish the challenged route, independent alternative and exact resolution?",
                "Does it avoid asserting physical truth, missing evidence or a different scope?",
                "Does its status agree with the independent reference, and is the stated reason faithful?",
            ],
        })
        explanation_link.append({"sample_id": sample_id, "case_id": case["case_id"],
                                 "model": case["model"], "format": case["format"],
                                 "exposure": arm, "instruction": case.get("instruction"),
                                 "author_group": case.get("author_group")})
    output.mkdir(parents=True, exist_ok=False)
    save(output / "author-review-packet.json", candidates)
    save(output / "explanation-review-packet.json", explanations)
    save(output / "private-linkage.json", {"author": author_link,
                                           "explanation": explanation_link})
    summary = {"schema": "eal2-deployment-800-review-extract/1",
               "freeze_sha256": frozen["freeze_sha256"],
               "protocol_sha256": sha(protocol_bytes), "ledger_sha256": sha(ledger_bytes),
               "author_products": 32, "explanation_slots": 48,
               "explanation_exposure_counts": {e: 16 for e in EXPOSURES},
               "selection_before_review": True,
               "limitations": ["Study is developmental and synthetic",
                               "Selection rule fixed after early ledger status was visible",
                               "Actual packets can reveal arm, so reviewers are not masked",
                               "AI review does not substitute for human review or all-in cost"],
               "packet_sha256": {p.name: sha(p.read_bytes()) for p in output.iterdir()}}
    save(output / "selection.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("freeze_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.freeze_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
