"""Check declared design adequacy for schema 1.2; not scientific validation."""
from __future__ import annotations

import math
import re

from validate_workflow import purpose_set

READY = {"preregisterable", "approved", "preregistered", "running", "complete"}
PROBABILITIES = {
    "power", "assurance", "correct-discrimination", "joint-success-probability",
    "false-positive-rate", "coverage", "inconclusive-probability",
    "failure-probability", "budget-overrun-probability",
}
MINIMUM = {"power", "assurance", "correct-discrimination", "joint-success-probability", "coverage"}
METRICS = PROBABILITIES | {"interval-half-width", "absolute-bias", "expected-loss", "expected-cost"}
INFORMATION = {"power", "assurance", "correct-discrimination", "joint-success-probability",
               "interval-half-width", "expected-loss", "failure-probability"}
UNEXECUTED = re.compile(r"^(planned\b|replace with\b|tbd\b|todo\b|not yet\b)", re.I)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    return text(value) and not UNEXECUTED.match(value.strip())


def records(value, label, errors):
    indexed = {}
    if not isinstance(value, list) or not value:
        errors.append(f"{label} requires a non-empty record list")
        return indexed
    for row in value:
        if not isinstance(row, dict) or not text(row.get("id")):
            errors.append(f"{label} records require a text id")
            continue
        if row["id"] in indexed:
            errors.append(f"{label} contains duplicate id {row['id']}")
        indexed[row["id"]] = row
    return indexed


def refs(value, allowed, label, errors):
    if not isinstance(value, list) or not value or not all(text(x) for x in value):
        errors.append(f"{label} requires a non-empty identifier list")
        return set()
    selected = set(value)
    if len(selected) != len(value) or selected - set(allowed):
        errors.append(f"{label} contains duplicate or unresolved identifiers")
    return selected


def index_existing(value):
    return {x["id"]: x for x in value if isinstance(x, dict) and text(x.get("id"))} if isinstance(value, list) else {}


def need_text(record, fields, label, errors):
    for key in fields:
        if not text(record.get(key)):
            errors.append(f"{label}.{key} requires an explanation")


def audit_design(data, errors):
    if data.get("schema_version") != "1.2":
        return
    label = "design_assessment"
    assessment = data.get(label)
    if not isinstance(assessment, dict):
        errors.append("schema 1.2 requires design_assessment")
        return
    mode = assessment.get("mode")
    state = assessment.get("status")
    if mode not in ("quantitative", "nonstatistical"):
        errors.append(f"{label}.mode must be quantitative or nonstatistical")
    if state not in ("planned", "evaluated"):
        errors.append(f"{label}.status must be planned or evaluated")
    if data.get("status") in {"concept", "superseded"}:
        return
    ready = data.get("status") in READY
    if ready and state != "evaluated":
        errors.append("ready status requires evaluated design_assessment")
    need_text(assessment, ("decision_use", "effect_or_precision_basis", "pilot_basis",
                          "selection_rationale"), label, errors)
    estimands = index_existing(data.get("estimands"))
    primary = refs(assessment.get("primary_estimand_ids"), estimands,
                   f"{label}.primary_estimand_ids", errors)
    hypotheses = index_existing(data.get("hypotheses"))
    purposes = purpose_set(data)
    if mode == "nonstatistical":
        if "equivalence" in purposes or any(
            h.get("kind") in {"statistical-null", "statistical-alternative"} for h in hypotheses.values()
        ):
            errors.append("nonstatistical assessment cannot support declared statistical hypotheses or equivalence")
        review = assessment.get("nonstatistical_assessment")
        if not isinstance(review, dict):
            review = {}
        need_text(review, ("criterion", "assessment", "evidence"), f"{label}.nonstatistical_assessment", errors)
        if ready and not evidence(review.get("evidence")):
            errors.append("ready nonstatistical assessment requires actual evidence")
    elif mode == "quantitative":
        audit_quantitative(assessment, estimands, primary, ready, errors)

    claims = data.get("claims", [])
    explanatory = bool(purposes & {"theory-discrimination", "mechanism-discrimination"}) or (
        isinstance(claims, list) and any(isinstance(c, dict) and c.get("claim_type") == "mechanistic" for c in claims)
    )
    if explanatory:
        review = assessment.get("discrimination")
        if not isinstance(review, dict):
            review = {}
        rivals = refs(review.get("rival_hypothesis_ids"), hypotheses, "discrimination.rival_hypothesis_ids", errors)
        if len(rivals) < 2:
            errors.append("discrimination requires at least two distinct rival hypotheses")
        predictions = index_existing(data.get("predictions"))
        separating = refs(review.get("separating_prediction_ids"), predictions,
                          "discrimination.separating_prediction_ids", errors)
        covered = set()
        for identifier in separating & set(predictions):
            row = predictions[identifier]
            own = set(x for x in row.get("hypothesis_ids", []) if text(x)) if isinstance(row.get("hypothesis_ids"), list) else set()
            other = set(x for x in row.get("discriminates_from_hypothesis_ids", []) if text(x)) if isinstance(row.get("discriminates_from_hypothesis_ids"), list) else set()
            if row.get("shared_prediction") is not False or not (own & rivals) or not (other & rivals) or len((own | other) & rivals) < 2:
                errors.append(f"discrimination prediction {identifier} does not separate listed rivals")
            else:
                covered.update((own | other) & rivals)
        if rivals - covered:
            errors.append("discrimination leaves listed rivals without a separating prediction")
        need_text(review, ("assessment", "evidence"), "discrimination", errors)
        if ready and not evidence(review.get("evidence")):
            errors.append("ready discrimination requires actual design evidence")
        targets = assessment.get("targets", [])
        if ready and mode == "quantitative" and not (
            isinstance(targets, list) and any(isinstance(t, dict) and t.get("metric") == "correct-discrimination" for t in targets)
        ):
            errors.append("quantitative explanatory claim requires a correct-discrimination target")


