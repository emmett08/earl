"""Credential-free real-HTTP and MCP controls for every development case."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .cases import build_cases, case_specs
from .materials import source_for
from .oracle import reference_report
from .routes import TrialTools


async def self_check(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    cases = await asyncio.to_thread(build_cases, output / "cases", case_specs("pilot"), 20260925)
    results = []
    for case in cases:
        for arm in ("json_prompt", "eal_mcp", "plain_validator"):
            source = source_for(case["target"]["input"], case["target"]["context"])
            tools = TrialTools(output / "checks" / case["id"] / arm, source, {"case": case})
            for report_id in case["reports"]:
                packet = await tools.execute(arm, report_id)
                truth = reference_report(case, report_id)
                if packet["metrics"] != truth["metrics"]:
                    raise RuntimeError(f"Collector metrics disagree with independent reference: {case['id']}")
                if arm in ("eal_mcp", "plain_validator"):
                    if (packet["status"] != truth["status"]
                            or set(packet["failed_checks"]) != set(truth["failed_checks"])
                            or set(packet["unknown_checks"]) != set(truth["unknown_checks"])):
                        raise RuntimeError(f"Checked decision disagrees with independent reference: {case['id']}")
                if arm == "eal_mcp":
                    host = tools.host_assessments[report_id]
                    expected_claims = {
                        "performance_criteria_met": ("supported" if truth["status"] == "supported" else "unsupported"),
                        "performance_criteria_failed": ("supported" if truth["status"] == "unsupported" else "unsupported"),
                    }
                    if (host["host_status"] != truth["status"] or host["claims"] != expected_claims
                            or host["evidence_status"] !=
                            ("unavailable" if truth["status"] == "unavailable" else "available")):
                        raise RuntimeError(f"MCP claims disagree with independent reference: {case['id']}")
                elif arm == "json_prompt" and any(key in packet for key in
                                                   ("status", "failed_checks", "unknown_checks")):
                    raise RuntimeError("Direct route must not supply a host verdict")
                if "host_status" in packet or "decision_status" in packet:
                    raise RuntimeError("Raw host status must remain outside model packets")
                results.append({"case_id": case["id"], "family": case["family"], "arm": arm,
                                "report_id": report_id, "reference": truth,
                                "host_assessment": tools.host_assessments.get(report_id),
                                "report_sha256": packet["provenance"]["report_sha256"]})
            (tools.workspace / "tool-trace.json").write_text(json.dumps(tools.trace, sort_keys=True, indent=2))
    document = {"passed": True, "model_calls": 0, "real_http_runs": len(cases),
                "report_inspections": len(results), "results": results}
    (output / "self-check.json").write_text(json.dumps(document, sort_keys=True, indent=2))
    print(json.dumps({key: document[key] for key in ("passed", "real_http_runs", "report_inspections", "model_calls")}))
