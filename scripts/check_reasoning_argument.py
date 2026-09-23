#!/usr/bin/env python3
"""Check the scientific argument against actual archive counts and pending data."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eal.runtime import ReasoningService
from eal.formatter import semantic_ir, format_source
from eal.parser import parse
from analyse_relay_transitions import analyse, DEFAULT


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
    audit = analyse(DEFAULT)
    if historical["value"] != historical_value(audit) or historical["details"]["source_files"] != audit["source_files"]:
        raise ValueError("Historical argument evidence differs from the retained archive")
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
        assessment = service.reason(source, historical["context"], collection["collection_id"], historical["observed_at"])
        statuses = {k: v["status"] for k, v in assessment["claims"].items()}
        expected = {"preservation_observed": "supported", "original_correction_unmeasured": "supported",
                    "whole_system_correction_observed": "supported", "notation_advantage": "unsupported",
                    "raw_evidence_correction": "unsupported", "bounded_engineering_transfer": "unsupported",
                    "requested_contribution_established": "unsupported"}
        if statuses != expected:
            raise ValueError({"expected": expected, "actual": statuses})
    return {"schema": "EAL/reasoning-argument-check/1", "valid": True, "historical_counts_recomputed": True,
            "parse_format_parse_equivalent": True, "claims": statuses,
            "interpretation": "Checked structured dependencies and real archive counts. Future empirical claims lack results; unsupported does not mean false."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
