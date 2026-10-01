"""Independent mathematical cases, counterexamples and malformed model inputs."""
import math

import pytest

from eal.modes import MODE_KINDS, assess_mode, validate_mode
from eal.evaluator import canonical_digest
from _provenance import synthetic_provenance


def run(mode, value):
    return assess_mode(f"{mode}/1", [{"id": "case", "kind": MODE_KINDS[mode], "value": value}], [])


def details(mode, value):
    result = run(mode, value)
    assert result["status"] == "supported", result
    return result["details"]


def test_modes_require_a_unique_designated_input():
    for mode, kind in MODE_KINDS.items():
        if kind is None:
            continue
        assert validate_mode(f"{mode}/1", [])
        assert not validate_mode(f"{mode}/1", [kind, "observation"])
        assert validate_mode(f"{mode}/1", [kind, kind])
    assert validate_mode("inference", ["observation"])
    assert validate_mode("deductive/1", "logical_case")
    assert validate_mode("structured/1", [0])


def test_structured_keeps_authored_support_distinct_from_computation():
    assert assess_mode("structured/1", [], [])["status"] == "unsupported"
    result = assess_mode("structured/1", [], [{"status": "supported"}])
    assert result["status"] == "supported"
    assert result["details"]["mechanically_proved"] is False
    # Contest propagation belongs to argument composition in the caller.
    assert assess_mode("structured/1", [], [{"status": "contested"}])["status"] == "supported"
    assert assess_mode("structured/1", [], [{"status": "unsupported"}])["status"] == "unsupported"


def test_deduction_modus_ponens_and_countermodel():
    case = {"premises": ["p", {"implies": ["p", "q"]}], "conclusion": "q"}
    computed = run("deductive", case)
    assert computed["input_digest"] == canonical_digest(case)
    result = details("deductive", case)
    assert result["entailed"] and result["consistent_premises"]
    assert result["satisfying_premise_valuations"] == 1
    assert result["counterexample"] is None
    # Affirming the consequent has the independently known p=false,q=true countermodel.
    case = {"premises": ["q", {"implies": ["p", "q"]}], "conclusion": "p"}
    result = run("deductive", case)
    assert result["status"] == "supported"
    assert result["details"]["entailed"] is False
    assert result["details"]["counterexample"] == {"p": False, "q": True}


def test_deduction_reports_vacuous_entailment_without_supporting_it():
    result = run("deductive", {"premises": ["p", {"not": "p"}], "conclusion": "q"})
    assert result["status"] == "unsupported"
    assert result["details"]["entailed"] is True  # Classical vacuous entailment.
    assert result["details"]["consistent_premises"] is False
    tautology = details("deductive", {"premises": [], "conclusion": {"or": ["p", {"not": "p"}]}})
    assert tautology["entailed"]


@pytest.mark.parametrize("case", [
    {"premises": [], "conclusion": True},
    {"premises": [], "conclusion": {"implies": ["p"]}},
    {"premises": [], "conclusion": {"and": []}},
    {"premises": [], "conclusion": {"xor": ["p", "q"]}},
    {"premises": [f"p{i}" for i in range(13)], "conclusion": "p0"},
    {"premises": ["p"]},
])
def test_deduction_rejects_unsupported_formulas_and_limits(case):
    assert run("deductive", case)["status"] == "unsupported"


def test_formula_depth_and_size_limits():
    formula = "p"
    for _ in range(34):
        formula = {"not": formula}
    assert run("deductive", {"premises": [], "conclusion": formula})["status"] == "unsupported"
    formula = {"and": [{"and": ["p"] * 128}] * 5}
    assert run("deductive", {"premises": [], "conclusion": formula})["status"] == "unsupported"


def test_wilson_matches_published_nist_example():
    result = details("inductive", {"successes": 20, "trials": 25, "confidence": 0.95})
    assert result["estimate"] == 0.8
    assert result["lower"] == pytest.approx(0.6086905, abs=5e-8)
    assert result["upper"] == pytest.approx(0.9113942, abs=5e-8)
    assert result["interpretation"] == "approximate_frequentist"
    assert result["assumptions_verified"] is False


