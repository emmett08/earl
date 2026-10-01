"""Hand-assessed outcomes and executable boundaries for the keyword example."""
from copy import deepcopy
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from eal.aspic import aspic_registry, solve_aspic
from eal.aspic_compiler import compile_eal_aspic
from eal.aspic_export import export_aspic_view
from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.runtime import ReasoningService

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples" / "aspic-keywords"
SPEC = importlib.util.spec_from_file_location("aspic_keywords_demo", HERE / "demo.py")
DEMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEMO)


@pytest.fixture(scope="module")
def execution(tmp_path_factory):
    output = tmp_path_factory.mktemp("aspic-keywords")
    summary = DEMO.run(output)
    return {"summary": summary, **{name: json.loads((output / f"{name}-result.json").read_text())
                                  for name in ("compiled", "formal")}}


@pytest.mark.parametrize("filename", ("source.eal", "formal.eal"))
def test_canonical_formatting_preserves_the_example_meaning(filename):
    source = (HERE / filename).read_text()
    formatted = format_source(source, registry=aspic_registry())
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
    assert format_source(formatted, registry=aspic_registry()) == formatted


def test_compiled_directives_and_independent_probe_match_hand_assessment(execution):
    result = execution["compiled"]
    assert result["formal"]["argument_count"] == 15
    assert result["formal"]["defeat_count"] == 6
    assert result["formal"]["query_status"] == "accepted"
    assert result["routes"]["primary_route"]["status"] == "rejected"
    assert result["routes"]["probe_route"]["status"] == "accepted"
    assert result["routes"]["fault_route"]["status"] == "rejected"
    mapping = result["source_map"]
    assert {d["kind"] for d in mapping["formal_directives"]} == {"strict", "rank", "contrary", "prefer"}
    assert mapping["arguments"]["definition_route"]["rule_kind"] == "strict"
    assert mapping["arguments"]["reporting_route"]["rule_kind"] == "strict"
    assert mapping["arguments"]["probe_route"]["origin"]["pattern"] == "observation_route"
    assert result["theory"]["options"]["preference"] == "last_link_partial"
    assert {p["kind"] for p in result["theory"]["priorities"]} == {"premise", "rule"}
    view = export_aspic_view(result)
    assert view["schema"] == "aspic-view/3"
    assert view["validation"] == {"formal_result": "recomputed", "provenance": "supplied"}


def test_explicit_theory_has_all_attack_kinds_and_strict_superargument_propagation(execution):
    result = execution["formal"]["formal"]
    assert result["argument_count"] == 15
    assert result["defeat_count"] == 10
    assert {d["kind"] for d in result["defeats"]} == {"undermine", "rebut", "undercut"}
    by_id = {a["id"]: a for a in result["arguments"]}
    axiom = next(a for a in result["arguments"] if a["conclusion"] == "criterion_defined")
    assert axiom["top"] == "axiom" and axiom["strength"] == 1001
    assert all(d["subargument"] != axiom["id"] for d in result["defeats"])
    primary = next(a for a in result["arguments"] if a.get("rule_id") == "primary_ready")
    probe = next(a for a in result["arguments"] if a.get("rule_id") == "probe_ready")
    reports = [a for a in result["arguments"] if a.get("rule_id") == "report_ready"]
    assert primary["label"] == "out" and probe["label"] == "in"
    assert {a["label"] for a in reports} == {"in", "out"}
    assert any(d["target"] in {a["id"] for a in reports}
               and d["subargument"] == primary["id"]
               for d in result["defeats"])
    assert len(result["extensions"]) == 2
    assert all(probe["id"] in extension for extension in result["extensions"])
    assert result["query_status"] == result["grounded_status"] == "accepted"


def test_every_supported_option_and_query_quantifier_is_executed(execution):
    rows = execution["summary"]["option_variants"]
    readiness = [row for row in rows if row["goal"] == "ready"]
    assert len(readiness) == 3 * 2 * 3
    assert {row["query_status"] for row in readiness} == {"accepted"}
    estimates = [row for row in rows if row["goal"] == "estimate_normal"]
    assert len(estimates) == 3 * 2
    assert all(row["query_status"] == ("accepted" if row["semantics"] != "grounded"
                                      and row["query_mode"] == "credulous" else "undecided")
               for row in estimates)
    assert execution["summary"]["preference_comparison"] == [
        {"preference": "minimum_rank", "query_status": "rejected"},
        {"preference": "last_link_rank", "query_status": "accepted"},
        {"preference": "last_link_partial", "query_status": "rejected"},
        {"preference": "last_link_partial_without_priority", "query_status": "undecided"},
    ]
    assert execution["summary"]["unresolved_outcomes"] == {
        "absent_goal": "unconstructed", "odd_attack_cycle_stable": "no_extension"}


def test_negative_spelling_requires_an_explicit_contrary_and_premise_priority_is_effective():
    theory = DEMO.fixture_theory()
    theory["contraries"] = [c for c in theory["contraries"]
                             if c != {"attacker": "~primary_ok", "target": "primary_ok"}]
    result = solve_aspic({"theory": theory})
    assert next(a for a in result["arguments"] if a["conclusion"] == "primary_ok")["label"] == "in"
    assert "undermine" in {d["kind"] for d in result["defeats"]}  # The tied estimates still undermine each other.
    theory["goal"] = "estimate_normal"
    theory["priorities"].append({"kind": "premise", "higher": "estimate_normal", "lower": "estimate_abnormal"})
    assert solve_aspic({"theory": theory})["query_status"] == "accepted"


def test_missing_probe_and_expired_calibration_have_distinct_effects(tmp_path):
    source = (HERE / "source.eal").read_text()
    service = ReasoningService(ROOT, HERE / "tools.toml", tmp_path / "runs.sqlite3")
    collection = service.collect(source, DEMO.CONTEXT)
    records = collection["records"]
    missing = {name: value for name, value in records.items() if name != "probe_record"}
    absent = compile_eal_aspic(source, missing, goal="reportable", now=DEMO.NOW,
                              context=DEMO.CONTEXT).to_dict()
    assert absent["formal"]["query_status"] == "rejected"
    issues = absent["source_map"]["evidence"]["probe_record"]["availability_issues"]
    assert set(issues) == {"missing_observation"}
    expired = compile_eal_aspic(source, records, goal="reportable", now="2026-10-01T07:02:01Z",
                               context=DEMO.CONTEXT).to_dict()
    assert expired["routes"]["primary_route"]["status"] == "unconstructed"
    assert expired["routes"]["probe_route"]["status"] == "accepted"
    assert expired["formal"]["query_status"] == "accepted"
    with pytest.raises(ValueError, match="context"):
        service.compile_aspic(source, {**DEMO.CONTEXT, "run_id": "another-run"},
                              collection["collection_id"], "reportable", DEMO.NOW)


def test_export_rejects_edited_labels(execution):
    altered = deepcopy(execution["formal"])
    altered["formal"]["arguments"][0]["label"] = "out"
    with pytest.raises(ValueError, match="recomputation"):
        export_aspic_view(altered)


def test_both_variants_execute_through_a_real_mcp_client_server():
    assert asyncio.run(DEMO.run_mcp()) == {
        "compiled_query_status": "accepted", "explicit_claim_status": "supported"}
