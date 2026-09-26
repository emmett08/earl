"""Reviewed EAL/2 formal choices are parsed, checked and compiled explicitly."""

from dataclasses import replace

import pytest

from eal.aspic_compiler import CompilationError, compile_eal_aspic
from eal.aspic_visualisation import build_aspic_view
from eal.formatter import format_source, semantic_ir
from eal.model import AspicDirective, SourceSpan
from eal.parser import parse
from eal.semantics import validate
from test_aspic_compiler import BASE, compare
from test_evaluator import CONTEXT, NOW, record


def codes(source):
    return {diagnostic.code for diagnostic in validate(parse(source))}


def test_directed_contrary_and_rank_are_reviewed_and_change_formal_defeat():
    source = BASE + '''
claim run_fails { statement "This synthetic run fails."; environment lab; }
argument failure_route { conclusion run_fails; reasoning authored; evidence gap_data; }
aspic {
  rank argument probe_route 800 reviewed "synthetic-review/high-confidence-probe";
  rank evidence probe_data 700 reviewed "synthetic-review/probe-record";
  rank argument failure_route 400 reviewed "synthetic-review/diagnostic-limit";
  contrary claim run_fails to run_passes reviewed "synthetic-review/incompatible-outcomes";
  contrary claim run_passes to run_fails reviewed "synthetic-review/incompatible-outcomes";
}
'''
    assert not codes(source)
    formatted = format_source(source)
    assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
    assert formatted == format_source(formatted)
    compilation, result = compare(source)
    mapping = result["source_map"]
    by_id = {arg["id"]: arg for arg in result["formal"]["arguments"]}
    probe = next(arg for arg in by_id.values()
                 if arg.get("rule_id") == mapping["arguments"]["probe_route"]["rule_id"])
    failure = next(arg for arg in by_id.values()
                   if arg.get("rule_id") == mapping["arguments"]["failure_route"]["rule_id"])
    assert probe["strength"] == 700
    assert failure["strength"] == 400
    assert probe["label"] == "in" and failure["label"] == "out"
    assert any(edge["attacker"] == probe["id"] and edge["subargument"] == failure["id"]
               and edge["kind"] == "rebut" for edge in result["formal"]["defeats"])
    assert not any(edge["attacker"] == failure["id"] and edge["subargument"] == probe["id"]
                   for edge in result["formal"]["defeats"])
    assert mapping["arguments"]["probe_route"]["rank_annotation"]["review"].startswith("synthetic-review/")
    assert mapping["evidence"]["probe_data"]["rank_annotation"]["span"]["line"] > 0
    assert len([pair for pair in mapping["contraries"] if pair["target_kind"] == "claim"]) == 2
    view = build_aspic_view(result)
    assert any(((event.get("relation_origin") or {}).get("annotation") or {}).get("review") ==
               "synthetic-review/incompatible-outcomes" for event in view["defeats"])
    assert any((arg["origin"].get("formal_review") or {}).get("kind") == "rank"
               for arg in view["arguments"])
    assert result["claim_status"] == "supported"
    assert compilation.assessment["claims"]["run_passes"]["status"] == "supported"


def test_one_way_contrary_ignores_preference_and_does_not_change_authored_eal():
    source = BASE + '''
claim run_fails { statement "This synthetic run fails."; environment lab; }
argument failure_route { conclusion run_fails; reasoning authored; evidence gap_data; }
aspic {
  rank argument failure_route 0 reviewed "review/weak-diagnostic";
  rank argument probe_route 1000 reviewed "review/probe";
  contrary claim run_fails to run_passes reviewed "review/one-way-incompatibility";
}
'''
    compilation, result = compare(source)
    assert compilation.assessment["claims"]["run_passes"]["status"] == "supported"
    assert result["formal"]["grounded_status"] == "rejected"
    assert result["claim_status"] == "contested"
    assert result["routes"]["probe_route"]["status"] == "rejected"
    assert result["routes"]["failure_route"]["status"] == "accepted"


