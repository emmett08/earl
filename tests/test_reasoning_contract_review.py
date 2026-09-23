"""Known numerical counterexamples and common method-contract boundaries."""
from copy import deepcopy
from dataclasses import replace

import pytest

from eal.methods import MethodRegistry, default_registry
from eal.modes import MODE_KINDS, assess_mode


def compute(mode, value, registry=None):
    return assess_mode(mode + "/1", [{"id": "case", "kind": MODE_KINDS[mode], "value": value}], [], registry)


def test_causal_contrast_preserves_a_unit_effect_above_binary64_integer_precision():
    origin = 2 ** 53
    value = {"assignment": "randomised", "treatment": [origin + 1] * 2, "control": [origin] * 2}
    result = compute("causal", value)
    assert result["status"] == "supported"
    assert result["details"]["estimate"] == 1
    assert result["details"]["treatment_mean"] == origin + 1
    assert result["details"]["control_mean"] == origin
    assert result["details"]["standard_error"] == 0


def test_causal_contrast_rounds_after_subtracting_fractional_means():
    origin = 2 ** 53
    value = {"assignment": "randomised", "treatment": [origin, origin, origin + 1],
             "control": [origin] * 3}
    result = compute("causal", value)
    assert result["status"] == "supported"
    assert result["details"]["estimate"] == pytest.approx(1 / 3)
    assert result["details"]["standard_error"] == pytest.approx(1 / 3)


def test_causal_standard_error_avoids_squaring_underflow():
    value = {"assignment": "randomised", "treatment": [1e-200, -1e-200], "control": [0, 0]}
    result = compute("causal", value)
    assert result["status"] == "supported"
    assert result["details"]["estimate"] == 0
    assert result["details"]["standard_error"] == pytest.approx(1e-200, rel=1e-14, abs=0)


def test_causal_nonzero_mean_cannot_silently_round_to_zero():
    value = {"assignment": "randomised", "treatment": [5e-324, 0], "control": [0, 0]}
    result = compute("causal", value)
    assert result["status"] == "unsupported"
    assert "underflows the representable number range" in result["reasons"][0]


def test_integer_affine_counterfactual_keeps_exact_values_and_effect():
    origin = 2 ** 53
    value = {"variables": {
        "x": {"intercept": origin, "noise": 1, "coefficients": {}},
        "y": {"intercept": 0, "noise": 0, "coefficients": {"x": 3}},
    }, "intervention": {"variable": "x", "value": origin + 2}, "outcome": "y"}
    result = compute("counterfactual", value)
    assert result["status"] == "supported"
    assert result["details"]["factual"] == 3 * (origin + 1)
    assert result["details"]["counterfactual"] == 3 * (origin + 2)
    assert result["details"]["difference"] == 3


@pytest.mark.parametrize("mode,value", [
    ("causal", {"assignment": "randomised", "treatment": [1e100] * 2, "control": [-1e100] * 2}),
    ("counterfactual", {"variables": {"x": {"intercept": -1e100, "noise": 0, "coefficients": {}}},
                        "intervention": {"variable": "x", "value": 1e100}, "outcome": "x"}),
])
def test_bounded_inputs_cannot_return_outputs_outside_the_declared_range(mode, value):
    result = compute(mode, value)
    assert result["status"] == "unsupported"
    assert "Method output contract violation" in result["reasons"][0]
    assert result["details"] == {}


def test_builtin_input_schema_is_enforced_in_addition_to_algorithm_domain_checks():
    contract = default_registry().get("causal/1")
    schema = deepcopy(contract.input_schema)
    schema["properties"]["treatment"]["minItems"] = 3
    registry = MethodRegistry([replace(contract, input_schema=schema)])
    result = compute("causal", {"assignment": "randomised", "treatment": [1, 2], "control": [1, 2]}, registry)
    assert result["status"] == "unsupported"
    assert "Method input contract violation" in result["reasons"][0]


def test_builtin_input_byte_limit_includes_unselected_feature_data():
    # Each field independently meets the JSON limits. Their combined payload
    # exceeds the declared one-MiB method limit even though only one feature is
    # relevant to the actual comparison.
    source = {"signal": 1, **{f"field{i}": "x" * 4096 for i in range(260)}}
    value = {"relevant_features": ["signal"], "source": source, "target": {"signal": 1}}
    result = compute("analogical", value)
    assert result["status"] == "unsupported"
    assert "Method input exceeds byte limit" in result["reasons"][0]


def test_builtin_output_byte_limit_is_enforced_after_the_computation():
    contract = default_registry().get("analogical/1")
    registry = MethodRegistry([replace(contract, max_output_bytes=1024)])
    features = ["feature" + str(i).zfill(56) for i in range(32)]
    value = {"relevant_features": features, "source": dict.fromkeys(features, 0),
             "target": dict.fromkeys(features, 1)}
    result = compute("analogical", value, registry)
    assert result["status"] == "unsupported"
    assert "Method output exceeds byte limit" in result["reasons"][0]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "invalid key"}, object(),
                                 "\ud800", {"\ud800": 1}])
def test_authored_support_still_requires_a_json_evidence_payload(value):
    result = assess_mode("structured/1", [{"id": "case", "kind": "observation", "value": value}], [])
    assert result["status"] == "unsupported"


def test_authored_support_rejects_cyclic_payloads():
    value = []
    value.append(value)
    result = assess_mode("structured/1", [{"id": "case", "kind": "observation", "value": value}], [])
    assert result["status"] == "unsupported"
