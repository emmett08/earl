#!/usr/bin/env python3
"""Check the scientific argument against actual archive counts and pending data."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eal.runtime import ReasoningService
from eal.formatter import semantic_ir, format_source
from eal.parser import parse
from analyse_relay_transitions import analyse, DEFAULT


def diagnostic_value(analysis):
    """Finite counts only; no population bound or transfer finding is inferred."""
    groups = {group["id"]: group for group in analysis["conditions"]}
    return {
        "status": "complete" if analysis["all_scheduled_finalized"] else "incomplete",
        "freeze_digest": analysis["freeze_digest"],
        "attempted": analysis["finalized_attempts"],
        "scheduled": analysis["scheduled"],
        "tasks": analysis["task_count"],
        "unknown_cost_attempts": analysis["totals"]["resources"]["cost_unknown_attempts"],
        "full_information": {
            name: {"correct": group["metrics"]["full_information"]["correctness"]["count"],
                   "false_support": group["metrics"]["full_information"]["false_support"]["count"],
                   "attempted": group["finalized_attempts"]}
            for name, group in groups.items()},
        "available_information": {
            name: {"correct": group["metrics"]["available_information"]["correctness"]["count"],
                   "false_support": group["metrics"]["available_information"]["false_support"]["count"],
                   "attempted": group["finalized_attempts"]}
            for name, group in groups.items()},
    }


def historical_value(analysis):
    counts = {k: v["counts"] for k, v in analysis["conditions"].items()}
    primary = counts["l_tool_n_evidence"]
    return {"primary": {"initially_correct": primary.get("producer_correct", 0),
                        "initially_incorrect": primary.get("producer_incorrect", 0),
                        "initially_incomplete": primary.get("producer_incomplete", 0),
                        "evidence_preserved": primary.get("preserved", 0),
                        "answer_preserved": counts["l_tool_n_answer"].get("preserved", 0),
                        "shared_producer_checked": analysis["comparisons"][0]["shared_producer_checked"]},
            "sequences": {"small_start_corrected": counts["n_l_tool_n"].get("corrected", 0),
                          "full_start_corrected": counts["l_n_tool_l"].get("corrected", 0),
                          "small_return_baseline_corrected": counts["n_n_answer"].get("corrected", 0),
                          "full_return_baseline_corrected": counts["l_l_answer"].get("corrected", 0),
                          "shared_producer_checked": all(c["shared_producer_checked"] for c in analysis["comparisons"][1:])}}


def check():
    directory = ROOT / "arguments/reasoning-advantage"
    source = (directory / "argument.eal").read_text()
    historical = json.loads((directory / "historical-analysis.json").read_text())
    prospective = json.loads((directory / "prospective-status.json").read_text())
    audit = analyse(DEFAULT)
    if historical["value"] != historical_value(audit) or historical["details"]["source_files"] != audit["source_files"]:
        raise ValueError("Historical argument evidence differs from the retained archive")
    has_diagnostic = "diagnostic" in prospective["value"]
    if has_diagnostic:
        from analyse_notation_transfer import analyse as analyse_diagnostic
        measured = analyse_diagnostic(ROOT / "benchmarks/results/2026-09-23-notation-transfer-live")
        if prospective["value"]["diagnostic"] != diagnostic_value(measured):
            raise ValueError("Diagnostic argument evidence differs from retained model trials")
    formatted = format_source(source)
    if semantic_ir(parse(formatted)) != semantic_ir(parse(source)):
        raise ValueError("Formatting changed the argument meaning")
    with tempfile.TemporaryDirectory(prefix="eal-reasoning-argument-") as temporary:
        service = ReasoningService(ROOT, directory / "tools.toml", Path(temporary) / "audit.sqlite")
        validation = service.validate(source)
        if not validation["valid"]:
            raise ValueError(validation)
        collection = service.collect(source, historical["context"])
        if any(r["status"] == "error" for r in collection["records"].values()):
            raise ValueError("Evidence collection error")
        assessment_time = max(historical["observed_at"], prospective["observed_at"],
                              key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")))
        assessment = service.reason(source, historical["context"], collection["collection_id"], assessment_time)
        statuses = {k: v["status"] for k, v in assessment["claims"].items()}
        expected = {"preservation_observed": "supported", "original_correction_unmeasured": "supported",
                    "whole_system_correction_observed": "supported", "notation_advantage": "unsupported",
                    "raw_evidence_correction": "unsupported", "bounded_engineering_transfer": "unsupported",
                    "requested_contribution_established": "unsupported"}
        if has_diagnostic:
            expected["diagnostic_result_observed"] = "supported"
        if statuses != expected:
            raise ValueError({"expected": expected, "actual": statuses})
    return {"schema": "EAL/reasoning-argument-check/1", "valid": True, "historical_counts_recomputed": True,
            "diagnostic_counts_recomputed": has_diagnostic,
            "parse_format_parse_equivalent": True, "claims": statuses,
            "interpretation": "Checked structured dependencies and retained empirical counts. The independent notation-advantage and transfer criteria remain unmet; unsupported does not mean false."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
