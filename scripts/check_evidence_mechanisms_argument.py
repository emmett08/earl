#!/usr/bin/env python3
"""Recompute both developmental results, then assess their EAL/2 argument."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eal.formatter import format_source, semantic_ir
from eal.parser import parse
from eal.runtime import ReasoningService
from analyse_evidence_mechanisms import analyse, compact, RUN
from experiment_evidence_switches import run as switch_run, OUTPUT as SWITCH_RESULT

DIRECTORY = ROOT / "arguments/evidence-mechanisms"
CONTEXT = {"study": "EAL2-evidence-mechanisms"}
OBSERVED_AT = "2026-09-23T21:56:49Z"
NOW = "2026-09-23T22:00:00Z"
EXPECTED = {
    "raw_transfer_observed": "supported", "executed_switches_observed": "supported",
    "bounded_companion_candidate": "supported", "new_task_gain": "unsupported",
    "eal_specific_gain": "unsupported", "physical_truth": "unsupported",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def summary(analysis: dict, switches: dict) -> dict[str, dict]:
    groups = {c["condition_id"]: c for c in analysis["conditions"]}

    def correct(name: str) -> int:
        return groups[name]["modes"]["strict"]["oracles"]["full_information"]["correct"]

    def copied(name: str) -> int:
        return groups[name]["modes"]["strict"]["copied_proposal"]

    irrelevant = [v for k, v in groups.items() if k.endswith("_answer_irrelevant")]
    return {
        "archive_reader": {
            "attempted": analysis["totals"]["attempts"], "tasks": len(analysis["tasks"]),
            "source_archive_sha256": analysis["provenance"]["archive_sha256"],
            "eal": {"raw_only": {"correct": correct("eal_raw_only")},
                    "incorrect_answer": {
                        "correct": correct("eal_incorrect_answer"),
                        "raw_correct": correct("eal_incorrect_answer_raw"),
                        "assessed_correct": correct("eal_incorrect_answer_assessed"),
                        "answer_copied": copied("eal_incorrect_answer"),
                        "raw_copied": copied("eal_incorrect_answer_raw")},
                    "correct_answer": {"answer_correct": correct("eal_correct_answer"),
                                       "raw_correct": correct("eal_correct_answer_raw")}},
            "json": {"raw_only": {"correct": correct("json_raw_only")}},
            "irrelevant": {"available_correct": sum(v["modes"]["strict"]["oracles"]["available_information"]["correct"] for v in irrelevant),
                           "false_support": sum(v["modes"]["strict"]["oracles"]["available_information"]["false_support"] for v in irrelevant)},
        },
        "switch_reader": {"total": switches["total"], "passed": switches["passed"],
                          "pairs": len(switches["switches"]),
                          "source_suite_sha256": switches["suite_sha256"]},
        "prospective_reader": {"state": "specified", "new_task_model_outcome_improved": False,
                               "equal_capability_checker_compared": False,
                               "eal_specific_value_established": False,
                               "independent_source_and_translation_validated": False},
    }


def observation(name: str, value: dict) -> dict:
    return {"value": value, "observed_at": OBSERVED_AT, "context": CONTEXT,
            "request": {"tool": name, "tool_version": "1", "mode": "deterministic",
                        "input": {}, "context": CONTEXT}}


def check(*, write: bool = False) -> dict:
    analysis = analyse(RUN)
    if json.loads((ROOT / "benchmarks/results/2026-09-23-evidence-mechanisms/analysis.json").read_text()) != compact(analysis):
        raise ValueError("Retained compact reanalysis differs from the archive")
    switches = switch_run()
    recorded_switches = json.loads(SWITCH_RESULT.read_text())
    if switches != recorded_switches:
        raise ValueError("Retained switch result differs from re-execution")
    values = summary(analysis, switches)
    for name, value in values.items():
        path = DIRECTORY / {"archive_reader": "archive-observation.json",
                            "switch_reader": "switch-observation.json",
                            "prospective_reader": "prospective-observation.json"}[name]
        expected = observation(name, value)
        if write:
            path.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
        if json.loads(path.read_text()) != expected:
            raise ValueError(f"Argument observation differs from recomputation: {path}")
    source = (DIRECTORY / "argument.eal").read_text()
    if semantic_ir(parse(source)) != semantic_ir(parse(format_source(source))):
        raise ValueError("Formatting changed the EAL/2 argument")
    with tempfile.TemporaryDirectory(prefix="eal-mechanisms-argument-") as tmp:
        service = ReasoningService(ROOT, DIRECTORY / "tools.toml", Path(tmp) / "audit.sqlite")
        validation = service.validate(source)
        if not validation["valid"]:
            raise ValueError(validation)
        collection = service.collect(source, CONTEXT)
        if any(record["status"] != "ok" for record in collection["records"].values()):
            raise ValueError("Observation collection failed")
        assessment = service.reason(source, CONTEXT, collection["collection_id"], NOW)
        statuses = {name: claim["status"] for name, claim in assessment["claims"].items()}
        if statuses != EXPECTED:
            raise ValueError({"expected": EXPECTED, "actual": statuses})
    return {"schema": "EAL/evidence-mechanisms-argument-check/1", "valid": True,
            "archive_trials_verified": analysis["totals"]["attempts"],
            "switches_reexecuted": switches["total"],
            "source_sha256": digest(source.encode()), "claims": statuses,
            "interpretation": "Finite descriptive claims only. Prospective outcome, comparative value and physical truth are unsupported, not disproved. The interpreter does not prove authored scientific warrants."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-observations", action="store_true",
                        help="Materialise derived observation files during initial authoring")
    args = parser.parse_args()
    print(json.dumps(check(write=args.write_observations), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
