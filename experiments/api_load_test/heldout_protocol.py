"""Freeze a new case list and fixed analysis contract before held-out execution.

This is an admission gate, not a paid runner or a source of engineering truth.
An operator must supply independently selected cases and validate their evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .cases import case_specs


REQUIRED_OUTCOMES = {"complete_correct_answer", "false_support", "correct_abstention",
                     "coverage", "elapsed_seconds", "total_cost_usd"}
PLAN_FIELDS = {"schema", "target_population", "comparator_family", "primary_outcome",
               "practical_margin", "stopping_rule", "case_family_dependence", "model_snapshots",
               "outcomes", "source_commit"}


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def freeze(plan: dict, cases: list[dict], output: Path) -> dict:
    """Reject development IDs and incomplete plans; retain exact new assignments."""
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS or plan["schema"] != "eal-api-heldout-plan/1":
        raise ValueError("A complete versioned held-out plan is required")
    if (not all(isinstance(plan[key], str) and plan[key].strip()
                for key in ("target_population", "case_family_dependence"))
            or not isinstance(plan["source_commit"], str)
            or re.fullmatch(r"[0-9a-f]{40}", plan["source_commit"]) is None):
        raise ValueError("Population, dependence and source commit must be declared")
    if (not isinstance(plan["comparator_family"], list)
            or not 2 <= len(plan["comparator_family"]) <= 8
            or not all(isinstance(item, str) and item.strip() for item in plan["comparator_family"])
            or len(set(plan["comparator_family"])) != len(plan["comparator_family"])):
        raise ValueError("Declare distinct executable comparators")
    if (plan["primary_outcome"] != "complete_correct_answer"
            or not isinstance(plan["outcomes"], list)
            or not all(isinstance(item, str) for item in plan["outcomes"])
            or set(plan["outcomes"]) != REQUIRED_OUTCOMES
            or len(plan["outcomes"]) != len(REQUIRED_OUTCOMES)):
        raise ValueError("Declare the complete outcome family, including unsafe support and abstention")
    if (type(plan["practical_margin"]) not in {int, float}
            or not math.isfinite(plan["practical_margin"])
            or not 0 < plan["practical_margin"] < 1):
        raise ValueError("Declare a positive paired practical effect margin")
    if (not isinstance(plan["model_snapshots"], list) or not plan["model_snapshots"]
            or not all(isinstance(item, str) and item.strip() for item in plan["model_snapshots"])
            or len(set(plan["model_snapshots"])) != len(plan["model_snapshots"])):
        raise ValueError("Declare exact model snapshots")
    stop = plan["stopping_rule"]
    if (not isinstance(stop, dict) or set(stop) != {"kind", "planned_cases"}
            or stop["kind"] != "fixed_case_count" or type(stop["planned_cases"]) is not int
            or stop["planned_cases"] < 2 or not isinstance(cases, list)
            or len(cases) != stop["planned_cases"]):
        raise ValueError("Declare and supply exactly the fixed number of held-out cases")
    development_ids = {item["id"] for item in case_specs("pilot")}
    if (any(not isinstance(case, dict) or set(case) != {"id", "family", "payload"}
            or not isinstance(case["id"], str) or not case["id"]
            or not isinstance(case["family"], str) or not case["family"]
            or not isinstance(case["payload"], dict) or not case["payload"] for case in cases)
            or len({case["id"] for case in cases}) != len(cases)
            or any(case["id"] in development_ids for case in cases)):
        raise ValueError("Held-out cases need new, unique identities and bounded payloads")
    plan_bytes, case_bytes = _bytes(plan), _bytes(cases)
    if len(plan_bytes) > 65536 or len(case_bytes) > 16 * 1024 * 1024:
        raise ValueError("Held-out declaration exceeds its byte limits")
    assignments = [{"id": case["id"], "family": case["family"],
                    "case_sha256": hashlib.sha256(_bytes(case)).hexdigest()} for case in cases]
    manifest = {"schema": "eal-api-heldout-freeze/1", "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                "cases_sha256": hashlib.sha256(case_bytes).hexdigest(), "assignments": assignments,
                "source_commit": plan["source_commit"], "state": "frozen_unexecuted"}
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_bytes(plan_bytes)
    (output / "cases.json").write_bytes(case_bytes)
    (output / "manifest.json").write_bytes(_bytes(manifest))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    freeze(json.loads(args.plan.read_text()), json.loads(args.cases.read_text()), args.output)
