"""Check the engineering example's calculations, identity binding and failure cases."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eal.parser import parse
from eal.runtime import ReasoningService, acquisition_request
from eal.semantics import validate


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/api-load-test"
SOURCE = (EXAMPLE / "source.eal").read_text()
RAW = (EXAMPLE / "report.json").read_bytes()
REPORT = json.loads(RAW)
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
CLAIM = "performance_criteria_met"
spec = importlib.util.spec_from_file_location("load_test_collector", EXAMPLE / "collect_results.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def request():
    return {"evidence_id": "load_test", "environment": "test_run",
            **acquisition_request(parse(SOURCE), "load_test", CONTEXT)}


def encode_report(report):
    return (json.dumps(report) + "\n").encode()


def assess(tmp_path, report, *, now=None):
    raw = encode_report(report)
    report_path = tmp_path / "report.json"
    report_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    source = SOURCE.replace(hashlib.sha256(RAW).hexdigest(), digest)
    registry = tmp_path / "tools.toml"
    argv = [sys.executable, str(EXAMPLE / "collect_results.py"), "--report", str(report_path)]
    registry.write_text(
        '[tools.load_test_report]\nkind="command"\nversion="1"\nmode="deterministic"\n'
        f'argv={json.dumps(argv)}\n'
        f'env={{PYTHONPATH={json.dumps(str(ROOT / "src"))}}}\n'
    )
    service = ReasoningService(tmp_path, registry)
    collected = service.collect(source, CONTEXT)
    assessed = service.reason(source, CONTEXT, collected["collection_id"], now or REPORT["observed_at"])
    return collected, assessed


def test_report_statistics_and_original_observation_time():
    assert not validate(parse(SOURCE))
    result = collector.summarise(request(), RAW)
    assert result["value"] == {
        "request_count": 100, "p95_ms": 180, "failed_requests": 1, "error_rate_percent": 1.0,
    }
    assert result["observed_at"] == REPORT["observed_at"]
    assert result["details"]["dataset"] == "synthetic"


def test_cli_and_actual_mcp_server_agree():
    result = subprocess.run([sys.executable, str(EXAMPLE / "run.py")], cwd=ROOT,
                            capture_output=True, text=True, timeout=60, check=True)
    report = json.loads(result.stdout)
    assert report["cli_claim_status"] == report["mcp_claim_status"] == "supported"
    assert report["dataset"] == "synthetic"


@pytest.mark.parametrize("variant,expected", [
    ("inclusive_limits", "supported"),
    ("latency", "unsupported"),
    ("errors", "unsupported"),
    ("incomplete", "unsupported"),
    ("stale", "unsupported"),
    ("build", "unsupported"),
])
def test_acceptance_limits_and_scope(tmp_path, variant, expected):
    report = copy.deepcopy(REPORT)
    now = None
    if variant == "inclusive_limits":
        for row in report["requests"][90:95]:
            row["elapsed_ms"] = 200
    elif variant == "latency":
        for row in report["requests"][-6:]:
            row["elapsed_ms"] = 201
    elif variant == "errors":
        report["requests"][0]["status_code"] = 0
    elif variant == "incomplete":
        report["requests"] = report["requests"][:99]
    elif variant == "stale":
        now = "2026-09-26T10:00:01Z"
    elif variant == "build":
        report["build_id"] = "another-build"
    collected, assessed = assess(tmp_path, report, now=now)
    assert collected["records"]["load_test"]["status"] == ("error" if variant == "build" else "ok")
    assert assessed["claims"][CLAIM]["status"] == expected


def test_changed_report_without_repinning_is_rejected():
    with pytest.raises(ValueError, match="SHA-256"):
        collector.summarise(request(), RAW + b" ")


def test_context_cannot_relabel_a_report():
    changed = request()
    changed["context"] = {**CONTEXT, "dataset": "measured"}
    with pytest.raises(ValueError, match="context"):
        collector.summarise(changed, RAW)


@pytest.mark.parametrize("row", [
    {"elapsed_ms": -1, "status_code": 200},
    {"elapsed_ms": True, "status_code": 200},
    {"elapsed_ms": 20, "status_code": True},
    {"elapsed_ms": 20, "status_code": 600},
    {"elapsed_ms": 20},
])
def test_malformed_results_are_rejected(row):
    report = copy.deepcopy(REPORT)
    report["requests"][0] = row
    raw = encode_report(report)
    changed = request()
    changed["input"] = {**changed["input"], "report_sha256": hashlib.sha256(raw).hexdigest()}
    with pytest.raises(ValueError):
        collector.summarise(changed, raw)
