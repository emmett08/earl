"""Both model hosts retain their usage schemas and unknown-measurement meaning."""

import asyncio
import hashlib

from eal.model_attempts import (
    invoke_provider, new_attempt, post_attempt_limit, pre_attempt_limit,
    record_response, summarise_usage,
)
from eal.providers import ModelResponse, ProviderError


def test_empty_usage_is_complete_but_has_no_tool_or_total_cost():
    common = {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        "known_input_tokens": 0, "known_output_tokens": 0,
        "token_usage_complete": True,
        "model_cost_usd": 0, "known_model_cost_usd": 0,
        "model_cost_complete": True, "cost_basis": "configured_token_rates",
        "tool_cost_usd": None, "total_cost_usd": None,
    }
    assert summarise_usage([], include_tool_completeness=False) == common
    assert summarise_usage([], include_tool_completeness=True) == {
        **common, "tool_cost_complete": False}


def test_failed_attempt_keeps_known_quantities_without_claiming_complete_usage():
    attempts = [
        {"input_tokens": 10, "output_tokens": 0, "model_cost_usd": 0.25},
        {"input_tokens": None, "output_tokens": 2, "model_cost_usd": None},
    ]
    expected = {
        "input_tokens": None, "output_tokens": None, "total_tokens": None,
        "known_input_tokens": 10, "known_output_tokens": 2,
        "token_usage_complete": False,
        "model_cost_usd": None, "known_model_cost_usd": 0.25,
        "model_cost_complete": False, "cost_basis": "configured_token_rates",
        "tool_cost_usd": None, "total_cost_usd": None,
    }
    assert summarise_usage(attempts, include_tool_completeness=False) == expected
    assert summarise_usage(attempts, include_tool_completeness=True) == {
        **expected, "tool_cost_complete": False}


def test_budget_thresholds_and_unknown_measurements_keep_host_ordering():
    usage = summarise_usage([{
        "input_tokens": 60, "output_tokens": 12, "model_cost_usd": 0.25,
    }], include_tool_completeness=False)
    assert pre_attempt_limit(usage, attempted=True, max_total_tokens=72,
                             max_model_cost_usd=0.25) == "token_budget_exhausted"
    assert pre_attempt_limit(usage, attempted=True, max_total_tokens=73,
                             max_model_cost_usd=0.25) == "model_cost_budget_exhausted"
    assert post_attempt_limit(usage, max_total_tokens=72, max_model_cost_usd=0.25,
                              require_token_usage=True) is None
    assert post_attempt_limit(usage, max_total_tokens=71, max_model_cost_usd=0.20,
                              require_token_usage=True) == "token_budget_exhausted"
    assert post_attempt_limit(usage, max_total_tokens=72, max_model_cost_usd=0.20,
                              require_token_usage=False) == "model_cost_budget_exhausted"
    assert pre_attempt_limit(usage, attempted=True, max_total_tokens=73,
                             max_model_cost_usd=1, pricing_available=False) == "cost_budget_unverifiable"

    unknown = summarise_usage([{
        "input_tokens": None, "output_tokens": None, "model_cost_usd": None,
    }], include_tool_completeness=False)
    assert pre_attempt_limit(unknown, attempted=True, max_total_tokens=73,
                             max_model_cost_usd=None) == "token_usage_unavailable"
    assert post_attempt_limit(unknown, max_total_tokens=73, max_model_cost_usd=None,
                              require_token_usage=True) == "token_usage_unavailable"
    # Recipient records an unknown response, then applies the token stop on its next turn.
    assert post_attempt_limit(unknown, max_total_tokens=73, max_model_cost_usd=None,
                              require_token_usage=False) is None
    assert post_attempt_limit(unknown, max_total_tokens=73, max_model_cost_usd=1,
                              require_token_usage=False) == "cost_budget_unverifiable"


def test_attempt_fields_and_response_measurement_are_stable():
    attempt = new_attempt(index=2, prompt="π", max_output_tokens=20,
                          prompt_digest_field="prompt_sha256")
    assert attempt == {
        "index": 2, "prompt_sha256": hashlib.sha256("π".encode()).hexdigest(),
        "prompt_bytes": 2, "max_output_tokens": 20,
        "input_tokens": None, "output_tokens": None, "model_cost_usd": None,
        "status": "pending",
    }
    response = ModelResponse("ok", 10, 2, model="sample", metadata={"cached_input_tokens": 3})
    data = record_response(
        attempt, response,
        {"pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2,
                     "cached_input_usd_per_million": 0.5}},
        response_digest_field="response_sha256", metadata={"cached_input_tokens": 3})
    assert data == b"ok"
    assert attempt["model_cost_usd"] == (7 + 1.5 + 4) / 1_000_000
    assert attempt["response_sha256"] == hashlib.sha256(b"ok").hexdigest()
    assert attempt["response_bytes"] == 2
    assert attempt["status"] == "pending"  # The caller owns success/failure transitions.


def test_provider_dispatch_copies_messages_and_preserves_invalid_response_error():
    class Provider:
        def __init__(self):
            self.calls = []

        async def complete(self, messages, max_output_tokens):
            self.calls.append(("text", messages, max_output_tokens))
            return ModelResponse("text")

        async def complete_request(self, messages, max_output_tokens, *, operations, native_tools):
            self.calls.append(("native", messages, max_output_tokens, operations, native_tools))
            return ModelResponse("native")

    provider = Provider()
    messages = [{"role": "user", "content": "request"}]
    assert asyncio.run(invoke_provider(provider, messages, 7, operations=None, native_tools=False,
                                      invalid_response_message="bad")) == ModelResponse("text")
    assert asyncio.run(invoke_provider(provider, messages, 8, operations=[], native_tools=True,
                                      invalid_response_message="bad")) == ModelResponse("native")
    assert provider.calls == [("text", messages, 7), ("native", messages, 8, [], True)]
    assert provider.calls[0][1] is not messages and provider.calls[1][1] is not messages

    async def invalid(_messages, _max_output_tokens):
        return None
    provider.complete = invalid
    try:
        asyncio.run(invoke_provider(provider, messages, 9, operations=None, native_tools=False,
                                    invalid_response_message="host-specific failure"))
    except ProviderError as exc:
        assert str(exc) == "host-specific failure"
    else:
        raise AssertionError("Invalid provider response was accepted")
