"""Sanitise remote JSON keys and values while retaining fixed host wrappers."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import AudioContent, EmbeddedResource, ImageContent, ResourceLink, TextContent

from .tool_acquisition import strict_json


_HOST_FIELDS = frozenset({"operation", "protocol_version", "is_error", "result", "content", "error"})
_HOST_METADATA = frozenset({"operation", "protocol_version", "is_error"})
# Only fields declared by the pinned MCP models are public wrapper names.
# Extra fields and keys inside application payloads remain remote data.
_CONTENT_FIELDS = {
    model.model_fields["type"].default: frozenset(model.model_fields) | frozenset(
        field.alias for field in model.model_fields.values() if field.alias
    )
    for model in (TextContent, ImageContent, AudioContent, ResourceLink, EmbeddedResource)
}


def _replacement(token: str) -> str:
    # An opaque credential may itself be the conventional marker or part of it.
    return "" if token in "[redacted]" else "[redacted]"


def _redact_text(value: str, token: str) -> str:
    sanitised = value.replace(token, _replacement(token))
    # Adjacent text can reconstruct the credential around a replacement marker.
    return "" if token in sanitised else sanitised


def _redact_object(value: dict[str, Any], token: str, *, public_keys: frozenset[str] = frozenset(),
                   public_values: frozenset[str] = frozenset()) -> dict[str, Any]:
    sanitised = {}
    for key, item in value.items():
        field = key if key in public_keys else _redact_text(key, token)
        if field in sanitised:
            raise ValueError("Credential redaction would merge distinct JSON object keys")
        sanitised[field] = item if key in public_values else _redact(item, token)
    return sanitised


def _redact(value: Any, token: str) -> Any:
    """Decode nested JSON representations before sanitising application data."""
    if isinstance(value, str):
        try:
            decoded = strict_json(value)
        except ValueError:
            # Unsafe JSON (including duplicate keys) can conceal an escaped
            # credential. Preserve no partially sanitised representation.
            if value.lstrip().startswith(("{", "[", '"')):
                return _replacement(token)
            decoded = None
        if isinstance(decoded, (dict, list, str)):
            sanitised = _redact(decoded, token)
            if sanitised == decoded:
                return value
            return json.dumps(sanitised, ensure_ascii=False, allow_nan=False)
        return _redact_text(value, token)
    if isinstance(value, list):
        return [_redact(item, token) for item in value]
    if isinstance(value, dict):
        return _redact_object(value, token)
    return value


def sanitise_response(response: dict[str, Any], token: str | None) -> dict[str, Any]:
    """Keep fixed wrappers stable; refuse redaction that would merge object keys."""
    if not token:
        return response
    content = response.get("content")
    public_values = _HOST_METADATA | {"content"} if isinstance(content, list) else _HOST_METADATA
    sanitised = _redact_object(response, token, public_keys=_HOST_FIELDS, public_values=public_values)
    if isinstance(content, list):
        sanitised["content"] = []
        for block in content:
            if isinstance(block, dict):
                kind = block.get("type")
                fields = _CONTENT_FIELDS.get(kind) if isinstance(kind, str) else None
                sanitised["content"].append(_redact_object(
                    block, token, public_keys=fields or frozenset({"type"}),
                    public_values=frozenset({"type"}) if fields else frozenset(),
                ))
            else:
                sanitised["content"].append(_redact(block, token))
    return sanitised