def test_wilson_zero_and_all_successes_remain_bounded():
    zero = details("inductive", {"successes": 0, "trials": 10, "confidence": 0.95})
    all_success = details("inductive", {"successes": 10, "trials": 10, "confidence": 0.95})
    assert zero["lower"] == pytest.approx(0)
    assert zero["upper"] == pytest.approx(0.2775327998628892)
    assert all_success["upper"] == 1
    assert all_success["lower"] == pytest.approx(1 - zero["upper"])


@pytest.mark.parametrize("value", [
    {"successes": True, "trials": 2, "confidence": 0.95},
    {"successes": 0, "trials": 0, "confidence": 0.95},
    {"successes": 3, "trials": 2, "confidence": 0.95},
    {"successes": 1, "trials": 2.0, "confidence": 0.95},
    {"successes": 1, "trials": 2, "confidence": 1},
    {"successes": 1, "trials": 2, "confidence": float("nan")},
    {"successes": 1, "trials": 2, "confidence": float("inf")},
])
def test_wilson_rejects_invalid_counts_and_confidence(value):
    assert run("inductive", value)["status"] == "unsupported"


def hypotheses(*candidates):
    return {"observed": "alarm", "candidates": [
        {"name": name, "prior": prior, "likelihood": likelihood}
        for name, prior, likelihood in candidates]}


def test_bayesian_abduction_normalises_joint_likelihoods():
    result = details("abductive", hypotheses(("fault", 0.1, 0.9), ("healthy", 0.9, 0.1)))
    assert result["posterior"] == pytest.approx({"fault": 0.5, "healthy": 0.5})
    assert result["best"] is None
    assert result["ties"] == ["fault", "healthy"]
    assert math.exp(result["log_evidence_probability"]) == pytest.approx(0.18)
    result = details("abductive", hypotheses(("fault", 0.2, 0.8), ("healthy", 0.8, 0.1)))
    assert result["best"] == "fault"
    assert result["best_posterior"] == pytest.approx(2 / 3)


def test_abduction_avoids_product_underflow_and_handles_impossible_observation():
    result = details("abductive", hypotheses(("a", 1e-200, 1e-200), ("b", 1.0, 0.0)))
    assert result["posterior"] == {"a": 1.0, "b": 0.0}
    assert math.isfinite(result["log_evidence_probability"])
    assert run("abductive", hypotheses(("a", 0.5, 0), ("b", 0.5, 0)))["status"] == "unsupported"


@pytest.mark.parametrize("value", [
    hypotheses(("a", 0.5, 1.1), ("b", 0.5, 0.1)),
    hypotheses(("a", 0.4, 0.5), ("b", 0.5, 0.1)),
    hypotheses(("a", 0.5, 0.5), ("a", 0.5, 0.1)),
    hypotheses(("a", True, 0.5), ("b", 0.0, 0.1)),
    hypotheses(("a", 1.0, 0.5)),
])
def test_abduction_rejects_invalid_hypothesis_models(value):
    assert run("abductive", value)["status"] == "unsupported"


def test_randomised_contrast_has_independent_expected_mean_and_se():
    result = details("causal", {"assignment": "randomised", "treatment": [3, 5, 7], "control": [1, 2, 3]})
    assert result["estimate"] == 3
    assert result["standard_error"] == pytest.approx(math.sqrt(5 / 3))
    assert result["sample_size"] == 6
    assert result["assumptions_verified"] is False


@pytest.mark.parametrize("assignment,treatment,control", [
    ("observational", [3, 5], [1, 2]),
    ("randomised", [3], [1, 2]),
    ("randomised", [True, 5], [1, 2]),
    ("randomised", [3, 5], [1, float("inf")]),
])
def test_causal_rejects_unsupported_design_and_bad_samples(assignment, treatment, control):
    assert run("causal", {"assignment": assignment, "treatment": treatment, "control": control})["status"] == "unsupported"


