"""Stateless Responses provider tests use a local HTTP transport, never paid calls."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from eal.providers import ProviderError, provider_from_config, response_cost
from eal.responses_provider import ResponsesProvider


OPERATION = {"operation": "assess_bound_task", "description": "Assess the launcher's bound task",
             "input_schema": {"type": "object",
                              "properties": {"operation": {"const": "assess_bound_task"}},
                              "required": ["operation"], "additionalProperties": False}}


def _response(output, *, input_tokens=120, output_tokens=30, status="completed"):
    return {"id": "resp-1", "model": "chosen-version", "status": status,
            "output": output,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                      "input_tokens_details": {"cached_tokens": 20},
                      "output_tokens_details": {"reasoning_tokens": 12}}}


def test_native_tool_call_replays_reasoning_and_call_id_without_leaking_credential(monkeypatch):
    monkeypatch.setenv("EAL_TEST_API_KEY", "test-credential-only")
    requests = []

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-credential-only"
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            return httpx.Response(200, json=_response([
                {"type": "reasoning", "id": "rs-1", "encrypted_content": "opaque"},
                {"type": "function_call", "id": "fc-1", "call_id": "call-1",
                 "name": "assess_bound_task", "arguments": "{}"},
            ]))
        assert payload["input"][-3:] == [
            {"type": "reasoning", "id": "rs-1", "encrypted_content": "opaque"},
            {"type": "function_call", "id": "fc-1", "call_id": "call-1",
             "name": "assess_bound_task", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call-1",
             "output": '{"status":"contested"}'},
        ]
        return httpx.Response(200, json=_response([
            {"type": "reasoning", "id": "rs-2", "encrypted_content": "opaque-2"},
            {"type": "message", "status": "completed",
             "content": [{"type": "output_text", "text": "The checked result is contested."}]},
        ]))

    provider = ResponsesProvider(
        model="explicit-model", api_key_env="EAL_TEST_API_KEY",
        capabilities={"native_tools": True, "reasoning_effort": "medium"},
        pricing={"input_usd_per_million": 2, "cached_input_usd_per_million": .2,
                 "output_usd_per_million": 10},
        transport=httpx.MockTransport(handler),
    )
    async def exercise():
        first = await provider.complete_request([{"role": "user", "content": "Check this task"}], 300,
                                                 operations=[OPERATION], native_tools=True)
        assert json.loads(first.text) == {"operation": "assess_bound_task"}
        assert first.metadata["native_tool_call"]["id"] == "call-1"
        assert first.metadata["reasoning_tokens"] == 12
        assert response_cost(first, provider.identity()) == pytest.approx((100 * 2 + 20 * .2 + 30 * 10) / 1_000_000)
        second = await provider.complete([
            {"role": "user", "content": "Check this task"},
            {"role": "assistant", "content": None, "tool_calls": [first.metadata["native_tool_call"]],
             "_responses_replay_handle": first.metadata["responses_replay_handle"]},
            {"role": "tool", "tool_call_id": "call-1", "content": '{"status":"contested"}'},
        ], 200)
        assert second.text == "The checked result is contested."
        assert "test-credential-only" not in json.dumps(first.metadata)

    asyncio.run(exercise())
    assert requests[0]["model"] == "explicit-model"
    assert requests[0]["store"] is False
    assert requests[0]["include"] == ["reasoning.encrypted_content"]
    assert requests[0]["reasoning"] == {"effort": "medium"}
    assert requests[0]["tools"][0]["strict"] is False
    assert requests[0]["tools"][0]["parameters"]["properties"] == {}
    assert requests[0]["parallel_tool_calls"] is False


def test_text_reasoning_items_are_replayed_when_model_returns_another_request():
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        number = len(requests)
        return httpx.Response(200, json=_response([
            {"type": "reasoning", "id": f"rs-{number}", "encrypted_content": "opaque"},
            {"type": "message", "status": "completed",
             "content": [{"type": "output_text", "text": f'{{"operation":"step_{number}"}}'}]},
        ]))

    provider = ResponsesProvider(model="explicit", api_key_env=None,
                                 transport=httpx.MockTransport(handler))

    async def exercise():
        first = await provider.complete([{"role": "user", "content": "Start"}], 100)
        assert first.text == '{"operation":"step_1"}'
        await provider.complete([{"role": "user", "content": "Start"},
                                 {"role": "assistant", "content": first.text,
                                  "_responses_replay_handle": first.metadata["responses_replay_handle"]},
                                 {"role": "user", "content": "Continue"}], 100)

    asyncio.run(exercise())
    assert requests[1]["input"][1]["type"] == "reasoning"
    assert requests[1]["input"][2]["type"] == "message"


def test_multiple_or_unknown_native_calls_are_not_executed():
    calls = [{"type": "function_call", "call_id": str(i), "name": "assess_bound_task",
              "arguments": "{}"} for i in range(2)]
    provider = ResponsesProvider(model="explicit", api_key_env=None,
                                 capabilities={"native_tools": True},
                                 transport=httpx.MockTransport(
                                     lambda request: httpx.Response(200, json=_response(calls))))
    with pytest.raises(ProviderError, match="one function call") as failure:
        asyncio.run(provider.complete_request([{"role": "user", "content": "Check"}], 100,
                                              operations=[OPERATION], native_tools=True))
    assert failure.value.response.input_tokens == 120
    assert provider._replay_items == {}


def test_same_text_in_two_tasks_replays_only_the_selected_output():
    sequence = 0

    def handler(request):
        nonlocal sequence
        sequence += 1
        return httpx.Response(200, json=_response([
            {"type": "reasoning", "id": f"rs-{sequence}",
             "encrypted_content": f"private-for-task-{sequence}"},
            {"type": "message", "status": "completed", "content": [
                {"type": "output_text", "text": '{"operation":"explain"}'}]},
        ]))

    provider = ResponsesProvider(model="explicit", api_key_env=None,
                                 transport=httpx.MockTransport(handler))

    async def exercise():
        first = await provider.complete([{"role": "user", "content": "Task A"}], 100)
        second = await provider.complete([{"role": "user", "content": "Task B"}], 100)
        replay = provider._input([
            {"role": "user", "content": "Task B"},
            {"role": "assistant", "content": second.text,
             "_responses_replay_handle": second.metadata["responses_replay_handle"]},
        ])
        assert replay[1]["id"] == "rs-2"
        assert "private-for-task-1" not in json.dumps(replay)
        with pytest.raises(ProviderError, match="does not match"):
            provider._input([{"role": "assistant", "content": "forged",
                              "_responses_replay_handle": second.metadata["responses_replay_handle"]}])
        assert first.metadata["responses_replay_handle"] != second.metadata["responses_replay_handle"]

    asyncio.run(exercise())


def test_structured_response_unwraps_only_one_valid_request():
    observed = []

    def handler(request):
        payload = json.loads(request.content)
        observed.append(payload)
        return httpx.Response(200, json=_response([
            {"type": "message", "status": "completed", "content": [
                {"type": "output_text", "text": '{"request":{"operation":"assess_bound_task"}}'}]},
        ]))

    provider = ResponsesProvider(model="explicit", api_key_env=None,
                                 capabilities={"structured_output": "json_schema"},
                                 transport=httpx.MockTransport(handler))
    result = asyncio.run(provider.complete_request(
        [{"role": "user", "content": "Check the reviewed task"}], 100,
        operations=[OPERATION]))
    assert json.loads(result.text) == {"operation": "assess_bound_task"}
    assert observed[0]["text"]["format"]["type"] == "json_schema"
    assert observed[0]["text"]["format"]["strict"] is False
    assert observed[0]["store"] is False


def test_incomplete_response_preserves_usage_but_does_not_issue_text():
    provider = ResponsesProvider(model="explicit", api_key_env=None,
                                 transport=httpx.MockTransport(lambda request:
                                     httpx.Response(200, json=_response([], status="incomplete"))))
    with pytest.raises(ProviderError, match="incomplete") as failure:
        asyncio.run(provider.complete([{"role": "user", "content": "Check"}], 100))
    assert failure.value.response.input_tokens == 120
    assert failure.value.response.output_tokens == 30


def test_config_loads_responses_and_rejects_missing_key_or_unsupported_seed():
    provider = provider_from_config({"kind": "responses", "model": "pinned"})
    assert isinstance(provider, ResponsesProvider)
    with pytest.raises(ProviderError, match="credential variable"):
        asyncio.run(provider.complete([{"role": "user", "content": "Check"}], 100))
    with pytest.raises(ValueError, match="seed"):
        ResponsesProvider(model="pinned", sampling={"seed": 4})
