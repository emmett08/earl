"""Stateless OpenAI Responses adapter for text and host-executed functions.

The host retains the full operation boundary. Native calls are translated to
the same flat requests used by text models; returned reasoning/function items
are replayed verbatim with the matching host feedback on the next turn.
Credentials remain environment references and never enter report metadata.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

import httpx

from .http_provider import (bearer_headers, native_operation_schema, post_json,
                            validate_api_key_env, validate_endpoint,
                            validate_max_response_bytes, validate_model)
from .providers import (ModelResponse, ProviderError, _capabilities, _positive,
                        _pricing, _sampling)
from .runtime import strict_json


class ResponsesProvider:
    """Non-streaming, byte-bounded Responses API model adapter."""

    def __init__(self, *, model: str, endpoint: str = "https://api.openai.com/v1/responses",
                 api_key_env: str | None = "OPENAI_API_KEY", sampling: dict | None = None,
                 pricing: dict | None = None, timeout_seconds: float = 60,
                 max_response_bytes: int = 1_048_576, label: str = "responses",
                 capabilities: dict | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        validate_endpoint(endpoint, invalid="endpoint must be an HTTPS URL or local HTTP URL without credentials or query")
        validate_api_key_env(api_key_env, invalid="api_key_env must name an environment variable or be null")
        validate_model(model, invalid="model must be an explicit nonempty identity")
        validate_max_response_bytes(max_response_bytes)
        self.model, self.endpoint, self.api_key_env = model, endpoint, api_key_env
        self.sampling, self.pricing = _sampling(sampling or {}), _pricing(pricing or {})
        if "seed" in self.sampling:
            raise ValueError("Responses adapter does not declare a seed parameter")
        self.timeout_seconds = _positive(timeout_seconds, "timeout_seconds")
        self.max_response_bytes, self.label = max_response_bytes, label
        self.capabilities = _capabilities(capabilities or {})
        self.transport = transport
        # A random, host-held handle selects the exact prior output. Matching
        # on model text would replay another task's private reasoning when two
        # runs produced the same JSON operation.
        self._replay_items: dict[str, tuple[str, str | None, list[dict[str, Any]]]] = {}

    def identity(self) -> dict[str, Any]:
        return {"provider": self.label, "adapter": "responses", "model": self.model,
                "endpoint": self.endpoint, "sampling": self.sampling, "pricing": self.pricing,
                "measurement_kind": "model", "capabilities": self.capabilities,
                "state": "stateless_replay"}

    def discard_replay_handles(self, handles: list[str]) -> None:
        """Release one completed host interaction's private reasoning items."""
        for handle in handles:
            self._replay_items.pop(handle, None)

    def _input(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        used_handles: set[str] = set()
        pending_call: str | None = None
        for message in messages:
            if not isinstance(message, dict):
                raise ProviderError("Model messages must be objects")
            role = message.get("role")
            if role in {"system", "developer", "user"}:
                if not isinstance(message.get("content"), str):
                    raise ProviderError("Model message content must be text")
                result.append({"role": role, "content": message["content"]})
            elif role == "assistant" and isinstance(message.get("tool_calls"), list):
                calls = message["tool_calls"]
                if len(calls) != 1 or not isinstance(calls[0], dict):
                    raise ProviderError("Only one retained function call can be replayed")
                call_id = calls[0].get("id")
                handle = message.get("_responses_replay_handle")
                retained = self._replay_items.get(handle) if isinstance(handle, str) else None
                if retained is None or retained[1] != call_id or handle in used_handles or pending_call:
                    raise ProviderError("Missing original reasoning and function call items for replay")
                result.extend(retained[2])
                used_handles.add(handle)
                pending_call = call_id
            elif role == "assistant" and isinstance(message.get("content"), str):
                content = message["content"]
                handle = message.get("_responses_replay_handle")
                retained = self._replay_items.get(handle) if isinstance(handle, str) else None
                if handle is not None and (retained is None or retained[0] != content or retained[1] is not None):
                    raise ProviderError("Assistant replay handle does not match returned text")
                if handle in used_handles or pending_call:
                    raise ProviderError("Assistant replay has a duplicate handle or pending function")
                if retained is not None:
                    result.extend(retained[2])
                    used_handles.add(handle)
                else:
                    result.append({"role": "assistant", "content": content})
            elif role == "tool" and isinstance(message.get("tool_call_id"), str) and isinstance(message.get("content"), str):
                if message["tool_call_id"] != pending_call:
                    raise ProviderError("Function output has no retained model call")
                result.append({"type": "function_call_output",
                               "call_id": message["tool_call_id"], "output": message["content"]})
                pending_call = None
            else:
                raise ProviderError("Model transcript has an unsupported message")
        if pending_call:
            raise ProviderError("Function call has no host output for continuation")
        return result

    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse:
        return await self._complete(messages, max_output_tokens)

    async def complete_request(self, messages: list[dict[str, Any]], max_output_tokens: int, *,
                               operations: list[dict], native_tools: bool = False) -> ModelResponse:
        return await self._complete(messages, max_output_tokens, operations=operations,
                                    native_tools=native_tools)

    async def _complete(self, messages: list[dict[str, Any]], max_output_tokens: int, *,
                        operations: list[dict] | None = None,
                        native_tools: bool = False) -> ModelResponse:
        if type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        if native_tools and (not self.capabilities["native_tools"] or not operations):
            raise ProviderError("Native functions require enabled capability and operation schemas")
        headers = bearer_headers(self.api_key_env, ProviderError)
        payload: dict[str, Any] = {"model": self.model, "input": self._input(messages),
                                   "store": False, "include": ["reasoning.encrypted_content"],
                                   "max_output_tokens": max_output_tokens,
                                   **self.sampling}
        if "reasoning_effort" in self.capabilities:
            payload["reasoning"] = {"effort": self.capabilities["reasoning_effort"]}
        if native_tools:
            tools = []
            for entry in operations or []:
                schema = native_operation_schema(entry)
                tools.append({"type": "function", "name": entry["operation"],
                              "description": entry.get("description") or entry["operation"],
                              "parameters": schema, "strict": False})
            payload.update(tools=tools, tool_choice="required", parallel_tool_calls=False)
        elif self.capabilities["structured_output"] == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        elif self.capabilities["structured_output"] == "json_schema" and operations:
            schema = {"type": "object", "properties": {
                "request": {"anyOf": [entry["input_schema"] for entry in operations]}},
                "required": ["request"], "additionalProperties": False}
            payload["text"] = {"format": {"type": "json_schema", "name": "eal_reply",
                                         "schema": schema, "strict": False}}
        data = await post_json(self.endpoint, headers, payload,
                               timeout_seconds=self.timeout_seconds,
                               max_response_bytes=self.max_response_bytes,
                               transport=self.transport, error_type=ProviderError)
        if not isinstance(data, dict) or not isinstance(data.get("output"), list):
            raise ProviderError("Responses endpoint returned malformed output")
        usage = data.get("usage")
        if not isinstance(usage, dict):
            raise ProviderError("Responses endpoint returned malformed usage")
        metadata = {key: data[key] for key in ("id", "service_tier") if key in data}
        cached = usage.get("input_tokens_details", {})
        if isinstance(cached, dict) and "cached_tokens" in cached:
            metadata["cached_input_tokens"] = cached["cached_tokens"]
        details = usage.get("output_tokens_details", {})
        if isinstance(details, dict) and "reasoning_tokens" in details:
            metadata["reasoning_tokens"] = details["reasoning_tokens"]
        try:
            measured = ModelResponse("", usage.get("input_tokens"), usage.get("output_tokens"),
                                     data.get("model"), metadata)
        except (ValueError, TypeError) as exc:
            raise ProviderError("Responses endpoint returned invalid usage", response=None) from exc
        if data.get("status") != "completed" or data.get("error") or data.get("incomplete_details"):
            raise ProviderError("Model response was incomplete", response=measured)
        output = data["output"]
        if native_tools:
            calls = [item for item in output if isinstance(item, dict) and item.get("type") == "function_call"]
            if len(calls) != 1 or any(not isinstance(item, dict) or item.get("type") not in
                                      {"function_call", "reasoning"} for item in output):
                raise ProviderError("Native response must contain one function call and optional reasoning", response=measured)
            call = calls[0]
            if (not isinstance(call.get("call_id"), str) or not call["call_id"]
                    or call.get("name") not in {entry["operation"] for entry in operations or []}
                    or not isinstance(call.get("arguments"), str)):
                raise ProviderError("Native response has an invalid function call", response=measured)
            try:
                arguments = strict_json(call["arguments"])
                if not isinstance(arguments, dict) or "operation" in arguments:
                    raise ValueError("Expected object arguments without an operation field")
                flat = json.dumps({"operation": call["name"], **arguments}, ensure_ascii=False, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ProviderError("Native function arguments are invalid", response=measured) from exc
            handle = secrets.token_urlsafe(24)
            self._replay_items[handle] = (flat, call["call_id"], output)
            metadata["responses_replay_handle"] = handle
            metadata["native_tool_call"] = {"id": call["call_id"], "type": "function",
                                            "function": {"name": call["name"], "arguments": call["arguments"]}}
            return ModelResponse(flat, measured.input_tokens, measured.output_tokens, measured.model, metadata)
        if any(not isinstance(item, dict) or item.get("type") not in {"message", "reasoning"} for item in output):
            raise ProviderError("Text response contained a tool or non-message item", response=measured)
        pieces = []
        for item in output:
            if item["type"] == "reasoning":
                continue
            if item.get("status") not in (None, "completed") or not isinstance(item.get("content"), list):
                raise ProviderError("Text response contained an incomplete message", response=measured)
            for content in item["content"]:
                if not isinstance(content, dict) or content.get("type") != "output_text" or not isinstance(content.get("text"), str):
                    raise ProviderError("Text response contained non-text content", response=measured)
                pieces.append(content["text"])
        if not pieces:
            raise ProviderError("Text response contained no text", response=measured)
        result = "".join(pieces)
        if self.capabilities["structured_output"] == "json_schema" and operations:
            try:
                wrapper = strict_json(result)
                if not isinstance(wrapper, dict) or set(wrapper) != {"request"} or not isinstance(wrapper["request"], dict):
                    raise ValueError("Expected a request envelope")
                metadata["structured_response_text"] = result
                result = json.dumps(wrapper["request"], ensure_ascii=False, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ProviderError("Structured response did not contain one request", response=measured) from exc
        handle = secrets.token_urlsafe(24)
        self._replay_items[handle] = (result, None, output)
        metadata["responses_replay_handle"] = handle
        return ModelResponse(result, measured.input_tokens, measured.output_tokens,
                             measured.model, metadata)
