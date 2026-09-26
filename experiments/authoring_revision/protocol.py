"""The small, public data contract for a paired authoring study."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


STAGES = ("initial", "revision")
STATUSES = {"supported", "unsupported", "unavailable", "contested", "out_of_scope"}
ARMS = ("eal2", "typed_rules")


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def identifier(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value) is not None


def seconds(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_plan(plan: object, oracle: object, participants: object) -> None:
    if not isinstance(plan, dict) or set(plan) != {
        "schema", "study_id", "target_population", "source_commit", "assignment_seed",
        "arms", "tasks", "practical_margins", "runner_sha256",
    } or plan["schema"] != "eal-authoring-plan/1":
        raise ValueError("Expected a complete eal-authoring-plan/1")
    if (not identifier(plan["study_id"])
            or not isinstance(plan["target_population"], str)
            or not plan["target_population"].strip()
            or not isinstance(plan["source_commit"], str)
            or re.fullmatch(r"[0-9a-f]{40}", plan["source_commit"]) is None
            or type(plan["assignment_seed"]) is not int
            or plan["arms"] != list(ARMS)):
        raise ValueError("Declare study identity, population, source revision, seed and both arms")
    runners = plan["runner_sha256"]
    if (not isinstance(runners, dict) or set(runners) != set(ARMS)
            or any(not isinstance(value, str)
                   or re.fullmatch(r"[0-9a-f]{64}", value) is None
                   for value in runners.values())):
        raise ValueError("Pin one operator runner digest for each arm")
    margins = plan["practical_margins"]
    if (not isinstance(margins, dict)
            or set(margins) != {"correct_case_fraction", "active_seconds", "semantic_defects"}
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
                   for v in margins.values())
            or margins["correct_case_fraction"] > 1):
        raise ValueError("Declare finite non-negative practical margins")
    tasks = plan["tasks"]
    if not isinstance(tasks, list) or len(tasks) < 2 or len(tasks) % 2:
        raise ValueError("Supply at least two tasks, in matched pairs")
    ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {
            "id", "family", "initial_brief", "revision_brief", "cases", "inputs", "target_claims",
        } or not identifier(task["id"]) or task["id"] in ids:
            raise ValueError("Task identities must be unique and complete")
        ids.add(task["id"])
        if (not all(isinstance(task[key], str) and task[key].strip()
                    for key in ("family", "initial_brief", "revision_brief"))
                or not isinstance(task["cases"], dict)
                or set(task["cases"]) != set(STAGES)
                or not isinstance(task["inputs"], dict)
                or set(task["inputs"]) != set(STAGES)
                or not isinstance(task["target_claims"], dict)
                or set(task["target_claims"]) != set(STAGES)):
            raise ValueError("Each task needs a family, both briefs, case IDs and frozen inputs")
        for stage in STAGES:
            cases = task["cases"][stage]
            claims = task["target_claims"][stage]
            if (not isinstance(cases, list) or not cases or not all(identifier(x) for x in cases)
                    or len(cases) != len(set(cases))
                    or not isinstance(claims, list) or not claims
                    or not all(identifier(x) for x in claims)
                    or len(claims) != len(set(claims))):
                raise ValueError("Each stage needs distinct case and target claim IDs")
            inputs = task["inputs"][stage]
            if (not isinstance(inputs, dict) or set(inputs) != set(cases)
                    or not all(isinstance(payload, dict) and payload
                               for payload in inputs.values())):
                raise ValueError("Frozen input payloads must cover exactly the named cases")
    if (not isinstance(participants, list) or not participants
            or not all(identifier(x) for x in participants)
            or len(participants) != len(set(participants))):
        raise ValueError("Supply distinct pseudonymous participant IDs")
    if (not isinstance(oracle, dict) or set(oracle) != {"schema", "tasks"}
            or oracle["schema"] != "eal-authoring-oracle/1"
            or not isinstance(oracle["tasks"], dict)
            or set(oracle["tasks"]) != ids):
        raise ValueError("The independent oracle must cover exactly the declared tasks")
    for task in tasks:
        expected = oracle["tasks"][task["id"]]
        if not isinstance(expected, dict) or set(expected) != set(STAGES):
            raise ValueError("The oracle must cover initial and revised requirements")
        for stage in STAGES:
            cases = expected[stage]
            if not isinstance(cases, dict) or set(cases) != set(task["cases"][stage]):
                raise ValueError("The oracle case identities must match the public plan")
            for claims in cases.values():
                if (not isinstance(claims, dict) or set(claims) != set(task["target_claims"][stage])
                        or not all(identifier(k) and isinstance(v, str) and v in STATUSES
                                   for k, v in claims.items())):
                    raise ValueError("Each expected case needs named claims and valid statuses")
    if any(tasks[i]["family"] != tasks[i + 1]["family"]
           for i in range(0, len(tasks), 2)):
        raise ValueError("Adjacent tasks must form a matched family pair")


def load_frozen(run: Path) -> tuple[dict, dict]:
    plan = read_json(run / "plan.json")
    manifest = read_json(run / "manifest.json")
    assignments = read_json(run / "assignments.json")
    if (not isinstance(manifest, dict)
            or digest(canonical(plan)) != manifest.get("plan_sha256")
            or digest(canonical(assignments)) != manifest.get("assignments_sha256")):
        raise ValueError("Frozen plan or assignments changed")
    return plan, assignments


def verify_oracle(run: Path, path: Path) -> dict:
    manifest = read_json(run / "manifest.json")
    oracle = read_json(path)
    if digest(canonical(oracle)) != manifest["oracle_sha256"]:
        raise ValueError("Oracle differs from the independently frozen reference")
    return oracle
