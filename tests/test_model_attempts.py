"""Both model hosts retain their usage schemas and unknown-measurement meaning."""

from eal.model_attempts import summarise_usage


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
