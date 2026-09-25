"""Shared HTTP boundary for model adapters; payload and response codecs stay local."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from .runtime import strict_json


class HTTPErrorFactory(Protocol):
    def __call__(self, message: str, *, category: str = "provider_error",
                 retryable: bool = False, diagnostics: dict[str, Any] | None = None) -> RuntimeError: ...


# These are classifications, not copied remote strings. Error messages and
# arbitrary remote fields can echo prompt content or credentials.
_SAFE_ERROR_CODES = frozenset({
    "invalid_api_key", "insufficient_quota", "billing_hard_limit_reached",
    "billing_not_active", "account_deactivated", "rate_limit_exceeded",
    "model_not_found", "permission_denied", "invalid_request_error",
    "server_error", "internal_server_error", "service_unavailable",
})
_SAFE_ERROR_TYPES = frozenset({
    "invalid_request_error", "authentication_error", "permission_error",
    "insufficient_quota", "rate_limit_error", "server_error", "api_error",
})


def safe_error_details(value: Any) -> dict[str, str]:
    """Retain documented error classifications without the remote message."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, allowed in (("code", _SAFE_ERROR_CODES), ("type", _SAFE_ERROR_TYPES)):
        item = value.get(key)
        if isinstance(item, str):
            result[key] = item if item in allowed else "unrecognised"
    return result


def http_error_classification(status: int, details: dict[str, str]) -> tuple[str, bool]:
    if set(details.values()) & {"insufficient_quota", "billing_hard_limit_reached",
                                "billing_not_active", "account_deactivated"} or status == 402:
        return "http_account", False
    if status == 401:
        return "http_authentication", False
    if status == 403:
        return "http_permission", False
    if status == 429:
        return "http_rate_limit", True
    if status >= 500:
        return "http_server", True
    if status in {408, 409}:
        return "http_transient", True
    return "http_request", False


def validate_endpoint(endpoint: str, *, invalid: str, insecure: str | None = None) -> None:
    url = urlsplit(endpoint)
    if (url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise ValueError(invalid)
    if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(insecure or invalid)


def validate_api_key_env(name: str | None, *, invalid: str) -> None:
    if name is not None and (not isinstance(name, str) or not name.isidentifier()):
        raise ValueError(invalid)


def validate_model(model: str, *, invalid: str) -> None:
    if not isinstance(model, str) or not model:
        raise ValueError(invalid)


def validate_max_response_bytes(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_response_bytes must be between 1 and 16 MiB")


def bearer_headers(api_key_env: str | None, error_type: HTTPErrorFactory) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key_env is not None:
        credential = os.environ.get(api_key_env)
        if not credential:
            raise error_type(f"Configured credential variable {api_key_env} is absent",
                             category="configuration")
        headers["Authorization"] = "Bearer " + credential
    return headers


def native_operation_schema(entry: dict) -> dict:
    """Copy and remove the host's operation discriminator for a native tool."""
    schema = strict_json(json.dumps(entry["input_schema"], allow_nan=False))
    schema.get("properties", {}).pop("operation", None)
    schema["required"] = [key for key in schema.get("required", []) if key != "operation"]
    return schema


async def post_json(endpoint: str, headers: dict[str, str], payload: dict[str, Any], *,
                    timeout_seconds: float, max_response_bytes: int,
                    transport: httpx.AsyncBaseTransport | None,
                    error_type: HTTPErrorFactory) -> Any:
    """Make one bounded, non-redirecting request without retaining a secret or remote body."""
    try:
        async with asyncio.timeout(timeout_seconds), httpx.AsyncClient(
                timeout=timeout_seconds, follow_redirects=False, transport=transport) as client:
            async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                status = response.status_code
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_response_bytes:
                        if status != 200:
                            category, retryable = http_error_classification(status, {})
                            raise error_type(f"Model endpoint returned HTTP {status}",
                                             category=category, retryable=retryable,
                                             diagnostics={"http_status": status, "error_body_over_limit": True})
                        raise error_type("Model endpoint response exceeded its byte limit",
                                         category="response_byte_limit")
                    chunks.append(chunk)
                if status != 200:
                    details = {}
                    try:
                        body = strict_json(b"".join(chunks).decode("utf-8"))
                        if isinstance(body, dict):
                            details = safe_error_details(body.get("error"))
                    except (UnicodeError, ValueError):
                        pass
                    category, retryable = http_error_classification(status, details)
                    raise error_type(f"Model endpoint returned HTTP {status}",
                                     category=category, retryable=retryable,
                                     diagnostics={"http_status": status, "error": details})
        return strict_json(b"".join(chunks).decode("utf-8"))
    except httpx.TimeoutException as exc:
        raise error_type("Model endpoint timed out", category="timeout", retryable=True) from exc
    except httpx.HTTPError as exc:
        raise error_type("Model endpoint transport failed", category="transport", retryable=True) from exc
    except TimeoutError as exc:
        raise error_type("Model endpoint timed out", category="timeout", retryable=True) from exc
    except (UnicodeError, ValueError) as exc:
        raise error_type("Model endpoint returned malformed UTF-8 JSON", category="invalid_response") from exc
