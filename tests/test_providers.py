import asyncio
import json
import sys

import httpx
import pytest

from eal.providers import (ChatCompletionsProvider, CommandProvider, ModelResponse,
                           ProviderError, provider_from_config, response_cost)


def test_command_provider_uses_literal_argv_and_real_subprocess(tmp_path):
    script = tmp_path / "provider.py"
    script.write_text("import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({'text':sys.argv[1], 'input_tokens':3, 'output_tokens':2,'model':r['model']}))\n")
    literal = "$(touch should-not-exist); echo secret"
    provider = CommandProvider(argv=[sys.executable, str(script), literal], model="scripted-interface", workspace=tmp_path,
                               measurement_kind="interface_only")
    result = asyncio.run(provider.complete([{"role": "user", "content": "task"}], 128))
    assert result.text == literal
    assert result.input_tokens == 3 and result.output_tokens == 2
    assert not (tmp_path / "should-not-exist").exists()
    assert provider.identity()["measurement_kind"] == "interface_only"


@pytest.mark.parametrize("script,expected", [
    ("import time; time.sleep(5)", "timed out"),
    ("print('x' * 2048)", "byte limit"),
    ("print('{bad')", "malformed"),
    ("import sys; print('credential-value',file=sys.stderr); sys.exit(2)", "status 2"),
    ("print('{\"text\":\"a\",\"input_tokens\":true}')", "invalid"),
])
def test_command_failure_is_bounded_and_sanitised(tmp_path, script, expected):
    provider = CommandProvider(argv=[sys.executable, "-c", script], model="scripted-interface", workspace=tmp_path,
                               timeout_seconds=0.1, max_response_bytes=1024)
    with pytest.raises(ProviderError, match=expected) as error:
        asyncio.run(provider.complete([], 20))
    assert "credential-value" not in str(error.value)


@pytest.mark.parametrize("text,exit_code", [(False, 0), ("unusable response body", 2)])
def test_command_failures_retain_available_usage(tmp_path, text, exit_code):
    script = "import json,sys; print(json.dumps(" + repr({"text": text, "input_tokens": 3, "output_tokens": 2}) + ")); sys.exit(" + str(exit_code) + ")"
    provider = CommandProvider(argv=[sys.executable, "-c", script], model="scripted-interface", workspace=tmp_path)
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 20))
    assert failure.value.response.input_tokens == 3
    assert failure.value.response.output_tokens == 2


def response_data(**updates):
    return {"model": "model-version", "id": "response-id", "usage": {"prompt_tokens": 120, "completion_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 20}},
            "choices": [{"message": {"content": '{"operation":"stop","reason":"done"}'}, "finish_reason": "stop"}], **updates}


def test_http_adapter_protocol_without_native_tool_or_json_features(monkeypatch):
    monkeypatch.setenv("TEST_PROVIDER_KEY", "never-log-this-key")

    def respond(request):
        assert request.headers["Authorization"] == "Bearer never-log-this-key"
        body = json.loads(request.content)
        assert body["max_completion_tokens"] == 123
        assert body["temperature"] == 0.2 and body["seed"] == 7
        assert not {"tools", "response_format", "tool_choice"} & body.keys()
        return httpx.Response(200, json=response_data())

    provider = ChatCompletionsProvider(model="explicit-model", api_key_env="TEST_PROVIDER_KEY",
                                      sampling={"temperature": 0.2, "seed": 7},
                                      transport=httpx.MockTransport(respond))
    result = asyncio.run(provider.complete([{"role": "user", "content": "task"}], 123))
    assert result.model == "model-version"
    assert result.metadata["cached_input_tokens"] == 20
    assert "never-log-this-key" not in json.dumps(provider.identity())
    assert "never-log-this-key" not in json.dumps(result.metadata)


@pytest.mark.parametrize("data", [
    response_data(choices=[]),
    response_data(choices=[{"message": {"content": None}, "finish_reason": "stop"}]),
    response_data(choices=[{"message": {"content": "partial"}, "finish_reason": "length"}]),
    response_data(choices=[{"message": {"content": "native", "tool_calls": [{}]}, "finish_reason": "stop"}]),
])
def test_http_rejected_response_retains_reported_usage(data):
    provider = ChatCompletionsProvider(model="explicit-model", api_key_env=None,
                                      transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)))
    with pytest.raises(ProviderError) as failure:
        asyncio.run(provider.complete([], 20))
    assert failure.value.response.input_tokens == 120
    assert failure.value.response.output_tokens == 10


def test_http_failure_body_and_credentials_do_not_enter_errors(monkeypatch):
    monkeypatch.setenv("TEST_PROVIDER_KEY", "never-log-this-key")
    provider = ChatCompletionsProvider(model="explicit-model", api_key_env="TEST_PROVIDER_KEY",
                                      transport=httpx.MockTransport(lambda _: httpx.Response(401, text="never-log-this-key")))
    with pytest.raises(ProviderError, match="HTTP 401") as failure:
        asyncio.run(provider.complete([], 20))
    assert "never-log-this-key" not in str(failure.value)
    assert failure.value.response is None


def test_http_output_and_url_limits():
    with pytest.raises(ValueError, match="credentials"):
        ChatCompletionsProvider(model="x", endpoint="https://host/path?key=secret")
    with pytest.raises(ValueError, match="HTTPS"):
        ChatCompletionsProvider(model="x", endpoint="http://example.com/path")
    provider = ChatCompletionsProvider(model="x", api_key_env=None, max_response_bytes=10,
                                      transport=httpx.MockTransport(lambda _: httpx.Response(200, text="x" * 20)))
    with pytest.raises(ProviderError, match="byte limit"):
        asyncio.run(provider.complete([], 20))


def test_cost_requires_usage_and_explicit_rates_including_cached_tokens():
    result = ModelResponse("x", 120, 10, metadata={"cached_input_tokens": 20})
    identity = {"pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2}}
    assert response_cost(result, identity) is None
    identity["pricing"]["cached_input_usd_per_million"] = 0.5
    assert response_cost(result, identity) == pytest.approx(0.00013)
    assert response_cost(ModelResponse("x"), identity) is None
    assert response_cost(result, {}) is None


@pytest.mark.parametrize("config", [
    {"kind": "unknown"}, {"kind": "command", "argv": ["x"], "model": "m", "secret": "bad"},
    {"kind": "chat_completions", "model": "m", "sampling": {"tools": []}},
    {"kind": "chat_completions", "model": "m", "pricing": {"input_usd_per_million": -1}},
])
def test_provider_configuration_rejects_unknown_or_invalid_contracts(config):
    with pytest.raises(ValueError):
        provider_from_config(config)
