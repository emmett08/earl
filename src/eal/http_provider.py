"""Shared HTTP boundary for model adapters; payload and response codecs stay local."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.parse import urlsplit

import httpx

from .runtime import strict_json


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


def bearer_headers(api_key_env: str | None, error_type: type[RuntimeError]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key_env is not None:
        credential = os.environ.get(api_key_env)
        if not credential:
            raise error_type(f"Configured credential variable {api_key_env} is absent")
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
                    error_type: type[RuntimeError]) -> Any:
    """Make one bounded, non-redirecting request without retaining a secret or remote body."""
    try:
        async with asyncio.timeout(timeout_seconds), httpx.AsyncClient(
                timeout=timeout_seconds, follow_redirects=False, transport=transport) as client:
            async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise error_type(f"Model endpoint returned HTTP {response.status_code}")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_response_bytes:
                        raise error_type("Model endpoint response exceeded its byte limit")
                    chunks.append(chunk)
        return strict_json(b"".join(chunks).decode("utf-8"))
    except httpx.HTTPError as exc:
        raise error_type("Model endpoint transport failed") from exc
    except TimeoutError as exc:
        raise error_type("Model endpoint timed out") from exc
    except (UnicodeError, ValueError) as exc:
        raise error_type("Model endpoint returned malformed UTF-8 JSON") from exc
