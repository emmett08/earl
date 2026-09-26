"""A view must preserve derivation, defeats, missing evidence and provenance."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from eal.aspic import solve_aspic
from eal.aspic_visualisation import build_aspic_view, render_aspic_html
from test_aspic_compiler import BASE, compare


def compiled_view(*, missing=()):
    source = BASE + 'objection challenge { target argument primary_route; evidence gap_data; }'
    return compare(source, missing=missing)[1]


def test_view_preserves_formal_routes_defeat_witnesses_and_checked_eal_origins():
    result = compiled_view()
    view = build_aspic_view(result)
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
    view = build_aspic_view(result)
    missing = next(item for item in view["unavailable_evidence"]
                   if item["name"] == "primary_data")
    assert missing["reasons"]
    assert missing["span"]
    assert not any(arg["origin"]["name"] == "primary_data" for arg in view["arguments"])
    assert result["routes"]["primary_route"]["status"] == "unconstructed"


def test_explicit_theory_without_source_map_has_formal_origin():
    theory = {"premises": [{"atom": "p", "kind": "ordinary", "rank": 5}],
              "rules": [{"id": "derive", "kind": "defeasible", "antecedents": ["p"],
                         "consequent": "q", "name": "applicable", "rank": 5}],
              "contraries": [], "goal": "q"}
    formal = solve_aspic({"theory": theory})
    view = build_aspic_view({"theory": theory, "formal": formal})
    assert view["arguments"][-1]["origin"] == {"kind": "formal rule", "name": "derive"}
    assert view["arguments"][-1]["direct_subarguments"] == ["A0"]


@pytest.mark.parametrize("alteration,match", [
    (lambda result: result["theory"]["rules"].pop(), "theory digest"),
    (lambda result: result["formal"]["arguments"][0].update(
        {"direct_subarguments": ["unknown"]}), "Direct subarguments"),
    (lambda result: result["formal"]["defeats"][0].update(
        {"subargument": "unknown"}), "Defeat witness"),
    (lambda result: result["source_map"].update({"theory_digest": "0" * 64}),
     "Source map"),
])
def test_rejects_inconsistent_theory_edges_and_provenance(alteration, match):
    result = deepcopy(compiled_view())
    alteration(result)
    with pytest.raises(ValueError, match=match):
        build_aspic_view(result)


def test_html_escapes_untrusted_strings_and_embeds_offline_svg_view():
    result = compiled_view()
    dangerous = '</script><script>alert("bad")</script><img src=x onerror=alert(2)>'
    result["claim"] = dangerous
    result["source_digest"] = dangerous
    result["source_map"]["claims"]["run_passes"]["statement"] = dangerous
    html = render_aspic_html(result, focus=result["formal"]["arguments"][-1]["id"])
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "\\u003c/script\\u003e" in html
    assert "&lt;/script&gt;" in html
    assert "Content-Security-Policy" in html
    assert '<svg id="derivation"' in html
    assert 'id="missing"' in html
    with pytest.raises(ValueError, match="Unknown formal argument"):
        render_aspic_html(result, focus="does_not_exist")


def test_cli_writes_standalone_page_inside_workspace(tmp_path):
    supplied = compiled_view()
    (tmp_path / "result.json").write_text(json.dumps(supplied), encoding="utf-8")
    command = [sys.executable, "-m", "eal.cli", "--workspace", str(tmp_path),
               "visualise-aspic", "result.json", "--output", "argument.html"]
    run = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, (run.stdout, run.stderr)
    output = json.loads(run.stdout)
    assert Path(output["output"]) == tmp_path / "argument.html"
    assert output["formal_status"] == "accepted"
    assert "ASPIC+ arguments" in (tmp_path / "argument.html").read_text(encoding="utf-8")
    outside = subprocess.run(command[:-1] + ["../outside.html"],
                             capture_output=True, text=True, timeout=20)
    assert outside.returncode == 2
    assert not (tmp_path.parent / "outside.html").exists()
