"""Opt-in translation is checked against the authored composed evaluator."""

import json
from itertools import product

import pytest

from eal.aspic_compiler import CompilationError, compile_eal_aspic
from eal.aspic_visualisation import build_aspic_view
from eal.evaluator import canonical_digest
from eal.parser import parse
from test_evaluator import CONTEXT, NOW, record


BASE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool collector { version "1"; }
evidence primary_data { tool collector; kind test; environment lab; max_age 60;
 require "ok" == true; }
evidence probe_data { tool collector; kind test; environment lab; max_age 60;
 require "ok" == true; }
evidence gap_data { tool collector; kind test; environment lab; max_age 60;
 require "ok" == true; }
evidence calibration_data { tool collector; kind test; environment lab; max_age 60;
 require "ok" == true; }
reasoning authored { method "structured/1"; rationale "Bounded measured route."; }
claim run_passes { statement "This run meets the specified result."; environment lab; }
claim reportable { statement "This run may be reported."; environment lab; }
argument primary_route { conclusion run_passes; reasoning authored; evidence primary_data;
 assumptions calibration; }
argument probe_route { conclusion run_passes; reasoning authored; evidence probe_data; }
argument reporting_route { conclusion reportable; reasoning authored; premises run_passes; }
assumption calibration { statement "Calibration is applicable to this run.";
 environment lab; validate calibration_data; }
