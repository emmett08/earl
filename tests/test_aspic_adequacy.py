"""Formal adequacy binds the assessed ASPIC+ input to the collected theory."""
from copy import deepcopy

from eal.adequacy import AdequacyContract, AdequacyEvaluator
from eal.aspic import METHOD, aspic_registry
from test_aspic import run, source, theory
from test_evaluator import CONTEXT, record


def _case():
    data = theory()
    del data["premises"][-1]
    del data["rules"][-1]
    program, records, assessment = run(data)
    assessment.update(collection_id="test-collection", assessment_id="test-assessment")
    inputs = {"source": source(data), "assessment": assessment, "context": CONTEXT,
              "collection": {"source_digest": program.source_digest, "context": CONTEXT,
                             "collection_id": "test-collection", "records": records}}
    config = {"source_digest": program.source_digest, "claim": "run_passes",
              "statement": program.claims["run_passes"].statement,
              "environment": "lab", "methods": ["structured/1", METHOD],
              "correspondence": "reviewed_source", "obligations": [{
                  "id": "formal_result", "role": "inference", "target": "argument",
                  "reference": "formal_arg", "path": "reasoning_result.details.grounded_accepted",
                  "operator": "==", "expected": True,
                  "rationale": "The selected scoped theory has an accepted goal."}],
              "premise_bindings": [
                  {"argument": "formal_arg", "formula": "report_checked", "claim": "report_checked"},
                  {"argument": "formal_arg", "formula": "latency_ok", "claim": "latency_ok"}]}
    return program, data, config, inputs


def _assess(config, inputs):
    return AdequacyEvaluator(method_registry=aspic_registry()).assess(
        AdequacyContract.from_dict(config), **inputs)


def test_substituted_aspic_theory_cannot_reuse_a_formal_result():
    program, data, config, inputs = _case()
    assert _assess(config, inputs)["status"] == "adequate"
    changed = deepcopy(inputs["collection"]["records"]["formal"]["value"])
    changed["payload"]["theory"]["goal"] = "unrelated"
    inputs["collection"]["records"]["formal"] = record(program, "formal", changed)
    result = _assess(config, inputs)
    assert result["status"] == "unresolved"
    assert any("collected formal input" in reason for reason in result["reasons"])


def test_substituted_valid_interval_cannot_reuse_a_typed_formal_result():
    program, _, config, inputs = _case()
    assert _assess(config, inputs)["status"] == "adequate"
    changed = deepcopy(inputs["collection"]["records"]["formal"]["value"])
    changed["valid_from"] = "2026-09-23T09:00:00Z"
    inputs["collection"]["records"]["formal"] = record(program, "formal", changed)
    result = _assess(config, inputs)
    assert result["status"] == "unresolved"
    assert any("collected typed observation" in reason for reason in result["reasons"])


def test_modified_aspic_result_binding_cannot_reuse_a_reviewed_contract():
    _, _, config, inputs = _case()
    assert _assess(config, inputs)["status"] == "adequate"
    inputs["assessment"]["arguments"]["formal_arg"]["reasoning_result"]["binding"]["actual"] = False
    result = _assess(config, inputs)
    assert result["status"] == "unresolved"
    assert any("result binding differs" in reason for reason in result["reasons"])
