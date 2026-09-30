"""Reviewed EAL/3 argumentation directives are parsed, checked and compiled explicitly."""

from dataclasses import replace

import pytest

from eal.aspic_compiler import CompilationError, compile_eal_aspic
from eal.aspic_export import export_aspic_view
from eal.formatter import format_source, semantic_ir
from eal.model import ArgumentationDirective, SourceSpan
from eal.parser import EALSyntaxError, parse
from eal.evaluator import evaluate
from eal.semantics import validate
from test_aspic_compiler import BASE, compare
from test_evaluator import CONTEXT, NOW, record


def codes(source):
    return {diagnostic.code for diagnostic in validate(parse(source))}


def test_directed_contrary_and_rank_are_reviewed_and_change_formal_defeat():
    source = BASE + '''claim run_fails {
  statement "This synthetic run fails."
  environment lab
}

argument failure_route = [evidence gap_data] via authored => run_fails

rank probe_route 800 reviewed "synthetic-review/high-confidence-probe"

rank probe_data 700 reviewed "synthetic-review/probe-record"

rank failure_route 400 reviewed "synthetic-review/diagnostic-limit"

contrary run_fails to run_passes reviewed "synthetic-review/incompatible-outcomes"

contrary run_passes to run_fails reviewed "synthetic-review/incompatible-outcomes"
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
    view = export_aspic_view(result)
    assert any(((event.get("relation_origin") or {}).get("annotation") or {}).get("review") ==
               "synthetic-review/incompatible-outcomes" for event in view["defeats"])
    assert any((arg["origin"].get("formal_review") or {}).get("kind") == "rank"
               for arg in view["arguments"])
    assert result["claim_status"] == "supported"
    assert compilation.assessment["claims"]["run_passes"]["status"] == "supported"


def test_one_way_contrary_ignores_preference_and_does_not_change_authored_eal():
    source = BASE + '''claim run_fails {
  statement "This synthetic run fails."
  environment lab
}

argument failure_route = [evidence gap_data] via authored => run_fails

rank failure_route 0 reviewed "review/weak-diagnostic"

rank probe_route 1000 reviewed "review/probe"

contrary run_fails to run_passes reviewed "review/one-way-incompatibility"
'''
    compilation, result = compare(source)
    assert compilation.assessment["claims"]["run_passes"]["status"] == "supported"
    assert result["formal"]["grounded_status"] == "rejected"
    assert result["claim_status"] == "contested"
    assert result["routes"]["probe_route"]["status"] == "rejected"
    assert result["routes"]["failure_route"]["status"] == "accepted"


def test_strict_nested_derivation_preserves_fallible_subarguments_and_defeats():
    source = BASE + '''objection challenge = [evidence gap_data] -x> argument primary_route

strict reporting_route reviewed "review/report-implication"
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
    source = BASE + f'''objection challenge = [evidence gap_data] -x> {target}

strict reporting_route reviewed "review/report-implication"'''
    programme = parse(source)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    with pytest.raises(CompilationError, match="strict route.*cannot be undercut"):
        compile_eal_aspic(source, records, goal="run_passes", now=NOW, context=CONTEXT)


def test_pattern_generated_argument_accepts_argumentation_directive():
    source = BASE + '''pattern measured_route(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c

apply measured_probe=measured_route(c=run_passes, r=authored, e=probe_data)

apply measured_second=measured_route(c=run_passes, r=authored, e=primary_data)

strict measured_probe reviewed "review/pattern-instance"

rank measured_second 700 reviewed "review/other-instance"
'''
    _, result = compare(source)
    formal = result["source_map"]["arguments"]["measured_probe"]
    assert formal["origin"] == {"pattern": "measured_route", "application": "measured_probe"}
    assert formal["rule_kind"] == "strict"
    second = result["source_map"]["arguments"]["measured_second"]
    assert second["origin"] == {"pattern": "measured_route", "application": "measured_second"}
    assert second["rule_kind"] == "defeasible" and second["rank"] == 700
    assert result["routes"]["measured_probe"]["status"] == "accepted"
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))


@pytest.mark.parametrize("annotation,expected", [
    ('rank primary_route 1.5 reviewed "review/x"', "invalid_formal_directive"),
    ('rank primary_route -1 reviewed "review/x"', "invalid_formal_directive"),
    ('rank primary_route 1001 reviewed "review/x"', "invalid_formal_directive"),
    ('strict primary_route reviewed ""', "missing_formal_review"),
    ('strict absent reviewed "review/x"', "unknown_formal_reference"),
    ('strict probe_data reviewed "review/x"', "formal_target_kind"),
    ('rank run_passes 400 reviewed "review/x"', "formal_target_kind"),
    ('rank authored 400 reviewed "review/x"', "formal_target_kind"),
    ('contrary probe_data to run_passes reviewed "review/x"', "formal_target_kind"),
    ('contrary run_passes to run_passes reviewed "review/x"', "invalid_formal_contrary"),
    ('contrary run_passes to absent reviewed "review/x"', "unknown_formal_reference"),
    ('''rank primary_route 400 reviewed "review/x"
'''
     'rank primary_route 500 reviewed "review/y"', "duplicate_formal_directive"),
    ('''contrary run_passes to reportable reviewed "review/x"
'''
     'contrary run_passes to reportable reviewed "review/y"', "duplicate_formal_directive"),
    ('''strict primary_route reviewed "review/x"
'''
     'rank primary_route 500 reviewed "review/y"', "formal_strict_rank"),
])
def test_invalid_argumentation_directive_fails_closed(annotation, expected):
    assert expected in codes(BASE + annotation)


