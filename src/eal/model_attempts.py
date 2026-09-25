"""Aggregate token and model cost fields from retained provider attempts."""

from __future__ import annotations


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
