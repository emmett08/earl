#!/usr/bin/env python3
"""Validate separation and readiness of the three prospective experiments."""

from __future__ import annotations

import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PLAN_PATHS = (
    HERE / "matched-json" / "plan.json",
    HERE / "equal-compute-topology" / "plan.json",
    HERE / "human-decisions" / "plan.json",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load_plans() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in PLAN_PATHS]


def validate() -> dict:
    plans = load_plans()
    ids = [plan["investigation_id"] for plan in plans]
    namespaces = [plan["family_namespace"] for plan in plans]
    if len(set(ids)) != len(ids) or len(set(namespaces)) != len(namespaces):
        raise ValueError("Investigation IDs and family namespaces must be unique")
    for plan in plans:
        if plan["schema"] != "eal2-next-experiment/1" or plan["source_language"] != "EAL/2":
            raise ValueError(f"Unsupported contract in {plan['investigation_id']}")
        if plan["outcomes"] is not None:
            raise ValueError(f"Prospective plan contains outcomes: {plan['investigation_id']}")
        if set(namespaces) - {plan["family_namespace"]} - set(plan["excluded_family_namespaces"]):
            raise ValueError(f"Plan does not exclude the other cohorts: {plan['investigation_id']}")
        if "bias_mechanisms_001" not in plan["excluded_family_namespaces"]:
            raise ValueError(f"Plan permits exposed Stage A families: {plan['investigation_id']}")
        for name, receipt in plan["required_receipts"].items():
            if receipt is not None and (not isinstance(receipt, str) or not SHA256.fullmatch(receipt)):
                raise ValueError(f"Invalid receipt {name} in {plan['investigation_id']}")
    api, topology, human = plans
    if api["credential_env"] != "OPENAI_API_TOKEN" or topology["credential_env"] != "OPENAI_API_TOKEN":
        raise ValueError("API experiments must name OPENAI_API_TOKEN")
    if human["credential_env"] is not None or human["live_api_during_observation"]:
        raise ValueError("Human observations must not depend on a live API secret")
    compute = topology["compute_contract"]
    if compute["calls_per_case"] != 2 or len(compute["repeated_direct_roles"]) != 2 or len(compute["independent_roles"]) != 2:
        raise ValueError("Topology arms do not have equal call counts")
    readiness = {
        plan["investigation_id"]: {
            "ready": all(plan["required_receipts"].values()),
            "missing_receipts": [name for name, value in plan["required_receipts"].items() if value is None],
        }
        for plan in plans
    }
    return {"valid": True, "experiments": readiness}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
