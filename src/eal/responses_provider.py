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
                            restore_optional_fields, strict_operation_schema,
                            safe_error_details,
                            validate_api_key_env, validate_endpoint,
                            validate_max_response_bytes, validate_model)
from .providers import (ModelResponse, ProviderError, _capabilities, _positive,
                        _pricing, _sampling)
from .runtime import strict_json


def _visible_output(output: Any) -> list[dict[str, Any]]:
    """Preserve message/part boundaries while omitting every reasoning item."""
    if not isinstance(output, list):
        return []
    visible = []
    for index, item in enumerate(output):
        if not isinstance(item, dict) or item.get("type") == "reasoning":
            continue
        if item.get("type") == "function_call":
            visible.append({"output_index": index, "type": "function_call", **{
                key: item[key] for key in ("id", "call_id", "name", "arguments", "status")
                if isinstance(item.get(key), str)}})
        elif item.get("type") == "message":
            message: dict[str, Any] = {"output_index": index, "type": "message", **{
                key: item[key] for key in ("id", "role", "status") if isinstance(item.get(key), str)}}
            if "phase" in item:
                phase = item["phase"]
                message["phase"] = phase if phase in ("commentary", "final_answer") else "unrecognised"
            message["content"] = []
            if isinstance(item.get("content"), list):
                for part_index, part in enumerate(item["content"]):
                    content: dict[str, Any] = {"content_index": part_index, "type": "unrecognised"}
                    if isinstance(part, dict) and part.get("type") in ("output_text", "refusal"):
                        kind = part["type"]
                        content["type"] = kind
                        key = "text" if kind == "output_text" else "refusal"
                        if isinstance(part.get(key), str):
                            content[key] = part[key]
                    message["content"].append(content)
            visible.append(message)
    return visible