def scm():
    return {"variables": {
        "x": {"intercept": 1, "coefficients": {}, "noise": 2},
        "y": {"intercept": 4, "coefficients": {"x": 2}, "noise": 1},
        "z": {"intercept": 0, "coefficients": {"y": 3}, "noise": -1},
    }, "intervention": {"variable": "x", "value": 5}, "outcome": "z"}


def test_counterfactual_reuses_noise_and_replaces_equation():
    result = details("counterfactual", scm())
    assert result["factual_values"] == {"x": 3, "y": 11, "z": 32}
    assert result["counterfactual_values"] == {"x": 5, "y": 15, "z": 44}
    assert result["difference"] == 12
    assert result["assumptions_verified"] is False
    value = scm()
    value["intervention"] = {"variable": "y", "value": 6}
    result = details("counterfactual", value)
    assert result["counterfactual_values"] == {"x": 3, "y": 6, "z": 17}


def test_counterfactual_checks_dag_even_when_intervention_would_cut_cycle():
    value = scm()
    value["variables"]["x"]["coefficients"]["z"] = 0.5
    assert run("counterfactual", value)["status"] == "unsupported"
    value = scm()
    value["variables"]["x"]["coefficients"]["missing"] = 0.5
    assert run("counterfactual", value)["status"] == "unsupported"
    value = scm()
    del value["variables"]["x"]["noise"]
    assert run("counterfactual", value)["status"] == "unsupported"


def test_counterfactual_limits_unrepresentable_model_results():
    value = scm()
    value["variables"]["x"]["intercept"] = 1e100
    value["variables"]["y"]["coefficients"]["x"] = 1e100
    assert run("counterfactual", value)["status"] == "unsupported"


def test_analogy_measures_only_declared_feature_correspondence():
    value = {"relevant_features": ["voltage", "protocol", "enabled"],
             "source": {"voltage": 3.3, "protocol": "i2c", "enabled": True},
             "target": {"voltage": 5, "protocol": "i2c", "enabled": 1}}
    result = details("analogical", value)
    assert result["complete"] is True
    assert result["match_fraction"] == pytest.approx(1 / 3)
    assert result["mismatches"] == ["voltage", "enabled"]
    assert result["interpretation"] == "feature_correspondence"
    del value["target"]["enabled"]
    result = run("analogical", value)
    assert result["status"] == "unsupported"
    assert result["details"]["missing"] == ["enabled"]


def test_analogy_rejects_nested_features_and_duplicate_relevance():
    for source, target, features in [({"x": []}, {"x": []}, ["x"]), ({"x": 1}, {"x": 1}, ["x", "x"])]:
        assert run("analogical", {"relevant_features": features, "source": source, "target": target})["status"] == "unsupported"


def trace():
    return {"start": 0, "end": 2, "max_gap": 1, "semantics": "sampled",
            "events": [{"time": t, "value": 3} for t in (0, 1, 2)],
            "property": {"operator": "lt", "value": 5}}


def test_trace_support_means_sampled_not_continuous_truth():
    result = details("temporal", trace())
    assert result["holds"] is True
    assert result["coverage"] is True
    assert result["continuous_truth_established"] is False
    value = trace()
    value["semantics"] = "continuous"
    assert run("temporal", value)["status"] == "unsupported"


def test_trace_missing_samples_gaps_and_violations_are_distinct():
    value = trace()
    del value["events"][1]
    result = run("temporal", value)
    assert result["status"] == "unsupported"
    assert result["details"]["holds"] is True
    assert result["details"]["coverage"] is False
    assert result["details"]["largest_gap"] == 2
    value = trace()
    value["events"][1]["value"] = 5
    result = run("temporal", value)
    assert result["status"] == "supported"
    assert result["details"]["holds"] is False
    assert result["details"]["coverage"] is True
    assert result["details"]["violation_times"] == [1]
    value = trace()
    del value["events"][0]
    assert run("temporal", value)["details"]["coverage"] is False


