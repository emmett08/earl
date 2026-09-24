#!/usr/bin/env python3
"""Reproduce retained Stage A reports and generate the paper's summary offline.

By default, reconstruct the pinned analysis material from local Git objects.
--source-root may instead name a checkout of that exact historical material.
No provider calls are made. Frozen inputs, ledgers and reports are read only.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_REF = "430945cd24588240fc5ea351b723f4cfc924dea5"
STUDY = Path("benchmarks/experiments/bias-mechanisms")
RESULTS = ROOT / "benchmarks/results"
ARCHIVE = RESULTS / "2026-09-24-bias-agent-stage-a"
STOPPED = RESULTS / "2026-09-24-bias-agent-pilot-stopped"


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def verify_manifest(directory: Path) -> dict[str, str]:
    entries = dict(re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|",
                              (directory / "README.md").read_text()))
    if not entries:
        raise ValueError(f"No archive hashes in {directory}")
    for name, expected in entries.items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Archive hash mismatch: {name}")
    return entries


def restore_sources(destination: Path, material: dict[str, str]) -> None:
    for name in material:
        path = Path(name) if name.startswith(("src/", "grammar/")) else STUDY / name
        content = subprocess.run(
            ["git", "show", f"{SOURCE_REF}:{path.as_posix()}"], cwd=ROOT,
            check=True, capture_output=True).stdout
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify(source_root: Path, temporary: Path) -> dict:
    hashes = {"stage_a": verify_manifest(ARCHIVE),
              "stopped_pilot": verify_manifest(STOPPED)}
    sys.path[:0] = [str(source_root / "src"), str(source_root / STUDY)]
    run = load_module("run", source_root / STUDY / "run.py")
    analyse = load_module("analyse", source_root / STUDY / "analyse.py")
    reports = {}
    for name in ("pilot", "full"):
        freeze = temporary / f"{name}.json"
        freeze.write_bytes(gzip.decompress((ARCHIVE / f"{name}-freeze-0.1.2.json.gz").read_bytes()))
        # Material hashes, the deterministic request matrix and both ledger
        # hash chains are checked by the unchanged historical analyser.
        result = run.redact(analyse.analyse(
            freeze, ARCHIVE / f"{name}-ledger.jsonl",
            ARCHIVE / "pilot-ledger.jsonl" if name == "full" else None))
        if encoded(result) != (ARCHIVE / f"{name}-report.json").read_bytes():
            raise ValueError(f"{name} report does not reproduce byte for byte")
        reports[name] = result
    pilot_bytes = (ARCHIVE / "pilot-ledger.jsonl").read_bytes()
    if not pilot_bytes.startswith((STOPPED / "pilot-ledger.jsonl").read_bytes()):
        raise ValueError("Stopped pilot events changed during continuation")
    events = run.ledger_events(ARCHIVE / "pilot-ledger.jsonl") + run.ledger_events(
        ARCHIVE / "full-ledger.jsonl")
    outcomes = [event for event in events if event["kind"] == "outcome"]
    if len({event["call_id"] for event in outcomes}) != len(outcomes):
        raise ValueError("Duplicate call outcome")
    if any(event["cost_usd"] is None for event in outcomes):
        raise ValueError("Unpriced call; amend paper accounting")
    report = reports["full"]
    rows = []
    for model in ("nano", "luna", "sol"):
        for route in ("direct", "independent"):
            summary = report["summary"][f"{model}/{route}"]
            assigned = [row for row in report["rows"]
                        if row["model"] == model and row["topology"] == route]
            positive = [row for row in assigned if row["gold_status"] in analyse.SUPPORT]
            rows.append({
                "model": model, "route": route,
                "valid_calls": summary["calls_completed"],
                "assigned_calls": summary["calls_expected"],
                "admitted_dispositions": summary["completed_assignments"],
                "assigned_dispositions": summary["assignments"],
                "fully_warranted": summary["fully_warranted"],
                "gated_fully_warranted": summary["gated_fully_warranted"],
                "supported_recall_count": sum(row["supported_recall"] for row in positive),
                "supported_recall_denominator": len(positive),
                "decisive_count": sum(row["decisive"] for row in assigned),
                "negative_strong_false_attributions_after_validation": summary["negative_raw_false_attribution"],
                "negative_strong_false_attributions_before_identifier_validation": summary["negative_analyst_strong_false_attribution"],
                "negative_parsed_analyst_answers": summary["negative_analyst_answers"],
                "wrong_corrections_before_identifier_validation": summary["analyst_wrong_correction"],
            })
    return {
        "historical_source_commit": SOURCE_REF,
        "archive_sha256": hashes,
        "reports_reproduced_byte_for_byte": ["pilot", "full"],
        "calls_terminal": len(outcomes),
        "calls_valid": sum(event["result"] == "ok" for event in outcomes),
        "call_results": dict(sorted(Counter(event["result"] for event in outcomes).items())),
        "failure_codes": dict(sorted(Counter(event["failure"] for event in outcomes if event["failure"]).items())),
        "validation_diagnostics": dict(sorted(Counter(code for event in outcomes for code in event["validation"]).items())),
        "configured_uncached_cost_usd": str(sum(Decimal(str(event["cost_usd"])) for event in outcomes)),
        "summed_serial_request_latency_seconds": str(sum(Decimal(str(event["latency_seconds"])) for event in outcomes)),
        "input_tokens": sum(event["usage"]["input_tokens"] for event in outcomes),
        "cached_input_tokens": sum(event["usage"].get("input_tokens_details", {}).get("cached_tokens", 0) for event in outcomes),
        "output_tokens": sum(event["usage"]["output_tokens"] for event in outcomes),
        "returned_model_ids": sorted({event["returned_model"] for event in outcomes}),
        "first_event_utc": min(event["utc"] for event in events),
        "last_event_utc": max(event["utc"] for event in events),
        "pilot_calls_terminal": reports["pilot"]["calls_terminal"],
        "pilot_calls_valid": reports["pilot"]["calls_valid"],
        "table_rows": rows,
        "paired_family_contrasts": report["paired"],
    }


def table(summary: dict) -> bytes:
    lines = [
        "% Generated by verify_stage_a.py from reproduced retained reports.",
        r"\begin{table}[!htbp]", r"\centering", r"\small",
        r"\setlength{\tabcolsep}{3pt}",
        r"\caption{Stage A on 48 synthetic cases per model and route. Valid calls pass response checks; independent admission requires two valid calls. Warranted is the full raw reference score. Recall counts supported answers on twelve positives; decisive counts non-\texttt{UNDECIDED} dispositions. Failures remain in every assigned denominator.}",
        r"\label{tab:bias-stage-a}", r"\vspace{4pt}",
        r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
        r"Model & Route & Valid calls & Admitted & Warranted & Recall & Decisive\\",
        r"\midrule",
    ]
    for row in summary["table_rows"]:
        def fraction(a, b):
            return f"{row[a]}/{row[b]}"
        values = [row["model"].title(), row["route"].title(),
                  fraction("valid_calls", "assigned_calls"),
                  fraction("admitted_dispositions", "assigned_dispositions"),
                  fraction("fully_warranted", "assigned_dispositions"),
                  fraction("supported_recall_count", "supported_recall_denominator"),
                  fraction("decisive_count", "assigned_dispositions")]
        lines.append(" & ".join(values) + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return ("\n".join(lines) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path,
                        help="Historical material checkout; every pinned hash is verified")
    parser.add_argument("--check", action="store_true",
                        help="Compare generated summary/table with committed files")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="eal-stage-a-paper-") as directory:
        temporary = Path(directory)
        source_root = args.source_root.resolve() if args.source_root else temporary / "source"
        if args.source_root is None:
            freeze = json.loads(gzip.decompress((ARCHIVE / "full-freeze-0.1.2.json.gz").read_bytes()))
            restore_sources(source_root, freeze["materials"])
        summary = verify(source_root, temporary)
        for name, data in {"stage-a-summary.json": encoded(summary),
                           "stage-a-table.tex": table(summary)}.items():
            target = HERE / name
            if args.check:
                if not target.exists() or target.read_bytes() != data:
                    raise ValueError(f"Generated paper material differs: {name}")
            else:
                target.write_bytes(data)
    print("Verified archive hashes, frozen sources, ledger chains and byte-identical reports; paper table and summary agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
