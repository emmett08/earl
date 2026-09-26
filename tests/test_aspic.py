"""The optional ASPIC+ method constructs defeat before EAL checks its claim."""
from copy import deepcopy
import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.adequacy import AdequacyContract, AdequacyEvaluator
from eal.aspic import METHOD, aspic_registry, solve_aspic
from eal.evaluator import evaluate
from eal.modes import assess_mode
from eal.parser import parse
from eal.semantics import validate
from test_evaluator import CONTEXT, NOW, record


def theory():
    return {
        "premises": [
            {"atom": "report_checked", "kind": "axiom"},
            {"atom": "latency_ok", "kind": "ordinary", "rank": 6},
            {"atom": "trace_gap", "kind": "ordinary", "rank": 1},
        ],
        "rules": [
            {"id": "r_pass", "kind": "defeasible",
             "antecedents": ["report_checked", "latency_ok"],
             "consequent": "run_passes", "name": "applicable_pass", "rank": 7},
            {"id": "r_gap", "kind": "strict", "antecedents": ["trace_gap"],
             "consequent": "~applicable_pass"},
        ],
        "contraries": [{"attacker": "~applicable_pass", "target": "applicable_pass"}],
        "goal": "run_passes",
    }


def computed(value):
    return assess_mode(METHOD, [{"id": "formal", "kind": "aspic_theory",
                                 "value": {"theory": value}}], [], registry=aspic_registry())


def test_constructs_rules_and_undercuts_even_from_a_weaker_argument():
    result = computed(theory())
    assert result["status"] == "supported", result
    details = result["details"]
    assert details["argument_count"] == 5
    assert details["grounded_status"] == "rejected"
    assert not details["grounded_accepted"] and details["grounded_rejected"]
    assert any(w["kind"] == "undercut" for w in details["defeats"])


def test_independent_derivation_survives_one_undercut():
    data = theory()
    data["premises"].append({"atom": "cold_run_ok", "kind": "ordinary", "rank": 8})
    data["rules"].append({"id": "r_cold", "kind": "defeasible", "antecedents": ["cold_run_ok"],
                          "consequent": "run_passes", "name": "applicable_cold", "rank": 8})
    answer = solve_aspic({"theory": data})
    assert answer["grounded_status"] == "accepted"
    goals = [a for a in answer["arguments"] if a["conclusion"] == "run_passes"]
    assert {a["label"] for a in goals} == {"in", "out"}


def test_rebuttal_preference_compares_the_attacked_subargument():
    data = {"premises": [{"atom": "p", "kind": "ordinary", "rank": 3},
                         {"atom": "q", "kind": "ordinary", "rank": 8}],
            "rules": [{"id": "r1", "kind": "defeasible", "antecedents": ["p"],
                       "consequent": "yes", "name": "can_yes", "rank": 4},
                      {"id": "r2", "kind": "defeasible", "antecedents": ["q"],
                       "consequent": "~yes", "name": "can_no", "rank": 8},
                      {"id": "r3", "kind": "strict", "antecedents": ["yes"],
                       "consequent": "downstream"}],
            "contraries": [{"attacker": "~yes", "target": "yes"},
                           {"attacker": "yes", "target": "~yes"}],
            "goal": "downstream"}
    answer = solve_aspic({"theory": data})
    assert answer["grounded_status"] == "rejected"
    assert any(x["kind"] == "rebut" and x["target"] != x["subargument"]
               for x in answer["defeats"])
    data["premises"][0]["rank"] = 9
    data["rules"][0]["rank"] = 9
    assert solve_aspic({"theory": data})["grounded_status"] == "accepted"


def test_equal_ordinary_premises_remain_undecided_and_no_goal_is_unconstructed():
    data = {"premises": [{"atom": "p", "kind": "ordinary", "rank": 5},
                         {"atom": "~p", "kind": "ordinary", "rank": 5}],
            "rules": [], "contraries": [
                {"attacker": "p", "target": "~p"}, {"attacker": "~p", "target": "p"}],
            "goal": "p"}
    assert solve_aspic({"theory": data})["grounded_status"] == "undecided"
    data["goal"] = "unmentioned"
    assert solve_aspic({"theory": data})["grounded_status"] == "unconstructed"


