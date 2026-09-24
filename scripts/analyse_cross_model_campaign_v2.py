#!/usr/bin/env python3
"""Read-only stricter acceptance analysis for v1 and route-v2 frozen ledgers.

V1's bytes remain pinned in the original freezes. This new analysis requires
the recipient's JSON verdict to agree with the accepted host/checker verdict
before an explanation can count toward a correct accepted decision. It never
turns absent human explanation reviews or unmeasured costs into zeros.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import analyse_cross_model_campaign as legacy_analysis
from audit_cross_model_ledger import inspect as forensic_inspect, validated_rows
from run_cross_model_campaign import read_json, write_json


def _route_v2_report(frozen: dict, ledger: dict, rows: list[dict], reviews: dict | None) -> dict:
    by_condition: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_condition[row["condition_id"]].append(row)
    summaries = {}
    for condition in frozen["plan"]["conditions"]:
        name = condition["id"]
        attempts = by_condition[name]
        completed = [row for row in attempts if row["attempt"]["status"] == "completed"]
        adverse = [row for row in completed if row["expected"] != "supported"]
        calls = [call for row in attempts for call in row["attempt"].get("calls", [])]
        known_costs = [call["usage"]["model_cost_usd"] for call in calls
                       if isinstance(call.get("usage"), dict)]
        unpriced_call = any(not isinstance(call.get("usage"), dict) for call in calls)
        uncertain_pending = any(row["attempt"]["status"] == "pending" for row in attempts)
        summaries[name] = {
            "arm": "skill_route", "skill_route_kind": "model_initiated_bounded_assessment",
            "model_class": condition["model_class"],
            "model": frozen["provider_identities"][name]["model"],
            "scheduled": sum(case["condition_id"] == name for case in frozen["cases"]),
            "attempted": len(attempts), "completed": len(completed),
            "failed": len(attempts) - len(completed),
            "exact_status_correct": sum(row["attempt"]["exact_status_correct"] for row in completed),
            "recipient_false_support": sum(row["attempt"]["recipient"]["status"] == "supported"
                                           for row in adverse),
            "final_false_support": sum(row["attempt"]["false_support"] for row in adverse),
            "adverse_completed": len(adverse),
            "malformed_responses": sum(not row["attempt"]["recipient"]["format_valid"]
                                       for row in completed),
            "total_input_tokens": sum(row["attempt"]["usage"]["input_tokens"] for row in completed),
            "total_output_tokens": sum(row["attempt"]["usage"]["output_tokens"] for row in completed),
            "observed_model_api_seconds": sum(row["attempt"]["model_api_seconds"] for row in completed),
            "observed_routed_host_seconds": sum(row["attempt"].get("route_host_seconds", 0)
                                                for row in completed),
            "retry_count": sum(row["attempt"]["retry_count"] for row in attempts),
            "model_calls": sum(len(row["attempt"].get("calls", [])) for row in attempts),
            "routed_assessments": sum(row["attempt"].get("route_requested") is True for row in attempts),
            "known_configured_rate_model_cost_usd_lower_bound": sum(known_costs),
            "configured_rate_model_cost_usd": (None if unpriced_call or uncertain_pending else sum(known_costs)),
            "root_author_review_and_direct_usd": None,
            "measured_acquisition_and_host_compute_usd": None,
            "measured_explanation_adjudication_usd": None,
            "full_cost_usd": None,
            "total_cost_per_correct_accepted_usd": None,
            "cost_gap": "Author/review, acquisition, host compute, invoice and independent explanation adjudication costs are unmeasured",
        }
    return {
        "schema": "eal2-cross-model-analysis/2", "study_kind": "developmental",
        "interpretation": frozen["interpretation"], "ledger_status": ledger["status"],
        "frozen_requests": len(frozen["cases"]), "attempts": len(rows),
        "root_count": len({case["root_id"] for case in frozen["cases"]}),
        "explanation_adjudication": "complete" if reviews is not None else "unavailable",
        "conditions": summaries, "within_model_paired_contrasts": {},
        "limitation": "Synthetic agent-authored roots, no independent human review, no all-in cost estimate.",
    }


def analyse(output: Path, explanation_review: Path | None = None) -> dict:
    frozen, ledger = read_json(output / "freeze.json"), read_json(output / "ledger.json")
    rows = validated_rows(frozen, ledger)
    reviews = legacy_analysis._explanation_reviews(frozen, ledger, explanation_review)
    if frozen.get("schema") == "eal2-cross-model-route-v2-freeze/1":
        report = _route_v2_report(frozen, ledger, rows, reviews)
    else:
        report = legacy_analysis.analyse(output, explanation_review)
    audit = forensic_inspect(output)
    by_condition: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_condition[row["condition_id"]].append(row)
    for condition_id, summary in report["conditions"].items():
        completed = [item for item in by_condition[condition_id] if item["attempt"]["status"] == "completed"]

        def consistent(row: dict) -> bool:
            attempt = row["attempt"]
            return (attempt["exact_status_correct"] and attempt["recipient"]["format_valid"]
                    and attempt["recipient"]["status"] == attempt["accepted_status"]
                    and bool(attempt["recipient"]["explanation"].strip()))

        pre_review = sum(consistent(row) for row in completed)
        reviewed = (sum(consistent(row) and reviews[row["case_id"]]["faithful"] for row in completed)
                    if reviews is not None else None)
        total_cost = summary["full_cost_usd"]
        summary["oracle_matching_and_recipient_consistent_before_explanation_review"] = pre_review
        summary["recipient_nonempty_explanations"] = sum(
            bool(item["attempt"]["recipient"].get("explanation") or "") and
            bool((item["attempt"]["recipient"].get("explanation") or "").strip())
            for item in completed)
        summary["consistent_faithful_accepted_decisions"] = reviewed
        summary["total_cost_per_consistent_faithful_accepted_usd"] = (
            total_cost / reviewed if total_cost is not None and reviewed else None)
        summary["recipient_final_status_disagreements"] = sum(
            item["attempt"]["recipient"]["format_valid"] and
            item["attempt"]["recipient"]["status"] != item["attempt"]["accepted_status"]
            for item in completed)
    report["schema"] = "eal2-cross-model-analysis/2"
    report["routing_revision"] = frozen.get("routing_revision", "legacy_conflicted_second_turn")
    report["read_only_ledger_audit"] = audit
    report["acceptance_rule"] = (
        "Oracle-matching final verdict, valid recipient JSON, nonempty explanation, recipient verdict equal to the final verdict, "
        "and independently reviewed faithful explanation; without complete review the accepted-decision cost is unavailable"
    )
    if frozen.get("routing_revision") is None:
        report["legacy_routing_caveat"] = (
            "The original skill_route second turn retained the operation-request system instruction, "
            "conflicting with its appended claim-answer request. Treat that arm as a procedure failure."
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--explanation-review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyse(args.run_directory, args.explanation_review)
    if args.output:
        write_json(args.output, result)
    else:
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
