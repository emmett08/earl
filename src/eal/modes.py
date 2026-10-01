"""Validate and dispatch registered reasoning assessments.

Algorithms and their local domain checks live in ``eal.reasoning``. This facade
owns evidence selection, shared resource/schema checks and result provenance.
"""
from __future__ import annotations

import hashlib
import json

from .limits import current_limits
from .builtin_methods import BUILTIN_SPECS
from .reasoning.validation import _check_json, _result

MODE_KINDS = {mode: spec.evidence_kind for mode, spec in BUILTIN_SPECS.items()}


def evidence_kind(method: str, registry=None):
    from .methods import default_registry
    contract = (registry or default_registry()).get(method)
    return contract.evidence_kind if contract else None


def validate_mode(method: str, kinds: list[str], registry=None) -> list[str]:
    """Resolve the host registry and check designated computational evidence."""
    from .methods import default_registry
    contract = (registry or default_registry()).get(method)
    if contract is None:
        return [f"Unknown registered reasoning method {method!r}; use an installed versioned identifier"]
    if not isinstance(kinds, list) or any(not isinstance(k, str) for k in kinds):
        return ["Evidence kinds must be a list of strings"]
    if len(kinds) > current_limits().declarations:
        return ["At most 4096 evidence entries are allowed"]
    required = contract.evidence_kind
    if required is not None and kinds.count(required) != 1:
        return [f"Method {method!r} requires exactly one evidence entry of kind {required!r}"]
    return []


def assess_mode(method: str, evidence: list[dict], premises: list[dict], registry=None) -> dict:
    """Return a bounded versioned method result without executing tools or trusting prose.

    Evidence entries are ``{id, kind, value}``; premise entries contain ``status``.
    The caller separately checks premise support and argument requirements.
    """
    from .methods import check_implementation_identity, default_registry, execute_extension, schema_errors
    registry = registry or default_registry()

    def identified(result):
        return {**result, "method": method,
                "reasons": [f"Method {method}: {reason}" for reason in result["reasons"]]}

    try:
        if not isinstance(evidence, list) or len(evidence) > current_limits().declarations:
            raise ValueError("Evidence must be a list with within the host declaration budget")
        if not isinstance(premises, list) or len(premises) > current_limits().declarations:
            raise ValueError("Premises must be a list with within the host declaration budget")
        if any(not isinstance(item, dict) or not isinstance(item.get("kind"), str) or
               "value" not in item or not isinstance(item.get("id"), str) for item in evidence):
            raise ValueError("Each evidence entry requires id, kind and value")
        if len({item["id"] for item in evidence}) != len(evidence):
            raise ValueError("Evidence identifiers must be unique")
        if any(not isinstance(item, dict) for item in premises):
            raise ValueError("Premise entries must be objects")
        # The authored method still consumes evidence entries. It must not make
        # malformed, nonfinite or cyclic payloads usable merely because it has
        # no designated numerical calculation.
        for item in evidence:
            _check_json(item["value"])
        errors = validate_mode(method, [item["kind"] for item in evidence], registry=registry)
        if errors:
            return identified({"status": "unsupported", "reasons": errors, "details": {}})
        contract = registry.get(method)
        if contract.builtin_mode is not None:
            check_implementation_identity(contract)
        selected = None
        if contract.builtin_mode == "structured":
            available = bool(evidence) or any(item.get("status") in ("supported", "contested") for item in premises)
            payload = {}
        else:
            selected = next(item for item in evidence if item["kind"] == contract.evidence_kind)
            payload = selected["value"]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        input_digest = hashlib.sha256(encoded).hexdigest()
        if len(encoded) > contract.max_input_bytes:
            raise ValueError("Method input exceeds byte limit")
        errors = schema_errors(payload, contract.input_schema)
        if errors:
            raise ValueError("Method input contract violation: " + "; ".join(errors))
        if contract.builtin_mode == "structured":
            result = _result(available, "Authored support is available; prose sufficiency is not mechanically established"
                             if available else "Structured reasoning requires evidence or a supported premise",
                             **contract.implementation(payload))
        else:
            result = (contract.implementation(payload) if contract.builtin_mode
                      else execute_extension(contract, payload))
        # Domain checks inside a computation can be stricter than the schema;
        # neither replaces the registered input/output contract. In particular,
        # bounded inputs can produce a numerical result outside the output's
        # represented range. A failed computation may intentionally return only
        # diagnostic fields, so the success schema applies to usable results.
        if result["status"] == "supported":
            errors = schema_errors(result["details"], contract.output_schema)
            if errors:
                raise ValueError("Method output contract violation: " + "; ".join(errors))
            encoded = json.dumps(result["details"], sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(encoded) > contract.max_output_bytes:
                raise ValueError("Method output exceeds byte limit")
        # Host provenance is not a method output and cannot overwrite a field
        # supplied under the registered result contract.
        if selected is not None:
            result["evidence_id"] = selected["id"]
            # Bind the computation to the exact finite JSON input it consumed.
            # Adequacy can then detect a collection substituted after assessment,
            # including an untyped method input that has no proposition query.
            result["input_digest"] = input_digest
        return identified(result)
    except (ValueError, TypeError, OverflowError, RecursionError, KeyError, UnicodeError) as exc:
        return identified(_result(False, f"Method evaluation failed: {exc}"))
