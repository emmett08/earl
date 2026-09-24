#!/usr/bin/env python3
"""Audit paired cross-model results and report root-clustered comparisons.

Semantic explanation fidelity is independently adjudicated; a matching status
or fluent sentence cannot substitute for that assessment. Unmeasured authoring,
review, acquisition or compute costs remain unavailable, never zero.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any

from run_cross_model_campaign import answer, digest, read_json, verify_freeze, write_json
from eal.providers import ModelResponse, response_cost


def _explanation_reviews(frozen: dict, ledger: dict, path: Path | None) -> dict[str, dict] | None:
    if path is None:
        return None
    review = read_json(path)
    if (review.get("schema") != "eal2-explanation-adjudication/1"
            or review.get("freeze_sha256") != frozen["freeze_sha256"]
            or review.get("ledger_sha256") != digest(ledger)):
        raise ValueError("Explanation adjudications do not address this immutable schedule and ledger")
    completed = {frozen["cases"][row["index"]]["case_id"] for row in ledger["attempts"]
                 if row["status"] == "completed"}
    results = {}
    for row in review.get("scores", []):
        case_id, reviewers = row.get("case_id"), row.get("reviewers")
        if (case_id not in completed or case_id in results or not isinstance(reviewers, list)
                or len({r.get("id") for r in reviewers if isinstance(r, dict)}) < 2
                or any(type(r.get("faithful")) is not bool or not r.get("reason") for r in reviewers)
                or type(row.get("adjudicated_faithful")) is not bool):
            raise ValueError("Each explanation needs two distinct, reasoned reviews and final adjudication")
        adjudication_cost = row.get("adjudication_cost_usd")
        if adjudication_cost is not None and (isinstance(adjudication_cost, bool)
                or not isinstance(adjudication_cost, (int, float))
                or not math.isfinite(adjudication_cost) or adjudication_cost < 0):
            raise ValueError("Adjudication cost must be measured, finite, nonnegative or null")
        results[case_id] = {"faithful": row["adjudicated_faithful"], "cost_usd": adjudication_cost}
    if set(results) != completed:
        raise ValueError("Explanation adjudications must cover every completed response")
    return results


def _audit(frozen: dict, ledger: dict) -> list[dict]:
    verify_freeze(frozen)
    if ledger.get("schema") != "eal2-cross-model-ledger/1" or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
        raise ValueError("Ledger is not linked to its frozen schedule")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list) or len(attempts) > len(frozen["cases"]):
        raise ValueError("Malformed attempt ledger")
    result = []
    for index, row in enumerate(attempts):
        case = frozen["cases"][index]
        if (row.get("index"), row.get("case_id"), row.get("prompt_sha256")) != (
                index, case["case_id"], case["prompt_sha256"]):
            raise ValueError(f"Attempt {index} was not the scheduled prompt")
        if row.get("retry_count") != 0:
            raise ValueError("Runner does not permit unrecorded or automatic retries")
        if row["status"] == "completed":
            recipient = (answer(row["response"]["text"], case["claim"])
                         if case["arm"] != "skill_route" or row.get("route_requested") else
                         {"status": None, "explanation": None, "format_valid": False,
                          "error": row.get("route_reason")})
            status = (case["host_status"] if case["arm"] == "eal_host" or
                      case["arm"] == "skill_route" and row.get("route_requested") else
                      case["checker_status"] if case["arm"] == "equal_checker" else recipient["status"])
            usage = row.get("usage")
            if (recipient != row["recipient"] or status != row["accepted_status"]
                    or row["exact_status_correct"] != (status == case["expected"])
                    or row["false_support"] != (status == "supported" and case["expected"] != "supported")
                    or not isinstance(usage, dict)
                    or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens"))
                    or not isinstance(usage.get("model_cost_usd"), (int, float))):
                raise ValueError(f"Retained response/score/usage is inconsistent at attempt {index}")
            measured = ModelResponse(row["response"]["text"], usage["input_tokens"],
                                     usage["output_tokens"], row["response"]["model"],
                                     row["response"]["metadata"])
            identity = frozen["provider_identities"][case["condition_id"]]
            if case["arm"] != "skill_route" and response_cost(measured, identity) != usage["model_cost_usd"]:
                raise ValueError("Retained model cost differs from pinned usage and configured rates")
            if case["arm"] == "skill_route":
                calls = row.get("calls", [])
                if (len(calls) != (2 if row.get("route_requested") else 1)
                        or any(call.get("status") != "completed" or call.get("prompt_sha256") != digest(call["messages"])
                               for call in calls)
                        or sum(call["usage"]["input_tokens"] for call in calls) != usage["input_tokens"]
                        or sum(call["usage"]["output_tokens"] for call in calls) != usage["output_tokens"]
                        or sum(call["usage"]["model_cost_usd"] for call in calls) != usage["model_cost_usd"]):
                    raise ValueError("Routed subcalls do not account for aggregated model usage")
        result.append({**case, "attempt": row})
    if ledger["status"] == "complete" and len(attempts) != len(frozen["cases"]):
        raise ValueError("Complete ledger is missing scheduled attempts")
    return result


def _cluster_difference(rows: list[dict], treatment: str, reference: str, *, seed: int = 31) -> dict:
    """Within-root paired contrasts; states/repeats are not independent roots."""
    cells = defaultdict(dict)
    for row in rows:
        if row["condition_id"] in {treatment, reference}:
            unit = (row["root_id"], row["state_id"], row["repetition"])
            cells[unit][row["condition_id"]] = int(row["attempt"].get("exact_status_correct", False))
    root_values: dict[str, list[float]] = defaultdict(list)
    for (root, _, _), condition_values in cells.items():
        if set(condition_values) == {treatment, reference}:
            root_values[root].append(condition_values[treatment] - condition_values[reference])
    means = [statistics.mean(values) for values in root_values.values()]
    if not means:
        return {"paired_roots": 0, "difference": None, "interval_95": None}
    estimate = statistics.mean(means)
    if len(means) < 2:
        return {"paired_roots": len(means), "difference": estimate, "interval_95": None}
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(2000))
    return {"paired_roots": len(means), "paired_states": sum(map(len, root_values.values())),
            "difference": estimate, "interval_95": [draws[49], draws[1949]],
            "interval_note": "Descriptive root bootstrap; sparse synthetic roots do not justify population inference"}


def analyse(output: Path, explanation_review: Path | None = None) -> dict:
    frozen, ledger = read_json(output / "freeze.json"), read_json(output / "ledger.json")
    rows = _audit(frozen, ledger)
    adjudications = _explanation_reviews(frozen, ledger, explanation_review)
    by_condition: dict[str, list[dict]] = defaultdict(list)
    condition_definitions = {c["id"]: c for c in frozen["plan"]["conditions"]}
    for row in rows:
        by_condition[row["condition_id"]].append(row)
    summaries = {}
    for condition in frozen["plan"]["conditions"]:
        name, arm = condition["id"], condition["arm"]
        scheduled = sum(case["condition_id"] == name for case in frozen["cases"])
        attempted = by_condition[name]
        completed = [row for row in attempted if row["attempt"]["status"] == "completed"]
        adverse = [row for row in completed if row["expected"] != "supported"]
        input_tokens = sum(row["attempt"]["usage"]["input_tokens"] for row in completed)
        output_tokens = sum(row["attempt"]["usage"]["output_tokens"] for row in completed)
        costs = [row["attempt"].get("usage", {}).get("model_cost_usd")
                 for row in attempted if row["attempt"].get("usage")]
        model_cost = sum(costs) if all(cost is not None for cost in costs) else None
        fixed = frozen["fixed_costs_by_root_usd"]
        fixed_cost = (sum(root["common"] + root.get(arm, 0) for root in fixed.values())
                      if all(root is not None and "common" in root for root in fixed.values()) else None)
        faithful = (sum(adjudications[row["case_id"]]["faithful"] for row in completed)
                    if adjudications is not None else None)
        correct_accepted = (sum(row["attempt"]["exact_status_correct"] and
                                row["attempt"]["recipient"]["format_valid"] and
                                adjudications[row["case_id"]]["faithful"] for row in completed)
                            if adjudications is not None else None)
        state_costs = frozen.get("variable_costs_by_state_usd", {})
        variable_cost = None
        if all(state_costs.get(row["root_id"] + "/" + row["state_id"]) is not None for row in attempted):
            variable_cost = sum(
                state_costs[row["root_id"] + "/" + row["state_id"]]["acquisition_usd"] +
                (state_costs[row["root_id"] + "/" + row["state_id"]]["eal_compute_usd"]
                 if arm == "eal_host" or arm == "skill_route" and row["attempt"].get("route_requested") else
                 state_costs[row["root_id"] + "/" + row["state_id"]]["checker_compute_usd"]
                 if arm == "equal_checker" else 0)
                for row in attempted)
        adjudication_cost = (sum(adjudications[row["case_id"]]["cost_usd"] for row in completed)
                             if adjudications is not None and all(adjudications[row["case_id"]]["cost_usd"] is not None
                                                              for row in completed) else None)
        partial_cost_per_accepted = ((model_cost + fixed_cost) / correct_accepted
                                     if model_cost is not None and fixed_cost is not None and correct_accepted else None)
        full_cost = (model_cost + fixed_cost + variable_cost + adjudication_cost
                     if all(value is not None for value in (model_cost, fixed_cost, variable_cost, adjudication_cost))
                     and len(attempted) == scheduled and all(row["attempt"]["usage"] is not None for row in attempted)
                     else None)
        full_cost_per_accepted = full_cost / correct_accepted if full_cost is not None and correct_accepted else None
        summaries[name] = {
            "arm": arm, "skill_route_kind": ("instruction_only" if arm == "skill" else
                                              "model_initiated_bounded_assessment" if arm == "skill_route" else None),
            "model_class": condition["model_class"], "model": frozen["provider_identities"][name]["model"],
            "scheduled": scheduled, "attempted": len(attempted), "completed": len(completed),
            "failed": len(attempted) - len(completed), "unattempted": scheduled - len(attempted),
            "exact_status_correct": sum(row["attempt"]["exact_status_correct"] for row in completed),
            "recipient_false_support": sum(row["attempt"]["recipient"]["status"] == "supported" and
                                           row["expected"] != "supported" for row in adverse),
            "final_false_support": sum(row["attempt"]["false_support"] for row in adverse),
            "adverse_completed": len(adverse),
            "recipient_contradictions": sum(row["attempt"].get("recipient_contradicted_host") is True
                                            for row in completed),
            "malformed_responses": sum(not row["attempt"]["recipient"]["format_valid"] for row in completed),
            "faithful_explanations": faithful,
            "correct_accepted_decisions": correct_accepted,
            "total_input_tokens": input_tokens, "total_output_tokens": output_tokens,
            "observed_model_api_seconds": sum(row["attempt"]["model_api_seconds"] for row in completed),
            "measured_offline_host_preassessment_seconds_unique_states": sum(
                frozen["snapshots"][key]["host_seconds"] for key in
                {row["root_id"] + "/" + row["state_id"] for row in completed}),
            "measured_offline_checker_seconds_unique_states": sum(
                frozen["snapshots"][key]["checker_seconds"] for key in
                {row["root_id"] + "/" + row["state_id"] for row in completed}),
            "observed_routed_host_seconds": sum(row["attempt"].get("route_host_seconds", 0) for row in completed),
            "retry_count": sum(row["attempt"]["retry_count"] for row in attempted),
            "model_calls": sum(len(row["attempt"].get("calls", [None])) for row in attempted),
            "routed_assessments": sum(row["attempt"].get("route_requested") is True for row in attempted),
            "configured_rate_model_cost_usd": model_cost,
            "root_author_review_and_direct_usd": fixed_cost,
            "measured_acquisition_and_host_compute_usd": variable_cost,
            "measured_explanation_adjudication_usd": adjudication_cost,
            "full_cost_usd": full_cost,
            "partial_cost_per_correct_accepted_usd": partial_cost_per_accepted,
            "total_cost_per_correct_accepted_usd": full_cost_per_accepted,
            "cost_gap": None if full_cost is not None else
            "Complete author/review, acquisition, host compute, model and explanation adjudication costs are required",
        }
    contrasts = {}
    for treatment in frozen["plan"]["conditions"]:
        for reference in frozen["plan"]["conditions"]:
            if (reference["arm"] == "raw" and treatment["arm"] != "raw"
                    and reference["model_class"] == treatment["model_class"]
                    and frozen["provider_identities"][reference["id"]]["model"] ==
                    frozen["provider_identities"][treatment["id"]]["model"]):
                key = treatment["id"] + "_versus_" + reference["id"]
                contrasts[key] = _cluster_difference(rows, treatment["id"], reference["id"])
    return {"schema": "eal2-cross-model-analysis/1", "study_kind": frozen["study_kind"],
            "interpretation": frozen["interpretation"], "ledger_status": ledger["status"],
            "frozen_requests": len(frozen["cases"]), "attempts": len(rows),
            "root_count": len({case["root_id"] for case in frozen["cases"]}),
            "explanation_adjudication": "complete" if adjudications is not None else "unavailable",
            "conditions": summaries, "within_model_paired_contrasts": contrasts,
            "limitation": "Synthetic repeated states share roots; root bootstrap is descriptive. Host status is final for checked arms. No unreviewed prose is counted faithful."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--explanation-review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyse(args.run_directory, args.explanation_review)
    if args.output:
        write_json(args.output, report)
    else:
        print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
