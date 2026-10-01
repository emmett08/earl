"""The optional ASPIC+ method constructs defeat before EAL checks its claim."""
from copy import deepcopy
import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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


@pytest.mark.parametrize("reciprocal", [False, True])
def test_accepted_strict_contraries_from_fallible_premises_are_outside_profile(reciprocal):
    data = {"premises": [{"atom": atom, "kind": "ordinary", "rank": 5}
                         for atom in ("p", "r")],
            "rules": [{"id": "s_yes", "kind": "strict", "antecedents": ["p"],
                       "consequent": "yes"},
                      {"id": "s_no", "kind": "strict", "antecedents": ["r"],
                       "consequent": "no"}],
            "contraries": [{"attacker": "yes", "target": "no"}],
            "goal": "yes"}
    if reciprocal:
        data["contraries"].append({"attacker": "no", "target": "yes"})
    with pytest.raises(ValueError, match="Accepted conclusions contain a declared contrary pair"):
        solve_aspic({"theory": data})
    assert computed(data)["status"] == "unsupported"

    # Defeating a fallible premise resolves this represented conflict without
    # inventing direct rebuttals against either strict rule.
    data["premises"].append({"atom": "not_p", "kind": "axiom"})
    data["contraries"].append({"attacker": "not_p", "target": "p"})
    result = solve_aspic({"theory": data})
    assert result["grounded_status"] == "rejected"
    assert {arg["label"] for arg in result["arguments"]
            if arg["conclusion"] == "no"} == {"in"}


def test_all_alternative_antecedent_derivations_are_built_independent_of_rule_names_and_order():
    data = {"premises": [{"atom": "seed", "kind": "ordinary", "rank": 2},
                         {"atom": "q", "kind": "ordinary", "rank": 9},
                         {"atom": "~apply_primary", "kind": "axiom"}],
            "rules": [{"id": "b_goal", "kind": "defeasible", "antecedents": ["p"],
                       "consequent": "goal", "name": "apply_goal", "rank": 9},
                      {"id": "z_alt", "kind": "strict", "antecedents": ["q"],
                       "consequent": "p"},
                      {"id": "a_primary", "kind": "defeasible", "antecedents": ["seed"],
                       "consequent": "p", "name": "apply_primary", "rank": 2}],
            "contraries": [{"attacker": "~apply_primary", "target": "apply_primary"}], "goal": "goal"}
    first = solve_aspic({"theory": data})
    assert first["grounded_status"] == "accepted"
    assert first["argument_count"] == 7
    goals = [a for a in first["arguments"] if a["conclusion"] == "goal"]
    assert sorted(a["label"] for a in goals) == ["in", "out"]
    assert all(a["rule_id"] == "b_goal" and a["rule_name"] == "apply_goal"
               and a["rank"] == 9 for a in goals)
    assert any(a.get("rule_id") == "z_alt" and a["top"] == "strict"
               and "rank" not in a for a in first["arguments"])
    # Historically the goal rule was consumed before z_alt constructed the
    # second p argument. Reorder and rename the rules across that boundary.
    renamed = deepcopy(data)
    renamed["rules"][0]["id"] = "z_goal"
    renamed["rules"][1]["id"] = "a_alt"
    renamed["rules"].reverse()
    second = solve_aspic({"theory": renamed})
    assert second["grounded_status"] == first["grounded_status"]
    assert second["argument_count"] == first["argument_count"]
    assert sorted((a["conclusion"], a["top"], a["strength"], a["label"])
                  for a in second["arguments"]) == sorted(
                      (a["conclusion"], a["top"], a["strength"], a["label"])
                      for a in first["arguments"])


def test_independent_antecedent_routes_form_every_cartesian_combination():
    data = {
        "premises": [{"atom": atom, "kind": "axiom"}
                     for atom in ("p1", "p2", "q1", "q2")],
        "rules": [
            {"id": "early_goal", "kind": "defeasible", "antecedents": ["p", "q"],
             "consequent": "goal", "name": "apply_goal", "rank": 5},
            *({"id": f"r_{atom}", "kind": "strict", "antecedents": [atom],
               "consequent": atom[0]} for atom in ("p1", "p2", "q1", "q2")),
        ],
        "contraries": [], "goal": "goal",
    }
    result = solve_aspic({"theory": data})
    by_id = {a["id"]: a for a in result["arguments"]}
    goals = [a for a in result["arguments"] if a["conclusion"] == "goal"]
    assert result["argument_count"] == 12 and result["grounded_status"] == "accepted"
    assert len(goals) == 4
    assert {frozenset(by_id[sub]["rule_id"] for sub in a["subarguments"]
                      if by_id[sub].get("rule_id") in {"r_p1", "r_p2", "r_q1", "r_q2"})
            for a in goals} == {frozenset({f"r_p{p}", f"r_q{q}"})
                             for p in (1, 2) for q in (1, 2)}


