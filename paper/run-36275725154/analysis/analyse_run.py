"""Audit the fixed development run and export aggregate, non-transcript data.

Usage: python3 analysis/analyse_run.py /path/to/api-experiment-36275725154-1.zip
The retained GitHub Actions archive is the input, not a re-run of paid models.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import zipfile

RUN_ID = 36275725154
COMMIT = "f8c629f49b5bef6c760de2029f6bc7db0e762a6f"
ARCHIVE_SHA256 = "0d1286e661eabb78470a2283d160979d4aae7221f98a086189ee7495124de018"
ARMS = ("eal_mcp", "json_prompt", "plain_brief", "plain_explicit", "plain_review", "plain_validator")
MODELS = ("gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1-nano-2025-04-14",
          "gpt-5.4-2026-03-05", "gpt-5.4-mini-2026-03-17", "gpt-5.4-nano-2026-03-17")


def analyse(archive: Path) -> dict:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"Archive SHA-256 differs: {digest}")
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read("run/manifest.json"))
        summary = json.loads(z.read("run/summary.json"))
        completion = json.loads(z.read("run/completion.json"))
        rows = [json.loads(z.read(name)) for name in z.namelist()
                if name.startswith("run/trials/") and name.endswith("/trial.json")]
    assert manifest["commit"] == COMMIT
    assert manifest["github_run_id"] == str(RUN_ID) or manifest["github_run_id"] == RUN_ID
    assert summary["measurement_valid"] and summary["mode"] == "pilot"
    assert completion["complete"] and completion["trials"] == summary["assigned"] == 1440
    assignments = {row["id"]: row for row in manifest["assignments"]}
    assert len(assignments) == len(rows) == 1440
    by_key = {}
    for row in rows:
        assignment = assignments[row["id"]]
        assert all(row[k] == assignment[k] for k in ("model", "arm", "case_id", "case_family", "transport", "finalisation"))
        assert row["model"] in MODELS and row["arm"] in ARMS
        assert row["transport"] == "native" and row["finalisation"] == "model"
        key = (row["model"], row["arm"], row["case_id"])
        assert key not in by_key
        by_key[key] = row
    cases = {row["case_id"] for row in rows}
    assert len(cases) == 40
    assert all((m, a, c) in by_key for m in MODELS for a in ARMS for c in cases)

    def correct(row):
        return row["state"] == "complete" and row.get("outcome", {}).get("correct") is True

    compact_rows = []
    for key in sorted(by_key):
        row = by_key[key]
        compact_rows.append({
            "model": row["model"], "arm": row["arm"], "case_id": row["case_id"],
            "case_family": row["case_family"], "state": row["state"],
            "reference_status": row["reference"]["status"],
            "answer_status": (row.get("answer") or {}).get("status") or "",
            "correct": int(correct(row)),
            "status_correct": int(row.get("outcome", {}).get("status_correct") is True),
            "false_support": int(row.get("outcome", {}).get("false_support") is True),
            "seconds": row["seconds"] if row.get("seconds") is not None else "",
            "known_usd": sum(call["estimated_usd"] for call in row["model_calls"]
                             if call.get("estimated_usd") is not None),
            "unknown_cost_calls": sum(call.get("estimated_usd") is None for call in row["model_calls"]),
        })
    cells, pairs, families = [], [], []
    summary_cells = {(x["model"], x["arm"]): x for x in summary["cells"]}
    for model in MODELS:
        for arm in ARMS:
            selected = [by_key[model, arm, case] for case in sorted(cases)]
            measured = {
                "model": model, "arm": arm, "assigned": len(selected),
                "completed": sum(row["state"] == "complete" for row in selected),
                "correct": sum(correct(row) for row in selected),
                "status_correct": sum(row.get("outcome", {}).get("status_correct") is True for row in selected),
                "false_support": sum(row.get("outcome", {}).get("false_support") is True for row in selected),
                "provider_calls": sum(len(row["model_calls"]) for row in selected),
                "cost_known_usd": sum(call["estimated_usd"] for row in selected for call in row["model_calls"]
                                      if call.get("estimated_usd") is not None),
                "unknown_cost_calls": sum(call.get("estimated_usd") is None for row in selected
                                          for call in row["model_calls"]),
            }
            recorded = summary_cells[model, arm]
            for field, target in (("assigned", "assigned"), ("completed", "completed"),
                                  ("correct", "correct"), ("status_correct", "status_correct"),
                                  ("false_support", "false_support"),
                                  ("provider_calls", "model_calls"),
                                  ("unknown_cost_calls", "unknown_cost_calls")):
                assert measured[field] == recorded[target], (model, arm, field)
            assert abs(measured["cost_known_usd"] - recorded["estimated_usd_known"]) < 1e-9
            cells.append(measured)
            for family in sorted({row["case_family"] for row in selected}):
                subset = [row for row in selected if row["case_family"] == family]
                assert len(subset) == 4
                families.append({"model": model, "arm": arm, "family": family,
                                 "assigned": 4, "correct": sum(correct(row) for row in subset),
                                 "false_support": sum(row.get("outcome", {}).get("false_support") is True
                                                      for row in subset)})
        for comparator in ARMS:
            if comparator == "eal_mcp":
                continue
            tally = Counter((correct(by_key[model, "eal_mcp", case]),
                             correct(by_key[model, comparator, case])) for case in cases)
            pair = {"model": model, "comparator": comparator, "paired_cases": 40,
                    "both_correct": tally[True, True], "eal_only": tally[True, False],
                    "comparator_only": tally[False, True], "both_incorrect": tally[False, False],
                    "difference": (tally[True, False] - tally[False, True]) / 40}
            recorded = next(x for x in summary["contrasts"] if x["model"] == model
                            and x["reference_arm"] == "eal_mcp" and x["comparator"] == comparator)
            assert (pair["eal_only"], pair["comparator_only"], pair["both_correct"], pair["both_incorrect"]) == (
                recorded["reference_only_correct"], recorded["comparator_only_correct"],
                recorded["both_correct"], recorded["both_incorrect"])
            pairs.append(pair)
    return {"schema": "eal-run-36275725154-aggregate/1", "run_id": RUN_ID,
            "source_commit": COMMIT, "archive_sha256": digest, "mode": summary["mode"],
            "transport": "native", "finalisation": "model", "inference": summary["inference"],
            "assigned": len(rows), "distinct_cases": len(cases), "models": list(MODELS),
            "arms": list(ARMS), "cells": cells, "pairs": pairs, "families": families,
            "assignments": compact_rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/aggregate.json"))
    args = parser.parse_args()
    result = analyse(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    compact = result.pop("assignments")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with args.output.with_name("assignments.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=tuple(compact[0]))
        writer.writeheader()
        writer.writerows(compact)
    print(f"Audited {result['assigned']} assignments across {result['distinct_cases']} cases")


if __name__ == "__main__":
    main()
