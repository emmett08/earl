"""Coherent synthetic provenance for pure evaluator unit tests.

The dummy binding identity is deliberately confined to tests that call
``evaluate`` directly; runtime integration tests use the real registry digest.
"""

from eal.evaluator import canonical_digest
from eal.runtime import acquisition_request


def synthetic_provenance(program, evidence_id, context):
    evidence = program.evidence[evidence_id]
    request = acquisition_request(program, evidence_id, context)
    full_request = {"evidence_id": evidence_id, "environment": evidence.environment,
                    **request}
    return {
        "tool_binding_digest": "0" * 64,
        "input": evidence.input,
        "context": dict(context),
        "acquisition_request": request,
        "acquisition_request_digest": canonical_digest(request),
        "request_digest": canonical_digest(full_request),
    }