'''


def compare(source, *, missing=(), stale=()):
    programme = parse(source)
    records = {name: record(programme, name, {"ok": True},
                            collected_at='2026-09-23T11:58:59Z' if name in stale else NOW)
               for name in programme.evidence if name not in missing}
    compiled = compile_eal_aspic(source, records, goal="run_passes",
                                 now=NOW, context=CONTEXT)
    return compiled, compiled.to_dict()


def test_route_specific_undercut_and_independent_probe_match_composed_eal():
    source = BASE + 'objection trace_gap { target argument primary_route; evidence gap_data; }'
    compiled, projection = compare(source)
    assert compiled.assessment["claims"]["run_passes"]["status"] == "supported"
    assert projection["claim_status"] == "supported"
    assert projection["formal"]["grounded_status"] == "accepted"
    assert projection["routes"]["primary_route"]["status"] == "rejected"
    assert projection["routes"]["probe_route"]["status"] == "accepted"
    assert projection["routes"]["reporting_route"]["status"] == "accepted"
    assert {entry["kind"] for entry in projection["formal"]["defeats"]} == {"undercut"}
    assert projection["source_map"]["arguments"]["primary_route"]["conclusion"] == "run_passes"
    assert projection["source_map"]["contraries"][0]["target_name"] == "primary_route"
    assert canonical_digest(projection["theory"]) == projection["formal"]["theory_sha256"]
    json.dumps(projection)


def test_missing_or_stale_primary_observation_preserves_probe_route():
    source = BASE + 'objection trace_gap { target argument primary_route; evidence gap_data; }'
    digests = set()
    for omission in ({"missing": ("primary_data",)}, {"stale": ("primary_data",)}):
        compiled, projection = compare(source, **omission)
        digests.add(projection["snapshot_digest"])
        assert compiled.assessment["claims"]["run_passes"]["status"] == "supported"
        assert projection["claim_status"] == "supported"
        assert projection["routes"]["primary_route"]["status"] == "unconstructed"
        assert projection["routes"]["probe_route"]["status"] == "accepted"
        assert projection["source_map"]["evidence"]["primary_data"]["available"] is False
        assert projection["source_map"]["evidence"]["primary_data"]["reasons"]
        assert projection["source_map"]["evidence"]["primary_data"]["atom"] not in {
            premise["atom"] for premise in projection["theory"]["premises"]}
    assert len(digests) == 2


def test_current_collector_binding_failure_removes_only_affected_route():
    programme = parse(BASE)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    bindings = {name: "0" * 64 for name in programme.evidence}
    bindings["primary_data"] = "1" * 64
    compilation = compile_eal_aspic(BASE, records, goal="run_passes", now=NOW,
                                    context=CONTEXT, binding_digests=bindings)
    projection = compilation.to_dict()
    assert projection["source_map"]["evidence"]["primary_data"]["available"] is False
    assert projection["routes"]["primary_route"]["status"] == "unconstructed"
    assert projection["claim_status"] == "supported"


def test_snapshot_fingerprint_includes_unusable_records_and_emitted_theory():
    programme = parse(BASE)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    records["primary_data"] = record(programme, "primary_data", {"ok": True},
                                     collected_at="2026-09-23T11:58:59Z")
    first = compile_eal_aspic(BASE, records, goal="run_passes",
                              now=NOW, context=CONTEXT).to_dict()
    records["primary_data"]["run_id"] = "another-stale-invocation"
    second = compile_eal_aspic(BASE, records, goal="run_passes",
                               now=NOW, context=CONTEXT).to_dict()
    assert first["theory"] == second["theory"]
    assert first["source_map"]["evidence"]["primary_data"]["identity"] is None
    assert first["source_map"]["evidence"]["primary_data"]["record_digest"] != (
        second["source_map"]["evidence"]["primary_data"]["record_digest"])
    assert first["snapshot_digest"] != second["snapshot_digest"]
    assert first["source_map"]["theory_digest"] == canonical_digest(first["theory"])
    assert len(first["source_map"]["assessment_digest"]) == 64
    assert len(first["source_map"]["backend"]["module_digest"]) == 64


def test_out_of_scope_result_preserves_eal_scope_decision():
    programme = parse(BASE)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    compilation = compile_eal_aspic(BASE, records, goal="run_passes", now=NOW,
                                    context={"site": "elsewhere"})
    result = compilation.to_dict()
    assert result["claim_status"] == "out_of_scope"
    assert result["formal"]["grounded_status"] == "unconstructed"


@pytest.mark.parametrize("target", ("argument primary_route", "claim run_passes"))
def test_small_snapshot_matrix_agrees_on_claim_status(target):
    source = BASE + f'objection challenge {{ target {target}; evidence gap_data; }}'
    names = ("primary_data", "probe_data", "gap_data", "calibration_data")
    for present in product((False, True), repeat=len(names)):
        missing = tuple(name for name, available in zip(names, present) if not available)
        compiled, projection = compare(source, missing=missing)
        actual = compiled.assessment["claims"]["run_passes"]["status"]
        assert projection["claim_status"] == actual, (target, missing, projection["formal"])


@pytest.mark.parametrize("objection,expected", [
    ('target argument primary_route', "supported"),
    ('target claim run_passes', "contested"),
    ('target reasoning authored', "contested"),
    ('target assumption calibration', "supported"),
])
def test_targeted_objection_kinds_preserve_affected_routes(objection, expected):
    source = BASE + f'objection challenge {{ {objection}; evidence gap_data; }}'
    compiled, projection = compare(source)
    assert compiled.assessment["claims"]["run_passes"]["status"] == expected
    assert projection["claim_status"] == expected
    assert projection["routes"]["primary_route"]["status"] == "rejected"
    assert projection["routes"]["probe_route"]["status"] == (
        "rejected" if expected == "contested" else "accepted")


def test_defence_of_objection_restores_primary_route():
    source = BASE + '''objection challenge { target argument primary_route; evidence gap_data; }
objection defence { target objection challenge; evidence probe_data; }
'''
    compiled, projection = compare(source)
    assert compiled.assessment["objections"]["challenge"]["status"] == "defeated"
    assert compiled.assessment["claims"]["run_passes"]["status"] == "supported"
    assert projection["routes"]["primary_route"]["status"] == "accepted"


def test_multi_level_alternative_derivations_keep_direct_edges_and_nested_defeats():
    source = BASE + '''
claim deployable { statement "Synthetic run may proceed."; environment lab; }
claim release_ready { statement "Synthetic release may be considered."; environment lab; }
argument deploy_route { conclusion deployable; reasoning authored;
 premises reportable, run_passes; }
