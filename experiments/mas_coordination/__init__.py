"""Optional EAL-aware agent coordination experiment; not an EAL extension."""

from .protocol import (
    PAYLOAD_SCHEMA,
    ProtocolError,
    ScopeAnchor,
    Validator,
    decode_payload,
    make_anchor,
    make_message,
    proposal_fields,
)

__all__ = [
    "PAYLOAD_SCHEMA", "ProtocolError", "ScopeAnchor", "Validator",
    "decode_payload", "make_anchor", "make_message", "proposal_fields",
]
