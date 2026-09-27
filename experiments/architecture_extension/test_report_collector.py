"""Focused identity and negative-finding checks for the frozen report collector."""
from __future__ import annotations

import json

import pytest

from report_collector import collect, CONTEXT, REPORT


def request(check: str = "baseline_contract") -> dict:
    return {"evidence_id": check, "environment": "notification_study",
            "tool": "architecture_report", "tool_version": "1",
            "input": {"case_id": "b_eal", "check_id": check}, "context": CONTEXT}


def test_checked_finding_and_explicit_negative_design_finding():
    positive = collect(request())
    assert positive["value"]["passed"] is True
    assert positive["context"] == CONTEXT
    negative_request = request()
    negative_request["evidence_id"] = "no_followup"
    negative_request["input"] = {"design_flag": "longitudinal_followup"}
    negative = collect(negative_request)
    assert negative["value"]["passed"] is False
    assert negative["observed_at"] == positive["observed_at"]
    assert negative["value"]["report_sha256"] == positive["value"]["report_sha256"]


@pytest.mark.parametrize("change", ["context", "check", "tool_version"])
def test_rejects_wrong_acquisition_request(change):
    query = request()
    if change == "context":
        query["context"] = {"experiment": "another-study", "dataset": "local-fixture"}
    elif change == "check":
        query["input"]["check_id"] = "unrecognised"
    else:
        query["tool_version"] = "2"
    with pytest.raises(ValueError):
        collect(query)


@pytest.mark.parametrize("change", ["eal", "starting_snapshot", "case_source", "assessor", "missing_check"])
def test_rejects_modified_report_identity_or_missing_measurement(change, tmp_path):
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if change == "eal":
        report["provenance"]["eal_sha256"] = "0" * 64
    elif change == "starting_snapshot":
        report["cases"]["b_eal"]["start_sha256"] = "0" * 64
    elif change == "case_source":
        report["cases"]["b_eal"]["source_sha256"] = "0" * 64
    elif change == "assessor":
        report["provenance"]["assessor_sha256"] = "0" * 64
    else:
        del report["cases"]["b_eal"]["checks"]["baseline_contract"]
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        collect(request(), report_path=changed)