@pytest.mark.parametrize("change", ["cycle", "duplicate", "strict_conflict", "invalid_rank"])
def test_invalid_or_unbounded_theory_cannot_create_support(change):
    data = theory()
    if change == "cycle":
        data["rules"].append({"id": "r_cycle", "kind": "strict",
                              "antecedents": ["run_passes"], "consequent": "latency_ok"})
    elif change == "duplicate":
        data["premises"].append(deepcopy(data["premises"][0]))
    elif change == "strict_conflict":
        data["premises"].append({"atom": "~report_checked", "kind": "axiom"})
        data["contraries"].append({"attacker": "report_checked", "target": "~report_checked"})
    else:
        data["rules"][0]["rank"] = True
    assert computed(data)["status"] == "unsupported"


def source(data):
    query = json.dumps({"theory": data}, separators=(",", ":"))
    return f'''language "EAL/2";
environment lab {{ require "site" == "bench"; }}
tool collector {{ version "1"; }}
evidence formal {{ tool collector; kind aspic_theory; environment lab; max_age 60;
 require "schema" == "EAL/typed-input/1"; }}
evidence report_record {{ tool collector; kind test; environment lab; max_age 60; require "checked" == true; }}
evidence latency_record {{ tool collector; kind test; environment lab; max_age 60; require "within_limit" == true; }}
evidence gap_record {{ tool collector; kind test; environment lab; max_age 60; require "gap_found" == true; }}
reasoning recorded {{ method "structured/1"; rationale "Each claim is limited to the observed run."; }}
reasoning argumentation {{ method "{METHOD}"; rationale "The declared theory resolves a conflict for this run."; }}
claim report_checked {{ statement "The selected run identity was checked."; environment lab; }}
claim latency_ok {{ statement "The selected run has p95 within the limit."; environment lab; }}
claim trace_gap {{ statement "A trace coverage gap was observed in the selected run."; environment lab; }}
argument report_arg {{ conclusion report_checked; reasoning recorded; evidence report_record; }}
argument latency_arg {{ conclusion latency_ok; reasoning recorded; evidence latency_record; }}
argument gap_arg {{ conclusion trace_gap; reasoning recorded; evidence gap_record; }}
claim run_passes {{ statement "The selected run is accepted by the specified formal theory.";
 environment lab; proposition {{
 subject "orders-api"; quantity "proposition"; unit "1"; scope "run-001";
 valid_from "2026-09-23T10:00:00Z"; valid_until "2026-09-23T11:00:00Z";
 query {query}; result "grounded_accepted" == true;
 }} }}
argument formal_arg {{ conclusion run_passes; reasoning argumentation; evidence formal;
 premises report_checked, latency_ok, trace_gap; binding formal; }}
'''


def run(data=None, *, value=None, collected_at=NOW):
    data = data or theory()
    program = parse(source(data))
    assert not validate(program, registry=aspic_registry())
    envelope = {"schema": "EAL/typed-input/1", "method": METHOD, "subject": "orders-api",
                "quantity": "proposition", "unit": "1", "scope": "run-001",
                "valid_from": "2026-09-23T10:00:00Z",
                "valid_until": "2026-09-23T11:00:00Z",
                "payload": {"theory": data}}
    records = {"formal": record(program, "formal", envelope if value is None else value, collected_at),
               "report_record": record(program, "report_record", {"checked": True}),
               "latency_record": record(program, "latency_record", {"within_limit": True}),
               "gap_record": record(program, "gap_record", {"gap_found": True})}
    assessment = evaluate(program, records, now=NOW, context=CONTEXT, registry=aspic_registry())
    return program, records, assessment


def test_typed_eal_observation_binds_whole_theory_scope_time_and_result():
    data = theory()
    del data["premises"][-1]
    del data["rules"][-1]
    program, records, assessment = run(data)
    # EAL explicitly requires a supporting named premise; the missing gap
    # formal premise is harmless because the claim remains separately grounded.
    assert assessment["claims"]["run_passes"]["status"] == "supported"
    binding = assessment["arguments"]["formal_arg"]["reasoning_result"]["binding"]
    assert binding["status"] == "supported" and binding["formal_query"] == {"theory": data}
    assert assessment["method_registry_fingerprint"] == aspic_registry().fingerprint
    assert validate(program)  # The default registry has no implicit solver.
    wrong = deepcopy(records["formal"]["value"])
    wrong["payload"]["theory"]["goal"] = "other_run"
    assert run(data, value=wrong)[2]["claims"]["run_passes"]["status"] == "unsupported"
    wrong = deepcopy(records["formal"]["value"])
    wrong["scope"] = "run-002"
    assert run(data, value=wrong)[2]["claims"]["run_passes"]["status"] == "unsupported"
    assert run(data, collected_at="2026-09-23T11:58:59Z")[2]["claims"]["run_passes"]["status"] == "unsupported"


