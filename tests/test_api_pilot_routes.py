"""Real measurements and report selection across independent direct/MCP routes."""
import asyncio
import copy
import json

import pytest

from eal.formatter import semantic_ir
from eal.parser import parse
from experiments.api_load_test.cases import FAMILIES, build_cases, case_specs, digest
from experiments.api_load_test.materials import CHECK_NAMES, operations, prompt_for, source_for
from experiments.api_load_test.oracle import reference, reference_report
from experiments.api_load_test.routes import ToolExecutionError, TrialTools


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    specs = [spec for spec in case_specs() if spec["variant"] == 0
             or (spec["family"] == "corrupt")
             or (spec["family"] == "wrong_identity" and spec["variant"] == 3)]
    values = build_cases(tmp_path_factory.mktemp("pilot-cases") / "cases", specs, 20260925)
    return {(case["family"], case["variant"]): case for case in values}


def test_case_matrix_is_fixed_and_identifiers_do_not_reveal_profiles():
    specs = case_specs()
    assert len(specs) == 40 == len({row["id"] for row in specs})
    assert all(sum(row["family"] == family for row in specs) == 4 for family in FAMILIES)
    assert len(case_specs("smoke")) == 4
    assert all(all(family not in row["id"] for family in FAMILIES) for row in specs)


def test_case_reports_keep_measurement_and_mutation_provenance(cases):
    for case in cases.values():
        assert case["audit"]["measurement_runs"] == 1
        assert case["audit"]["report_sha256"] == {key: digest(report) for key, report in case["reports"].items()}
        assert case["expected_report_id"] in case["reports"]
        assert case["audit"]["development_only"]


def test_json_prompt_preserves_the_same_argument_and_catalogue(cases):
    case = cases["distractor", 0]
    workload, context = case["target"]["input"], case["target"]["context"]
    source = source_for(workload, context)
    prompt = prompt_for("json_prompt", source, workload, case=case)
    encoded = prompt.split("\n\n", 1)[1].split("\n\nReport catalogue", 1)[0]
    assert json.loads(encoded) == json.loads(json.dumps(semantic_ir(parse(source))))
    for row in case["catalogue"]:
        assert row["report_id"] in prompt
    assert "expected_report_id" not in prompt and '"family"' not in prompt


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("arm", ("json_prompt", "eal_mcp", "plain_validator"))
def test_every_failure_mechanism_agrees_with_independent_raw_reference(cases, tmp_path, monkeypatch, family, arm):
    case = cases[family, 0]
    source = source_for(case["target"]["input"], case["target"]["context"])
    tools = TrialTools(tmp_path, source, {"case": case})
    if arm != "eal_mcp":
        async def forbidden(*_):
            raise AssertionError("Direct routes must never execute MCP")
        monkeypatch.setattr(tools, "_mcp", forbidden)
        def forbidden_source(*_):
            raise AssertionError("Direct routes must never parse or evaluate EAL")
        monkeypatch.setattr("experiments.api_load_test.routes.source_for", forbidden_source)
        monkeypatch.setattr("experiments.api_load_test.materials.parse", forbidden_source)
    report_id = case["expected_report_id"]
    packet = asyncio.run(tools.execute(arm, report_id))
    truth = reference(case)
    assert packet["metrics"] == truth["metrics"]
    assert asyncio.run(tools.execute(arm, report_id)) == packet
    assert tools.inspected_report_ids == [report_id]
    assert json.loads(tools.report_path.read_text()) == case["reports"][report_id]
    assert "host_status" not in packet and "decision_status" not in packet
    if arm in ("eal_mcp", "plain_validator"):
        assert packet["status"] == truth["status"]
        assert set(packet["failed_checks"]) == set(truth["failed_checks"])
        assert set(packet["unknown_checks"]) == set(truth["unknown_checks"])
        assert not set(packet["failed_checks"]) & set(packet["unknown_checks"])
    if arm == "eal_mcp":
        assert tools.host_assessments[report_id]["host_status"] == truth["status"]
        assert tools.host_assessments[report_id]["claims"] == {
            "performance_criteria_met": "supported" if truth["status"] == "supported" else "unsupported",
            "performance_criteria_failed": "supported" if truth["status"] == "unsupported" else "unsupported",
        }
        assert "reasoning" not in packet and "evidence" not in packet
        assert [row["tool"] for row in tools.trace if "tool" in row] == [
            "eal_validate", "eal_collect", "eal_reason", "eal_explain"]
    else:
        assert not tools.host_assessments
        assert all(row.get("route") != "mcp_stdio" for row in tools.trace)
        if arm == "json_prompt":
            assert all(key not in packet for key in ("status", "failed_checks", "unknown_checks"))
            assert all(row.get("route") != "direct_validator" for row in tools.trace)


