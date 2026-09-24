#!/usr/bin/env python3
"""Read-only merge of A2 failure and C1 never-attempted continuation.

The combined view represents 800 assigned attempts, including the original
no-usage A2 HTTP 500. It does not turn that failure into a successful call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import run as study


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(a2: Path, c1: Path, output: Path) -> dict:
    a2_freeze = a2 / "freeze.json"
    a2_ledger = a2 / "ledger.json"
    descriptor_path = c1 / "continuation-freeze.json"
    c1_ledger = c1 / "ledger.json"
    frozen, old = study.read_json(a2_freeze), study.read_json(a2_ledger)
    desc, new = study.read_json(descriptor_path), study.read_json(c1_ledger)
    if (desc["source_freeze_sha256"] != frozen["freeze_sha256"]
            or desc["source_freeze_file_sha256"] != sha(a2_freeze)
            or desc["source_ledger_file_sha256"] != sha(a2_ledger)
            or desc["continuation_sha256"] != new["continuation_sha256"]
            or old["status"] != "stopped_provider_or_integrity_failure"
            or new["status"] not in ("complete", "complete_with_recorded_failures")
            or len(old["attempts"]) != 128 or len(new["attempts"]) != 672):
        raise ValueError("A2 and C1 are not matching terminal ledgers")
    ids = {c["case_id"] for c in frozen["cases"]}
    if (set(old["attempts"]) & set(new["attempts"])
            or ids != set(old["attempts"]) | set(new["attempts"])
            or set(new["attempts"]) != set(desc["attempt_case_ids"])):
        raise ValueError("Attempted cases overlap, changed or failed to cover 800 assignments")
    rows = {**old["attempts"], **new["attempts"]}
    for case in frozen["cases"]:
        row = rows[case["case_id"]]
        if (row["index"] != case["index"] or row["case_id"] != case["case_id"]
                or row["prompt_sha256"] != study.digest(row["messages"])
                or row["prompt_bytes"] != len(study.canonical(row["messages"]))
                or row["retry_count"] != 0 or row["status"] not in ("completed", "failed")):
            raise ValueError("Combined row failed payload/index/attempt audit")
    failures = sorted([k for k, row in rows.items() if row["status"] == "failed"])
    if failures != sorted(old["failures"] + new["failures"]):
        raise ValueError("Failed row count does not match failure log")
    combined = {"schema": study.LEDGER_SCHEMA,
                "freeze_sha256": frozen["freeze_sha256"],
                "status": "complete_with_recorded_failures",
                "attempts": rows, "failures": failures}
    lineage = {"schema": "eal2-deployment-800-merged-attempt-lineage/1",
               "source_freeze_sha256": frozen["freeze_sha256"],
               "a2_freeze_file_sha256": sha(a2_freeze),
               "a2_ledger_file_sha256": sha(a2_ledger),
               "c1_freeze_file_sha256": sha(descriptor_path),
               "c1_ledger_file_sha256": sha(c1_ledger),
               "a2_attempts": 128, "c1_attempts": 672,
               "completed": 800 - len(failures), "failed": len(failures),
               "failure_case_ids": failures,
               "unknown_billing_reserve_usd": desc["failed_unknown_billing_reserve_usd"]
                   + sum(row.get("unknown_billing_reserve_usd", 0) or 0
                         for row in new["attempts"].values()),
               "note": "Combined outcome count includes failed and unknown-billing slots; A1 and capability probes remain separate."}
    output.mkdir(parents=True, exist_ok=False)
    study.write_json(output / "freeze.json", frozen)
    study.write_json(output / "ledger.json", combined)
    study.write_json(output / "lineage.json", lineage)
    return lineage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a2", type=Path)
    parser.add_argument("c1", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(merge(args.a2, args.c1, args.output), indent=2))


if __name__ == "__main__":
    main()