def test_cross_environment_contrary_and_tampered_typed_ir_are_rejected():
    source = BASE + '''environment other {
  require "site" == "remote"
}

claim remote_claim {
  statement "A remote result."
  environment other
}

contrary run_passes to remote_claim reviewed "review/different-scopes"
'''
    assert "formal_environment_mismatch" in codes(source)
    programme = parse(BASE)
    forged = replace(programme, argumentation_directives=(ArgumentationDirective("rank", "primary_route",
                                                       None, "high", "review/x", SourceSpan(1, 1, 1, 2)),))
    assert "invalid_ir" in {diagnostic.code for diagnostic in validate(forged)}


def test_missing_objection_record_never_becomes_a_negative_premise():
    source = BASE + 'objection challenge = [evidence gap_data] -x> argument primary_route'
    _, result = compare(source, missing=("gap_data",))
    assert result["routes"]["primary_route"]["status"] == "accepted"
    assert result["source_map"]["objections"]["challenge"]["emitted"] is False
    assert result["source_map"]["evidence"]["gap_data"]["available"] is False
    assert result["source_map"]["evidence"]["gap_data"]["atom"] not in {
        item["atom"] for item in result["theory"]["premises"]}


def test_unique_eal_names_resolve_all_rank_target_kinds_after_collection():
    source = BASE + '''objection challenge = [evidence gap_data] -x> argument primary_route

rank primary_data 610 reviewed "review/measurement"

rank calibration 620 reviewed "review/assumption"

rank probe_route 630 reviewed "review/inference"
'''
    _, result = compare(source)
    origins = result["source_map"]
    assert [(item["name"], item["target_kind"]) for item in origins["formal_directives"]] == [
        ("primary_data", "evidence"), ("calibration", "assumption"),
        ("probe_route", "argument")]
    assert origins["evidence"]["primary_data"]["rank"] == 610
    assert origins["assumptions"]["calibration"]["rank"] == 620
    assert origins["arguments"]["probe_route"]["rank"] == 630


def test_objection_rank_is_rejected_because_undercuts_ignore_preferences():
    source = BASE + '''objection challenge = [evidence gap_data] -x> argument primary_route

rank challenge 640 reviewed "review/objection"'''
    diagnostic = next(d for d in validate(parse(source)) if d.code == "formal_target_kind")
    assert diagnostic.actual == "objection"
    assert diagnostic.expected == "argument | assumption | evidence"
    assert diagnostic.span.line == source.count("\n") + 1
    programme = parse(source)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    with pytest.raises(CompilationError, match="invalid"):
        compile_eal_aspic(source, records, goal="run_passes", now=NOW, context=CONTEXT)


def test_wrong_kind_and_ambiguous_name_diagnostics_point_to_argumentation_directive():
    source = BASE + 'rank run_passes 700 reviewed "review/wrong-kind"'
    diagnostic = next(d for d in validate(parse(source)) if d.code == "formal_target_kind")
    assert diagnostic.expected == "argument | assumption | evidence"
    assert diagnostic.actual == "claim"
    assert diagnostic.span.line == source.count("\n") + 1

    duplicate = BASE + '''tool probe_data {
  version "2"
}

rank probe_data 700 reviewed "review/ambiguous"'''
    assert {"duplicate_symbol", "ambiguous_formal_reference"} <= codes(duplicate)


def test_argumentation_directives_are_order_independent_and_default_eal_is_unchanged():
    preface = '''rank probe_data 700 reviewed "review/probe"
'''
    source = BASE.replace('''language "EAL/3"
''', '''language "EAL/3"
''' + preface)
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))
    original = parse(BASE)
    annotated = parse(source)
    records = {name: record(original, name, {"ok": True}) for name in original.evidence}
    # Record source bindings are exact; rebuild them for the changed source.
    annotated_records = {name: record(annotated, name, {"ok": True}) for name in annotated.evidence}
    plain = evaluate(original, records, now=NOW, context=CONTEXT)
    annotated_result = evaluate(annotated, annotated_records, now=NOW, context=CONTEXT)
    assert plain["claims"] == annotated_result["claims"]
    assert plain["arguments"] == annotated_result["arguments"]


def test_obsolete_solver_named_block_is_rejected_as_eal_source():
    with pytest.raises(EALSyntaxError):
        parse(BASE + 'aspic { rank probe_data 700 reviewed "review/old"\n }')


def test_argumentation_words_remain_contextual_identifiers():
    source = BASE + '''evidence rank {
  tool collector
  kind test
  environment lab
  max_age 60
  require "ok" == true
}

rank rank 650 reviewed "review/contextual-name"
'''
    assert not codes(source)
    assert semantic_ir(parse(source)) == semantic_ir(parse(format_source(source)))
