"""Aggregate token and model cost fields from retained provider attempts."""

from __future__ import annotations

import hashlib
from typing import Any

from .providers import ModelResponse, ProviderError, TextProvider, response_cost


def summarise_usage(attempts: list[dict], *, include_tool_completeness: bool) -> dict:
    """Preserve each host's usage schema, including partial and unknown totals."""
    known_input = sum(attempt["input_tokens"] or 0 for attempt in attempts)
    known_output = sum(attempt["output_tokens"] or 0 for attempt in attempts)
    tokens_complete = all(attempt["input_tokens"] is not None
                          and attempt["output_tokens"] is not None for attempt in attempts)
    known_cost = sum(attempt["model_cost_usd"] or 0 for attempt in attempts)
    cost_complete = all(attempt["model_cost_usd"] is not None for attempt in attempts)
    usage = {
        "input_tokens": known_input if tokens_complete else None,
        "output_tokens": known_output if tokens_complete else None,
        "total_tokens": known_input + known_output if tokens_complete else None,
        "known_input_tokens": known_input,
        "known_output_tokens": known_output,
        "token_usage_complete": tokens_complete,
        "model_cost_usd": known_cost if cost_complete else None,
        "known_model_cost_usd": known_cost,
        "model_cost_complete": cost_complete,
        "cost_basis": "configured_token_rates",
        "tool_cost_usd": None,
    }
    if include_tool_completeness:
        usage["tool_cost_complete"] = False
    usage["total_cost_usd"] = None
    return usage


def pre_attempt_limit(usage: dict, *, attempted: bool, max_total_tokens: int,
                      max_model_cost_usd: float | None,
                      pricing_available: bool = True) -> str | None:
    """Check known pre-call usage; callers own prompt, turn and time limits."""
    if attempted and not usage["token_usage_complete"]:
        return "token_usage_unavailable"
    if usage["known_input_tokens"] + usage["known_output_tokens"] >= max_total_tokens:
        return "token_budget_exhausted"
    if max_model_cost_usd is not None:
        if not pricing_available or not usage["model_cost_complete"]:
            return "cost_budget_unverifiable"
        if usage["known_model_cost_usd"] >= max_model_cost_usd:
            return "model_cost_budget_exhausted"
    return None


def post_attempt_limit(usage: dict, *, max_total_tokens: int,
                       max_model_cost_usd: float | None,
                       require_token_usage: bool) -> str | None:
    """Check post-response thresholds, preserving each host's unknown-usage rule."""
    if require_token_usage and not usage["token_usage_complete"]:
        return "token_usage_unavailable"
    if usage["total_tokens"] is not None and usage["total_tokens"] > max_total_tokens:
        return "token_budget_exhausted"
    if max_model_cost_usd is not None:
        if not usage["model_cost_complete"]:
            return "cost_budget_unverifiable"
        if usage["known_model_cost_usd"] > max_model_cost_usd:
            return "model_cost_budget_exhausted"
    return None


def new_attempt(*, index: int, prompt: str, max_output_tokens: int,
                prompt_digest_field: str) -> dict[str, Any]:
    """Start a pending attempt before invoking a provider that may fail."""
    data = prompt.encode("utf-8")
    return {"index": index, prompt_digest_field: hashlib.sha256(data).hexdigest(),
            "prompt_bytes": len(data), "max_output_tokens": max_output_tokens,
            "input_tokens": None, "output_tokens": None, "model_cost_usd": None,
            "status": "pending"}


async def invoke_provider(provider: TextProvider, messages: list[dict], max_output_tokens: int,
                          *, operations: list[dict] | None, native_tools: bool,
                          invalid_response_message: str) -> ModelResponse:
    """Select the provider's request API and validate its response type."""
    if operations is not None and callable(getattr(provider, "complete_request", None)):
        response = await provider.complete_request(
            messages.copy(), max_output_tokens, operations=operations, native_tools=native_tools)
    else:
        response = await provider.complete(messages.copy(), max_output_tokens)
    if not isinstance(response, ModelResponse):
        raise ProviderError(invalid_response_message)
    return response


def record_response(attempt: dict, response: ModelResponse, identity: dict, *,
                    response_digest_field: str, metadata: dict) -> bytes:
    """Record successful or error-attached response metrics; caller enforces size."""
    data = response.text.encode("utf-8")
    attempt.update(input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                   model_cost_usd=response_cost(response, identity),
                   response_model=response.model, metadata=metadata,
                   **{response_digest_field: hashlib.sha256(data).hexdigest()},
                   response_bytes=len(data))
    return data
