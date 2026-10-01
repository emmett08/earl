"""Sanitise host response values without changing their JSON contracts."""

from __future__ import annotations

import json
from typing import Any

from .tool_acquisition import strict_json


def _redact(value: Any, token: str | None) -> Any:
    """Sanitise remote values while preserving their JSON field names.

    A credential can coincide with a public schema identifier. Field names are
    structural metadata, so redaction applies to values instead. MCP text blocks
    can contain a second JSON representation of the application result; decode
    those before redaction to preserve the same field names in both forms.
    """
    if token is None:
        return value
    if isinstance(value, str):
        try:
            decoded = strict_json(value)
        except ValueError:
            decoded = None
        if isinstance(decoded, (dict, list, str)):
            sanitised = _redact(decoded, token)
            if sanitised == decoded:
                return value
            return json.dumps(sanitised, ensure_ascii=False, allow_nan=False)
        return value.replace(token, "[redacted]")
    if isinstance(value, list):
        return [_redact(item, token) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item, token) for key, item in value.items()}
    return value


def sanitise_response(response: dict[str, Any], token: str | None) -> dict[str, Any]:
    """Keep public host metadata stable and sanitise application data and errors."""
    metadata = {"operation", "protocol_version", "is_error"}
    sanitised = {key: value if key in metadata else _redact(value, token)
                 for key, value in response.items()}
    if isinstance(response.get("content"), list):
        sanitised["content"] = [
            {key: value if key == "type" else _redact(value, token)
             for key, value in block.items()} if isinstance(block, dict)
            else _redact(block, token)
            for block in response["content"]
        ]
    return sanitised