def test_strict_nested_derivation_preserves_fallible_subarguments_and_defeats():
    source = BASE + '''
objection challenge { target argument primary_route; evidence gap_data; }
aspic {
  strict argument reporting_route reviewed "review/report-implication";
  rank objection challenge 10 reviewed "review/trace-gap";
}
'''
    _, result = compare(source)
    rule = next(rule for rule in result["theory"]["rules"]
                if rule["id"] == result["source_map"]["arguments"]["reporting_route"]["rule_id"])
    assert rule["kind"] == "strict" and set(rule) == {"id", "kind", "antecedents", "consequent"}
    assert result["source_map"]["arguments"]["reporting_route"]["applicability_atom"] is None
    reports = [arg for arg in result["formal"]["arguments"] if arg.get("rule_id") == rule["id"]]
    assert len(reports) == 2
    assert {arg["label"] for arg in reports} == {"in", "out"}
    assert all(arg["top"] == "strict" and arg["direct_subarguments"] for arg in reports)
    assert any(edge["kind"] == "undercut" and edge["target"] in {arg["id"] for arg in reports}
               for edge in result["formal"]["defeats"])


@pytest.mark.parametrize("target", ["argument reporting_route", "claim reportable", "reasoning authored"])
def test_objections_cannot_undercut_strict_routes(target):
    source = BASE + f'''objection challenge {{ target {target}; evidence gap_data; }}
aspic {{ strict argument reporting_route reviewed "review/report-implication"; }}'''
    programme = parse(source)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    with pytest.raises(CompilationError, match="strict route.*cannot be undercut"):
        compile_eal_aspic(source, records, goal="run_passes", now=NOW, context=CONTEXT)


def test_pattern_generated_argument_accepts_formal_annotation():
    source = BASE + '''
pattern measured_route(c: claim, r: reasoning, e: evidence) {
 conclusion c; reasoning r; evidence e;
}
apply measured_probe = measured_route(c=run_passes, r=authored, e=probe_data);
aspic { strict argument measured_probe reviewed "review/pattern-instance"; }
'''
    _, result = compare(source)
    formal = result["source_map"]["arguments"]["measured_probe"]
    assert formal["origin"] == {"pattern": "measured_route", "application": "measured_probe"}
    assert formal["rule_kind"] == "strict"
    assert result["routes"]["measured_probe"]["status"] == "accepted"
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))


@pytest.mark.parametrize("annotation,expected", [
    ('rank argument primary_route 1.5 reviewed "review/x";', "invalid_aspic_annotation"),
    ('rank argument primary_route -1 reviewed "review/x";', "invalid_aspic_annotation"),
    ('rank argument primary_route 1001 reviewed "review/x";', "invalid_aspic_annotation"),
    ('strict argument primary_route reviewed "";', "missing_aspic_review"),
    ('strict argument absent reviewed "review/x";', "unknown_aspic_reference"),
    ('contrary claim run_passes to run_passes reviewed "review/x";', "invalid_aspic_contrary"),
    ('contrary claim run_passes to absent reviewed "review/x";', "unknown_aspic_reference"),
    ('rank argument primary_route 400 reviewed "review/x";\n'
     'rank argument primary_route 500 reviewed "review/y";', "duplicate_aspic_annotation"),
    ('strict argument primary_route reviewed "review/x";\n'
     'rank argument primary_route 500 reviewed "review/y";', "aspic_strict_rank"),
])
def test_invalid_formal_annotation_fails_closed(annotation, expected):
    assert expected in codes(BASE + f'aspic {{ {annotation} }}')


def test_cross_environment_contrary_and_tampered_typed_ir_are_rejected():
    source = BASE + '''environment other { require "site" == "remote"; }
claim remote_claim { statement "A remote result."; environment other; }
aspic { contrary claim run_passes to remote_claim reviewed "review/different-scopes"; }
'''
    assert "aspic_environment_mismatch" in codes(source)
    programme = parse(BASE)
    forged = replace(programme, aspic=(AspicDirective("rank", "argument", "primary_route",
                                                       None, "high", "review/x", SourceSpan(1, 1, 1, 2)),))
    assert "invalid_ir" in {diagnostic.code for diagnostic in validate(forged)}


def test_missing_objection_record_never_becomes_a_negative_premise():
    source = BASE + '''objection challenge { target argument primary_route; evidence gap_data; }
aspic { rank objection challenge 900 reviewed "review/diagnostic"; }'''
    _, result = compare(source, missing=("gap_data",))
    assert result["routes"]["primary_route"]["status"] == "accepted"
    assert result["source_map"]["objections"]["challenge"]["emitted"] is False
    assert result["source_map"]["evidence"]["gap_data"]["available"] is False
    assert result["source_map"]["evidence"]["gap_data"]["atom"] not in {
        item["atom"] for item in result["theory"]["premises"]}
