"""Paid-attempt error categories come from bounded HTTP responses, without retries."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from eal.providers import ChatCompletionsProvider, ProviderError
from eal.responses_provider import ResponsesProvider


@pytest.mark.parametrize("adapter", [ChatCompletionsProvider, ResponsesProvider])
@pytest.mark.parametrize("status, code, category, retryable", [
    (401, "invalid_api_key", "http_authentication", False),
    (403, "permission_denied", "http_permission", False),
    (429, "insufficient_quota", "http_account", False),
    (429, "rate_limit_exceeded", "http_rate_limit", True),
    (503, "server_error", "http_server", True),
    (400, "invalid_request_error", "http_request", False),
])
def test_http_failure_diagnostics_are_classified_and_do_not_retain_remote_messages(
        adapter, status, code, category, retryable):
    attempts = []

    def handler(request):
        attempts.append(request)
        return httpx.Response(status, json={"error": {
            "message": "private prompt and credential must not be retained", "code": code,
            "type": "invalid_request_error", "extra": "private-value"}})

    provider = adapter(model="explicit", api_key_env=None, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 100))
    error = failure.value
    assert len(attempts) == 1
    assert error.category == category
    assert error.retryable is retryable
    assert error.response is None  # No token usage returned; the host keeps accounting unknown.
    assert error.diagnostics == {"http_status": status, "error": {
        "code": code, "type": "invalid_request_error"}}
    assert "private" not in json.dumps(error.diagnostics) + str(error)


def test_unknown_remote_error_codes_are_not_copied_into_diagnostics():
    provider = ResponsesProvider(model="explicit", api_key_env=None,
        transport=httpx.MockTransport(lambda _: httpx.Response(400, json={"error": {
            "code": "private-credential", "type": "private-prompt", "message": "private-message"}})))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 100))
    assert failure.value.diagnostics == {"http_status": 400, "error": {
        "code": "unrecognised", "type": "unrecognised"}}
    assert "private" not in json.dumps(failure.value.diagnostics)


@pytest.mark.parametrize("transport_error, category", [
    (httpx.ConnectError("private-host"), "transport"),
    (httpx.ReadTimeout("private-host"), "timeout"),
])
def test_transport_failures_are_retryable_but_never_implicitly_retried(transport_error, category):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        raise transport_error

    provider = ResponsesProvider(model="explicit", api_key_env=None,
                                 transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 100))
    assert attempts == 1
    assert failure.value.category == category
    assert failure.value.retryable is True
    assert failure.value.response is None
    assert "private" not in str(failure.value)


def test_oversized_authentication_error_keeps_status_with_bounded_diagnostics():
    provider = ResponsesProvider(model="explicit", api_key_env=None, max_response_bytes=32,
        transport=httpx.MockTransport(lambda _: httpx.Response(401, text="private" * 100)))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 100))
    assert failure.value.category == "http_authentication"
    assert failure.value.diagnostics == {"http_status": 401, "error_body_over_limit": True}
    assert "private" not in str(failure.value)
