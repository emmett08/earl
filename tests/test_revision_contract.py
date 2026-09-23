"""Independent checks that a computed answer still answers the declared question."""
from copy import deepcopy
import asyncio
import json

import pytest

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse


NOW = "2026-09-23T12:00:00Z"
CONTEXT = {"site": "bench"}
KINDS = {"deductive": "logical_case", "causal": "experiment",
         "counterfactual": "causal_model", "temporal": "trace"}


def source(mode, query, *, quantity="proposition", unit="1", result='"entailed" == true'):
    return f'''language "EAL/0.2";
environment lab {{ require "site" == "bench"; }}
tool collector {{ version "1"; mode deterministic; }}
evidence measured {{ tool collector; kind {KINDS[mode]}; environment lab;
  max_age 60; require "schema" == "EAL/typed-input/1";
}}
reasoning method {{ mode {mode}; rationale "Apply the declared finite computation."; }}
claim checked_claim {{ statement "This prose is an interpretation, not a checked formula.";
  environment lab;
  proposition {{ subject "controller"; quantity "{quantity}"; unit "{unit}";
    scope "model-A/episode-1"; valid_from "2026-09-23T11:00:00Z";
    valid_until "2026-09-23T13:00:00Z"; query {json.dumps(query)};
    result {result};
  }}
}}
argument derivation {{ conclusion checked_claim; reasoning method; evidence measured; binding measured; }}
'''


def envelope(mode, payload, *, quantity="proposition", unit="1"):
    return {"schema": "EAL/typed-input/1", "method": f"{mode}/1",
            "subject": "controller", "quantity": quantity, "unit": unit,
            "scope": "model-A/episode-1", "valid_from": "2026-09-23T11:00:00Z",
            "valid_until": "2026-09-23T13:00:00Z", "payload": payload}


def assess(text, value):
    program = parse(text)
    record = {"evidence_id": "measured", "source_digest": program.source_digest,
              "tool": "collector", "tool_version": "1", "mode": "deterministic",
              "evidence_kind": program.evidence["measured"].kind, "environment": "lab",
              "environment_fingerprint": environment_fingerprint("lab", CONTEXT),
              "input_digest": canonical_digest(program.evidence["measured"].input),
              "collected_at": NOW, "run_id": "independent-review", "status": "ok",
              "value": value, "data_digest": canonical_digest(value)}
    result = evaluate(program, {"measured": record}, now=NOW, context=CONTEXT)
    assert result["valid"], result["diagnostics"]
    return result


def test_replacing_the_formal_question_with_an_easier_one_cannot_supply_support():
    query = {"premises": ["A"], "conclusion": "B"}
    text = source("deductive", query)
    intended = assess(text, envelope("deductive", query))
    assert intended["claims"]["checked_claim"]["status"] == "unsupported"
    assert intended["arguments"]["derivation"]["reasoning_result"]["details"]["entailed"] is False

    easier = {"premises": ["A"], "conclusion": "A"}
    substituted = assess(text, envelope("deductive", easier))
    assert substituted["claims"]["checked_claim"]["status"] == "unsupported"
    binding = substituted["arguments"]["derivation"]["reasoning_result"]["binding"]
    assert binding["status"] == "unsupported"
    assert any("query field 'conclusion'" in reason for reason in binding["reasons"])


def test_verified_formula_does_not_promote_prose_or_physical_interpretation():
    query = {"premises": ["A"], "conclusion": "A"}
    result = assess(source("deductive", query), envelope("deductive", query))
    claim = result["claims"]["checked_claim"]
    binding = result["arguments"]["derivation"]["reasoning_result"]["binding"]
    assert claim["status"] == "supported"
    assert claim["prose_verified"] is False
    assert binding["prose_verified"] is False
    assert binding["physical_interpretation_verified"] is False
    assert binding["formal_query"] == query
    assert binding["input_payload_digest"] == canonical_digest(query)


@pytest.mark.parametrize("field,value", [
    ("subject", "other-controller"), ("scope", "model-A/episode-2"),
    ("quantity", "probability"), ("unit", "s"), ("method", "deductive/2"),
    ("valid_from", "2026-09-23T11:00:01Z"),
    ("valid_until", "2026-09-23T12:59:59Z"),
])
def test_same_scalar_result_cannot_hide_mismatched_interpretation_or_partial_interval(field, value):
    query = {"premises": ["A"], "conclusion": "A"}
    observed = envelope("deductive", query)
    observed[field] = value
    result = assess(source("deductive", query), observed)
    assert result["claims"]["checked_claim"]["status"] == "unsupported"