@pytest.mark.parametrize("attack", ["undermine", "rebut"])
def test_one_way_contrary_ignores_preference_but_reciprocal_contradiction_uses_it(attack):
    if attack == "undermine":
        premises = [{"atom": "p", "kind": "ordinary", "rank": 9},
                    {"atom": "q", "kind": "ordinary", "rank": 1}]
        rules = []
    else:
        premises = [{"atom": "base_p", "kind": "axiom"},
                    {"atom": "base_q", "kind": "axiom"}]
        rules = [{"id": "p_rule", "kind": "defeasible", "antecedents": ["base_p"],
                  "consequent": "p", "name": "apply_p", "rank": 9},
                 {"id": "q_rule", "kind": "defeasible", "antecedents": ["base_q"],
                  "consequent": "q", "name": "apply_q", "rank": 1}]
    data = {"premises": premises, "rules": rules,
            "contraries": [{"attacker": "q", "target": "p"}], "goal": "p"}
    one_way = solve_aspic({"theory": data})
    arguments = {a["id"]: a for a in one_way["arguments"]}
    assert one_way["grounded_status"] == "rejected"
    assert any(w["kind"] == attack and arguments[w["attacker"]]["conclusion"] == "q"
               and arguments[w["subargument"]]["conclusion"] == "p"
               for w in one_way["defeats"])
    data["contraries"].append({"attacker": "p", "target": "q"})
    reciprocal = solve_aspic({"theory": data})
    arguments = {a["id"]: a for a in reciprocal["arguments"]}
    assert reciprocal["grounded_status"] == "accepted"
    assert not any(arguments[w["attacker"]]["conclusion"] == "q"
                   and arguments[w["subargument"]]["conclusion"] == "p"
                   for w in reciprocal["defeats"])


@pytest.mark.parametrize("change", ["duplicate", "strict_conflict", "invalid_rank"])
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
    return f'''language "EAL/3"

environment lab {{
  require "site" == "bench"
}}

tool collector {{
  version "1"
}}

evidence formal {{
  tool collector
  kind aspic_theory
  environment lab
  max_age 60
  require "schema" == "EAL/typed-input/1"
}}

evidence report_record {{
  tool collector
  kind test
  environment lab
  max_age 60
  require "checked" == true
}}

evidence latency_record {{
  tool collector
  kind test
  environment lab
  max_age 60
  require "within_limit" == true
}}

evidence gap_record {{
  tool collector
  kind test
  environment lab
  max_age 60
  require "gap_found" == true
}}

reasoning recorded {{
  method "structured/1"
  rationale "Each claim is limited to the observed run."
}}

reasoning argumentation {{
  method "{METHOD}"
  rationale "The declared theory resolves a conflict for this run."
}}

claim report_checked {{
  statement "The selected run identity was checked."
  environment lab
}}

claim latency_ok {{
  statement "The selected run has p95 within the limit."
  environment lab
}}

claim trace_gap {{
  statement "A trace coverage gap was observed in the selected run."
  environment lab
}}

argument report_arg = [evidence report_record] via recorded => report_checked

argument latency_arg = [evidence latency_record] via recorded => latency_ok

argument gap_arg = [evidence gap_record] via recorded => trace_gap

claim run_passes {{
  statement "The selected run is accepted by the specified formal theory."
  environment lab
  proposition {{
    subject "orders-api"
    quantity "proposition"
    unit "1"
    scope "run-001"
    valid_from "2026-09-23T10:00:00Z"
    valid_until "2026-09-23T11:00:00Z"
    query {query}
    result "grounded_accepted" == true
  }}
}}

argument formal_arg = [evidence formal, premises report_checked, latency_ok, trace_gap] via argumentation => run_passes binding formal
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