def test_trace_rejects_duplicate_unsorted_or_outside_timestamps():
    for times in ([0, 0, 2], [0, 2, 1], [-1, 1, 2], [0, 1, 3]):
        value = trace()
        value["events"] = [{"time": t, "value": 3} for t in times]
        assert run("temporal", value)["status"] == "unsupported"
    value = trace()
    value["start"] = value["end"] = 1
    value["events"] = [{"time": 1, "value": 3}]
    assert details("temporal", value)["coverage"] is True


def test_entry_contract_and_json_limits():
    assert assess_mode("inductive/1", {}, [])["status"] == "unsupported"
    assert assess_mode("inductive/1", [{"kind": "sample", "value": {}}], [])["status"] == "unsupported"
    entry = {"id": "a", "kind": "sample", "value": {}}
    assert assess_mode("inductive/1", [entry, entry], [])["status"] == "unsupported"
    nested = []
    nested.append(nested)
    assert run("inductive", nested)["status"] == "unsupported"
    assert run("inductive", [0] * 10_001)["status"] == "unsupported"
    assert run("inductive", {"x": 10 ** 200})["status"] == "unsupported"
    assert run("inductive", {0: "non-string-key"})["status"] == "unsupported"


@pytest.mark.parametrize("mode,kind,input_predicate,output_field,value", [
    ("deductive", "logical_case", '"conclusion" == "p"', "entailed",
     {"premises": ["q", {"implies": ["p", "q"]}], "conclusion": "p"}),
    ("temporal", "trace", '"semantics" == "sampled"', "holds",
     {"start": 0, "end": 1, "max_gap": 1, "semantics": "sampled",
      "events": [{"time": 0, "value": 6}, {"time": 1, "value": 3}],
      "property": {"operator": "lt", "value": 5}}),
])
def test_negative_computed_results_can_support_explicit_negative_claims(mode, kind, input_predicate, output_field, value):
    from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
    from eal.parser import parse

    context = {"site": "bench"}
    now = "2026-09-23T12:00:00Z"
    source = f'''language "EAL/3"

    environment lab {{ require "site" == "bench"
 }}
    tool calculation {{ version "1"
 }}
    evidence observed {{ tool calculation
 kind {kind}
 environment lab
 max_age 60

      require {input_predicate}
 }}
    reasoning check_result {{ method "{mode}/1"
 rationale "The computed negative result establishes the stated failure."

      require "{output_field}" == false
 }}
    claim failure {{ statement "The supplied case fails the stated property."
 environment lab
 }}
    argument failure_argument = [evidence observed] via check_result => failure'''
    program = parse(source)
    observation = {"evidence_id": "observed", "source_digest": program.source_digest,
                   "tool": "calculation", "tool_version": "1",
                   "evidence_kind": kind, "environment": "lab",
                   "environment_fingerprint": environment_fingerprint("lab", context),
                   "input_digest": canonical_digest(program.evidence["observed"].input),
                   "collected_at": now, "run_id": "negative-result", "status": "ok",
                   "value": value, "data_digest": canonical_digest(value),
                   **synthetic_provenance(program, "observed", context)}
    result = evaluate(program, {"observed": observation}, now=now, context=context)
    assert result["valid"]
    assert result["claims"]["failure"]["status"] == "supported", result
    calculation = result["arguments"]["failure_argument"]["reasoning_result"]
    assert calculation["details"][output_field] is False
    assert calculation["predicates"][0]["holds"] is True


def test_integer_trace_coordinates_and_comparisons_keep_exact_integer_identity():
    # Nanosecond-like integer coordinates may exceed binary64's exact range.
    start = 2 ** 53
    value = {"start": start, "end": start + 1, "max_gap": 1, "semantics": "sampled",
             "events": [{"time": start, "value": start + 1}, {"time": start + 1, "value": start + 1}],
             "property": {"operator": "gt", "value": start}}
    result = details("temporal", value)
    assert result["holds"] and result["coverage"]
    assert result["largest_gap"] == 1
