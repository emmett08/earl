#!/usr/bin/env python3
"""Validate a scientific investigation protocol and its readiness claim."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from validate_workflow import audit_workflow, needs_hypotheses
from validate_design import audit_design


ROOT_FIELDS = (
    "schema_version",
    "investigation_id",
    "title",
    "version",
    "status",
    "question",
    "primary_claim_id",
    "scope",
    "claims",
    "assumptions",
    "hypotheses",
    "predictions",
    "constructs",
    "measurements",
    "design",
    "units",
    "interventions_or_exposures",
    "controls",
    "confounds",
    "estimands",
    "identification",
    "sampling",
    "analysis",
    "decision_matrix",
    "bias_assessment",
    "ethics_and_safety",
    "feasibility",
    "reproducibility",
    "execution",
    "provenance",
)
STATUSES = {
    "concept",
    "specified",
    "preregisterable",
    "approved",
    "preregistered",
    "running",
    "complete",
    "superseded",
}
SPECIFIED_STATUSES = STATUSES - {"concept", "superseded"}
READY_STATUSES = {
    "preregisterable",
    "approved",
    "preregistered",
    "running",
    "complete",
}
CLAIM_TYPES = {
    "existence",
    "difference",
    "association",
    "prediction",
    "causal",
    "mechanistic",
    "measurement",
    "descriptive",
}
CLAIM_ROLES = {"primary", "secondary", "bridge", "background"}
ASSUMPTION_ROLES = {
    "theoretical",
    "derivational",
    "measurement",
    "identification",
    "sampling",
    "analysis",
    "transport",
    "operational",
}
ASSUMPTION_STATUSES = {"supported", "tested", "untested", "contested", "failed"}
HYPOTHESIS_KINDS = {
    "substantive",
    "mechanism",
    "rival",
    "statistical-null",
    "statistical-alternative",
    "measurement",
}
SCIENTIFIC_HYPOTHESIS_KINDS = {
    "substantive",
    "mechanism",
    "rival",
    "measurement",
}
CONSTRUCT_ROLES = {
    "intervention",
    "exposure",
    "outcome",
    "mediator",
    "moderator",
    "confounder",
    "selection",
    "diagnostic",
}
INTERVENTION_KINDS = {"intervention", "exposure"}
ADMISSIBILITIES = {
    "admissible",
    "conditional",
    "prohibited",
    "unknown",
    "not-applicable",
}
CONTROL_TYPES = {
    "negative",
    "positive",
    "sham",
    "procedural",
    "baseline",
    "placebo",
    "active-comparator",
    "manipulation",
    "off-target",
    "recovery",
    "calibration",
    "falsification",
    "other",
}
ESTIMAND_TYPES = {
    "descriptive",
    "associational",
    "predictive",
    "causal",
    "mechanistic",
    "measurement",
}
IDENTIFICATION_STATUSES = {
    "identified",
    "partially-identified",
    "nonidentified",
    "not-assessed",
}
DISCRIMINATION_RESULTS = {
    "parameter-estimated",
    "pattern-generated",
    "feasibility-demonstrated",
    "adequacy-assessed",
    "favours-hypothesis",
    "contradicts-hypothesis",
    "fails-to-discriminate",
    "invalid-measurement",
    "failed-manipulation",
    "assumption-failure",
    "inconclusive",
}
FAILURE_RESULTS = {
    "fails-to-discriminate",
    "invalid-measurement",
    "failed-manipulation",
    "assumption-failure",
    "inconclusive",
}
CLAIM_DISPOSITIONS = {
    "strengthen",
    "weaken",
    "contradict",
    "no-change",
    "revise",
    "suspend",
}
BIAS_TYPES = {
    "confounding",
    "selection",
    "measurement",
    "leakage",
    "circularity",
    "researcher-flexibility",
    "expectancy",
    "attrition",
    "interference",
    "reporting",
    "other",
}
REVIEW_STATUSES = {
    "not-required",
    "planned",
    "pending",
    "approved",
    "rejected",
    "expired",
}
FEASIBILITY_STATUSES = {
    "conceptual",
    "partially-feasible",
    "feasible",
    "operational",
    "currently-infeasible",
}
PREREGISTRATION_STATUSES = {"not-planned", "planned", "registered", "amended"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PLACEHOLDER = re.compile(
    r"^(replace with|not yet|tbd\b|todo\b|unknown: not assessed)",
    re.IGNORECASE,
)


def present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def placeholder(value: Any) -> bool:
    return present(value) and bool(PLACEHOLDER.match(value.strip()))


def require_fields(
    owner: str,
    value: Any,
    fields: tuple[str, ...],
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{owner} must be an object")
        return {}
    for field in fields:
        if field not in value:
            errors.append(f"{owner} missing {field}")
    return value


def require_text(
    owner: str,
    value: dict[str, Any],
    fields: tuple[str, ...],
    errors: list[str],
) -> None:
    for field in fields:
        if field in value and not present(value.get(field)):
            errors.append(f"{owner}.{field} must be a non-empty string")


def enum_value(
    owner: str,
    value: Any,
    allowed: set[str],
    errors: list[str],
) -> None:
    if value not in allowed:
        errors.append(
            f"{owner} has invalid value {value!r}; expected one of "
            + ", ".join(sorted(allowed))
        )


def string_list(
    owner: str,
    value: Any,
    errors: list[str],
    *,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{owner} must be a list")
        return []
    result = [item.strip() for item in value if present(item)]
    if len(result) != len(value):
        errors.append(f"{owner} must contain only non-empty strings")
    if not allow_empty and not result:
        errors.append(f"{owner} must not be empty")
    if len(result) != len(set(result)):
        errors.append(f"{owner} contains duplicate values")
    return result


def records(
    owner: str,
    value: Any,
    required: tuple[str, ...],
    global_ids: dict[str, str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{owner} must be a list")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(value):
        item_owner = f"{owner}[{position}]"
        if not isinstance(item, dict):
            errors.append(f"{item_owner} must be an object")
            continue
        identifier = item.get("id")
        if not present(identifier):
            errors.append(f"{item_owner}.id must be a non-empty string")
            continue
        identifier = identifier.strip()
        if identifier in global_ids:
            errors.append(
                f"duplicate global id {identifier}: "
                f"{global_ids[identifier]} and {owner}"
            )
        else:
            global_ids[identifier] = owner
        if identifier in indexed:
            errors.append(f"duplicate {owner} id: {identifier}")
        indexed[identifier] = item
        for field in required:
            if field not in item:
                errors.append(f"{owner} {identifier} missing {field}")
    return indexed


def check_refs(
    owner: str,
    value: Any,
    available: set[str],
    errors: list[str],
    *,
    allow_empty: bool = True,
) -> list[str]:
    result = string_list(owner, value, errors, allow_empty=allow_empty)
    unresolved = sorted(set(result) - available)
    if unresolved:
        errors.append(f"{owner} has unresolved ids: {', '.join(unresolved)}")
    return result


def timestamp(
    owner: str,
    value: Any,
    errors: list[str],
    *,
    nullable: bool = False,
) -> None:
    if value is None and nullable:
        return
    if not present(value):
        errors.append(f"{owner} must be an ISO-8601 timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{owner} is not valid ISO-8601: {value!r}")
        return
    if parsed.tzinfo is None:
        errors.append(f"{owner} must include a timezone")


def placeholder_paths(value: Any, owner: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{owner}.{key}" if owner else key
            found.extend(placeholder_paths(item, child))
    elif isinstance(value, list):
        for position, item in enumerate(value):
            found.extend(placeholder_paths(item, f"{owner}[{position}]"))
    elif placeholder(value):
        found.append(owner)
    return found


def audit(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, int] = {}

    if not isinstance(data, dict):
        return {
            "valid": False,
            "status": None,
            "errors": ["protocol root must be a JSON object"],
            "warnings": [],
            "metrics": {},
        }

    for field in ROOT_FIELDS:
        if field not in data:
            errors.append(f"missing root field: {field}")

    require_text(
        "protocol",
        data,
        (
            "schema_version",
            "investigation_id",
            "title",
            "version",
            "question",
            "primary_claim_id",
        ),
        errors,
    )
    if data.get("schema_version") not in ("1.0", "1.1", "1.2"):
        errors.append("schema_version must be '1.0', '1.1' or '1.2'")
    if present(data.get("version")) and not SEMVER.match(data["version"]):
        errors.append("version must use MAJOR.MINOR.PATCH")
    status = data.get("status")
    enum_value("status", status, STATUSES, errors)
    specified = status in SPECIFIED_STATUSES
    ready = status in READY_STATUSES

    scope = require_fields(
        "scope",
        data.get("scope"),
        (
            "system_or_population",
            "conditions",
            "spatial_scope",
            "temporal_scope",
            "exclusions",
            "knowledge_cut",
        ),
        errors,
    )
    require_text(
        "scope",
        scope,
        (
            "system_or_population",
            "conditions",
            "spatial_scope",
            "temporal_scope",
            "knowledge_cut",
        ),
        errors,
    )
    if "exclusions" in scope:
        string_list("scope.exclusions", scope.get("exclusions"), errors)

    global_ids: dict[str, str] = {}
    claims = records(
        "claims",
        data.get("claims"),
        (
            "statement",
            "claim_type",
            "role",
            "scope_limit",
            "success_consequence",
            "failure_consequence",
        ),
        global_ids,
        errors,
    )
    for identifier, item in claims.items():
        owner = f"claims.{identifier}"
        require_text(
            owner,
            item,
            (
                "statement",
                "scope_limit",
                "success_consequence",
                "failure_consequence",
            ),
            errors,
        )
        enum_value(f"{owner}.claim_type", item.get("claim_type"), CLAIM_TYPES, errors)
        enum_value(f"{owner}.role", item.get("role"), CLAIM_ROLES, errors)
    primary_claim_id = data.get("primary_claim_id")
    if present(primary_claim_id) and primary_claim_id not in claims:
        errors.append(f"primary_claim_id is unresolved: {primary_claim_id}")
    primary_ids = {
        identifier
        for identifier, item in claims.items()
        if item.get("role") == "primary"
    }
    if len(primary_ids) != 1:
        errors.append("claims must contain exactly one primary claim")
    elif primary_claim_id not in primary_ids:
        errors.append("primary_claim_id must identify the claim with role 'primary'")

    assumptions = records(
        "assumptions",
        data.get("assumptions"),
        (
            "statement",
            "role",
            "status",
            "test_or_justification",
            "failure_consequence",
        ),
        global_ids,
        errors,
    )
    for identifier, item in assumptions.items():
        owner = f"assumptions.{identifier}"
        require_text(
            owner,
            item,
            ("statement", "test_or_justification", "failure_consequence"),
            errors,
        )
        enum_value(f"{owner}.role", item.get("role"), ASSUMPTION_ROLES, errors)
        enum_value(
            f"{owner}.status", item.get("status"), ASSUMPTION_STATUSES, errors
        )

    hypotheses = records(
        "hypotheses",
        data.get("hypotheses"),
        (
            "label",
            "kind",
            "statement",
            "claim_ids",
            "auxiliary_assumption_ids",
            "scope",
        ),
        global_ids,
        errors,
    )
    for identifier, item in hypotheses.items():
        owner = f"hypotheses.{identifier}"
        require_text(owner, item, ("label", "statement", "scope"), errors)
        enum_value(f"{owner}.kind", item.get("kind"), HYPOTHESIS_KINDS, errors)
        check_refs(
            f"{owner}.claim_ids",
            item.get("claim_ids"),
            set(claims),
            errors,
            allow_empty=False,
        )
        check_refs(
            f"{owner}.auxiliary_assumption_ids",
            item.get("auxiliary_assumption_ids"),
            set(assumptions),
            errors,
        )

    constructs = records(
        "constructs",
        data.get("constructs"),
        (
            "name",
            "definition",
            "role",
            "scope",
            "proxy_for_claim_ids",
            "validity_evidence",
            "validity_threats",
        ),
        global_ids,
        errors,
    )
    for identifier, item in constructs.items():
        owner = f"constructs.{identifier}"
        require_text(owner, item, ("name", "definition", "scope"), errors)
        enum_value(f"{owner}.role", item.get("role"), CONSTRUCT_ROLES, errors)
        check_refs(
            f"{owner}.proxy_for_claim_ids",
            item.get("proxy_for_claim_ids"),
            set(claims),
            errors,
        )
        string_list(f"{owner}.validity_evidence", item.get("validity_evidence"), errors)
        string_list(f"{owner}.validity_threats", item.get("validity_threats"), errors)

    measurements = records(
        "measurements",
        data.get("measurements"),
        (
            "construct_ids",
            "observable",
            "instrument_or_procedure",
            "scale_or_units",
            "timing",
            "preprocessing",
            "calibration",
            "reliability",
            "validity",
            "measurement_invariance",
            "reactivity",
            "error_model",
            "blinding",
        ),
        global_ids,
        errors,
    )
    measurement_text_fields = (
        "observable",
        "instrument_or_procedure",
        "scale_or_units",
        "timing",
        "preprocessing",
        "calibration",
        "reliability",
        "validity",
        "measurement_invariance",
        "reactivity",
        "error_model",
        "blinding",
    )
    for identifier, item in measurements.items():
        owner = f"measurements.{identifier}"
        require_text(owner, item, measurement_text_fields, errors)
        check_refs(
            f"{owner}.construct_ids",
            item.get("construct_ids"),
            set(constructs),
            errors,
            allow_empty=False,
        )

    interventions = records(
        "interventions_or_exposures",
        data.get("interventions_or_exposures"),
        (
            "kind",
            "description",
            "target",
            "implementation",
            "dose_or_intensity",
            "timing",
            "admissibility",
            "manipulation_checks",
            "off_target_checks",
            "recovery_checks",
        ),
        global_ids,
        errors,
    )
    for identifier, item in interventions.items():
        owner = f"interventions_or_exposures.{identifier}"
        require_text(
            owner,
            item,
            ("description", "target", "implementation", "dose_or_intensity", "timing"),
            errors,
        )
        enum_value(f"{owner}.kind", item.get("kind"), INTERVENTION_KINDS, errors)
        enum_value(
            f"{owner}.admissibility", item.get("admissibility"), ADMISSIBILITIES, errors
        )
        for field in ("manipulation_checks", "off_target_checks", "recovery_checks"):
            string_list(f"{owner}.{field}", item.get(field), errors)

    controls = records(
        "controls",
        data.get("controls"),
        (
            "control_type",
            "description",
            "failure_mode_addressed",
            "implementation",
            "diagnostic_consequence",
        ),
        global_ids,
        errors,
    )
    for identifier, item in controls.items():
        owner = f"controls.{identifier}"
        require_text(
            owner,
            item,
            (
                "description",
                "failure_mode_addressed",
                "implementation",
                "diagnostic_consequence",
            ),
            errors,
        )
        enum_value(
            f"{owner}.control_type", item.get("control_type"), CONTROL_TYPES, errors
        )

    confounds = records(
        "confounds",
        data.get("confounds"),
        (
            "description",
            "causal_or_measurement_path",
            "control_or_adjustment",
            "diagnostic",
            "residual_risk",
        ),
        global_ids,
        errors,
    )
    for identifier, item in confounds.items():
        require_text(
            f"confounds.{identifier}",
            item,
            (
                "description",
                "causal_or_measurement_path",
                "control_or_adjustment",
                "diagnostic",
                "residual_risk",
            ),
            errors,
        )

    estimands = records(
        "estimands",
        data.get("estimands"),
        (
            "claim_ids",
            "estimand_type",
            "population_or_system",
            "intervention_or_exposure",
            "comparator",
            "outcome_measurement_ids",
            "time",
            "summary_measure",
            "interpretation",
        ),
        global_ids,
        errors,
    )
    for identifier, item in estimands.items():
        owner = f"estimands.{identifier}"
        require_text(
            owner,
            item,
            (
                "population_or_system",
                "intervention_or_exposure",
                "comparator",
                "time",
                "summary_measure",
                "interpretation",
            ),
            errors,
        )
        enum_value(
            f"{owner}.estimand_type", item.get("estimand_type"), ESTIMAND_TYPES, errors
        )
        check_refs(
            f"{owner}.claim_ids",
            item.get("claim_ids"),
            set(claims),
            errors,
            allow_empty=False,
        )
        check_refs(
            f"{owner}.outcome_measurement_ids",
            item.get("outcome_measurement_ids"),
            set(measurements),
            errors,
            allow_empty=False,
        )

    predictions = records(
        "predictions",
        data.get("predictions"),
        (
            "hypothesis_ids",
            "claim_ids",
            "estimand_ids",
            "measurement_ids",
            "expected_pattern",
            "direction",
            "magnitude_or_range",
            "time_window",
            "tolerance",
            "auxiliary_assumption_ids",
            "discriminates_from_hypothesis_ids",
            "shared_prediction",
        ),
        global_ids,
        errors,
    )
    for identifier, item in predictions.items():
        owner = f"predictions.{identifier}"
        require_text(
            owner,
            item,
            (
                "expected_pattern",
                "direction",
                "magnitude_or_range",
                "time_window",
                "tolerance",
            ),
            errors,
        )
        check_refs(
            f"{owner}.hypothesis_ids",
            item.get("hypothesis_ids"),
            set(hypotheses),
            errors,
            allow_empty=False,
        )
        check_refs(
            f"{owner}.claim_ids",
            item.get("claim_ids"),
            set(claims),
            errors,
            allow_empty=False,
        )
        check_refs(
            f"{owner}.estimand_ids",
            item.get("estimand_ids"),
            set(estimands),
            errors,
            allow_empty=False,
        )
        check_refs(
            f"{owner}.measurement_ids",
            item.get("measurement_ids"),
            set(measurements),
            errors,
            allow_empty=False,
        )
        check_refs(
            f"{owner}.auxiliary_assumption_ids",
            item.get("auxiliary_assumption_ids"),
            set(assumptions),
            errors,
        )
        rivals = check_refs(
            f"{owner}.discriminates_from_hypothesis_ids",
            item.get("discriminates_from_hypothesis_ids"),
            set(hypotheses),
            errors,
        )
        if not isinstance(item.get("shared_prediction"), bool):
            errors.append(f"{owner}.shared_prediction must be boolean")
        if item.get("shared_prediction") is False and not rivals:
            errors.append(
                f"{owner} is non-shared but names no hypothesis it discriminates from"
            )
        own_hypotheses = set(item.get("hypothesis_ids", []))
        overlap = own_hypotheses & set(rivals)
        if overlap:
            errors.append(
                f"{owner} cannot discriminate a hypothesis from itself: "
                + ", ".join(sorted(overlap))
            )

    design = require_fields(
        "design",
        data.get("design"),
        (
            "design_type",
            "rationale",
            "setting",
            "temporal_structure",
            "assignment_method",
            "allocation_concealment",
            "masking",
            "comparator",
            "control_ids",
        ),
        errors,
    )
    require_text(
        "design",
        design,
        (
            "design_type",
            "rationale",
            "setting",
            "temporal_structure",
            "assignment_method",
            "allocation_concealment",
            "masking",
            "comparator",
        ),
        errors,
    )
    if "control_ids" in design:
        check_refs(
            "design.control_ids", design.get("control_ids"), set(controls), errors
        )

    units = require_fields(
        "units",
        data.get("units"),
        (
            "target_population_or_system",
            "sampling_frame",
            "experimental_unit",
            "observational_unit",
            "assignment_unit",
            "analysis_unit",
            "inclusion_criteria",
            "exclusion_criteria",
            "recruitment_or_selection",
        ),
        errors,
    )
    require_text(
        "units",
        units,
        (
            "target_population_or_system",
            "sampling_frame",
            "experimental_unit",
            "observational_unit",
            "assignment_unit",
            "analysis_unit",
            "recruitment_or_selection",
        ),
        errors,
    )
    for field in ("inclusion_criteria", "exclusion_criteria"):
        if field in units:
            string_list(f"units.{field}", units.get(field), errors)

    identification = require_fields(
        "identification",
        data.get("identification"),
        (
            "target_estimand_ids",
            "status",
            "causal_and_measurement_structure",
            "assumption_ids",
            "identified_parameters",
            "nonidentified_alternatives",
            "threats",
            "diagnostics",
            "rescue_actions",
        ),
        errors,
    )
    if "status" in identification:
        enum_value(
            "identification.status",
            identification.get("status"),
            IDENTIFICATION_STATUSES,
            errors,
        )
    require_text(
        "identification",
        identification,
        ("causal_and_measurement_structure",),
        errors,
    )
    target_estimand_ids = check_refs(
        "identification.target_estimand_ids",
        identification.get("target_estimand_ids"),
        set(estimands),
        errors,
    )
    check_refs(
        "identification.assumption_ids",
        identification.get("assumption_ids"),
        set(assumptions),
        errors,
    )
    for field in (
        "identified_parameters",
        "nonidentified_alternatives",
        "threats",
        "diagnostics",
        "rescue_actions",
    ):
        if field in identification:
            string_list(
                f"identification.{field}", identification.get(field), errors
            )

    sampling = require_fields(
        "sampling",
        data.get("sampling"),
        (
            "method",
            "sample_size_or_information_target",
            "inputs",
            "dependence_structure",
            "multiplicity",
            "attrition_or_loss",
            "result",
            "sensitivity_analysis",
            "stopping_implications",
        ),
        errors,
    )
    require_text(
        "sampling",
        sampling,
        (
            "method",
            "sample_size_or_information_target",
            "dependence_structure",
            "multiplicity",
            "attrition_or_loss",
            "result",
            "sensitivity_analysis",
            "stopping_implications",
        ),
        errors,
    )
    if "inputs" in sampling:
        string_list("sampling.inputs", sampling.get("inputs"), errors)

    analysis = require_fields(
        "analysis",
        data.get("analysis"),
        (
            "preprocessing_lock",
            "exclusion_lock",
            "models",
            "contrasts",
            "uncertainty",
            "multiplicity",
            "missing_data",
            "stopping_rule",
            "robustness_checks",
            "software_and_versions",
            "inconclusive_handling",
        ),
        errors,
    )
    require_text(
        "analysis",
        analysis,
        (
            "preprocessing_lock",
            "exclusion_lock",
            "uncertainty",
            "multiplicity",
            "missing_data",
            "stopping_rule",
            "inconclusive_handling",
        ),
        errors,
    )
    models = records(
        "analysis.models",
        analysis.get("models"),
        (
            "estimand_ids",
            "model_or_procedure",
            "assumptions",
            "diagnostics",
            "outputs",
        ),
        global_ids,
        errors,
    )
    for identifier, item in models.items():
        owner = f"analysis.models.{identifier}"
        require_text(owner, item, ("model_or_procedure",), errors)
        check_refs(
            f"{owner}.estimand_ids",
            item.get("estimand_ids"),
            set(estimands),
            errors,
            allow_empty=False,
        )
        for field in ("assumptions", "diagnostics", "outputs"):
            string_list(
                f"{owner}.{field}",
                item.get(field),
                errors,
                allow_empty=(field == "assumptions"),
            )
    for field in (
        "contrasts",
        "robustness_checks",
        "software_and_versions",
    ):
        if field in analysis:
            string_list(f"analysis.{field}", analysis.get(field), errors)

    decision_matrix = records(
        "decision_matrix",
        data.get("decision_matrix"),
        (
            "prediction_ids",
            "observation_region",
            "analysis_outputs",
            "decision_rule",
            "discrimination_result",
            "claim_effects",
            "hypothesis_effects",
            "assumption_failure_response",
            "next_action",
        ),
        global_ids,
        errors,
    )
    matrix_prediction_coverage: set[str] = set()
    matrix_claim_coverage: set[str] = set()
    discrimination_results: set[str] = set()
    for identifier, item in decision_matrix.items():
        owner = f"decision_matrix.{identifier}"
        require_text(
            owner,
            item,
            (
                "observation_region",
                "decision_rule",
                "assumption_failure_response",
                "next_action",
            ),
            errors,
        )
        prediction_refs = check_refs(
            f"{owner}.prediction_ids",
            item.get("prediction_ids"),
            set(predictions),
            errors,
        )
        matrix_prediction_coverage.update(prediction_refs)
        string_list(
            f"{owner}.analysis_outputs",
            item.get("analysis_outputs"),
            errors,
            allow_empty=False,
        )
        result = item.get("discrimination_result")
        enum_value(
            f"{owner}.discrimination_result",
            result,
            DISCRIMINATION_RESULTS,
            errors,
        )
        if isinstance(result, str):
            discrimination_results.add(result)
        effects = item.get("claim_effects")
        if not isinstance(effects, list) or not effects:
            errors.append(f"{owner}.claim_effects must be a non-empty list")
        else:
            for position, effect in enumerate(effects):
                effect_owner = f"{owner}.claim_effects[{position}]"
                effect = require_fields(
                    effect_owner,
                    effect,
                    ("claim_ids", "disposition", "rationale", "scope_limit"),
                    errors,
                )
                refs_found = check_refs(
                    f"{effect_owner}.claim_ids",
                    effect.get("claim_ids"),
                    set(claims),
                    errors,
                    allow_empty=False,
                )
                matrix_claim_coverage.update(refs_found)
                enum_value(
                    f"{effect_owner}.disposition",
                    effect.get("disposition"),
                    CLAIM_DISPOSITIONS,
                    errors,
                )
                require_text(
                    effect_owner, effect, ("rationale", "scope_limit"), errors
                )
        string_list(
            f"{owner}.hypothesis_effects",
            item.get("hypothesis_effects"),
            errors,
            allow_empty=not needs_hypotheses(data),
        )

    bias = require_fields(
        "bias_assessment",
        data.get("bias_assessment"),
        (
            "risks",
            "researcher_degrees_of_freedom",
            "negative_controls",
            "positive_controls",
            "falsification_checks",
            "reporting_controls",
            "residual_limitations",
        ),
        errors,
    )
    bias_risks = records(
        "bias_assessment.risks",
        bias.get("risks"),
        (
            "risk_type",
            "mechanism",
            "prevention",
            "detection",
            "sensitivity_or_correction",
            "residual_risk",
        ),
        global_ids,
        errors,
    )
    for identifier, item in bias_risks.items():
        owner = f"bias_assessment.risks.{identifier}"
        require_text(
            owner,
            item,
            (
                "mechanism",
                "prevention",
                "detection",
                "sensitivity_or_correction",
                "residual_risk",
            ),
            errors,
        )
        enum_value(f"{owner}.risk_type", item.get("risk_type"), BIAS_TYPES, errors)
    for field in (
        "researcher_degrees_of_freedom",
        "negative_controls",
        "positive_controls",
        "falsification_checks",
        "reporting_controls",
        "residual_limitations",
    ):
        if field in bias:
            string_list(f"bias_assessment.{field}", bias.get(field), errors)

    ethics = require_fields(
        "ethics_and_safety",
        data.get("ethics_and_safety"),
        (
            "applicable",
            "rationale",
            "risks",
            "mitigations",
            "monitoring",
            "stopping_rules",
            "stop_authority",
            "review_status",
            "post_stop_actions",
        ),
        errors,
    )
    if "applicable" in ethics and not isinstance(ethics.get("applicable"), bool):
        errors.append("ethics_and_safety.applicable must be boolean")
    require_text(
        "ethics_and_safety", ethics, ("rationale", "stop_authority"), errors
    )
    if "review_status" in ethics:
        enum_value(
            "ethics_and_safety.review_status",
            ethics.get("review_status"),
            REVIEW_STATUSES,
            errors,
        )
    for field in (
        "risks",
        "mitigations",
        "monitoring",
        "stopping_rules",
        "post_stop_actions",
    ):
        if field in ethics:
            string_list(f"ethics_and_safety.{field}", ethics.get(field), errors)

    feasibility = require_fields(
        "feasibility",
        data.get("feasibility"),
        (
            "current_status",
            "apparatus_or_data",
            "access",
            "skills",
            "resources",
            "dependencies",
            "blockers",
            "fallback",
        ),
        errors,
    )
    if "current_status" in feasibility:
        enum_value(
            "feasibility.current_status",
            feasibility.get("current_status"),
            FEASIBILITY_STATUSES,
            errors,
        )
    require_text("feasibility", feasibility, ("access", "fallback"), errors)
    for field in (
        "apparatus_or_data",
        "skills",
        "resources",
        "dependencies",
        "blockers",
    ):
        if field in feasibility:
            string_list(f"feasibility.{field}", feasibility.get(field), errors)

    reproducibility = require_fields(
        "reproducibility",
        data.get("reproducibility"),
        (
            "preregistration_status",
            "registration",
            "immutable_materials",
            "data_plan",
            "code_plan",
            "randomisation_or_seed_plan",
            "provenance_plan",
            "deviation_and_amendment_plan",
            "replication_plan",
        ),
        errors,
    )
    if "preregistration_status" in reproducibility:
        enum_value(
            "reproducibility.preregistration_status",
            reproducibility.get("preregistration_status"),
            PREREGISTRATION_STATUSES,
            errors,
        )
    require_text(
        "reproducibility",
        reproducibility,
        (
            "registration",
            "data_plan",
            "code_plan",
            "randomisation_or_seed_plan",
            "provenance_plan",
            "deviation_and_amendment_plan",
            "replication_plan",
        ),
        errors,
    )
    if "immutable_materials" in reproducibility:
        string_list(
            "reproducibility.immutable_materials",
            reproducibility.get("immutable_materials"),
            errors,
        )

    execution = require_fields(
        "execution",
        data.get("execution"),
        (
            "protocol_version_used",
            "started_at",
            "completed_at",
            "deviations",
            "data_location",
            "code_location",
            "observed_results",
            "interpretation_status",
        ),
        errors,
    )
    if "started_at" in execution:
        timestamp(
            "execution.started_at", execution.get("started_at"), errors, nullable=True
        )
    if "completed_at" in execution:
        timestamp(
            "execution.completed_at",
            execution.get("completed_at"),
            errors,
            nullable=True,
        )
    for field in ("deviations", "observed_results"):
        if field in execution:
            string_list(f"execution.{field}", execution.get(field), errors)
    if "interpretation_status" in execution and not present(
        execution.get("interpretation_status")
    ):
        errors.append("execution.interpretation_status must be a non-empty string")

    provenance = require_fields(
        "provenance",
        data.get("provenance"),
        (
            "authors",
            "created_at",
            "updated_at",
            "sources",
            "knowledge_cut",
            "change_log",
        ),
        errors,
    )
    for field in ("authors", "sources", "change_log"):
        if field in provenance:
            string_list(
                f"provenance.{field}",
                provenance.get(field),
                errors,
                allow_empty=(field == "sources"),
            )
    require_text("provenance", provenance, ("knowledge_cut",), errors)
    if "created_at" in provenance:
        timestamp("provenance.created_at", provenance.get("created_at"), errors)
    if "updated_at" in provenance:
        timestamp("provenance.updated_at", provenance.get("updated_at"), errors)

    audit_workflow(data, errors)
    audit_design(data, errors)

    # Cross-record and readiness invariants.
    metrics.update(
        {
            "claims": len(claims),
            "assumptions": len(assumptions),
            "hypotheses": len(hypotheses),
            "predictions": len(predictions),
            "constructs": len(constructs),
            "measurements": len(measurements),
            "estimands": len(estimands),
            "models": len(models),
            "decision_rows": len(decision_matrix),
        }
    )

    if not claims:
        errors.append("at least one claim is required")

    if specified:
        if needs_hypotheses(data):
            scientific_hypotheses = [
                item
                for item in hypotheses.values()
                if item.get("kind") in SCIENTIFIC_HYPOTHESIS_KINDS
            ]
            if len(scientific_hypotheses) < 2:
                errors.append(
                    "specified status requires at least two competing scientific "
                    "hypotheses; statistical hypotheses alone are insufficient"
                )
            statements = {
                item.get("statement", "").strip().casefold()
                for item in scientific_hypotheses
                if present(item.get("statement"))
            }
            if len(statements) < 2:
                errors.append("competing scientific hypotheses must be non-identical")
            if not predictions:
                errors.append("specified status requires derived predictions")
            discriminating = [
                item
                for item in predictions.values()
                if item.get("shared_prediction") is False
                and item.get("discriminates_from_hypothesis_ids")
            ]
            if not discriminating:
                errors.append(
                    "specified status requires at least one prediction that "
                    "discriminates live hypotheses"
                )
        for label, collection in (
            ("construct", constructs),
            ("measurement", measurements),
            ("estimand", estimands),
            ("analysis model", models),
            ("decision-matrix row", decision_matrix),
        ):
            if not collection:
                errors.append(f"specified status requires at least one {label}")
        if identification.get("status") == "not-assessed":
            errors.append("specified status requires an identification assessment")
        if not target_estimand_ids:
            errors.append("identification must name at least one target estimand")
        modelled_estimands = {
            ref
            for item in models.values()
            for ref in item.get("estimand_ids", [])
            if isinstance(ref, str)
        }
        missing_models = sorted(set(target_estimand_ids) - modelled_estimands)
        if missing_models:
            errors.append(
                "target estimands without an analysis model: "
                + ", ".join(missing_models)
            )
        nonshared_ids = {
            identifier
            for identifier, item in predictions.items()
            if item.get("shared_prediction") is False
        }
        uncovered_predictions = sorted(nonshared_ids - matrix_prediction_coverage)
        if uncovered_predictions:
            errors.append(
                "non-shared predictions absent from decision matrix: "
                + ", ".join(uncovered_predictions)
            )
        if primary_claim_id not in matrix_claim_coverage:
            errors.append("decision matrix does not state an effect on the primary claim")
        if not (discrimination_results & FAILURE_RESULTS):
            errors.append(
                "decision matrix requires a failure, non-discrimination, or "
                "inconclusive row"
            )
        placeholders = placeholder_paths(data)
        if placeholders:
            errors.append(
                "specified status contains unresolved placeholders: "
                + ", ".join(placeholders[:20])
                + (" ..." if len(placeholders) > 20 else "")
            )

    causal_claim_ids = {
        identifier
        for identifier, item in claims.items()
        if item.get("claim_type") in {"causal", "mechanistic"}
    }
    for claim_id in causal_claim_ids:
        linked_types = {
            item.get("estimand_type")
            for item in estimands.values()
            if claim_id in item.get("claim_ids", [])
        }
        if specified and not (linked_types & {"causal", "mechanistic"}):
            errors.append(
                f"{claim_id} is causal or mechanistic but has no causal or "
                "mechanistic estimand"
            )

    if ready:
        used_assumptions = set(identification.get("assumption_ids", []))
        for item in hypotheses.values():
            used_assumptions.update(item.get("auxiliary_assumption_ids", []))
        for item in predictions.values():
            used_assumptions.update(item.get("auxiliary_assumption_ids", []))
        failed_used = sorted(
            identifier
            for identifier in used_assumptions
            if assumptions.get(identifier, {}).get("status") == "failed"
        )
        if failed_used:
            errors.append(
                "ready status relies on failed assumptions: " + ", ".join(failed_used)
            )
        identification_status = identification.get("status")
        if identification_status not in {"identified", "partially-identified"}:
            errors.append(
                "preregisterable or later status requires identified or "
                "explicitly partially identified target estimands"
            )
        if (
            identification_status == "partially-identified"
            and not identification.get("nonidentified_alternatives")
        ):
            errors.append(
                "partial identification requires explicit nonidentified alternatives"
            )
        if feasibility.get("current_status") not in {"feasible", "operational"}:
            errors.append(
                "preregisterable or later status requires feasible or operational "
                "feasibility status"
            )
        if feasibility.get("blockers"):
            errors.append("preregisterable or later status cannot retain blockers")
        if (
            data.get("schema_version") == "1.0"
            and reproducibility.get("preregistration_status") == "not-planned"
        ):
            errors.append(
                "preregisterable or later status requires a preregistration plan"
            )
        if not sampling.get("inputs"):
            errors.append("ready status requires explicit information-design inputs")
        if not analysis.get("robustness_checks"):
            errors.append("ready status requires robustness checks")
        if not bias_risks:
            errors.append("ready status requires at least one assessed bias risk")

    if status in {"approved", "preregistered", "running", "complete"}:
        if ethics.get("applicable") is True and ethics.get("review_status") != "approved":
            errors.append("approved or later status requires applicable review approval")
        if (
            ethics.get("applicable") is False
            and ethics.get("review_status") != "not-required"
        ):
            errors.append(
                "non-applicable ethics and safety requires review_status not-required"
            )

    if status == "preregistered" or (
        data.get("schema_version") == "1.0" and status in {"running", "complete"}
    ):
        if reproducibility.get("preregistration_status") not in {
            "registered",
            "amended",
        }:
            errors.append("preregistered or later status requires a registration")
        if placeholder(reproducibility.get("registration")):
            errors.append("registration must contain an immutable reference")

    if status in {"running", "complete"}:
        if execution.get("started_at") is None:
            errors.append("running or complete status requires execution.started_at")
        if not execution.get("protocol_version_used"):
            errors.append(
                "running or complete status requires execution.protocol_version_used"
            )
        if ethics.get("applicable") and not ethics.get("stopping_rules"):
            errors.append("running applicable work requires executable stopping rules")

    if status == "complete":
        if execution.get("completed_at") is None:
            errors.append("complete status requires execution.completed_at")
        if not execution.get("observed_results"):
            errors.append("complete status requires observed_results")
        if execution.get("interpretation_status") in {None, "not-started", "pending"}:
            errors.append("complete status requires a bounded interpretation status")

    if status == "superseded":
        change_log = provenance.get("change_log", [])
        if not any(
            present(item) and "successor" in item.casefold() for item in change_log
        ):
            errors.append("superseded status requires a successor in the change log")

    if specified and not controls:
        warnings.append(
            "no explicit controls are recorded; verify that the design rationale "
            "explains why none can change interpretation"
        )
    if specified and not confounds:
        warnings.append(
            "no confounds are recorded; verify that causal, measurement, selection, "
            "and temporal alternatives were assessed"
        )
    if specified and "inconclusive" not in discrimination_results:
        warnings.append(
            "decision matrix lacks an explicit inconclusive row; a different failure "
            "row may not cover unanticipated results"
        )
    if not provenance.get("sources"):
        warnings.append("provenance.sources is empty")
    if status == "concept":
        warnings.append(
            "concept status does not establish hypotheses, identification, analysis, "
            "or decision readiness"
        )

    return {
        "valid": not errors,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def preregisterable_fixture(base: dict[str, Any]) -> dict[str, Any]:
    """Build a small complete protocol used only by deterministic self-tests."""
    data = copy.deepcopy(base)
    data["schema_version"] = "1.0"
    data.pop("method_selection", None)
    data.pop("implementation", None)
    data.pop("design_assessment", None)
    data.update(
        {
            "title": "Temperature perturbation of metal-film resistance",
            "version": "1.0.0",
            "status": "preregisterable",
            "question": (
                "Does raising ambient temperature from 20 to 40 degrees Celsius "
                "increase four-wire resistance in batch B metal-film resistors?"
            ),
        }
    )
    data["scope"] = {
        "system_or_population": "Ten-kilohm batch B metal-film resistors",
        "conditions": "Forty per cent relative humidity and specified chamber cycle",
        "spatial_scope": "One calibrated environmental chamber and measurement rig",
        "temporal_scope": "One baseline and one post-equilibration reading per cycle",
        "exclusions": ["Predeclared open-circuit or damaged components"],
        "knowledge_cut": "Engineering records available on 2026-07-31",
    }
    data["claims"] = [
        {
            "id": "CLM-001",
            "statement": (
                "Within the declared batch and conditions, assignment to 40 rather "
                "than 20 degrees Celsius increases mean relative resistance."
            ),
            "claim_type": "causal",
            "role": "primary",
            "scope_limit": "No generalisation beyond the declared batch and range",
            "success_consequence": "Strengthen the bounded positive-temperature claim",
            "failure_consequence": "Weaken or contradict that bounded claim",
        }
    ]
    data["assumptions"] = [
        {
            "id": "ASM-001",
            "statement": "Randomised cycle order removes systematic order effects",
            "role": "identification",
            "status": "untested",
            "test_or_justification": "Inspect balance and period-by-condition interaction",
            "failure_consequence": "Restrict inference to an order-adjusted contrast",
        },
        {
            "id": "ASM-002",
            "statement": "Four-wire calibration remains valid over each cycle",
            "role": "measurement",
            "status": "tested",
            "test_or_justification": "Run traceable reference standards before and after",
            "failure_consequence": "Classify the cycle as invalid measurement",
        },
    ]
    data["hypotheses"] = [
        {
            "id": "H-001",
            "label": "Positive temperature response",
            "kind": "substantive",
            "statement": "The assigned temperature increase raises mean resistance",
            "claim_ids": ["CLM-001"],
            "auxiliary_assumption_ids": ["ASM-001", "ASM-002"],
            "scope": "Declared batch, temperature range, humidity, and equilibration",
        },
        {
            "id": "H-002",
            "label": "No material temperature response",
            "kind": "rival",
            "statement": "The assigned temperature increase leaves mean resistance unchanged",
            "claim_ids": ["CLM-001"],
            "auxiliary_assumption_ids": ["ASM-001", "ASM-002"],
            "scope": "Declared batch, temperature range, humidity, and equilibration",
        },
    ]
    data["constructs"] = [
        {
            "id": "CON-001",
            "name": "Electrical resistance",
            "definition": "Voltage-to-current ratio under the declared four-wire procedure",
            "role": "outcome",
            "scope": "Stable low-power measurements after thermal equilibration",
            "proxy_for_claim_ids": ["CLM-001"],
            "validity_evidence": ["Traceable reference-standard agreement"],
            "validity_threats": ["Self-heating and contact-instability artefacts"],
        }
    ]
    data["measurements"] = [
        {
            "id": "M-001",
            "construct_ids": ["CON-001"],
            "observable": "Four-wire voltage and current record",
            "instrument_or_procedure": "Calibrated source meter using fixed low current",
            "scale_or_units": "Ohms and relative change from 20-degree baseline",
            "timing": "After thirty minutes within the thermal acceptance band",
            "preprocessing": "Predeclared conversion and within-component baseline ratio",
            "calibration": "Traceable standards before and after each chamber cycle",
            "reliability": "Duplicate readings with maximum relative deviation specified",
            "validity": "Measures electrical resistance under the bounded procedure",
            "measurement_invariance": "Same rig, range, current, and procedure in both arms",
            "reactivity": "Low current limits self-heating; current reversal checks it",
            "error_model": "Additive meter error plus component-level random intercept",
            "blinding": "Component identifiers masked during quality review",
        }
    ]
    data["interventions_or_exposures"] = [
        {
            "id": "INT-001",
            "kind": "intervention",
            "description": "Assign chamber set point to 20 or 40 degrees Celsius",
            "target": "Resistor body temperature",
            "implementation": "Randomised crossover chamber cycles",
            "dose_or_intensity": "Twenty-degree Celsius contrast",
            "timing": "Thirty-minute equilibration, reading, washout, and crossover",
            "admissibility": "admissible",
            "manipulation_checks": ["Independent body-temperature probe within tolerance"],
            "off_target_checks": ["Humidity and source-current stability"],
            "recovery_checks": ["Return to baseline resistance after washout"],
        }
    ]
    data["controls"] = [
        {
            "id": "CTRL-001",
            "control_type": "sham",
            "description": "Matched chamber cycle retained at 20 degrees Celsius",
            "failure_mode_addressed": "Time, handling, and chamber-cycle drift",
            "implementation": "Interleaved using the same duration and procedure",
            "diagnostic_consequence": "Estimate cycle drift and invalidate unstable periods",
        },
        {
            "id": "CTRL-002",
            "control_type": "calibration",
            "description": "Traceable reference resistance measured around each cycle",
            "failure_mode_addressed": "Meter calibration drift",
            "implementation": "Pre-cycle and post-cycle readings",
            "diagnostic_consequence": "Classify affected cycles as invalid measurement",
        },
    ]
    data["confounds"] = [
        {
            "id": "CF-001",
            "description": "Humidity may change with chamber temperature",
            "causal_or_measurement_path": "Humidity could alter measured resistance",
            "control_or_adjustment": "Actively hold humidity and record residual deviation",
            "diagnostic": "Test humidity balance and sensitivity to measured deviation",
            "residual_risk": "Uncontrolled deviation weakens the temperature attribution",
        }
    ]
    data["estimands"] = [
        {
            "id": "EST-001",
            "claim_ids": ["CLM-001"],
            "estimand_type": "causal",
            "population_or_system": "Batch B components surviving predeclared quality checks",
            "intervention_or_exposure": "Assignment to 40 degrees Celsius",
            "comparator": "Assignment to 20 degrees Celsius",
            "outcome_measurement_ids": ["M-001"],
            "time": "Post-equilibration reading",
            "summary_measure": "Mean within-component relative resistance difference",
            "interpretation": "Bounded average effect of the assigned temperature contrast",
        }
    ]
    data["predictions"] = [
        {
            "id": "P-001",
            "hypothesis_ids": ["H-001"],
            "claim_ids": ["CLM-001"],
            "estimand_ids": ["EST-001"],
            "measurement_ids": ["M-001"],
            "expected_pattern": "Positive mean within-component resistance change",
            "direction": "increase",
            "magnitude_or_range": "Greater than the predeclared negligible-effect bound",
            "time_window": "At the post-equilibration reading",
            "tolerance": "Calibration and repeatability acceptance limits",
            "auxiliary_assumption_ids": ["ASM-001", "ASM-002"],
            "discriminates_from_hypothesis_ids": ["H-002"],
            "shared_prediction": False,
        },
        {
            "id": "P-002",
            "hypothesis_ids": ["H-002"],
            "claim_ids": ["CLM-001"],
            "estimand_ids": ["EST-001"],
            "measurement_ids": ["M-001"],
            "expected_pattern": "Mean change lies inside the negligible-effect interval",
            "direction": "bounded-null",
            "magnitude_or_range": "Within the predeclared negligible-effect bound",
            "time_window": "At the post-equilibration reading",
            "tolerance": "Calibration and repeatability acceptance limits",
            "auxiliary_assumption_ids": ["ASM-001", "ASM-002"],
            "discriminates_from_hypothesis_ids": ["H-001"],
            "shared_prediction": False,
        },
    ]
    data["design"] = {
        "design_type": "controlled-experiment",
        "rationale": "Randomised crossover assignment identifies the bounded contrast",
        "setting": "Calibrated environmental chamber",
        "temporal_structure": "Randomised crossover with washout",
        "assignment_method": "Computer-generated blocked random cycle order",
        "allocation_concealment": "Sequence concealed until each cycle is configured",
        "masking": "Quality reviewer and analyst remain masked to component identifiers",
        "comparator": "Matched 20-degree chamber cycle",
        "control_ids": ["CTRL-001", "CTRL-002"],
    }
    data["units"] = {
        "target_population_or_system": "Ten-kilohm batch B metal-film resistors",
        "sampling_frame": "Complete manufacturer tray for batch B",
        "experimental_unit": "Individual resistor",
        "observational_unit": "Component-by-cycle resistance reading",
        "assignment_unit": "Chamber cycle",
        "analysis_unit": "Individual resistor with repeated readings",
        "inclusion_criteria": ["Intact component within baseline tolerance"],
        "exclusion_criteria": ["Open circuit or failed predeclared calibration check"],
        "recruitment_or_selection": "Uniform random sample from the complete tray",
    }
    data["identification"] = {
        "target_estimand_ids": ["EST-001"],
        "status": "identified",
        "causal_and_measurement_structure": (
            "Randomised crossover assignment, component effect, period effect, "
            "temperature, humidity, and calibrated resistance measurement"
        ),
        "assumption_ids": ["ASM-001", "ASM-002"],
        "identified_parameters": ["Mean within-component assignment contrast"],
        "nonidentified_alternatives": [],
        "threats": ["Carry-over, humidity imbalance, and calibration drift"],
        "diagnostics": ["Period interaction, humidity balance, and standards check"],
        "rescue_actions": ["Extend washout or restrict analysis to valid balanced cycles"],
    }
    data["sampling"] = {
        "method": "Precision analysis for the paired mean contrast",
        "sample_size_or_information_target": "Ninety-five per cent interval half-width",
        "inputs": ["Pilot paired variance", "Calibration variance", "Two-sided coverage"],
        "dependence_structure": "Repeated readings nested within component",
        "multiplicity": "One primary estimand; secondary checks labelled exploratory",
        "attrition_or_loss": "Inflate for predeclared calibration failures",
        "result": "Forty components provide the target simulated interval width",
        "sensitivity_analysis": "Report width over plausible variance and loss ranges",
        "stopping_implications": "Fixed information target; no outcome-dependent stopping",
    }
    data["analysis"] = {
        "preprocessing_lock": "Frozen conversion, baseline ratio, and cycle joins",
        "exclusion_lock": "Only predeclared component and calibration failures",
        "models": [
            {
                "id": "MOD-001",
                "estimand_ids": ["EST-001"],
                "model_or_procedure": "Paired component-level contrast with period term",
                "assumptions": ["Stable calibration and bounded carry-over"],
                "diagnostics": ["Residual, period, influence, and calibration checks"],
                "outputs": ["Estimate and ninety-five per cent interval for EST-001"],
            }
        ],
        "contrasts": ["Forty-degree minus twenty-degree relative resistance"],
        "uncertainty": "Ninety-five per cent interval plus sensitivity bounds",
        "multiplicity": "No multiplicity adjustment for the sole primary estimand",
        "missing_data": "Report causes and use only predeclared valid paired cycles",
        "stopping_rule": "Stop after the fixed valid-pair information target",
        "robustness_checks": ["Alternative period adjustment and leave-one-cycle-out fit"],
        "software_and_versions": ["Python version and analysis package lockfile"],
        "inconclusive_handling": "Suspend the claim if interval crosses both regions",
    }
    data["decision_matrix"] = [
        {
            "id": "DM-001",
            "prediction_ids": ["P-001"],
            "observation_region": "Interval wholly above the negligible-effect bound",
            "analysis_outputs": ["Estimate and interval for EST-001"],
            "decision_rule": "All manipulation and calibration checks pass",
            "discrimination_result": "favours-hypothesis",
            "claim_effects": [
                {
                    "claim_ids": ["CLM-001"],
                    "disposition": "strengthen",
                    "rationale": "The identified contrast has the predicted direction",
                    "scope_limit": "Only the declared batch, range, and conditions",
                }
            ],
            "hypothesis_effects": ["H-001 favoured over H-002"],
            "assumption_failure_response": "Apply the relevant failure row instead",
            "next_action": "Independent batch replication",
        },
        {
            "id": "DM-002",
            "prediction_ids": ["P-002"],
            "observation_region": "Interval wholly inside the negligible-effect bounds",
            "analysis_outputs": ["Estimate and interval for EST-001"],
            "decision_rule": "All manipulation and calibration checks pass",
            "discrimination_result": "contradicts-hypothesis",
            "claim_effects": [
                {
                    "claim_ids": ["CLM-001"],
                    "disposition": "contradict",
                    "rationale": "The bounded positive-effect prediction fails",
                    "scope_limit": "Only the declared batch, range, and conditions",
                }
            ],
            "hypothesis_effects": ["H-001 weakened; H-002 retained"],
            "assumption_failure_response": "Apply the relevant failure row instead",
            "next_action": "Check a wider temperature range",
        },
        {
            "id": "DM-003",
            "prediction_ids": ["P-001", "P-002"],
            "observation_region": "Interval overlaps positive and negligible regions",
            "analysis_outputs": ["Estimate and interval for EST-001"],
            "decision_rule": "No unique hypothesis preference is licensed",
            "discrimination_result": "inconclusive",
            "claim_effects": [
                {
                    "claim_ids": ["CLM-001"],
                    "disposition": "suspend",
                    "rationale": "The feasible information did not discriminate",
                    "scope_limit": "No claim change beyond recording imprecision",
                }
            ],
            "hypothesis_effects": ["H-001 and H-002 remain live"],
            "assumption_failure_response": "Classify invalid checks separately",
            "next_action": "Increase precision or redesign the contrast",
        },
    ]
    data["bias_assessment"] = {
        "risks": [
            {
                "id": "BIAS-001",
                "risk_type": "measurement",
                "mechanism": "Meter drift could mimic a temperature response",
                "prevention": "Traceable standards around every chamber cycle",
                "detection": "Pre-cycle and post-cycle calibration difference",
                "sensitivity_or_correction": "Repeat after recalibration and bound drift",
                "residual_risk": "Unresolved drift invalidates affected cycles",
            }
        ],
        "researcher_degrees_of_freedom": ["Frozen exclusions and one primary model"],
        "negative_controls": ["Matched sham chamber cycle"],
        "positive_controls": ["Known reference-standard change"],
        "falsification_checks": ["No temperature effect on the fixed reference"],
        "reporting_controls": ["Report every matrix row and protocol deviation"],
        "residual_limitations": ["Single batch and apparatus limit transport"],
    }
    data["ethics_and_safety"] = {
        "applicable": False,
        "rationale": "Benchtop passive components create no human or animal intervention",
        "risks": ["Routine electrical and heated-apparatus risks"],
        "mitigations": ["Laboratory electrical and chamber operating procedures"],
        "monitoring": ["Chamber over-temperature and source-current limits"],
        "stopping_rules": ["Automatic stop on limit breach"],
        "stop_authority": "Laboratory operator",
        "review_status": "not-required",
        "post_stop_actions": ["Isolate apparatus and record the event"],
    }
    data["feasibility"] = {
        "current_status": "feasible",
        "apparatus_or_data": ["Environmental chamber and calibrated source meter"],
        "access": "Laboratory access confirmed",
        "skills": ["Four-wire metrology and crossover analysis"],
        "resources": ["Forty batch B components and traceable standards"],
        "dependencies": ["Current calibration certificates"],
        "blockers": [],
        "fallback": "Run a calibration study if paired variance exceeds the range",
    }
    data["reproducibility"] = {
        "preregistration_status": "planned",
        "registration": "Freeze this protocol and record its content hash before data",
        "immutable_materials": ["Protocol JSON", "Assignment script", "Analysis script"],
        "data_plan": "Publish raw instrument records and a data dictionary",
        "code_plan": "Archive executable assignment and analysis environments",
        "randomisation_or_seed_plan": "Generate and record one seed before assignment",
        "provenance_plan": "Hash raw files and retain calibration certificates",
        "deviation_and_amendment_plan": "Timestamp, justify, and distinguish all changes",
        "replication_plan": "Repeat on an independently sampled manufacturing batch",
    }
    data["provenance"] = {
        "authors": ["Metrology investigator"],
        "created_at": "2026-07-31T09:00:00+01:00",
        "updated_at": "2026-07-31T09:00:00+01:00",
        "sources": ["Batch specification and calibration records"],
        "knowledge_cut": "2026-07-31",
        "change_log": ["1.0.0: preregisterable protocol completed"],
    }
    return data


def self_test() -> tuple[bool, list[str]]:
    messages: list[str] = []
    template_path = (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "investigation-protocol.template.json"
    )
    try:
        concept = load_json(template_path)
    except ValueError as exc:
        return False, [str(exc)]

    concept_report = audit(concept)
    if concept_report["errors"]:
        messages.append(
            "concept template unexpectedly failed: "
            + "; ".join(concept_report["errors"])
        )

    valid_ready = preregisterable_fixture(concept)
    valid_ready_report = audit(valid_ready)
    if valid_ready_report["errors"]:
        messages.append(
            "complete preregisterable fixture unexpectedly failed: "
            + "; ".join(valid_ready_report["errors"])
        )

    promoted = copy.deepcopy(concept)
    promoted["status"] = "specified"
    promoted["schema_version"] = "1.0"
    promoted.pop("method_selection", None)
    promoted.pop("implementation", None)
    promoted_report = audit(promoted)
    expected_fragments = (
        "competing scientific hypotheses",
        "derived predictions",
        "unresolved placeholders",
    )
    for fragment in expected_fragments:
        if not any(fragment in item for item in promoted_report["errors"]):
            messages.append(f"strict readiness test missed: {fragment}")

    nonidentified = copy.deepcopy(valid_ready)
    nonidentified["identification"]["status"] = "nonidentified"
    nonidentified["estimands"][0]["estimand_type"] = "associational"
    nonidentified_report = audit(nonidentified)
    for fragment in (
        "identified or explicitly partially identified",
        "no causal or mechanistic estimand",
    ):
        if not any(fragment in item for item in nonidentified_report["errors"]):
            messages.append(f"non-identification test missed: {fragment}")

    nondiscriminating = copy.deepcopy(valid_ready)
    for prediction in nondiscriminating["predictions"]:
        prediction["shared_prediction"] = True
        prediction["discriminates_from_hypothesis_ids"] = []
    nondiscriminating_report = audit(nondiscriminating)
    if not any(
        "requires at least one prediction that discriminates" in item
        for item in nondiscriminating_report["errors"]
    ):
        messages.append("non-discrimination test was incorrectly accepted")

    uncovered = copy.deepcopy(valid_ready)
    for row in uncovered["decision_matrix"]:
        row["prediction_ids"] = [
            identifier
            for identifier in row["prediction_ids"]
            if identifier != "P-001"
        ]
    uncovered_report = audit(uncovered)
    if not any(
        "non-shared predictions absent from decision matrix" in item
        for item in uncovered_report["errors"]
    ):
        messages.append("decision-coverage test was incorrectly accepted")

    broken = {"status": "concept"}
    broken_report = audit(broken)
    if broken_report["valid"]:
        messages.append("malformed protocol was incorrectly accepted")

    return not messages, messages


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a scientific investigation protocol."
    )
    parser.add_argument("protocol", nargs="?", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit the validation report as JSON.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run deterministic validator checks.",
    )
    args = parser.parse_args(argv)
    if not args.self_test and args.protocol is None:
        parser.error("protocol is required unless --self-test is used")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        passed, messages = self_test()
        if passed:
            print("self-test passed")
            return 0
        for message in messages:
            print(f"SELF-TEST ERROR: {message}", file=sys.stderr)
        return 1

    assert args.protocol is not None
    try:
        data = load_json(args.protocol)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    report = audit(data)
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        label = "VALID" if report["valid"] else "INVALID"
        print(
            f"{label}: {args.protocol} "
            f"(status={report['status']!r}, "
            f"errors={len(report['errors'])}, "
            f"warnings={len(report['warnings'])})"
        )
        for error in report["errors"]:
            print(f"ERROR: {error}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
