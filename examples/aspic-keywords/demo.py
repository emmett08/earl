"""Exercise the authored compiler and explicit formal method on one synthetic run."""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.aspic import aspic_registry, solve_aspic
from eal.aspic_export import export_aspic_view
from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.runtime import ReasoningService

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CONTEXT = {"device": "synthetic-controller", "run_id": "keywords-001", "dataset": "synthetic"}
NOW = "2026-10-01T07:00:30Z"


def fixture_theory():
    return json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))["theory"]


def solve(theory):
    return solve_aspic({"theory": theory})


def variants(theory):
    """Evaluate each implemented option; expectations are worked out in README."""
    rows = []
    for semantics in ("grounded", "preferred", "stable"):
        for query_mode in ("credulous", "sceptical"):
            for preference in ("minimum_rank", "last_link_rank", "last_link_partial"):
                instance = deepcopy(theory)
                instance["options"] = {"semantics": semantics, "query_mode": query_mode,
                                       "preference": preference}
                if preference != "last_link_partial":
                    instance.pop("priorities", None)
                result = solve(instance)
                assert result["query_status"] == "accepted", result
                rows.append({**instance["options"], "goal": "ready",
                             "query_status": result["query_status"],
                             "extensions": len(result["extensions"])})
    # The tied estimate pair has two preferred/stable extensions.
    for semantics in ("grounded", "preferred", "stable"):
        for query_mode in ("credulous", "sceptical"):
            instance = deepcopy(theory)
            instance["goal"] = "estimate_normal"
            instance["options"].update(semantics=semantics, query_mode=query_mode)
            result = solve(instance)
            expected = "accepted" if semantics != "grounded" and query_mode == "credulous" else "undecided"
            assert result["query_status"] == expected, result
            rows.append({**instance["options"], "goal": instance["goal"],
                         "query_status": result["query_status"],
                         "extensions": len(result["extensions"])})
    return rows


def preference_comparison(theory):
    """Remove the probe and diagnostic attacks to isolate reciprocal rebutting."""
    instance = deepcopy(theory)
    instance["premises"] = [p for p in instance["premises"]
                            if p["atom"] in ("criterion_defined", "primary_ok", "fault")]
    instance["rules"] = [r for r in instance["rules"]
                         if r["id"] in ("primary_ready", "fault_blocks")]
    instance["contraries"] = [p for p in instance["contraries"]
                             if p["attacker"] in ("ready", "~ready")]
    instance["priorities"] = [{"kind": "rule", "higher": "fault_blocks", "lower": "primary_ready"}]
    instance["options"] = {"semantics": "grounded", "query_mode": "sceptical"}
    rows = []
    for preference, expected in (("minimum_rank", "rejected"),
                                 ("last_link_rank", "accepted"),
                                 ("last_link_partial", "rejected")):
        selected = deepcopy(instance)
        selected["options"]["preference"] = preference
        if preference != "last_link_partial":
            selected.pop("priorities", None)
        result = solve(selected)
        assert result["query_status"] == expected, result
        rows.append({"preference": preference, "query_status": expected})
    instance["priorities"] = []
    instance["options"]["preference"] = "last_link_partial"
    assert solve(instance)["query_status"] == "undecided"
    rows.append({"preference": "last_link_partial_without_priority", "query_status": "undecided"})
    return rows


def unresolved_outcomes(theory):
    """Distinguish an absent derivation from a stable extension family of size zero."""
    absent = deepcopy(theory)
    absent["goal"] = "unobserved_result"
    assert solve(absent)["query_status"] == "unconstructed"
    odd_cycle = deepcopy(theory)
    odd_cycle["premises"].append({"atom": "estimate_uncertain", "kind": "ordinary", "rank": 500})
    estimates = {"estimate_normal", "estimate_abnormal"}
    odd_cycle["contraries"] = [c for c in odd_cycle["contraries"]
                               if c["attacker"] not in estimates]
    odd_cycle["contraries"].extend([
        {"attacker": "estimate_normal", "target": "estimate_abnormal"},
        {"attacker": "estimate_abnormal", "target": "estimate_uncertain"},
        {"attacker": "estimate_uncertain", "target": "estimate_normal"},
    ])
    odd_cycle["options"]["semantics"] = "stable"
    result = solve(odd_cycle)
    assert result["extensions"] == [] and result["query_status"] == "no_extension"
    assert result["query_accepted"] is False
    return {"absent_goal": "unconstructed", "odd_attack_cycle_stable": "no_extension"}


