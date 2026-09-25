"""Configured text-generation adapters; model text never selects an executable.

Adapters do not retry implicitly: every charged attempt belongs in the host's
record. Credentials are environment references and are never included in its
identity, response metadata, or exception messages.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import tomllib
from typing import Any, Protocol

import httpx

from .http_provider import (bearer_headers, native_operation_schema, post_json,
                            validate_api_key_env, validate_endpoint,
                            validate_max_response_bytes, validate_model)
from .runtime import strict_json


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise ValueError("Model response text must be a string")
        for count in (self.input_tokens, self.output_tokens):
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError("Token usage must be a non-negative integer or null")
        if self.model is not None and not isinstance(self.model, str):
            raise ValueError("Response model must be a string or null")
        if not isinstance(self.metadata, dict):
            raise ValueError("Response metadata must be an object")
        try:
            self.text.encode("utf-8")
            json.dumps(self.metadata, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("Response strings must contain valid Unicode scalar values") from exc


class ProviderError(RuntimeError):
    """A failed attempt with measured usage and sanitised boundary diagnostics.

    ``retryable`` describes the error class; adapters never retry themselves.
    Hosts retain each failed attempt and decide whether to schedule later work.
    """

    def __init__(self, message: str, *, response: ModelResponse | None = None,
                 category: str = "provider_error", retryable: bool = False,
                 diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.response = response
        self.category = category
        self.retryable = retryable
        self.diagnostics = diagnostics or {}


class TextProvider(Protocol):
    def identity(self) -> dict[str, Any]: ...
    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse: ...


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _sampling(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) - {"temperature", "top_p", "seed"}:
        raise ValueError("sampling accepts only temperature, top_p and seed")
    for key, item in value.items():
        if key == "seed":
            if type(item) is not int:
                raise ValueError("seed must be an integer")
        elif isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{key} must be finite")
        elif not (0 <= item <= (2 if key == "temperature" else 1)):
            raise ValueError(f"{key} is outside its supported interval")
    return dict(value)


def _pricing(value: Any) -> dict:
    allowed = {"input_usd_per_million", "output_usd_per_million", "cached_input_usd_per_million"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("pricing accepts input/output/cached_input_usd_per_million")
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item < 0:
            raise ValueError(f"{key} must be a non-negative finite number")
    return dict(value)


def _capabilities(value: Any) -> dict:
    allowed = {"native_tools", "structured_output", "reasoning_effort", "tool_reasoning_compatible"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Unknown provider capability; configure native_tools, structured_output, reasoning_effort or tool_reasoning_compatible")
    result = {"native_tools": False, "structured_output": "none", "tool_reasoning_compatible": False, **value}
    for key in ("native_tools", "tool_reasoning_compatible"):
        if type(result[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    if result["structured_output"] not in {"none", "json_object", "json_schema"}:
        raise ValueError("structured_output must be none, json_object or json_schema")
    if "reasoning_effort" in result and result["reasoning_effort"] not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("reasoning_effort is not a supported explicit setting")
    return result


def response_cost(response: ModelResponse, identity: dict) -> float | None:
    """Configured token-rate estimate; absence of a rate or usage stays unknown."""
    rates = identity.get("pricing", {})
    if response.input_tokens is None or response.output_tokens is None:
        return None
    if not {"input_usd_per_million", "output_usd_per_million"} <= rates.keys():
        return None
    cached = response.metadata.get("cached_input_tokens", 0)
    if type(cached) is not int or not 0 <= cached <= response.input_tokens:
        return None
    if cached and "cached_input_usd_per_million" not in rates:
        return None
    cost = ((response.input_tokens - cached) * rates["input_usd_per_million"]
            + cached * rates.get("cached_input_usd_per_million", 0)
            + response.output_tokens * rates["output_usd_per_million"]) / 1_000_000
    return cost if math.isfinite(cost) else None


def _command_response(value: Any) -> ModelResponse:
    allowed = {"text", "input_tokens", "output_tokens", "model", "metadata"}
    if not isinstance(value, dict):
        raise ProviderError("Command provider must return a response object with text and optional usage/model/metadata")
    measured = None
    try:
        measured = ModelResponse("", value.get("input_tokens"), value.get("output_tokens"), value.get("model"), value.get("metadata", {}))
    except (TypeError, ValueError):
        pass
    if "text" not in value or set(value) - allowed:
        raise ProviderError("Command provider must return a response object with text and optional usage/model/metadata", response=measured)
    try:
        return ModelResponse(**value)
    except (TypeError, ValueError) as exc:
        raise ProviderError("Command provider returned invalid response fields", response=measured) from exc


class CommandProvider:
    """One trusted configured command per generation, using JSON stdin/stdout."""

    def __init__(self, *, argv: list[str], model: str, workspace: Path | None = None,
                 sampling: dict | None = None, pricing: dict | None = None,
                 timeout_seconds: float = 60, max_response_bytes: int = 1_048_576,
                 label: str = "command", measurement_kind: str = "model"):
        if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or "\0" in a for a in argv):
            raise ValueError("argv must be a non-empty list of literal strings")
        if not isinstance(model, str) or not model:
            raise ValueError("model must be an explicit non-empty identity")
        validate_max_response_bytes(max_response_bytes)
        if measurement_kind not in {"model", "interface_only"}:
            raise ValueError("measurement_kind must be model or interface_only")
        self.argv, self.model = list(argv), model
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()
        self.sampling, self.pricing = _sampling(sampling or {}), _pricing(pricing or {})
        self.timeout_seconds = _positive(timeout_seconds, "timeout_seconds")
        self.max_response_bytes = max_response_bytes
        self.label, self.measurement_kind = label, measurement_kind

    def identity(self) -> dict:
        return {"provider": self.label, "adapter": "command", "model": self.model,
                "sampling": self.sampling, "pricing": self.pricing,
                "measurement_kind": self.measurement_kind,
                "command_digest": hashlib.sha256(json.dumps(self.argv).encode()).hexdigest()}

    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse:
        request = json.dumps({"model": self.model, "messages": messages,
                              "sampling": self.sampling, "max_output_tokens": max_output_tokens},
                             allow_nan=False, ensure_ascii=False).encode("utf-8")
        process = None
        tasks: list[asyncio.Task] = []
        try:
            process = await asyncio.create_subprocess_exec(
                *self.argv, cwd=self.workspace, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name == "posix")
            output_size = 0

            async def read_bounded(stream):
                nonlocal output_size
                chunks = []
                while chunk := await stream.read(65536):
                    output_size += len(chunk)
                    if output_size > self.max_response_bytes:
                        raise ProviderError("Command provider output exceeded its byte limit")
                    chunks.append(chunk)
                return b"".join(chunks)

            async def send():
                process.stdin.write(request)
                await process.stdin.drain()
                process.stdin.close()

            tasks = [asyncio.create_task(read_bounded(process.stdout)),
                     asyncio.create_task(read_bounded(process.stderr)), asyncio.create_task(send()),
                     asyncio.create_task(process.wait())]
            async with asyncio.timeout(self.timeout_seconds):
                out, _stderr, _, returncode = await asyncio.gather(*tasks)
            if returncode:
                measured = None
                try:
                    failed = _command_response(strict_json(out.decode("utf-8")))
                    measured = ModelResponse("", failed.input_tokens, failed.output_tokens, failed.model, failed.metadata)
                except ProviderError as exc:
                    measured = exc.response
                except (ValueError, UnicodeError):
                    pass
                raise ProviderError(f"Command provider exited with status {returncode}", response=measured)
            try:
                value = strict_json(out.decode("utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise ProviderError("Command provider returned malformed UTF-8 JSON") from exc
            return _command_response(value)
        except TimeoutError as exc:
            raise ProviderError("Command provider timed out") from exc
        except OSError as exc:
            raise ProviderError("Command provider could not be started") from exc
        finally:
            if process is not None:
                try:
                    if os.name == "posix":
                        # A child can retain the pipes after its parent exits.
                        os.killpg(process.pid, signal.SIGKILL)
                    elif process.returncode is None:
                        process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)


class ChatCompletionsProvider:
    """Non-streaming HTTP text endpoint compatible with Chat Completions.

    No native tool API or JSON-generation feature is required from the model.
    The host receives plain message content and validates that content itself.
    """

    def __init__(self, *, model: str, endpoint: str = "https://api.openai.com/v1/chat/completions",
                 api_key_env: str | None = "OPENAI_API_KEY", sampling: dict | None = None,
                 pricing: dict | None = None, timeout_seconds: float = 60,
                 max_response_bytes: int = 1_048_576, max_tokens_field: str = "max_completion_tokens",
                 label: str = "chat_completions", capabilities: dict | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        validate_endpoint(endpoint, invalid="endpoint must be an HTTP(S) URL without credentials, query or fragment",
                          insecure="Non-local HTTP endpoints must use HTTPS")
        validate_api_key_env(api_key_env, invalid="api_key_env must be an environment variable name or null")
        validate_model(model, invalid="model must be an explicit non-empty identity")
        if max_tokens_field not in {"max_tokens", "max_completion_tokens"}:
            raise ValueError("max_tokens_field must be max_tokens or max_completion_tokens")
        validate_max_response_bytes(max_response_bytes)
        self.model, self.endpoint, self.api_key_env = model, endpoint, api_key_env
        self.sampling, self.pricing = _sampling(sampling or {}), _pricing(pricing or {})
        self.timeout_seconds = _positive(timeout_seconds, "timeout_seconds")
        self.max_response_bytes, self.max_tokens_field = max_response_bytes, max_tokens_field
        self.label, self.transport = label, transport
        self.capabilities = _capabilities(capabilities or {})

    def identity(self) -> dict:
        return {"provider": self.label, "adapter": "chat_completions", "model": self.model,
                "endpoint": self.endpoint, "sampling": self.sampling, "pricing": self.pricing,
                "max_tokens_field": self.max_tokens_field, "measurement_kind": "model", "capabilities": self.capabilities}

    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse:
        return await self._complete(messages, max_output_tokens)

    async def complete_request(self, messages: list[dict[str, Any]], max_output_tokens: int, *,
                               operations: list[dict], native_tools: bool = False) -> ModelResponse:
        return await self._complete(messages, max_output_tokens, operations=operations, native_tools=native_tools)

    async def _complete(self, messages: list[dict[str, Any]], max_output_tokens: int, *,
                        operations: list[dict] | None = None, native_tools: bool = False) -> ModelResponse:
        if native_tools and not self.capabilities["native_tools"]:
            raise ProviderError("Native tools were not enabled in provider capabilities")
        if native_tools and self.capabilities.get("reasoning_effort", "none") != "none" and not self.capabilities["tool_reasoning_compatible"]:
            raise ProviderError("Native tools with reasoning effort require an explicitly compatible model/endpoint configuration")
        if native_tools and not operations:
            raise ProviderError("Native tool requests require operation schemas")
        headers = bearer_headers(self.api_key_env, ProviderError)
        payload = {"model": self.model, "messages": messages, "stream": False, "n": 1,
                   self.max_tokens_field: max_output_tokens, **self.sampling}
        if "reasoning_effort" in self.capabilities:
            payload["reasoning_effort"] = self.capabilities["reasoning_effort"]
        structured = self.capabilities["structured_output"]
        if native_tools:
            functions = []
            for entry in operations:
                parameters = native_operation_schema(entry)
                functions.append({"type": "function", "function": {"name": entry["operation"],
                    "description": entry.get("description") or entry["operation"], "parameters": parameters,
                    "strict": False}})
            payload.update(tools=functions, tool_choice="required", parallel_tool_calls=False)
        elif structured == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif structured == "json_schema":
            schema = {"type": "object"}
            if operations:
                schema = {"type": "object", "properties": {"request": {"anyOf": [entry["input_schema"] for entry in operations]}},
                          "required": ["request"], "additionalProperties": False}
                payload["messages"] = [*messages, {"role": "system", "content":
                    "For this response wrap the single flat operation request in a JSON object with exactly one field: request. Example: {\"request\":{\"operation\":\"validate\"}}. The host will unwrap it before execution."}]
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "eal_reply", "schema": schema, "strict": False}}
        data = await post_json(self.endpoint, headers, payload,
                               timeout_seconds=self.timeout_seconds,
                               max_response_bytes=self.max_response_bytes,
                               transport=self.transport, error_type=ProviderError)
        if not isinstance(data, dict):
            raise ProviderError("Model endpoint returned a non-object response")
        usage = data.get("usage") or {}
        if not isinstance(usage, dict):
            raise ProviderError("Model endpoint returned malformed usage")
        metadata = {key: data[key] for key in ("id", "system_fingerprint", "service_tier") if key in data}
        cached = usage.get("prompt_tokens_details", {})
        if isinstance(cached, dict) and "cached_tokens" in cached:
            metadata["cached_input_tokens"] = cached["cached_tokens"]
        completion_details = usage.get("completion_tokens_details", {})
        if isinstance(completion_details, dict) and "reasoning_tokens" in completion_details:
            metadata["reasoning_tokens"] = completion_details["reasoning_tokens"]
        # Preserve the already byte-bounded provider response on every parsing
        # failure. This contains model messages, never request/auth headers.
        metadata["response_choices"] = data.get("choices")
        try:
            measured = ModelResponse("", usage.get("prompt_tokens"), usage.get("completion_tokens"), data.get("model"), metadata)
        except (TypeError, ValueError) as exc:
            raise ProviderError("Model endpoint returned invalid usage or metadata") from exc
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ProviderError("Model endpoint must return exactly one choice", response=measured)
        choice = choices[0]
        message = choice.get("message")
        metadata["finish_reason"] = choice.get("finish_reason")
        if native_tools:
            calls = message.get("tool_calls") if isinstance(message, dict) else None
            if choice.get("finish_reason") != "tool_calls" or not isinstance(calls, list) or len(calls) != 1:
                raise ProviderError("Native model response must contain exactly one completed tool call", response=measured)
            call = calls[0]
            if not isinstance(call, dict) or call.get("type") != "function" or not isinstance(call.get("id"), str) or not call["id"]:
                raise ProviderError("Native model response has an invalid function call", response=measured)
            function = call.get("function")
            if not isinstance(function, dict) or function.get("name") not in {entry["operation"] for entry in operations} or not isinstance(function.get("arguments"), str):
                raise ProviderError("Native model response names an unknown operation or malformed arguments", response=measured)
            try:
                arguments = strict_json(function["arguments"])
                if not isinstance(arguments, dict) or "operation" in arguments:
                    raise ValueError("Native operation arguments must be an object without an operation field")
                flat = json.dumps({"operation": function["name"], **arguments}, ensure_ascii=False, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ProviderError("Native model response arguments are invalid JSON", response=measured) from exc
            metadata["native_tool_call"] = {"id": call["id"], "type": "function", "function": {
                "name": function["name"], "arguments": function["arguments"]}}
            if message.get("content") is not None:
                metadata["native_content"] = message["content"]
            metadata.pop("response_choices", None)
            return ModelResponse(flat, measured.input_tokens, measured.output_tokens, measured.model, metadata)
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError("Model endpoint did not return text content", response=measured)
        result = ModelResponse(message["content"], measured.input_tokens, measured.output_tokens, measured.model, metadata)
        if choice.get("finish_reason") != "stop" or message.get("tool_calls") or message.get("function_call"):
            raise ProviderError("Model response was incomplete or attempted native tools", response=result)
        if structured == "json_schema" and operations:
            try:
                envelope = strict_json(result.text)
                if not isinstance(envelope, dict) or set(envelope) != {"request"} or not isinstance(envelope["request"], dict):
                    raise ValueError("Expected a request envelope")
                metadata["structured_response_text"] = result.text
                metadata.pop("response_choices", None)
                return ModelResponse(json.dumps(envelope["request"], ensure_ascii=False, allow_nan=False),
                                     measured.input_tokens, measured.output_tokens, measured.model, metadata)
            except (ValueError, TypeError) as exc:
                raise ProviderError("Structured model response did not contain one request object", response=result) from exc
        metadata.pop("response_choices", None)
        return result


def provider_from_config(config: dict, *, workspace: Path | None = None) -> TextProvider:
    if not isinstance(config, dict):
        raise ValueError("Provider configuration must be an object")
    values = dict(config)
    kind = values.pop("kind", None)
    try:
        if kind == "command":
            return CommandProvider(workspace=workspace, **values)
        if kind == "chat_completions":
            return ChatCompletionsProvider(**values)
        if kind == "responses":
            from .responses_provider import ResponsesProvider
            return ResponsesProvider(**values)
    except TypeError as exc:
        raise ValueError("Provider configuration has missing or unknown fields") from exc
    raise ValueError("provider.kind must be command, chat_completions or responses")


def load_provider(path: Path) -> TextProvider:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    if "provider" not in config:
        raise ValueError("Provider configuration requires a [provider] table")
    return provider_from_config(config["provider"], workspace=path.resolve().parent)
