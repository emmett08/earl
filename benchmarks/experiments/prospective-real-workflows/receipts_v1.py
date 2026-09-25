"""Verify content-addressed, externally signed study stage prerequisites.

Signatures authenticate an attestation by a configured external key. They do
not independently prove the underlying review or authorise a production write.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from gateway_v1 import canonical


SCHEMA = "eal2-real-workflow-receipts/1"
REQUIRED = {
    "feasibility_pilot": {
        "independent_case_manifest_sha256": {"domain_reviewer": 2},
        "reference_review_sha256": {"domain_reviewer": 2},
        "tool_allowlist_and_isolation_sha256": {"security_owner": 1},
        "prompt_and_method_parity_sha256": {"method_reviewer": 1},
        "model_snapshot_manifest_sha256": {"method_reviewer": 1},
    },
    "retrospective_execution": {
        "adapter_execution_and_authentication_sha256": {"security_owner": 1},
        "pilot_report_sha256": {"method_reviewer": 1},
        "power_and_margin_approval_sha256": {"method_reviewer": 1},
        "frozen_schedule_sha256": {"method_reviewer": 1},
        "registration_sha256": {"study_owner": 1},
    },
    "prospective_shadow": {
        "shadow_access_and_stop_authority_sha256": {"security_owner": 1},
    },
}


class ReceiptError(ValueError):
    pass


def verify_stage(*, stage: str, bundle: Mapping, root: Path,
                 trust_roster: Mapping[str, Mapping[str, str]], plan_bytes: bytes) -> dict:
    if stage not in REQUIRED:
        raise ReceiptError("No study stage gate exists for this stage")
    if (bundle.get("schema") != SCHEMA or bundle.get("investigation_id") != "INV-EAL-REAL-001"
            or bundle.get("plan_sha256") != hashlib.sha256(plan_bytes).hexdigest()):
        raise ReceiptError("Receipt bundle does not bind the exact study specification")
    needs = dict(REQUIRED["feasibility_pilot"])
    if stage in {"retrospective_execution", "prospective_shadow"}:
        needs.update(REQUIRED["retrospective_execution"])
    if stage == "prospective_shadow":
        needs.update(REQUIRED["prospective_shadow"])
    artifacts = bundle.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ReceiptError("Receipt bundle has no artifacts")
    checked = {}
    for name, roles in needs.items():
        item = artifacts.get(name)
        if not isinstance(item, dict):
            raise ReceiptError(f"Missing signed artifact {name}")
        relative = item.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ReceiptError(f"Invalid bounded artifact path for {name}")
        file = (root / relative).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():
            raise ReceiptError(f"Artifact is unavailable for {name}")
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != item.get("sha256"):
            raise ReceiptError(f"Artifact bytes differ from signed digest for {name}")
        role_keys = {role: set() for role in roles}
        message = canonical({"schema": SCHEMA, "investigation_id": bundle["investigation_id"],
                             "plan_sha256": bundle["plan_sha256"], "receipt": name,
                             "sha256": actual})
        for signature in item.get("attestations", []):
            try:
                key_id = signature["key_id"]
                signer = trust_roster[key_id]
                role = signer["role"]
                if role not in role_keys:
                    continue
                key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer["public_key_hex"]))
                key.verify(bytes.fromhex(signature["signature_hex"]), message)
                role_keys[role].add(key_id)
            except (KeyError, TypeError, ValueError) as exc:
                raise ReceiptError(f"Invalid attestation on {name}") from exc
            except Exception as exc:
                raise ReceiptError(f"Invalid cryptographic signature on {name}") from exc
        if any(len(role_keys[role]) < required for role, required in roles.items()):
            raise ReceiptError(f"Independent signer roles are missing for {name}")
        checked[name] = actual
    return {"verified_receipts": checked, "plan_sha256": bundle["plan_sha256"], "stage": stage}
