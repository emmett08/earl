"""Purpose and implementation checks for investigation protocol schemas 1.1/1.2.

These are structural checks, not evidence of scientific adequacy or execution.
"""
from __future__ import annotations

from urllib.parse import urlparse

PURPOSES = {
    "estimation", "hypothesis-test", "theory-discrimination", "causal-comparison",
    "mechanism-discrimination", "measurement-validation", "prediction",
    "exploration", "equivalence", "feasibility",
}
TEST_PURPOSES = {"hypothesis-test", "theory-discrimination", "mechanism-discrimination"}
STAGES = ("assignment", "collection", "scoring", "analysis")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and all(text(x) for x in value)


def purpose_set(data):
    method = data.get("method_selection")
    if not isinstance(method, dict):
        return set()
    primary = method.get("primary_purpose")
    secondary = method.get("secondary_purposes", [])
    return ({primary} if isinstance(primary, str) else set()) | (
        {x for x in secondary if isinstance(x, str)} if isinstance(secondary, list) else set()
    )


def needs_hypotheses(data):
    if data.get("schema_version") == "1.0":
        return True
    claims = data.get("claims", [])
    return bool(purpose_set(data) & TEST_PURPOSES) or (
        isinstance(claims, list) and any(
            isinstance(c, dict) and c.get("claim_type") == "mechanistic" for c in claims
        )
    )


def resolve_pointer(data, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False
    try:
        for part in pointer[1:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            data = data[int(part)] if isinstance(data, list) and part.isdigit() else data[part]
        return True
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def audit_workflow(data, errors):
    if data.get("schema_version") not in ("1.1", "1.2"):
        return
    strict = data.get("status") not in {"concept", "superseded"}
    method = data.get("method_selection")
    implementation = data.get("implementation")
    if not isinstance(method, dict):
        errors.append("method_selection must be an object for schema 1.1/1.2")
        method = {}
    if not isinstance(implementation, dict):
        errors.append("implementation must be an object for schema 1.1/1.2")
        implementation = {}
    if method.get("primary_purpose") not in sorted(PURPOSES):
        errors.append("method_selection.primary_purpose must be a supported purpose")
    secondary = method.get("secondary_purposes")
    if not strings(secondary) or any(x not in PURPOSES for x in secondary):
        errors.append("method_selection.secondary_purposes must list supported purposes")
    if not strict:
        return
    for field in ("rationale", "inference_framework", "information_criterion",
                  "discovery_confirmation_separation"):
        if not text(method.get(field)):
            errors.append(f"method_selection.{field} requires an explicit explanation")
    for field in ("alternatives_considered", "permitted_conclusions", "excluded_conclusions"):
        if not strings(method.get(field)) or not method[field]:
            errors.append(f"method_selection.{field} must be a non-empty text list")
    sources = method.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("method_selection.sources requires a relevant methodological source")
    else:
        for source in sources:
            if not isinstance(source, dict) or not all(
                text(source.get(k)) for k in ("citation", "url", "design_consequence")
            ):
                errors.append("methodological sources require citation, url and design_consequence")
            elif urlparse(source["url"]).scheme not in {"http", "https"} or not urlparse(source["url"]).netloc:
                errors.append("methodological source url must be an absolute HTTP(S) URL")

    state = implementation.get("status")
    if state not in ("planned", "implemented", "verified"):
        errors.append("implementation.status must be planned, implemented or verified")
    if data.get("status") in {"running", "complete"} and state != "verified":
        errors.append("running or complete status requires verified implementation")
    for stage in STAGES:
        record = implementation.get(stage)
        if not isinstance(record, dict) or not all(
            text(record.get(k)) for k in ("procedure", "artifact", "failure_response")
        ):
            errors.append(f"implementation.{stage} requires procedure, artifact and failure_response")

    checks = implementation.get("verification")
    indexed = {}
    if not isinstance(checks, list) or not checks:
        errors.append("implementation.verification must contain planned or executed checks")
    else:
        for check in checks:
            if not isinstance(check, dict) or not all(text(check.get(k)) for k in
                    ("id", "stage", "case", "expected_result", "status")):
                errors.append("verification check requires id, stage, case, expected_result and status")
                continue
            identifier = check["id"]
            if identifier in indexed:
                errors.append(f"duplicate verification check id: {identifier}")
            indexed[identifier] = check
            if check["stage"] not in (*STAGES, "pipeline"):
                errors.append(f"verification {identifier} has an unknown stage")
            if check["status"] not in ("planned", "passed", "failed", "not-applicable"):
                errors.append(f"verification {identifier} has an invalid status")
            if check["status"] in ("passed", "failed", "not-applicable") and not all(
                text(check.get(k)) for k in ("observed_result", "evidence")
            ):
                errors.append(f"verification {identifier} requires observed_result and evidence or applicability rationale")
            if state == "verified" and check["status"] not in ("passed", "not-applicable"):
                errors.append(f"verified implementation retains unresolved check {identifier}")
    stages = {x["stage"] for x in indexed.values()}
    for stage in (*STAGES, "pipeline"):
        if stage not in stages:
            errors.append(f"implementation.verification lacks {stage} coverage")
    if state == "verified" and not any(
        x["stage"] == "pipeline" and x["status"] == "passed" for x in indexed.values()
    ):
        errors.append("verified implementation requires a passed pipeline rehearsal")

    traceability = implementation.get("traceability")
    covered = set()
    if not isinstance(traceability, list):
        errors.append("implementation.traceability must be a list")
    else:
        for row in traceability:
            if not isinstance(row, dict):
                errors.append("implementation.traceability rows must be objects")
                continue
            ref = row.get("protocol_ref")
            if not resolve_pointer(data, ref):
                errors.append(f"unresolved protocol_ref: {ref!r}")
            else:
                covered.add(ref)
            if not text(row.get("artifact")):
                errors.append("traceability row requires an artifact or planned procedure")
            ids = row.get("check_ids")
            if not strings(ids) or not ids or any(x not in indexed for x in ids):
                errors.append("traceability row requires resolved check_ids")
    required = {"/design/assignment_method"}
    analysis = data.get("analysis")
    models = analysis.get("models", []) if isinstance(analysis, dict) else []
    for key, values in (("measurements", data.get("measurements", [])),
                        ("analysis/models", models)):
        if isinstance(values, list):
            required.update(f"/{key}/{i}" for i in range(len(values)))
    if required - covered:
        errors.append("implementation.traceability missing requirements: " + ", ".join(sorted(required - covered)))
