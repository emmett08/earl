"""Fail-closed study stage gate; a pending plan cannot run real assignments."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from protocol_v1 import Case, canonical, digest
from eal.runtime import strict_json


SCHEMA = "eal2-ci-prospective-receipts/1"
EXECUTION_SCHEMA = "eal2-ci-prospective-execution/1"
STUDY_ID = "INV-EAL-CI-001"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED = {
    "pilot": {"case_manifest": {"domain_reviewer": 2},
              "reference_review": {"domain_reviewer": 2},
              "tool_isolation": {"security_owner": 1},
              "arm_parity": {"method_reviewer": 1},
              "json_eal_differential": {"method_reviewer": 1},
              "model_matrix": {"method_reviewer": 1}},
    "retrospective": {"adapter_authentication": {"security_owner": 1},
                      "pilot_report": {"method_reviewer": 1},
                      "freeze_and_analysis": {"method_reviewer": 1, "study_owner": 1}},
    "prospective_shadow": {"shadow_access": {"security_owner": 1}},
}


class PreflightError(ValueError):
    pass


def _artifact(name: str, item: Mapping, *, root: Path, roster: Mapping,
              bundle: Mapping, roles: Mapping[str, int]) -> dict:
    if type(item) is not dict or set(item) != {"path", "sha256", "attestations"}:
        raise PreflightError(f"Missing exact receipt {name}")
    relative = item["path"]
    if (type(relative) is not str or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts):
        raise PreflightError(f"Invalid receipt path {name}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise PreflightError(f"Receipt {name} is unavailable")
    raw = path.read_bytes()
    actual = sha256(raw).hexdigest()
    if actual != item["sha256"]:
        raise PreflightError(f"Receipt {name} changed")
    signed = canonical({"schema": SCHEMA, "investigation_id": STUDY_ID,
                        "plan_sha256": bundle["plan_sha256"],
                        "receipt": name, "sha256": actual})
    seen = {role: set() for role in roles}
    for entry in item["attestations"]:
        try:
            key_id = entry["key_id"]
            signer = roster[key_id]
            role = signer["role"]
            if role not in roles:
                continue
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer["public_key_hex"])).verify(
                bytes.fromhex(entry["signature_hex"]), signed)
            seen[role].add(key_id)
        except Exception as exc:
            raise PreflightError(f"Invalid signature on {name}") from exc
    if any(len(seen[role]) < count for role, count in roles.items()):
        raise PreflightError(f"Independent reviewers have not approved {name}")
    document = strict_json(raw.decode("utf-8"))
    if type(document) is not dict:
        raise PreflightError(f"Receipt {name} must be a JSON object")
    return document


def preflight(*, stage: str, case: Case, model_id: str, assignment: dict,
              study_path: Path, execution_path: Path, bundle_path: Path,
              receipt_root: Path, trust_roster: Mapping,
              arm_manifest: dict, registry_sha256: str,
              tool_manifest: list[dict], provider_identity: dict) -> dict:
    if stage not in REQUIRED:
        raise PreflightError("Unknown real study stage")
    study_bytes = study_path.read_bytes()
    study = strict_json(study_bytes.decode("utf-8"))
    if (type(study) is not dict or study.get("schema") != "eal2-ci-prospective-study/1"
            or study.get("study_id") != STUDY_ID
            or study.get("status") != "specified_not_ready"):
        raise PreflightError("Study specification is missing or unexpectedly changed")
    execution = strict_json(execution_path.read_text(encoding="utf-8"))
    if (type(execution) is not dict or execution.get("schema") != EXECUTION_SCHEMA
            or execution.get("investigation_id") != STUDY_ID
            or execution.get("stage") != stage
            or execution.get("status") != "ready"
            or execution.get("supersedes_sha256") != digest(study_bytes)):
        raise PreflightError("A separately frozen ready execution plan is required")
    schedule = execution.get("schedule")
    if type(schedule) is not list or schedule.count(assignment) != 1:
        raise PreflightError("Exact assignment is missing or duplicated in the frozen schedule")
    bundle = strict_json(bundle_path.read_text(encoding="utf-8"))
    if (type(bundle) is not dict or bundle.get("schema") != SCHEMA
            or bundle.get("investigation_id") != STUDY_ID
            or bundle.get("plan_sha256") != digest(execution_path.read_bytes())):
        raise PreflightError("Receipt bundle does not bind the execution plan")
    requirements = dict(REQUIRED["pilot"])
    if stage in {"retrospective", "prospective_shadow"}:
        requirements.update(REQUIRED["retrospective"])
    if stage == "prospective_shadow":
        requirements.update(REQUIRED["prospective_shadow"])
    artifacts = bundle.get("artifacts")
    if type(artifacts) is not dict:
        raise PreflightError("Receipt bundle lacks reviewed artifacts")
    checked = {key: _artifact(key, artifacts.get(key), root=receipt_root,
                              roster=trust_roster, bundle=bundle, roles=roles)
               for key, roles in requirements.items()}
    cases = checked["case_manifest"].get("cases")
    if type(cases) is not list or cases.count(case.as_dict()) != 1:
        raise PreflightError("The exact case is absent from the independent manifest")
    references = checked["reference_review"].get("entries")
    if (type(references) is not list or sum(
            type(entry) is dict and entry.get("case_id") == case.id
            and entry.get("case_sha256") == digest(case.as_dict())
            and entry.get("reference_id") == case.reference_id for entry in references) != 1):
        raise PreflightError("Case lacks an independently reviewed reference")
    tool_review = checked["tool_isolation"]
    if (tool_review.get("schema") != "eal2-ci-tool-review/1"
            or tool_review.get("registry_sha256") != registry_sha256
            or tool_review.get("tools") != tool_manifest
            or tool_review.get("operator_isolation") in (None, {}, "")
            or tool_review.get("decision_cut_enforced") is not True):
        raise PreflightError("Registry, exact grants or execution isolation differ from review")
    attestations = tool_review.get("actual_execution_receipts")
    if (type(attestations) is not dict or set(attestations) != set(case.allowed)
            or any(type(item) is not dict
                   or item.get("read_only") is not True
                   or item.get("executed") is not True
                   or item.get("source_identity") in (None, "")
                   or type(item.get("receipt_sha256")) is not str
                   or not _SHA256.fullmatch(item["receipt_sha256"])
                   for item in attestations.values())):
        raise PreflightError("Actual read-only adapter execution receipts are missing")
    parity = checked["arm_parity"]
    if (parity.get("schema") != "eal2-ci-arm-review/1"
            or parity.get("manifest") != arm_manifest
            or parity.get("mcp_transport") != "stdio"
            or parity.get("mcp_operations") != [
                "eal_describe", "eal_validate", "eal_collect", "eal_reason", "eal_explain"]
            or parity.get("source_subset") != "direct_declarations"
            or parity.get("same_typed_backend") is not True):
        raise PreflightError("Injected prompts, MCP contract or checker differ from parity review")
    differential = checked["json_eal_differential"]
    if (differential.get("schema") != "eal2-ci-differential/1"
            or type(differential.get("valid_cases")) is not int
            or differential["valid_cases"] < 1
            or type(differential.get("adversarial_cases")) is not int
            or differential["adversarial_cases"] < 1
            or differential.get("all_typed_meanings_equal") is not True
            or differential.get("all_checked_outputs_equal") is not True
            or type(differential.get("test_trace_sha256")) is not str
            or not _SHA256.fullmatch(differential["test_trace_sha256"])):
        raise PreflightError("Reviewed JSON/EAL differential parity is incomplete")
    model_review = checked["model_matrix"]
    models = model_review.get("models")
    if (type(models) is not list or sum(
            type(model) is dict and model.get("id") == model_id
            and model.get("identity_sha256") == digest(provider_identity)
            for model in models) != 1):
        raise PreflightError("Resolved model differs from frozen model matrix")
    if (any(type(model) is not dict or type(model.get("id")) is not str
            or type(model.get("provider_family")) is not str
            or not model["provider_family"]
            or model.get("size_class") not in {"small", "large", "undisclosed"}
            for model in models)
            or len({model["id"] for model in models}) != len(models)):
        raise PreflightError("Model matrix has malformed or repeated snapshots")
    if stage in {"retrospective", "prospective_shadow"}:
        adapter = checked["adapter_authentication"]
        if (adapter.get("schema") != "eal2-ci-adapter-authentication/1"
                or adapter.get("source_authenticated") is not True
                or adapter.get("as_of_cut_enforced") is not True):
            raise PreflightError("CI adapter lacks source authentication or time boundary")
        if stage == "retrospective" and (
                adapter.get("historical_snapshot_immutable") is not True
                or type(adapter.get("snapshot_id")) is not str
                or not adapter["snapshot_id"]):
            raise PreflightError("Historical CI adapter lacks an immutable as-of snapshot")
        freeze = checked["freeze_and_analysis"]
        if freeze.get("schema") != "eal2-ci-frozen-analysis/1":
            raise PreflightError("Frozen analysis has an unknown schema")
        if any(freeze.get(key) is None for key in (
                "family_count", "benefit_margin", "false_support_margin",
                "minimum_coverage", "analysis_sha256", "schedule_sha256")):
            raise PreflightError("Analysis margins and schedule are not frozen")
        if freeze["schedule_sha256"] != digest(schedule):
            raise PreflightError("Frozen schedule differs from execution plan")
        scope = freeze.get("inference_scope")
        if scope == "represented_strata":
            if (len(models) < 8
                    or len({model.get("provider_family") for model in models}) < 3
                    or sum(model.get("size_class") == "small" for model in models) < 2
                    or sum(model.get("size_class") == "large" for model in models) < 2
                    or any(model.get("size_class") in {"small", "large"}
                           and not model.get("published_parameter_source") for model in models)
                    or not freeze.get("small_large_boundary")):
                raise PreflightError("Frozen matrix does not cover the declared model strata")
        elif scope == "named_snapshots_only":
            if not freeze.get("narrowing_rationale"):
                raise PreflightError("Named-snapshot narrowing must be independently approved")
        else:
            raise PreflightError("Analysis must freeze a bounded model inference scope")
    if stage == "prospective_shadow":
        shadow = checked["shadow_access"]
        if (shadow.get("schema") != "eal2-ci-shadow-access/1"
                or shadow.get("read_only") is not True
                or type(shadow.get("authenticated_principal")) is not str
                or not shadow["authenticated_principal"]
                or shadow.get("stop_authority") in (None, "")):
            raise PreflightError("Shadow stage lacks bounded read-only authority")
    return {"stage": stage, "plan_sha256": bundle["plan_sha256"],
            "inference_scope": checked.get("freeze_and_analysis", {}).get(
                "inference_scope", "pilot_only"),
            "receipts": {key: artifacts[key]["sha256"] for key in checked}}