def _response_metadata(data: dict) -> dict[str, Any]:
    metadata = {key: data[key] for key in ("id", "service_tier") if isinstance(data.get(key), str)}
    status = data.get("status")
    metadata["status"] = status if isinstance(status, str) and status in {
        "completed", "failed", "in_progress", "cancelled", "queued", "incomplete"} else "unrecognised"
    if isinstance(data.get("incomplete_details"), dict):
        reason = data["incomplete_details"].get("reason")
        metadata["incomplete_details"] = {
            "reason": reason if isinstance(reason, str) and reason in {
                "max_output_tokens", "content_filter"} else "unrecognised"}
    if data.get("error"):
        metadata["error"] = safe_error_details(data["error"])
    metadata["visible_output"] = _visible_output(data.get("output"))
    return metadata


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
            raise ProviderError("Native functions require enabled capability and operation schemas",
                                category="configuration")
        headers = bearer_headers(self.api_key_env, ProviderError)
        payload: dict[str, Any] = {"model": self.model, "input": self._input(messages),
                                   "store": False, "include": ["reasoning.encrypted_content"],
                                   "max_output_tokens": max_output_tokens,
                                   **self.sampling}
        if "reasoning_effort" in self.capabilities:
            payload["reasoning"] = {"effort": self.capabilities["reasoning_effort"]}
        schema_modes: dict[str, bool] = {}
        if native_tools:
            tools = []
            for entry in operations or []:
                try:
                    schema = strict_operation_schema(entry, native=True)
                    strict = True
                except ValueError:
                    # An open host schema cannot be closed without changing
                    # its contract. Its host-side validator remains required.
                    schema, strict = native_operation_schema(entry), False
                schema_modes[entry["operation"]] = strict
                tools.append({"type": "function", "name": entry["operation"],
                              "description": entry.get("description") or entry["operation"],
                              "parameters": schema, "strict": strict})
            payload.update(tools=tools, tool_choice="required", parallel_tool_calls=False)
        elif self.capabilities["structured_output"] == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        elif self.capabilities["structured_output"] == "json_schema" and operations:
            try:
                alternatives = [strict_operation_schema(entry, native=False) for entry in operations]
                strict = True
            except ValueError:
                alternatives = [entry["input_schema"] for entry in operations]
                strict = False
            schema = {"type": "object", "properties": {
                "request": {"anyOf": alternatives}},
                "required": ["request"], "additionalProperties": False}
            payload["text"] = {"format": {"type": "json_schema", "name": "eal_reply",
                                         "schema": schema, "strict": strict}}
            schema_modes = {entry["operation"]: strict for entry in operations}
        data = await post_json(self.endpoint, headers, payload,
                               timeout_seconds=self.timeout_seconds,
                               max_response_bytes=self.max_response_bytes,
                               transport=self.transport, error_type=ProviderError)
        if not isinstance(data, dict):
            raise ProviderError("Responses endpoint returned malformed output", category="invalid_response")
        metadata = _response_metadata(data)
        usage = data.get("usage")
        if not isinstance(usage, dict):
            raise ProviderError("Responses endpoint returned malformed usage", category="invalid_usage",
                                diagnostics=metadata)
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
            raise ProviderError("Responses endpoint returned invalid usage", category="invalid_usage",
                                diagnostics=metadata) from exc

        def failure(message: str, category: str = "invalid_response") -> ProviderError:
            return ProviderError(message, response=measured, category=category, diagnostics=metadata)

        if data.get("status") != "completed" or data.get("error") or data.get("incomplete_details"):
            reason = metadata.get("incomplete_details", {}).get("reason")
            category = {"max_output_tokens": "output_truncated", "content_filter": "output_filtered"}.get(
                reason, "output_incomplete")
            raise failure("Model response was incomplete", category)
        if not isinstance(data.get("output"), list):
            raise failure("Responses endpoint returned malformed output")
        output = data["output"]
        if native_tools:
            calls = [item for item in output if isinstance(item, dict) and item.get("type") == "function_call"]
            if len(calls) != 1 or any(not isinstance(item, dict) or item.get("type") not in
                                      ("function_call", "reasoning") for item in output):
                raise failure("Native response must contain one function call and optional reasoning", "invalid_operation")
            call = calls[0]
            if call.get("status") not in (None, "completed"):
                raise failure("Native response contained an incomplete function call", "output_incomplete")
            if (not isinstance(call.get("call_id"), str) or not call["call_id"]
                    or not isinstance(call.get("name"), str)
                    or call["name"] not in {entry["operation"] for entry in operations or []}
                    or not isinstance(call.get("arguments"), str)):
                raise failure("Native response has an invalid function call", "invalid_operation")
            try:
                arguments = strict_json(call["arguments"])
                if not isinstance(arguments, dict) or "operation" in arguments:
                    raise ValueError("Expected object arguments without an operation field")
                entry = next(entry for entry in operations or [] if entry["operation"] == call["name"])
                if schema_modes[call["name"]]:
                    arguments = restore_optional_fields(arguments, native_operation_schema(entry))
                flat_request = {"operation": call["name"], **arguments}
                flat = json.dumps(flat_request, ensure_ascii=False, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise failure("Native function arguments are invalid", "invalid_operation") from exc
            handle = secrets.token_urlsafe(24)
            self._replay_items[handle] = (flat, call["call_id"], output)
            metadata["responses_replay_handle"] = handle
            metadata["native_tool_call"] = {"id": call["call_id"], "type": "function",
                                            "function": {"name": call["name"], "arguments": call["arguments"]}}
            metadata["operation_schema_mode"] = "strict" if schema_modes[call["name"]] else "host_validated"
            return ModelResponse(flat, measured.input_tokens, measured.output_tokens, measured.model, metadata)
        if any(not isinstance(item, dict) or item.get("type") not in ("message", "reasoning") for item in output):
            raise failure("Text response contained a tool or non-message item")
        messages_returned = [item for item in output if item["type"] == "message"]
        if operations is not None and len(messages_returned) != 1:
            raise failure("Operation response must contain exactly one assistant message",
                          "multiple_messages" if len(messages_returned) > 1 else "missing_message")
        pieces = []
        for item in output:
            if item["type"] == "reasoning":
                continue
            if item.get("role") not in (None, "assistant") or (operations is not None and item.get("role") != "assistant"):
                raise failure("Text response contained a non-assistant message")
            if item.get("status") not in (None, "completed") or not isinstance(item.get("content"), list):
                raise failure("Text response contained an incomplete message", "output_incomplete")
            for content in item["content"]:
                if not isinstance(content, dict) or content.get("type") != "output_text" or not isinstance(content.get("text"), str):
                    raise failure("Text response contained non-text content")
                pieces.append(content["text"])
        if not pieces:
            raise failure("Text response contained no text", "missing_message")
        result = "".join(pieces)
        if self.capabilities["structured_output"] == "json_schema" and operations:
            try:
                wrapper = strict_json(result)
                if not isinstance(wrapper, dict) or set(wrapper) != {"request"} or not isinstance(wrapper["request"], dict):
                    raise ValueError("Expected a request envelope")
                name = wrapper["request"].get("operation")
                entry = next((entry for entry in operations if entry["operation"] == name), None)
                if entry is None:
                    raise ValueError("Unknown structured operation")
                request = (restore_optional_fields(wrapper["request"], entry["input_schema"])
                           if schema_modes[name] else wrapper["request"])
                metadata["structured_response_text"] = result
                metadata["operation_schema_mode"] = "strict" if schema_modes[name] else "host_validated"
                result = json.dumps(request, ensure_ascii=False, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise failure("Structured response did not contain one request", "invalid_operation") from exc
        handle = secrets.token_urlsafe(24)
        self._replay_items[handle] = (result, None, output)
        metadata["responses_replay_handle"] = handle
        return ModelResponse(result, measured.input_tokens, measured.output_tokens,
                             measured.model, metadata)
