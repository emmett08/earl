#!/usr/bin/env python3
"""Audit retained finite-graph outcomes, then collect and assess the EAL argument."""
from __future__ import annotations

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

from experiment_finite_model_checker import oracle

RESULT = ROOT / "benchmarks/results/2026-09-23-finite-model-checker-v101/result.json"
DIRECTORY = ROOT / "arguments/finite-model-checker"
CONTEXT = {"investigation": "INV-EAL2-COMPANION-001"}
NOW = "2026-09-23T17:30:00Z"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check() -> dict:
    result = json.loads(RESULT.read_text())
    observation = json.loads((DIRECTORY / "observation.json").read_text())
    if result["protocol_sha256"] != digest(ROOT / "benchmarks/experiments/eal2-finite-model-checker.json"):
        raise ValueError("Protocol bytes changed after the experiment")
    if result["runner_sha256"] != digest(ROOT / "scripts/experiment_finite_model_checker.py"):
        raise ValueError("Runner bytes changed after the experiment")
    if result["method_source_sha256"] != digest(ROOT / "src/eal/reachability.py"):
        raise ValueError("Method source changed after the experiment")
    observed = observation["value"]
    if observed["result_sha256"] != digest(RESULT) or any(
        observed[key] != result[key] for key in ("complete", "graphs", "results", "counterfeit", "protocol_sha256", "method_source_sha256")
    ):
        raise ValueError("The collected summary is not the retained experiment result")
    counts = {"computed_correct": 0, "authored_correct": 0,
              "authored_wrong_scope_supported": 0, "wrong_scope_refused": 0,
              "stale_refused": 0, "witnesses_valid": 0, "edge_order_invariant": 0}
    labels = set()
    for case in result["cases"]:
        label = (case["pair"], case["variant"])
        if label in labels:
            raise ValueError("Duplicate case")
        labels.add(label)
        graph = case["graph"]
        reach, shortest = oracle(graph)
        if (reach, shortest) != (case["oracle_reachable"], case["oracle_path"]):
            raise ValueError(f"Oracle mismatch in {label}")
        expected = "unsupported" if reach else "supported"
        counts["computed_correct"] += case["computed_status"] == expected
        counts["authored_correct"] += case["authored_status"] == expected
        counts["wrong_scope_refused"] += case["wrong_scope_status"] == "unsupported"
        counts["authored_wrong_scope_supported"] += case["authored_wrong_scope_status"] == "supported"
        counts["stale_refused"] += case["stale_status"] == "unsupported"
        counts["edge_order_invariant"] += case["edge_order_status"] == case["computed_status"]
        witness = case["counterexample"]
        valid = not reach and witness == [] or (reach and len(witness) == len(shortest) and
            witness[0] == graph["start"] and witness[-1] in graph["forbidden"] and
            all([a, b] in graph["edges"] for a, b in zip(witness, witness[1:])))
        counts["witnesses_valid"] += bool(valid)
    if (result["graphs"] != 48 or labels != {(pair, variant) for pair in range(24)
         for variant in ("safe", "unsafe")} or counts != result["results"] or not result["complete"]):
        raise ValueError("Result completeness or aggregate mismatch")
    source = (DIRECTORY / "argument.eal").read_text()
    if semantic_ir(parse(source)) != semantic_ir(parse(format_source(source))):
        raise ValueError("EAL parse–format–parse meaning changed")
    with tempfile.TemporaryDirectory(prefix="eal-companion-") as temporary:
        service = ReasoningService(ROOT, DIRECTORY / "tools.toml", Path(temporary) / "results.sqlite3")
        validation = service.validate(source)
        if not validation["valid"]:
            raise ValueError(validation)
        collection = service.collect(source, CONTEXT)
        if any(entry["status"] != "ok" for entry in collection["records"].values()):
            raise ValueError("An observation could not be collected")
        assessment = service.reason(source, CONTEXT, collection["collection_id"], NOW)
        statuses = {name: entry["status"] for name, entry in assessment["claims"].items()}
    expected = {"finite_result": "supported", "companion_capability": "supported",
                "graph_authentication_unestablished": "supported",
                "physical_device_safe": "unsupported", "general_engineering_gain": "unsupported"}
    if statuses != expected:
        raise ValueError({"expected": expected, "actual": statuses})
    return {"case_records_audited": len(labels), "aggregate_recomputed": counts,
            "parse_format_parse_equivalent": True, "claim_statuses": statuses,
            "result_sha256": digest(RESULT)}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