@pytest.mark.parametrize("variant", (1, 2, 3))
def test_corrupt_field_variants_cannot_become_negative_performance_results(cases, tmp_path, variant):
    case = cases["corrupt", variant]
    tools = TrialTools(tmp_path, source_for(case["target"]["input"], case["target"]["context"]), {"case": case})
    packet = asyncio.run(tools.execute("eal_mcp", case["expected_report_id"]))
    assert packet["status"] == "unavailable"
    assert packet["failed_checks"] == ["report_valid"]
    assert set(packet["unknown_checks"]) == set(CHECK_NAMES) - {"report_valid"}
    assert all(value is None for value in packet["metrics"].values())


def test_selection_can_inspect_a_distractor_then_the_target_without_regenerating(cases, tmp_path):
    case = cases["distractor", 0]
    before = digest(case)
    tools = TrialTools(tmp_path, source_for(case["target"]["input"], case["target"]["context"]), {"case": case})
    for report_id in reversed(list(case["reports"])):
        packet = asyncio.run(tools.execute("json_prompt", report_id))
        assert packet["metrics"] == reference_report(case, report_id)["metrics"]
    assert len(tools.inspected_report_ids) == 2
    assert digest(case) == before


def test_report_tampering_is_rejected_before_it_becomes_model_evidence(cases, tmp_path):
    case = copy.deepcopy(cases["healthy", 0])
    case["reports"][case["expected_report_id"]]["requests"][0]["elapsed_ms"] += 1
    tools = TrialTools(tmp_path, source_for(case["target"]["input"], case["target"]["context"]), {"case": case})
    with pytest.raises(ToolExecutionError, match="collector failed"):
        asyncio.run(tools.execute("json_prompt", case["expected_report_id"]))
    assert not tools.inspected_report_ids


def test_invalid_model_selector_remains_repairable(cases, tmp_path):
    case = cases["healthy", 0]
    tools = TrialTools(tmp_path, source_for(case["target"]["input"], case["target"]["context"]), {"case": case})
    with pytest.raises(ValueError, match="Choose a report_id"):
        asyncio.run(tools.execute("json_prompt", "not-in-the-catalogue"))
    assert not tools.attempted_report_ids
    packet = asyncio.run(tools.execute("json_prompt", case["expected_report_id"]))
    assert packet["report_id"] == case["expected_report_id"]


def test_malformed_collector_envelope_is_an_internal_failure(cases, tmp_path, monkeypatch):
    import subprocess
    case = cases["healthy", 0]
    tools = TrialTools(tmp_path, source_for(case["target"]["input"], case["target"]["context"]), {"case": case})
    monkeypatch.setattr("experiments.api_load_test.routes.subprocess.run",
                        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "{bad json", ""))
    with pytest.raises(ToolExecutionError):
        asyncio.run(tools.execute("json_prompt", case["expected_report_id"]))
    assert not tools.packets and not tools.inspected_report_ids


def test_conventional_validator_keeps_exact_plain_explicit_prompt(cases):
    case = cases["healthy", 0]
    workload, context = case["target"]["input"], case["target"]["context"]
    source = source_for(workload, context)
    assert prompt_for("plain_validator", source, workload, case) == prompt_for(
        "plain_explicit", source, workload, case)
    assert operations("plain_validator")[0]["operation"] == "inspect_report"


@pytest.mark.parametrize("arm", ("eal_mcp", "plain_validator"))
def test_checked_packets_expose_one_canonical_status_for_unavailable_evidence(cases, tmp_path, arm):
    case = cases["corrupt", 0]
    tools = TrialTools(tmp_path, source_for(case["target"]["input"], case["target"]["context"]), {"case": case})
    packet = asyncio.run(tools.execute(arm, case["expected_report_id"]))
    assert packet["status"] == "unavailable"
    assert "host_status" not in json.dumps(packet) and "decision_status" not in json.dumps(packet)
    assert "unsupported" not in json.dumps(packet)
    if arm == "eal_mcp":
        assert tools.host_assessments[case["expected_report_id"]]["host_status"] == "unavailable"
        assert any(row.get("tool") == "eal_reason" and row["result"]["claims"]["performance_criteria_met"]["status"]
                   == "unsupported" for row in tools.trace)