def test_causal_output_conversion_preserves_the_declared_quantity():
    query = {"assignment": "randomised"}
    text = source("causal", query, quantity="pressure", unit="kPa", result='"estimate" > 1')
    measured = envelope("causal", {**query, "treatment": [2000, 2200], "control": [0, 200]},
                        quantity="pressure", unit="Pa")
    result = assess(text, measured)
    assert result["claims"]["checked_claim"]["status"] == "supported"
    binding = result["arguments"]["derivation"]["reasoning_result"]["binding"]
    assert binding["actual"] == 2.0
    assert binding["output_unit"] == "kPa"


@pytest.mark.parametrize("mode,query,observations,result", [
    ("temporal", {"start": 0, "end": 1, "max_gap": 1,
                  "property": {"operator": "lt", "value": 40}, "semantics": "sampled"},
     {"events": [{"time": 0, "value": 2}, {"time": 1, "value": 2}]}, '"holds" == true'),
    ("counterfactual", {"variables": {"x": {"intercept": 0, "coefficients": {}, "noise": 0}},
                        "intervention": {"variable": "x", "value": 2}, "outcome": "x"}, {}, '"counterfactual" == 2'),
])
def test_dimensional_query_constants_cannot_silently_change_unit(mode, query, observations, result):
    text = source(mode, query, quantity="time", unit="ms", result=result)
    valid = envelope(mode, {**deepcopy(query), **observations}, quantity="time", unit="ms")
    assert assess(text, valid)["claims"]["checked_claim"]["status"] == "supported"
    measured = envelope(mode, {**deepcopy(query), **observations}, quantity="time", unit="s")
    assessment = assess(text, measured)
    assert assessment["claims"]["checked_claim"]["status"] == "unsupported"
    binding = assessment["arguments"]["derivation"]["reasoning_result"]["binding"]
    assert any("unit" in reason for reason in binding["reasons"])


@pytest.mark.parametrize("budget_values,reason", [
    ({"max_total_tokens": 100}, "token_budget_exhausted"),
    ({"max_model_cost_usd": 0.01}, "model_cost_budget_exhausted"),
])
def test_terminal_model_answer_cannot_bypass_a_measured_budget_overrun(budget_values, reason):
    from eal.agent import AgentBudget, run_unaided
    from eal.providers import ModelResponse

    class MeasuredInterface:
        def identity(self):
            return {"model": "interface-fixture", "measurement_kind": "interface_only",
                    "pricing": {"input_usd_per_million": 1000, "output_usd_per_million": 1000}}

        async def complete(self, messages, max_output_tokens):
            return ModelResponse('{"claims":{"checked_claim":"supported"}}', 100, 1)

    report = asyncio.run(run_unaided("Assess the fixture", MeasuredInterface(),
                                    budget=AgentBudget(**budget_values)))
    assert report["status"] == "incomplete"
    assert report["stop_reason"] == reason
    assert report["final"] is None
    assert len(report["attempts"]) == 1
    assert report["usage"]["total_tokens"] == 101
    assert report["usage"]["model_cost_usd"] == pytest.approx(0.101)


def test_benchmark_identity_distinguishes_boolean_predicates_from_numbers():
    from eal.benchmark import source_correspondence

    original = '''language "EAL/0.1";
environment lab { require "enabled" == true; }
claim checked_claim { statement "The environment is enabled."; environment lab; }
'''
    assert source_correspondence(original, "// reformatted only\n" + original)
    assert not source_correspondence(original, original.replace("== true", "== 1"))


def test_rejected_generation_usage_remains_in_completed_run_total():
    from eal.agent import run_unaided
    from eal.providers import ModelResponse, ProviderError

    class FailedThenCorrect:
        def __init__(self):
            self.calls = 0

        def identity(self):
            return {"model": "interface-fixture", "measurement_kind": "interface_only",
                    "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 2}}

        async def complete(self, messages, max_output_tokens):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError("Incomplete output", response=ModelResponse("partial", 200, 40))
            return ModelResponse('{"claims":{"checked_claim":"unsupported"}}', 300, 10)

    report = asyncio.run(run_unaided("Assess the fixture", FailedThenCorrect()))
    assert report["status"] == "completed"
    assert [a["status"] for a in report["attempts"]] == ["provider_error", "received"]
    assert report["usage"]["input_tokens"] == 500
    assert report["usage"]["output_tokens"] == 50
    assert report["usage"]["model_cost_usd"] == pytest.approx(0.0006)
