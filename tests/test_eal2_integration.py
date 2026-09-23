"""EAL/2 abstractions exercised through installed interfaces and task scoring."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from mcp import StdioServerParameters

from eal.agent import run_agent
from eal.benchmark import compare_sources
from eal.formatter import format_program
from eal.parser import parse
from test_agent import ScriptedProvider
from eal.runtime import ReasoningService

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "examples/reusable-measurements.eal").read_text()
CONTEXT = {"site": "bench", "revision": "A"}
NOW = "2026-09-23T10:30:00Z"


def setup_example(tmp_path):
    (tmp_path / "examples").mkdir()
    for name in ("reusable-measurements.eal", "reusable-observation.json", "reusable-tools.toml"):
        shutil.copyfile(ROOT / "examples" / name, tmp_path / "examples" / name)
    return ReasoningService(tmp_path, tmp_path / "examples/reusable-tools.toml")


def expanded_source():
    program = parse(SOURCE)
    arguments = {name: replace(arg, origin=None) for name, arg in program.arguments.items()}
    return format_program(replace(program, arguments=arguments, patterns={}, applications={},
                                  declaration_count=program.declaration_count - len(program.patterns)))


def test_expansion_equivalence_is_scored_and_executed(tmp_path):
    service = setup_example(tmp_path)
    expanded = expanded_source()
    assert compare_sources(SOURCE, expanded, anchored_claims=("pressure_increase", "pressure_bounded"))["equivalent"]
    results = []
    for source in (SOURCE, expanded):
        collection = service.collect(source, CONTEXT)
        assert list(collection["records"]) == ["pressure_trial"]
        report = service.reason(source, CONTEXT, collection["collection_id"], NOW)
        results.append(report)
        assert {v["status"] for v in report["claims"].values()} == {"supported"}
        for name in ("pressure_argument", "upper_argument"):
            assert report["arguments"][name]["reasoning_result"]["binding"]["output_unit"] == "kPa"
    assert results[0]["claims"] == results[1]["claims"]
    assert not compare_sources(SOURCE, SOURCE.replace("result \"estimate\" <= 10", "result \"estimate\" <= 1"))["equivalent"]


def test_invalid_pattern_and_semantic_error_have_locations(tmp_path):
    service = setup_example(tmp_path)
    bad = SOURCE.replace("c=pressure_increase", "c=pressure_trial")
    result = service.validate(bad)
    assert not result["valid"]
    assert any(d.get("span", {}).get("line", 0) > 0 for d in result["diagnostics"] if d.get("span"))
    assert not compare_sources(bad, bad)["equivalent"]


def test_cli_format_and_validate_pattern_source(tmp_path):
    setup_example(tmp_path)
    args = [sys.executable, "-m", "eal.cli", "--workspace", str(tmp_path)]
    for operation in ("validate", "format"):
        result = subprocess.run(args + [operation, "examples/reusable-measurements.eal"],
                                capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        if operation == "validate":
            assert value["valid"]
        else:
            assert "pattern estimate_from_trial" in value["source"]
            assert "apply upper_argument" in value["source"]


def test_text_model_host_assesses_reusable_arguments_through_mcp(tmp_path):
    setup_example(tmp_path)
    server = StdioServerParameters(command=sys.executable, args=["-m", "eal.server", "--workspace", str(tmp_path),
        "--registry", str(tmp_path / "examples/reusable-tools.toml")], env=dict(os.environ))
    provider = ScriptedProvider([{"operation": "assess"}, {"operation": "finish"}])
    report = asyncio.run(run_agent("Assess the two pressure estimates from the supplied trial.", provider, server,
        required_claims=("pressure_increase", "pressure_bounded"),
        initial_data={"source": SOURCE, "context": CONTEXT, "now": NOW}))
    assert report["status"] == "completed", report
    assert all(claim["status"] == "supported" for claim in report["final"]["claims"].values())
    assert report["final"]["verification"] == "server_assessment"
    assert len([event for event in report["tool_calls"] if event["tool"] == "eal_collect"]) == 1
