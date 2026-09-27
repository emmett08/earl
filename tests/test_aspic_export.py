"""Export recomputes semantics and preserves supplied provenance explicitly."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from eal.aspic import solve_aspic
from eal.aspic_export import VIEW_SCHEMA, export_aspic_view
from test_aspic_compiler import BASE, compare


def compiled_view(*, missing=()):
    source = BASE + 'objection challenge { target argument primary_route; evidence gap_data; }'
    return compare(source, missing=missing)[1]


def test_view_preserves_formal_routes_defeat_witnesses_and_checked_eal_origins():
    result = compiled_view()
    view = export_aspic_view(result)
    assert view["formal_status"] == "accepted"
    assert view["authored_claim_status"] == "supported"
    assert view["snapshot_digest"] == result["snapshot_digest"]
    by_id = {arg["id"]: arg for arg in view["arguments"]}
    primary = result["source_map"]["arguments"]["primary_route"]
    selected = [arg for arg in by_id.values() if arg.get("rule_id") == primary["rule_id"]]
    assert len(selected) == 1
    arg = selected[0]
    assert arg["origin"]["name"] == "primary_route"
    assert arg["origin"]["span"] == primary["span"]
    assert arg["display_conclusion"] == "run_passes"
    assert "specified result" in arg["authored_statement"]
    assert arg["origin"]["rationale"] == "Bounded measured route."
    assert arg["label"] == "out"
    assert {by_id[child]["origin"]["name"] for child in arg["direct_subarguments"]} == {
        "primary_data", "calibration"}
    assert any(item["target"] == arg["id"] and item["subargument"] == arg["id"]
               and item["kind"] == "undercut" for item in view["defeats"])
    evidence = next(arg for arg in by_id.values()
                    if arg["origin"]["name"] == "primary_data")
    assert evidence["origin"]["observation"]["run_id"]


def test_missing_observation_stays_unresolved_and_never_becomes_a_premise():
    result = compiled_view(missing=("primary_data",))
    view = export_aspic_view(result)
    missing = next(item for item in view["unavailable_evidence"]
                   if item["name"] == "primary_data")
    assert missing["reasons"]
    assert missing["availability_issues"] == ["missing_observation"]
    assert missing["span"]
    assert not any(arg["origin"]["name"] == "primary_data" for arg in view["arguments"])
    assert result["routes"]["primary_route"]["status"] == "unconstructed"


def test_previous_compiled_result_is_unclassified_without_guessing_from_prose():
    result = compiled_view(missing=("primary_data",))
    del result["source_map"]["evidence"]["primary_data"]["availability_issues"]
    view = export_aspic_view(result)
    item = next(item for item in view["unavailable_evidence"]
                if item["name"] == "primary_data")
    assert item["availability_issues"] == ["unclassified_legacy"]


def test_rejects_untyped_or_forged_availability_issue_codes():
    result = compiled_view(missing=("primary_data",))
    item = result["source_map"]["evidence"]["primary_data"]
    item["availability_issues"] = ["probably_absent"]
    with pytest.raises(ValueError, match="source map structure"):
        export_aspic_view(result)


def test_explicit_theory_without_source_map_has_formal_origin():
    theory = {"premises": [{"atom": "p", "kind": "ordinary", "rank": 5}],
              "rules": [{"id": "derive", "kind": "defeasible", "antecedents": ["p"],
                         "consequent": "q", "name": "applicable", "rank": 5}],
              "contraries": [], "goal": "q"}
    formal = solve_aspic({"theory": theory})
    view = export_aspic_view({"theory": theory, "formal": formal})
    assert view["arguments"][-1]["origin"] == {"kind": "formal rule", "name": "derive"}
    assert view["arguments"][-1]["direct_subarguments"] == ["A0"]


@pytest.mark.parametrize("alteration,match", [
    (lambda result: result["theory"]["rules"].pop(), "theory digest"),
    (lambda result: result["formal"]["arguments"][0].update(
        {"direct_subarguments": ["unknown"]}), "recomputation"),
    (lambda result: result["formal"]["defeats"][0].update(
        {"subargument": "unknown"}), "recomputation"),
    (lambda result: result["source_map"].update({"theory_digest": "0" * 64}),
     "Source map"),
])
def test_rejects_inconsistent_theory_edges_and_provenance(alteration, match):
    result = deepcopy(compiled_view())
    alteration(result)
    with pytest.raises(ValueError, match=match):
        export_aspic_view(result)


def test_supplied_prose_is_preserved_without_authentication_claim():
    result = compiled_view()
    dangerous = '</script><script>alert("bad")</script><img src=x onerror=alert(2)>'
    result["source_map"]["claims"]["run_passes"]["statement"] = dangerous
    view = export_aspic_view(result)
    assert view["schema"] == "aspic-view/2"
    assert view["validation"] == {"formal_result": "recomputed", "provenance": "supplied"}
    assert view["theory_digest"] == result["formal"]["theory_sha256"]
    assert view["evaluated_at"] == result["source_map"]["assessed_at"]
    assert any(arg.get("authored_statement") == dangerous for arg in view["arguments"])
    view["arguments"][0]["direct_subarguments"].append("edited")
    assert "edited" not in result["formal"]["arguments"][0]["direct_subarguments"]


@pytest.mark.parametrize("alteration", [
    lambda result: result["formal"]["arguments"][0].update({"label": "out"}),
    lambda result: result["formal"]["arguments"][0].update({"strength": 499}),
    lambda result: result["formal"]["arguments"][0].update({"rank": 499}),
    lambda result: result["formal"].update({"defeats": [], "defeat_count": 0}),
    lambda result: result["formal"].update({"argument_count": 1}),
    lambda result: result["formal"].update({"grounded_accepted": False}),
    lambda result: result["formal"]["arguments"].pop(),
])
def test_rejects_forged_labels_ranks_counts_and_omitted_defeats(alteration):
    result = compiled_view()
    alteration(result)
    with pytest.raises(ValueError, match="recomputation"):
        export_aspic_view(result)


@pytest.mark.parametrize("alteration", [
    lambda source: source["evidence"]["primary_data"].update({"atom": []}),
    lambda source: source["arguments"]["primary_route"].update({"rank": 0}),
    lambda source: source["arguments"]["primary_route"].update({"conclusion_atom": "unrelated"}),
    lambda source: source.update({"contraries": [{"attacker": "absent", "target": "absent"}]}),
    lambda source: source["evidence"]["primary_data"].update({"identity": "not an observation"}),
])
def test_rejects_invalid_source_map_structure_and_correspondence(alteration):
    result = compiled_view()
    alteration(result["source_map"])
    with pytest.raises(ValueError, match="[Ss]ource map"):
        export_aspic_view(result)


def test_rejects_goal_claim_mapped_to_a_different_formal_atom():
    result = compiled_view()
    result["claim"] = result["source_map"]["goal"]["claim"] = "reportable"
    with pytest.raises(ValueError, match="goal claim does not name the formal goal atom"):
        export_aspic_view(result)


@pytest.mark.parametrize("clear_evidence", [False, True])
def test_structural_basis_cannot_relabel_an_ordinary_premise(clear_evidence):
    result = compiled_view()
    atom = result["source_map"]["evidence"]["primary_data"]["atom"]
    result["source_map"]["structural_basis"] = {"atom": atom, "meaning": "No observation"}
    if clear_evidence:
        result["source_map"]["evidence"] = {}
    with pytest.raises(ValueError, match="structural basis must name an unmapped axiom"):
        export_aspic_view(result)


def test_structural_basis_must_reference_a_declared_axiom():
    result = compiled_view()
    result["source_map"]["structural_basis"] = {"atom": "absent", "meaning": "No observation"}
    with pytest.raises(ValueError, match="structural basis must name an unmapped axiom"):
        export_aspic_view(result)


def test_empty_observation_snapshot_preserves_structural_basis():
    result = compare(BASE, missing=("primary_data", "probe_data", "gap_data", "calibration_data"))[1]
    view = export_aspic_view(result)
    basis = next(arg for arg in view["arguments"] if arg["origin"]["kind"] == "structural basis")
    assert basis["top"] == "axiom"
    assert "no observation" in basis["origin"]["meaning"]
    assert view["goal_claim"] == "run_passes"


def test_published_schema_matches_export_contract():
    from jsonschema import Draft202012Validator

    path = Path(__file__).resolve().parents[1] / "docs" / "aspic-view.schema.json"
    published = json.loads(path.read_text(encoding="utf-8"))
    assert published == VIEW_SCHEMA
    Draft202012Validator.check_schema(published)
    Draft202012Validator(published).validate(export_aspic_view(compiled_view()))


def test_failed_bounded_recomputation_cannot_export(monkeypatch):
    result = compiled_view()
    monkeypatch.setattr("eal.aspic_export.execute_extension", lambda *args: {
        "status": "unsupported", "reasons": ["Method execution exceeded its timeout"]})
    with pytest.raises(ValueError, match="Bounded ASPIC recomputation failed"):
        export_aspic_view(result)


def test_cli_writes_graph_json_inside_workspace(tmp_path):
    supplied = compiled_view()
    (tmp_path / "result.json").write_text(json.dumps(supplied), encoding="utf-8")
    command = [sys.executable, "-m", "eal.cli", "--workspace", str(tmp_path),
               "export-aspic", "result.json", "--output", "argument.json"]
    run = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, (run.stdout, run.stderr)
    output = json.loads(run.stdout)
    assert Path(output["output"]) == tmp_path / "argument.json"
    assert output["formal_status"] == "accepted"
    view = json.loads((tmp_path / "argument.json").read_text(encoding="utf-8"))
    assert view == export_aspic_view(supplied)
    outside = subprocess.run(command[:-1] + ["../outside.json"],
                             capture_output=True, text=True, timeout=20)
    assert outside.returncode == 2
    assert not (tmp_path.parent / "outside.json").exists()
    (tmp_path / "result.json").write_text(" " * (4 * 1024 * 1024 + 1), encoding="utf-8")
    oversized = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert oversized.returncode == 2
    assert "4 MiB" in json.loads(oversized.stdout)["error"]