async def run_mcp():
    """Call the same source through a genuine stdio MCP client/server session."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    with tempfile.TemporaryDirectory(prefix="eal-aspic-keywords-mcp-") as folder:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "eal.server", "--workspace", str(ROOT),
                  "--registry", str(HERE / "tools.toml"), "--database", str(Path(folder) / "runs.sqlite3"),
                  "--methods", "eal.aspic:aspic_registry"], env=environment)
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()

                async def call(tool, arguments):
                    response = await session.call_tool(tool, arguments)
                    if response.is_error:
                        raise RuntimeError(f"{tool} failed: {response.content}")
                    return response.structured_content

                source = (HERE / "source.eal").read_text(encoding="utf-8")
                assert (await call("eal_validate", {"source": source}))["valid"]
                collection = await call("eal_collect", {"source": source, "context": CONTEXT})
                compiled = await call("eal_compile_aspic", {
                    "source": source, "context": CONTEXT, "collection_id": collection["collection_id"],
                    "goal": "reportable", "now": NOW, "semantics": "preferred"})
                assert compiled["formal"]["query_status"] == "accepted"
                source = (HERE / "formal.eal").read_text(encoding="utf-8")
                assert (await call("eal_validate", {"source": source}))["valid"]
                collection = await call("eal_collect", {"source": source, "context": CONTEXT})
                assessment = await call("eal_reason", {
                    "source": source, "context": CONTEXT,
                    "collection_id": collection["collection_id"], "now": NOW})
                explanation = await call("eal_explain", {
                    "assessment_id": assessment["assessment_id"], "claim": "readiness_query"})
                assert explanation["result"]["status"] == "supported"
                return {"compiled_query_status": compiled["formal"]["query_status"],
                        "explicit_claim_status": explanation["result"]["status"]}


def run(output: Path):
    registry = aspic_registry()
    sources = {name: (HERE / name).read_text(encoding="utf-8")
               for name in ("source.eal", "formal.eal")}
    for source in sources.values():
        formatted = format_source(source, registry=registry)
        assert semantic_ir(parse(source)) == semantic_ir(parse(formatted))
        assert format_source(formatted, registry=registry) == formatted
    with tempfile.TemporaryDirectory(prefix="eal-aspic-keywords-") as folder:
        service = ReasoningService(ROOT, HERE / "tools.toml", Path(folder) / "runs.sqlite3",
                                   method_registry=registry)
        collection = service.collect(sources["source.eal"], CONTEXT)
        assert all(record["status"] == "ok" for record in collection["records"].values()), collection
        compiled = service.compile_aspic(sources["source.eal"], CONTEXT,
                                         collection["collection_id"], "reportable", NOW,
                                         semantics="preferred")
        assert compiled["formal"]["query_status"] == "accepted", compiled
        assert compiled["routes"]["primary_route"]["status"] == "rejected"
        assert compiled["routes"]["probe_route"]["status"] == "accepted"
        assert compiled["routes"]["fault_route"]["status"] == "rejected"
        assert {item["kind"] for item in compiled["source_map"]["formal_directives"]} == {
            "strict", "rank", "contrary", "prefer"}
        formal_collection = service.collect(sources["formal.eal"], CONTEXT)
        assert formal_collection["records"]["formal_theory"]["status"] == "ok", formal_collection
        formal_assessment = service.reason(sources["formal.eal"], CONTEXT,
                                            formal_collection["collection_id"], NOW)
        assert formal_assessment["claims"]["readiness_query"]["status"] == "supported", formal_assessment
        formal = {"theory": fixture_theory(), "formal":
                  formal_assessment["arguments"]["formal_route"]["reasoning_result"]["details"]}
        assert {item["kind"] for item in formal["formal"]["defeats"]} == {"undermine", "rebut", "undercut"}
        assert len(formal["formal"]["extensions"]) == 2

    output.mkdir(parents=True, exist_ok=True)
    for name, result in (("compiled", compiled), ("formal", formal)):
        (output / f"{name}-result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (output / f"{name}-view.json").write_text(json.dumps(export_aspic_view(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary = {"dataset": "synthetic", "round_trip": "passed",
               "compiled": {key: compiled["formal"][key] for key in (
                   "argument_count", "defeat_count", "query_status", "grounded_status", "semantics", "preference")},
               "authored_claim_status": compiled["authored_claim_status"],
               "formal": {key: formal["formal"][key] for key in (
                   "argument_count", "defeat_count", "query_status", "grounded_status", "semantics", "preference")},
               "option_variants": variants(formal["theory"]),
               "preference_comparison": preference_comparison(formal["theory"]),
               "unresolved_outcomes": unresolved_outcomes(formal["theory"])}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "output",
                        help="Directory for results and aspic-view/3 browser imports")
    parser.add_argument("--mcp", action="store_true", help="Also validate a stdio MCP client/server round trip")
    arguments = parser.parse_args()
    summary = run(arguments.output.resolve())
    if arguments.mcp:
        summary["mcp"] = asyncio.run(run_mcp())
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
