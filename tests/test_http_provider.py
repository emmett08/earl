"""HTTP boundary checks shared by both model API codecs."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from eal.providers import ChatCompletionsProvider, ProviderError
from eal.responses_provider import ResponsesProvider


@pytest.mark.parametrize("adapter", [ChatCompletionsProvider, ResponsesProvider])
def test_http_adapters_enforce_same_endpoint_and_response_bounds(adapter):
    with pytest.raises(ValueError, match="credentials"):
        adapter(model="m", endpoint="https://user:secret@example.com/v1")
    with pytest.raises(ValueError, match="HTTPS"):
        adapter(model="m", endpoint="http://example.com/v1")
    with pytest.raises(ValueError, match="max_response_bytes"):
        adapter(model="m", max_response_bytes=True)
    assert adapter(model="m", endpoint="http://127.0.0.1/v1", api_key_env=None).endpoint.endswith("/v1")


@pytest.mark.parametrize("adapter", [ChatCompletionsProvider, ResponsesProvider])
@pytest.mark.parametrize("response,expected", [
    (httpx.Response(302, headers={"Location": "https://example.com/redirect"}, text="private"), "HTTP 302"),
    (httpx.Response(200, text="x" * 200), "byte limit"),
    (httpx.Response(200, text='{"duplicate":1,"duplicate":2}'), "malformed UTF-8 JSON"),
])
def test_http_adapters_sanitise_transport_failures(adapter, response, expected):
    provider = adapter(model="m", api_key_env=None, max_response_bytes=100,
                       transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(ProviderError, match=expected) as failure:
        asyncio.run(provider.complete([{"role": "user", "content": "case"}], 20))
    assert "private" not in str(failure.value)
    assert failure.value.response is None


@pytest.mark.parametrize("adapter", [ChatCompletionsProvider, ResponsesProvider])
def test_native_schema_does_not_mutate_host_operation(adapter):
    operation = {"operation": "check", "input_schema": {"type": "object",
                 "properties": {"operation": {"const": "check"}, "subject": {"type": "string"}},
                 "required": ["operation", "subject"]}}
    original = json.dumps(operation, sort_keys=True)

    def respond(request):
        body = json.loads(request.content)
        if isinstance(provider, ChatCompletionsProvider):
            schema = body["tools"][0]["function"]["parameters"]
        else:
            schema = body["tools"][0]["parameters"]
        assert "operation" not in schema["properties"]
        assert schema["required"] == ["subject"]
        return httpx.Response(401)

    provider = adapter(model="m", api_key_env=None, capabilities={"native_tools": True},
                       transport=httpx.MockTransport(respond))
    with pytest.raises(ProviderError, match="HTTP 401"):
        asyncio.run(provider.complete_request([], 20, operations=[operation], native_tools=True))
    assert json.dumps(operation, sort_keys=True) == original