def test_adequacy_requires_a_supported_named_claim_for_every_formal_premise():
    data = theory()
    del data["premises"][-1]
    del data["rules"][-1]
    program, records, assessment = run(data)
    assessment.update(collection_id="test-collection", assessment_id="test-assessment")
    args = {"source": source(data), "assessment": assessment, "context": CONTEXT,
            "collection": {"source_digest": program.source_digest, "context": CONTEXT,
                           "collection_id": "test-collection", "records": records}}
    config = {"source_digest": program.source_digest, "claim": "run_passes",
              "statement": program.claims["run_passes"].statement,
              "environment": "lab", "methods": ["structured/1", METHOD],
              "correspondence": "reviewed_source", "obligations": [{
                  "id": "formal_result", "role": "inference", "target": "argument",
                  "reference": "formal_arg", "path": "reasoning_result.details.grounded_accepted",
                  "operator": "==", "expected": True,
                  "rationale": "The formal grounded result must be accepted."}],
              "premise_bindings": [
                  {"argument": "formal_arg", "formula": "report_checked", "claim": "report_checked"},
                  {"argument": "formal_arg", "formula": "latency_ok", "claim": "latency_ok"}]}

    def check():
        return AdequacyEvaluator(method_registry=aspic_registry()).assess(
            AdequacyContract.from_dict(config), **args)

    assert check()["status"] == "adequate", check()
    config["premise_bindings"].pop()
    assert check()["status"] == "unresolved"
    config["premise_bindings"].append({"argument": "formal_arg", "formula": "latency_ok", "claim": "absent_claim"})
    assert check()["status"] == "unresolved"


def test_installed_method_runs_over_real_mcp_collection_and_reasoning(tmp_path):
    data = theory()
    del data["premises"][-1]
    del data["rules"][-1]
    values = {
        "formal": {"schema": "EAL/typed-input/1", "method": METHOD,
                   "subject": "orders-api", "quantity": "proposition", "unit": "1",
                   "scope": "run-001", "valid_from": "2026-09-23T10:00:00Z",
                   "valid_until": "2026-09-23T11:00:00Z", "payload": {"theory": data}},
        "report_record": {"checked": True},
        "latency_record": {"within_limit": True},
        "gap_record": {"gap_found": True},
    }
    (tmp_path / "values.json").write_text(json.dumps(values))
    script = tmp_path / "collector.py"
    script.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "req=json.load(sys.stdin)\n"
        "values=json.loads((Path(__file__).parent/'values.json').read_text())\n"
        "print(json.dumps({'value':values[req['evidence_id']],"
        "'observed_at':'2026-09-23T12:00:00Z','context':req['context'],"
        "'request':{k:req[k] for k in ('tool','tool_version','input','context')}}))\n"
    )
    (tmp_path / "tools.toml").write_text(
        '[tools.collector]\nkind="command"\nversion="1"\nargv='
        + json.dumps([sys.executable, str(script)]) + "\n"
    )
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path),
              "--registry", str(tmp_path / "tools.toml"),
              "--methods", "eal.aspic:aspic_registry"],
        env=dict(os.environ),
    )

    async def exercise():
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                described = await session.call_tool("eal_describe", {})
                methods = described.structuredContent["typed_bindings"]["methods"]
                assert METHOD in methods
                valid = await session.call_tool("eal_validate", {"source": source(data)})
                assert valid.structuredContent["valid"]
                collected = await session.call_tool(
                    "eal_collect", {"source": source(data), "context": CONTEXT})
                assert not collected.isError, collected
                reasoned = await session.call_tool("eal_reason", {
                    "source": source(data), "context": CONTEXT,
                    "collection_id": collected.structuredContent["collection_id"], "now": NOW})
                assert not reasoned.isError, reasoned
                report = reasoned.structuredContent
                assert report["claims"]["run_passes"]["status"] == "supported"
                assert report["arguments"]["formal_arg"]["reasoning_result"]["details"]["grounded_accepted"]
                explained = await session.call_tool("eal_explain", {
                    "assessment_id": report["assessment_id"], "claim": "run_passes"})
                assert explained.structuredContent["result"]["status"] == "supported"

    asyncio.run(exercise())
