"""Public provider imports, configuration and error contracts across adapters."""

from __future__ import annotations

import asyncio
import pickle

import httpx
import pytest

from eal.providers import (ChatCompletionsProvider, CommandProvider, ModelResponse,
                           ProviderError, TextProvider, provider_from_config)
from eal.responses_provider import ResponsesProvider


def test_public_response_types_remain_defined_and_importable_from_providers():
    assert ModelResponse.__module__ == "eal.providers"
    assert ProviderError.__module__ == "eal.providers"
    assert TextProvider.__module__ == "eal.providers"
    response = ModelResponse("checked", 2, 1, "m", {"id": "test"})
    assert pickle.loads(pickle.dumps(response)) == response
    assert isinstance(ProviderError("failed", response=response).response, ModelResponse)


def test_default_provider_identities_and_command_digest_are_stable():
    command = CommandProvider(argv=["echo", "ok"], model="m")
    assert command.identity() == {
        "provider": "command", "adapter": "command", "model": "m",
        "sampling": {}, "pricing": {}, "measurement_kind": "model",
        "command_digest": "b1214315518d99b627a49b2c46534c8481b626d31ce9572b906c3d968b67ae82",
    }
    default_capabilities = {"native_tools": False, "structured_output": "none",
                            "tool_reasoning_compatible": False}
    assert ChatCompletionsProvider(model="m").identity() == {
        "provider": "chat_completions", "adapter": "chat_completions", "model": "m",
        "endpoint": "https://api.openai.com/v1/chat/completions", "sampling": {},
        "pricing": {}, "max_tokens_field": "max_completion_tokens",
        "measurement_kind": "model", "capabilities": default_capabilities,
    }
    assert ResponsesProvider(model="m").identity() == {
        "provider": "responses", "adapter": "responses", "model": "m",
        "endpoint": "https://api.openai.com/v1/responses", "sampling": {},
        "pricing": {}, "measurement_kind": "model", "capabilities": default_capabilities,
        "state": "stateless_replay",
    }


@pytest.mark.parametrize("kind,expected", [
    ("chat_completions", ChatCompletionsProvider),
    ("responses", ResponsesProvider),
    ("command", CommandProvider),
])
def test_config_selects_same_public_adapter(kind, expected):
    fields = {"argv": ["echo"]} if kind == "command" else {}
    assert isinstance(provider_from_config({"kind": kind, "model": "m", **fields}), expected)
    with pytest.raises(ValueError, match="missing or unknown fields"):
        provider_from_config({"kind": kind, "model": "m", **fields, "unknown": True})


@pytest.mark.parametrize("adapter,endpoint,message", [
    (ChatCompletionsProvider, "https://host/path?key=secret",
     "endpoint must be an HTTP(S) URL without credentials, query or fragment"),
    (ChatCompletionsProvider, "http://example.com/path",
     "Non-local HTTP endpoints must use HTTPS"),
    (ResponsesProvider, "https://host/path?key=secret",
     "endpoint must be an HTTPS URL or local HTTP URL without credentials or query"),
    (ResponsesProvider, "http://example.com/path",
     "endpoint must be an HTTPS URL or local HTTP URL without credentials or query"),
])
def test_endpoint_errors_retain_adapter_specific_wording(adapter, endpoint, message):
    with pytest.raises(ValueError) as failure:
        adapter(model="m", endpoint=endpoint)
    assert str(failure.value) == message


@pytest.mark.parametrize("adapter", [ChatCompletionsProvider, ResponsesProvider])
def test_absent_credential_and_status_errors_remain_exact(adapter, monkeypatch):
    monkeypatch.delenv("EAL_CONFORMANCE_KEY", raising=False)
    provider = adapter(model="m", api_key_env="EAL_CONFORMANCE_KEY")
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 20))
    assert str(failure.value) == "Configured credential variable EAL_CONFORMANCE_KEY is absent"
    assert failure.value.response is None
    provider = adapter(model="m", api_key_env=None,
                       transport=httpx.MockTransport(lambda _: httpx.Response(403, text="secret body")))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 20))
    assert str(failure.value) == "Model endpoint returned HTTP 403"
    assert failure.value.response is None
    assert failure.value.__cause__ is None
