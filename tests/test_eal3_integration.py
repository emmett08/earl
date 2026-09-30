"""EAL/3 abstractions exercised through installed interfaces."""
from dataclasses import replace
import json
import subprocess
import sys

from eal.formatter import format_program
from eal.parser import parse
from eal.runtime import ReasoningService
from _runtime_cases import PRESSURE_SOURCE, write_case

SOURCE = PRESSURE_SOURCE
CONTEXT = {"site": "bench", "revision": "A"}
NOW = "2026-09-23T10:30:00Z"


def setup_example(tmp_path):
    _, _, registry = write_case(tmp_path, "pressure")
    return ReasoningService(tmp_path, registry)


def expanded_source():
    program = parse(SOURCE)
    arguments = {name: replace(arg, origin=None) for name, arg in program.arguments.items()}
    return format_program(replace(program, arguments=arguments, patterns={}, applications={},
                                  declaration_count=program.declaration_count - len(program.patterns)))


def test_expansion_equivalence_is_executed(tmp_path):
    service = setup_example(tmp_path)
    expanded = expanded_source()
    original_arguments = {name: replace(argument, origin=None)
                          for name, argument in parse(SOURCE).arguments.items()}
    assert original_arguments == parse(expanded).arguments
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
    changed = SOURCE.replace('result "estimate" <= 10', 'result "estimate" <= 1')
    assert parse(SOURCE).claims != parse(changed).claims


def test_invalid_pattern_and_semantic_error_have_locations(tmp_path):
    service = setup_example(tmp_path)
    bad = SOURCE.replace("c=pressure_increase", "c=pressure_trial")
    result = service.validate(bad)
    assert not result["valid"]
    assert any(d.get("span", {}).get("line", 0) > 0 for d in result["diagnostics"] if d.get("span"))


def test_cli_format_and_validate_pattern_source(tmp_path):
    setup_example(tmp_path)
    args = [sys.executable, "-m", "eal.cli", "--workspace", str(tmp_path)]
    for operation in ("validate", "format"):
        result = subprocess.run(args + [operation, "cases/pressure.eal"],
                                capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        if operation == "validate":
            assert value["valid"]
        else:
            assert "pattern estimate_from_trial" in value["source"]
            assert "apply upper_argument" in value["source"]