argument release_route { conclusion release_ready; reasoning authored;
 premises deployable; }
objection challenge { target argument primary_route; evidence gap_data; }
'''
    programme = parse(source)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    compiled = compile_eal_aspic(source, records, goal="release_ready",
                                 now=NOW, context=CONTEXT)
    result = compiled.to_dict()
    assert result["claim_status"] == result["authored_claim_status"] == "supported"
    formal = result["formal"]
    assert formal["grounded_status"] == "accepted"
    by_id = {item["id"]: item for item in formal["arguments"]}
    mapping = result["source_map"]["arguments"]
    deployments = [arg for arg in by_id.values()
                   if arg.get("rule_id") == mapping["deploy_route"]["rule_id"]]
    assert len(deployments) == 4  # two independent routes for each premise claim
    assert {by_id[child]["conclusion"] for child in deployments[0]["direct_subarguments"]} == {
        result["source_map"]["claims"][name]["atom"] for name in ("reportable", "run_passes")}
    assert any(any(child in by_id[other]["subarguments"]
                   for other in deployment["direct_subarguments"] if other != child)
               for deployment in deployments for child in deployment["direct_subarguments"])
    releases = [arg for arg in by_id.values()
                if arg.get("rule_id") == mapping["release_route"]["rule_id"]]
    assert len(releases) == 4
    assert all(len(arg["direct_subarguments"]) == 1 for arg in releases)
    assert {arg["label"] for arg in releases} == {"in", "out"}
    primary = {arg["id"] for arg in by_id.values()
               if arg.get("rule_id") == mapping["primary_route"]["rule_id"]}
    assert all(arg["label"] == "out" for arg in releases
               if primary.intersection(arg["subarguments"]))
    assert any(w["kind"] == "undercut" and w["target"] in {a["id"] for a in releases}
               and w["subargument"] in primary for w in formal["defeats"])
    view = build_aspic_view(result)
    assert {arg["id"] for arg in view["arguments"] if arg["origin"]["name"] == "release_route"} == {
        arg["id"] for arg in releases}
    assert any(event["target"] in {arg["id"] for arg in releases}
               and event["subargument"] in primary for event in view["defeats"])


def test_circular_objection_is_undecided_in_both_compositions():
    source = BASE + '''objection circular { target claim run_passes; premises run_passes; }'''
    compiled, projection = compare(source)
    assert compiled.assessment["claims"]["run_passes"]["grounded_label"] == "undecided"
    assert projection["formal"]["grounded_status"] == "undecided"


def test_source_map_is_stable_under_source_declaration_reordering():
    source = BASE + 'objection challenge { target argument primary_route; evidence gap_data; }'
    moved = source.replace('claim run_passes { statement "This run meets the specified result."; environment lab; }\n', '')
    moved += 'claim run_passes { statement "This run meets the specified result."; environment lab; }\n'
    first = compare(source)[1]
    second = compare(moved)[1]
    assert first["theory"] == second["theory"]
    assert first["formal"]["grounded_status"] == second["formal"]["grounded_status"]
    assert first["source_map"]["arguments"]["primary_route"]["rule_id"] == (
        second["source_map"]["arguments"]["primary_route"]["rule_id"])
    assert first["source_digest"] != second["source_digest"]


def test_unknown_goal_invalid_programme_and_formal_self_import_are_rejected():
    programme = parse(BASE)
    records = {name: record(programme, name, {"ok": True}) for name in programme.evidence}
    with pytest.raises(CompilationError, match="Unknown EAL goal"):
        compile_eal_aspic(BASE, records, goal="absent", now=NOW, context=CONTEXT)
    programme.claims["run_passes"] = programme.claims["reportable"]
    with pytest.raises(TypeError, match="source must be EAL/2 text"):
        compile_eal_aspic(programme, records, goal="run_passes", now=NOW, context=CONTEXT)
    with pytest.raises(CompilationError, match="invalid"):
        compile_eal_aspic(BASE.replace("structured/1", "unknown/1"), records,
                          goal="run_passes", now=NOW, context=CONTEXT)