def audit_quantitative(assessment, estimands, primary, ready, errors):
    need_text(assessment, ("budget_unit", "scenario_coverage"), "design_assessment", errors)
    designs = records(assessment.get("candidate_designs"), "candidate_designs", errors)
    if len(designs) < 2 and not text(assessment.get("single_design_reason")):
        errors.append("compare at least two candidate designs or give single_design_reason")
    selected = assessment.get("selected_design_id")
    if not text(selected) or selected not in designs:
        errors.append("selected_design_id must resolve to a candidate")
        selected = None
    budget = assessment.get("budget_limit")
    if not number(budget) or budget < 0:
        errors.append("budget_limit must be a finite nonnegative number")
    for identifier, design in designs.items():
        need_text(design, ("allocation", "cost_unit"), f"candidate {identifier}", errors)
        count = design.get("independent_units")
        if type(count) is not int or count < 1:
            errors.append(f"candidate {identifier} requires positive integer independent_units")
        cost = design.get("cost")
        if not number(cost) or cost < 0:
            errors.append(f"candidate {identifier} requires finite nonnegative cost")
        if design.get("cost_unit") != assessment.get("budget_unit"):
            errors.append(f"candidate {identifier} cost and budget units differ")
        if ready and identifier == selected and number(cost) and number(budget) and cost > budget:
            errors.append("selected design exceeds budget_limit")

    scenarios = records(assessment.get("scenarios"), "scenarios", errors)
    for identifier, scenario in scenarios.items():
        need_text(scenario, ("description",), f"scenario {identifier}", errors)
        if not text(scenario.get("kind")) or scenario["kind"] not in {"null", "boundary", "meaningful", "adverse", "rival", "reference"}:
            errors.append(f"scenario {identifier} has unsupported kind")
    targets = records(assessment.get("targets"), "targets", errors)
    needed = set()
    information_covered = set()
    calibrated = set()
    for identifier, target in targets.items():
        linked = refs(target.get("estimand_ids"), estimands, f"target {identifier}.estimand_ids", errors)
        required = refs(target.get("required_scenario_ids"), scenarios, f"target {identifier}.required_scenario_ids", errors)
        needed.update((selected, identifier, s) for s in required)
        metric = target.get("metric")
        if not text(metric):
            metric = None
        if metric not in METRICS:
            errors.append(f"target {identifier} has unsupported metric")
        direction = "at-least" if metric in MINIMUM else "at-most"
        if target.get("direction") != direction:
            errors.append(f"target {identifier} requires direction {direction}")
        threshold = target.get("threshold")
        if not number(threshold) or threshold < 0 or (metric in PROBABILITIES and threshold > 1):
            errors.append(f"target {identifier} has invalid numerical threshold")
        need_text(target, ("units", "rationale"), f"target {identifier}", errors)
        if metric in PROBABILITIES and target.get("units") != "probability":
            errors.append(f"target {identifier} must use probability units")
        if metric in INFORMATION:
            information_covered.update(linked)
        if metric in {"coverage", "false-positive-rate"}:
            calibrated.update(linked)
        if ready and metric == "false-positive-rate" and not any(
            scenarios[s].get("kind") in ("null", "boundary") for s in required & set(scenarios)
        ):
            errors.append(f"target {identifier} requires a null or boundary calibration scenario")
    if primary - information_covered:
        errors.append("information targets do not cover every principal estimand")
    if ready and primary - calibrated:
        errors.append("calibration targets do not cover every principal estimand")

    result_rows = assessment.get("results")
    if not isinstance(result_rows, list):
        errors.append("design_assessment.results must be a list")
        result_rows = []
    evaluated = set()
    for row in result_rows:
        if not isinstance(row, dict):
            errors.append("design assessment results must be objects")
            continue
        keys = (row.get("design_id"), row.get("target_id"), row.get("scenario_id"))
        if not all(text(x) for x in keys) or keys[0] not in designs or keys[1] not in targets or keys[2] not in scenarios:
            errors.append("design result contains unresolved design, target or scenario")
            continue
        if keys in evaluated:
            errors.append("duplicate design/target/scenario result")
        evaluated.add(keys)
        target = targets[keys[1]]
        metric = target.get("metric") if text(target.get("metric")) else None
        value = row.get("value")
        if not number(value) or value < 0 or (metric in PROBABILITIES and value > 1):
            errors.append("design result requires a finite value in its metric's range")
            continue
        if not evidence(row.get("evidence")):
            errors.append("design result requires actual calculation evidence")
        low = high = value
        if row.get("method") == "simulation":
            reps, mcse, interval = row.get("replications"), row.get("mcse"), row.get("mc_interval")
            if type(reps) is not int or reps < 2 or not number(mcse) or mcse < 0:
                errors.append("simulation result requires replications >= 2 and finite nonnegative mcse")
            if not isinstance(interval, list) or len(interval) != 2 or not all(number(x) for x in interval):
                errors.append("simulation result requires a finite mc_interval")
                continue
            low, high = interval
            if low > value or high < value:
                errors.append("mc_interval must contain the simulated value")
            if metric in PROBABILITIES and not (0 <= low < high <= 1):
                errors.append("probability mc_interval must be nondegenerate within [0,1]")
        elif row.get("method") == "analytic":
            if any(row.get(key) is not None for key in ("replications", "mcse", "mc_interval")):
                errors.append("analytic result must not claim Monte Carlo quantities")
        else:
            errors.append("design result method must be analytic or simulation")
        bound = low if target.get("direction") == "at-least" else high
        threshold = target.get("threshold")
        if ready and keys in needed and number(threshold) and (
            (target.get("direction") == "at-least" and bound < threshold)
            or (target.get("direction") == "at-most" and bound > threshold)
        ):
            errors.append(f"selected design does not meet target {keys[1]} in scenario {keys[2]}")
    if ready:
        if needed - evaluated:
            errors.append("selected design lacks required evaluated target/scenario cells")
        missing_designs = set(designs) - {x[0] for x in evaluated}
        if missing_designs:
            errors.append("candidate designs lack comparison results: " + ", ".join(sorted(missing_designs)))
