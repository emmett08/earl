"""Freeze a paired, counterbalanced allocation without seeing results."""
from __future__ import annotations

from pathlib import Path
import random

from .protocol import ARMS, canonical, digest, read_json, validate_plan


def freeze(plan_path: Path, oracle_path: Path, participants_path: Path, output: Path) -> dict:
    plan = read_json(plan_path)
    oracle = read_json(oracle_path)
    participants = read_json(participants_path)
    validate_plan(plan, oracle, participants)
    if len(canonical(plan)) > 1024 * 1024 or len(canonical(oracle)) > 1024 * 1024:
        raise ValueError("Plan or oracle exceeds 1 MiB")
    if len(participants) > 10000:
        raise ValueError("Too many participants")
    shuffled = list(participants)
    random.Random(plan["assignment_seed"]).shuffle(shuffled)
    assignments: list[dict] = []
    for index, participant in enumerate(shuffled):
        # Adjacent tasks form matched pairs. Four consecutive participants
        # balance task order, first arm and arm allocation within each pair.
        for pair_index in range(0, len(plan["tasks"]), 2):
            pair = plan["tasks"][pair_index:pair_index + 2]
            if index % 4 in (2, 3):
                pair = list(reversed(pair))
            for position, task in enumerate(pair):
                canonical_task_index = pair_index + (0 if task["id"] == plan["tasks"][pair_index]["id"] else 1)
                arm = ARMS[(index + canonical_task_index) % 2]
                assignment_id = digest(canonical([plan["study_id"], participant, task["id"], arm]))[:20]
                assignments.append({
                    "id": assignment_id, "participant_id": participant,
                    "task_id": task["id"], "family": task["family"], "arm": arm,
                    "pair_index": pair_index // 2, "order": pair_index + position + 1,
                })
    manifest = {
        "schema": "eal-authoring-freeze/1",
        "plan_sha256": digest(canonical(plan)),
        "oracle_sha256": digest(canonical(oracle)),
        "assignments_sha256": digest(canonical(assignments)),
        "runner_sha256": plan["runner_sha256"],
        "participant_count": len(shuffled),
        "balance_note": ("Complete four-participant blocks balance arm and order within each "
                         "matched task pair. A partial block may be imbalanced."),
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_bytes(canonical(plan))
    (output / "assignments.json").write_bytes(canonical(assignments))
    (output / "manifest.json").write_bytes(canonical(manifest))
    (output / "submissions").mkdir()
    (output / "reviews").mkdir()
    return manifest
