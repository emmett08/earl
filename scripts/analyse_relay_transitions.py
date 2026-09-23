#!/usr/bin/env python3
"""Describe correction and damage in the retained relay cohort; no model calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "benchmarks/results/2026-09-23-relays-recovery"


def analyse(root: Path) -> dict:
    endpoints_path = root / "complete-block-endpoints.csv"
    stages_path = root / "complete-block-stages.csv"
    with endpoints_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    with stages_path.open(newline="") as stream:
        stage_rows = list(csv.DictReader(stream))
    stages = {(r["cohort"], r["stage_key"]): r for r in stage_rows}
    if len(stages) != len(stage_rows):
        raise ValueError("Duplicate stage identity")
    by_condition = defaultdict(list)
    seen = set()
    for row in rows:
        identity = (row["block_id"], row["condition_id"])
        if identity in seen:
            raise ValueError("Duplicate endpoint in selected cohort")
        seen.add(identity)
        states = [int(s) for s in row["stage_correctness"].split(",")]
        keys = row["stage_keys"].split(";")
        if len(states) != len(keys) or any(x not in (0, 1) for x in states):
            raise ValueError("Stage identities and correctness disagree")
        if states[-1] != int(row["correct"]):
            raise ValueError("Endpoint correctness differs from final stage")
        linked = [stages[(row["cohort"], key)] for key in keys]
        if any(s["task_id"] != row["task_id"] for s in linked):
            raise ValueError("Stage/task join mismatch")
        row = dict(row, states=states, linked=linked)
        by_condition[row["condition_id"]].append(row)
    block_sets = [{r["block_id"] for r in v} for v in by_condition.values()]
    if any(b != block_sets[0] for b in block_sets):
        raise ValueError("Conditions do not cover the same blocks")

    summaries = {}
    for condition, items in sorted(by_condition.items()):
        if len(items[0]["states"]) == 1:
            continue
        counts = Counter()
        changes = []
        for row in items:
            start, end = row["states"][0], row["states"][-1]
            completed = row["linked"][0]["status"] == "completed"
            start_label = "correct" if start else "incorrect" if completed else "incomplete"
            counts["producer_" + start_label] += 1
            outcome = ("preserved" if end else "damaged") if start else (
                "corrected" if end and completed else "recovered_incomplete" if end else "remained_incorrect_or_incomplete")
            counts[outcome] += 1
            if start != end:
                changes.append({"block_id": row["block_id"], "cohort": row["cohort"],
                                "producer_state": start_label, "transition": outcome,
                                "stage_correctness": row["states"],
                                "models": [s["model"] for s in row["linked"]],
                                "arms": [s["arm"] for s in row["linked"]],
                                "stage_keys": row["stage_keys"].split(";")})
        summaries[condition] = {"blocks": len(items), "counts": dict(counts), "changes": changes}

    # These pairs reuse the exact same first-stage output, within each cohort.
    pairs = [("l_tool_n_evidence", "l_tool_n_answer"),
             ("n_l_tool_n", "n_n_answer"), ("l_n_tool_l", "l_l_answer")]
    comparisons = []
    for left, right in pairs:
        left_rows = {r["block_id"]: r for r in by_condition[left]}
        right_rows = {r["block_id"]: r for r in by_condition[right]}
        differences = []
        for block in sorted(left_rows):
            a, b = left_rows[block], right_rows[block]
            if (a["cohort"], a["stage_keys"].split(";")[0]) != (b["cohort"], b["stage_keys"].split(";")[0]):
                raise ValueError("Comparison lacks a shared saved producer")
            differences.append(int(a["correct"]) - int(b["correct"]))
        comparisons.append({"left": left, "right": right, "shared_producer_checked": True,
                            "blocks": len(differences), "left_correct": sum(int(r["correct"]) for r in left_rows.values()),
                            "right_correct": sum(int(r["correct"]) for r in right_rows.values()),
                            "difference": sum(differences) / len(differences),
                            "interpretation": "Descriptive whole-sequence contrast; exposed tasks; no notation intervention."})
    return {"schema": "EAL/relay-transition-analysis/1", "analysis_kind": "post-hoc descriptive reanalysis",
            "source_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (endpoints_path, stages_path)},
            "endpoints": len(rows), "task_clusters": len({r["task_id"] for r in rows}),
            "blocks": len(block_sets[0]), "conditions": summaries, "comparisons": comparisons,
            "limitations": ["Overlapping stages and task repetitions are dependent.",
                            "Incomplete producer runs are separate from completed incorrect answers.",
                            "Correct status labels do not establish independent verification or source repair.",
                            "A zero denominator gives no estimate of error-correction probability.",
                            "These tasks cannot supply new held-out evidence or a notation effect."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyse(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("endpoints", "task_clusters", "blocks")}))


if __name__ == "__main__":
    main()
