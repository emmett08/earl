"""Contract tests for the single GitHub workflow example.

The saved API projection exercises acquisition mechanics. It is not a live
observation or a study result.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eal.parser import parse
from eal.runtime import acquisition_request


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-gate"
spec = importlib.util.spec_from_file_location("workflow_collector_example", EXAMPLE / "collect_workflow.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
SOURCE = (EXAMPLE / "source.eal").read_text()
CONTEXT = {"repository": "emmett08/earl", "decision": "workflow-result"}
ACQUISITION = acquisition_request(parse(SOURCE), "workflow_result", CONTEXT)
REQUEST = {"evidence_id": "workflow_result", "environment": "github", **ACQUISITION}
RECEIPT = json.loads((EXAMPLE / "receipt.json").read_text())


def captured_get(responses):
    base = "/repos/emmett08/earl/actions/runs/36133531512"
    pages = [f"{base}/attempts/1/jobs?per_page=100&page=1"]
    count = {base: 0}

    def get(path):
        if path == base:
            count[base] += 1
            return responses["current_run"]
        if path == f"{base}/attempts/1":
            return responses["attempt"]
        if path in pages:
            return responses["jobs"]
        raise AssertionError(f"Unreviewed API endpoint: {path}")

    return get, count


def test_pinned_api_projection_checks_latest_attempt_and_required_steps():
    get, count = captured_get(RECEIPT["responses"])
    output = collector.collect(REQUEST, get)
    assert count == {"/repos/emmett08/earl/actions/runs/36133531512": 2}
    assert output["value"]["acquisition"] == "live_api"  # injected transport only
    assert output["value"]["all_jobs_success"] is True
    assert output["value"]["required_steps_success"] is True
    assert output["value"]["job_ids"] == [108066088623]
    assert output["request"] == ACQUISITION
    assert output["context"] == CONTEXT


@pytest.mark.parametrize("section,field,replacement", [
    ("current_run", "head_sha", "0" * 40),
    ("attempt", "run_attempt", 2),
    ("attempt", "workflow_id", 42),
    ("current_run", "created_at", "2026-09-25T12:11:38Z"),
    ("jobs", "total_count", 101),
])
def test_wrong_identity_or_incomplete_pagination_cannot_satisfy_claim(section, field, replacement):
    responses = copy.deepcopy(RECEIPT["responses"])
    responses[section][field] = replacement
    get, _ = captured_get(responses)
    with pytest.raises(ValueError):
        collector.collect(REQUEST, get)


def test_prior_attempt_job_cannot_satisfy_current_attempt():
    responses = copy.deepcopy(RECEIPT["responses"])
    responses["jobs"]["jobs"][0]["run_attempt"] = 0
    get, _ = captured_get(responses)
    with pytest.raises(ValueError, match="another run, commit or attempt"):
        collector.collect(REQUEST, get)


def test_missing_required_step_and_failed_job_produce_negative_observations():
    responses = copy.deepcopy(RECEIPT["responses"])
    responses["jobs"]["jobs"][0]["steps"] = [
        step for step in responses["jobs"]["jobs"][0]["steps"] if step["name"] != "Run make build"
    ]
    get, _ = captured_get(responses)
    result = collector.collect(REQUEST, get)["value"]
    assert result["all_jobs_success"] is True
    assert result["required_steps_success"] is False
    responses["jobs"]["jobs"][0]["conclusion"] = "failure"
    get, _ = captured_get(responses)
    result = collector.collect(REQUEST, get)["value"]
    assert result["all_jobs_success"] is False
    assert result["required_steps_success"] is False


def test_rerun_during_acquisition_fails_closed():
    responses = copy.deepcopy(RECEIPT["responses"])
    get, count = captured_get(responses)

    def rerun(path):
        result = get(path)
        if path.endswith("/36133531512") and count[path] == 2:
            result = {**result, "run_attempt": 2}
        return result

    with pytest.raises(ValueError, match="Run identity differs"):
        collector.collect(REQUEST, rerun)


def test_offline_cli_and_mcp_keep_fixture_status_untrusted():
    result = subprocess.run([sys.executable, str(EXAMPLE / "run.py"), "--offline"],
                            cwd=ROOT, capture_output=True, text=True, timeout=30, check=True)
    report = json.loads(result.stdout)
    assert report["cli"]["claim_status"] == "unsupported"
    assert report["mcp"]["claim_status"] == "unsupported"
    assert report["historical_capture"]["cli_claim_status"] == "supported"
    assert report["historical_capture"]["mcp"]["claim_status"] == "supported"
    assert report["fixture"].endswith("not live evidence")


def test_captured_argument_explicitly_limits_claim_and_provenance():
    from eal.semantics import validate

    program = parse((EXAMPLE / "captured.eal").read_text())
    assert not validate(program)
    assert program.tools["github_workflow"].mode == "deterministic"
    assert program.evidence["workflow_result"].input == parse(SOURCE).evidence["workflow_result"].input
    assert "retained GitHub API projection" in program.claims["workflow_passed"].statement
