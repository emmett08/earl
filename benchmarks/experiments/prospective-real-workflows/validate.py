"""Lint the unrun study specification; do not use this as an execution gate.

This command reads no provider credential, executes no tool and makes no API call.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PLAN = Path(__file__).with_name("plan.json")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
STAGES = (
    "feasibility_pilot",
    "freeze_and_preregister",
    "retrospective_execution",
    "prospective_shadow",
)
ARMS = ("P", "T", "E", "J")
RECEIPTS = (
    "independent_case_manifest_sha256",
    "reference_review_sha256",
    "tool_allowlist_and_isolation_sha256",
    "adapter_execution_and_authentication_sha256",
    "prompt_and_method_parity_sha256",
    "pilot_report_sha256",
    "power_and_margin_approval_sha256",
    "model_snapshot_manifest_sha256",
    "frozen_schedule_sha256",
    "registration_sha256",
    "shadow_access_and_stop_authority_sha256",
)


def validate(plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (structural errors, unresolved execution prerequisites)."""
    errors: list[str] = []
    blockers: list[str] = []

    if plan.get("schema") != "eal2-prospective-real-workflows/1":
        errors.append("Unknown plan schema")
    if plan.get("investigation_id") != "INV-EAL-REAL-001":
        errors.append("The separate investigation ID changed")
    if plan.get("status") != "specified_not_ready":
        errors.append("Version 0.1.0 describes an unrun specification only; execution needs a reviewed version and separate ledger validator")
    if plan.get("source_language") != "EAL/2" or plan.get("tool_trace_schema") != "proposed-real-tool-trace/1":
        errors.append("Current source language or proposed tool-trace contract changed")

    scope = plan.get("scope", {})
    namespace = scope.get("family_namespace")
    if not namespace or namespace in scope.get("excluded_family_namespaces", []):
        errors.append("Study family namespace is missing or overlaps an excluded cohort")
    if not scope.get("retrospective_and_shadow_separate"):
        errors.append("Retrospective and shadow estimands must stay separate")
    if len(set(scope.get("domains", []))) < 4:
        errors.append("The sampling frame must span four declared engineering domains")

    stages = plan.get("stages", [])
    if [s.get("id") for s in stages] != list(STAGES) or [s.get("order") for s in stages] != [1, 2, 3, 4]:
        errors.append("Stages must follow pilot, freeze, retrospective, shadow in that order")
    if any(not s.get("purpose") or not s.get("exit_receipt") for s in stages):
        errors.append("Every stage needs a purpose and exit receipt")
    if stages and (stages[0].get("families_min"), stages[0].get("families_max")) != (12, 20):
        errors.append("Pilot information range changed without a protocol version")
    if any(s.get("status") != "pending" for s in stages):
        errors.append("This specification version cannot report an executed stage")

    conditions = plan.get("conditions", {})
    arms = conditions.get("core_arms", [])
    if [a.get("id") for a in arms] != list(ARMS):
        errors.append("Core arms must contain P, T, E and J once each")
    if len(arms) == 4:
        for field in ("starting_material", "tool_permissions", "answer_schema"):
            if len({a.get(field) for a in arms}) != 1 or any(not a.get(field) for a in arms):
                errors.append(f"Core arms lack equal {field}")
        if any(a.get("tool_permissions") != "common_read_only_catalogue" for a in arms):
            errors.append("All core arms must have the same read-only tool catalogue")
    contract = conditions.get("tool_contract", {})
    prohibited = set(contract.get("prohibited", []))
    if not {"production_write", "unisolated_command_adapter", "credential_in_prompt_or_ledger", "post_decision_evidence"}.issubset(prohibited):
        errors.append("Tool contract omits a required execution prohibition")
    if not contract.get("shared_capture") or len(contract.get("trace_fields", [])) < 12:
        errors.append("The proposed real-execution trace contract is incomplete")
    if len(contract.get("operations", [])) < 5 or "Actually execute" not in contract.get("execution", ""):
        errors.append("The plan omits actual tool execution or the common method catalogue")

    model = plan.get("model_matrix", {})
    if model.get("minimum_snapshots", 0) < 8 or model.get("minimum_providers", 0) < 3:
        errors.append("Model matrix no longer covers the declared cross-model question")
    if model.get("minimum_per_declared_class", 0) < 2 or not model.get("cross_each_case_and_core_arm"):
        errors.append("Model class representation or full crossing is missing")
    if "marginal" not in model.get("class_coverage", ""):
        errors.append("Model class coverage must distinguish marginal strata from intersections")
    reference = plan.get("reference", {})
    if "third adjudicator" not in reference.get("reviewers", ""):
        errors.append("Independent reference disagreements need an adjudicator")

    outcomes = plan.get("outcomes", {})
    if not outcomes.get("primary_binary") or "intention-to-treat" not in outcomes.get("primary_estimand", ""):
        errors.append("The end-to-end primary outcome or assigned-attempt estimand is missing")
    if not outcomes.get("shadow_estimand") or not outcomes.get("safety_estimand"):
        errors.append("Shadow and false-support outcomes must be separate")
    if "minimum actionable decision-coverage" not in outcomes.get("coverage_gate", ""):
        errors.append("The false-support gate requires an actionable-coverage safeguard")
    if not plan.get("analysis", {}).get("missingness", "").startswith("Retain authoring"):
        errors.append("Failed authoring and tool attempts must remain in the primary denominator")

    receipts = plan.get("required_receipts", {})
    if set(receipts) != set(RECEIPTS):
        errors.append("Required receipt set changed; review and version the protocol")
    for key in RECEIPTS:
        value = receipts.get(key)
        if value is None:
            blockers.append(key)
        elif not isinstance(value, str) or not SHA256.fullmatch(value):
            errors.append(f"{key} must be a 64-character SHA-256 digest")

    analysis = plan.get("analysis", {})
    if analysis.get("family_count_confirmatory") is None:
        blockers.append("family_count_confirmatory")
    elif type(analysis["family_count_confirmatory"]) is not int or analysis["family_count_confirmatory"] < 1:
        errors.append("Confirmatory family count must be a positive integer")
    for key in ("practical_gain_margin", "false_support_margin", "minimum_decision_coverage"):
        value = analysis.get(key)
        if value is None:
            blockers.append(key)
        elif type(value) not in (int, float) or not 0 <= value <= 1 or (key in {"practical_gain_margin", "minimum_decision_coverage"} and value == 0):
            errors.append(f"{key} needs a valid probability threshold; practical gain and coverage must be positive")

    execution = plan.get("execution", {})
    if any(execution.get(key) is not None for key in ("pilot_started_at", "retrospective_started_at", "shadow_started_at", "ledgers", "observed_results")):
        errors.append("This unrun specification cannot contain execution dates, ledgers or results")
    ledgers = plan.get("post_run_artifacts", {})
    if set(ledgers) != {"retrospective_ledger_sha256", "shadow_ledger_sha256"} or any(value is not None for value in ledgers.values()):
        errors.append("Post-run ledgers must remain separate and empty in this specification")

    # A syntactically plausible digest is not an independently authenticated
    # receipt. This version has no real-tool runner or ledger verification and
    # must never authorise pilot or confirmatory execution by itself.
    blockers.append("external_receipt_and_execution_validation_not_implemented")

    return errors, blockers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-ready", action="store_true", help="always fail in this specification-only version")
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    errors, blockers = validate(plan)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    if blockers:
        print("SPECIFICATION VALID — EXECUTION BLOCKED: " + ", ".join(blockers))
        return 2 if args.require_ready else 0
    raise AssertionError("Specification-only version cannot become executable")


if __name__ == "__main__":
    raise SystemExit(main())
