#!/usr/bin/env python3
"""Replay the frozen architecture experiment without changing retained results.

Run from any directory with ``python experiments/architecture_extension_v2/replay.py``.
This verifies the recorded local pair. It does not launch coding agents, infer
that an agent read its context, or reproduce the stochastic coding sessions.
"""

from __future__ import annotations

import argparse
import difflib
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
RESULTS = HERE / "results"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "metrics"))
from freeze import make_record  # noqa: E402
from prepare_trial import GUIDANCE, manifest  # noqa: E402
from cognitive_complexity import collect as collect_complexity, compare as compare_complexity  # noqa: E402


CASES = {
    "baseline": (HERE / "materials" / "base", "baseline"),
    "a": (RESULTS / "snapshots" / "a", "a"),
    "b_control": (RESULTS / "snapshots" / "b_control", "b"),
    "b_treatment": (RESULTS / "snapshots" / "b_treatment", "b"),
}
EXCHANGES = {
    "a": ("pre-a-mcp-success", "pre-a-packet"),
    "b_control": ("pre-b-control-mcp", "pre-b-control-packet"),
    "b_treatment": ("pre-b-treatment-mcp", "pre-b-treatment-packet"),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_freeze() -> dict[str, Any]:
    frozen = read(HERE / "materials" / "freeze.json")
    require(frozen.get("schema_version") == "architecture-extension-freeze/1", "freeze schema changed")
    files, tree = make_record(frozen["entries"])
    require(len(files) == 23 and len(frozen["files"]) == 23, "pre-run freeze must enumerate 23 files")
    require(files == frozen["files"] and tree == frozen["tree_sha256"],
            "frozen pre-run files or tree digest changed")
    base = read(HERE / "materials" / "freeze-base.json")
    from baseline_collector import baseline_digest  # Frozen pre-run implementation.
    require(base["source_sha256"] == baseline_digest(), "baseline source differs from baseline freeze")
    return {"files": len(files), "tree_sha256": tree}


def check_source_chain() -> dict[str, Any]:
    source = {name: manifest(path) for name, (path, _) in CASES.items()}
    for name in ("a", "b_control", "b_treatment"):
        require(source[name] == read(RESULTS / "snapshots" / f"{name}-manifest.json"),
                f"{name} source manifest differs from retained snapshot")
        preparation = read(RESULTS / "preparations" / f"{name}.json")
        expected = source["baseline"] if name == "a" else source["a"]
        require(preparation.get("schema") == "architecture-extension-trial-preparation/1",
                f"{name} preparation schema differs")
        require(preparation["source"] == expected, f"{name} did not start from the recorded common source")
        require(preparation["guidance_sha256"] == digest(GUIDANCE.encode("utf-8")),
                f"{name} common guidance differs")
    require(source["a"] != source["baseline"], "A snapshot has no source change")
    require(read(RESULTS / "preparations" / "b_control.json")["source"] ==
            read(RESULTS / "preparations" / "b_treatment.json")["source"],
            "B starting source manifests differ")
    for name, before in (("a", "baseline"), ("b_control", "a"), ("b_treatment", "a")):
        require(patch(CASES[before][0], CASES[name][0]) ==
                (RESULTS / "patches" / f"{name}.patch").read_text(encoding="utf-8"),
                f"{name} retained patch differs from source transition")
    return {name: item["tree_sha256"] for name, item in source.items()}


def patch(before: Path, after: Path) -> str:
    """Reconstruct the retained unified source patch, including new files."""
    names = sorted(set(manifest(before)["files"]) | set(manifest(after)["files"]))
    chunks: list[str] = []
    for name in names:
        old = (before / name).read_text(encoding="utf-8").splitlines(keepends=True) if (before / name).exists() else []
        new = (after / name).read_text(encoding="utf-8").splitlines(keepends=True) if (after / name).exists() else []
        chunks.extend(difflib.unified_diff(
            old, new, fromfile=f"a/{name}", tofile=f"b/{name}",
        ))
    return "".join(chunks)


def check_wire() -> dict[str, Any]:
    source = (HERE / "argument.eal").read_bytes()
    registry = (HERE / "eal-tools.toml").read_bytes()
    exposure: dict[str, Any] = {}
    for arm, (stem, packet_stem) in EXCHANGES.items():
        summary = read(RESULTS / f"{stem}-summary.json")
        packet_path = RESULTS / f"{packet_stem}.json"
        packet = read(packet_path)
        compressed = RESULTS / "wire" / f"{stem}.json.gz"
        require(summary["compressed_path"] == f"wire/{stem}.json.gz", f"{arm} wire path differs")
        raw_compressed = compressed.read_bytes()
        require(digest(raw_compressed) == summary["compressed_sha256"], f"{arm} compressed wire digest differs")
        raw = gzip.decompress(raw_compressed)  # CRC and length are checked by gzip.
        require(digest(raw) == summary["full_json_sha256"], f"{arm} recovered MCP wire digest differs")
        wire = json.loads(raw)
        require(isinstance(wire, dict), f"{arm} wire is not an object")
        require(wire["schema"] == summary["schema"] == "architecture-extension-mcp-wire/1",
                f"{arm} wire schema differs")
        require(wire["status"] == summary["status"] == "ok" and
                wire["server_exit_code"] == summary["server_exit_code"] == 0,
                f"{arm} MCP exchange did not complete successfully")
        require(wire["source_sha256"] == packet["source_sha256"] ==
                summary["source_sha256"] == digest(source), f"{arm} MCP argument digest differs")
        require(wire["registry_sha256"] == summary["registry_sha256"] == digest(registry),
                f"{arm} MCP tool registry digest differs")
        require(packet["source"].encode("utf-8") == source, f"{arm} packet argument differs")
        require(wire["context"] == packet["context"] == summary["context"] and
                wire["goal"] == packet["goal"] == summary["goal"],
                f"{arm} MCP scope or goal differs")
        require(wire["assessed_at"] == packet["assessed_at"] == summary["assessed_at"],
                f"{arm} assessment time differs")
        require(wire["packet_sha256"] == summary["packet_sha256"] == digest(packet_path.read_bytes()),
                f"{arm} packet digest differs")
        require(wire["collection"]["collection_id"] == packet["collection_id"] and
                wire["assessment"]["assessment_id"] == packet["assessment_id"] and
                wire["explanation"] == packet["explanation"],
                f"{arm} packet does not match MCP results")
        require(wire["validation"]["valid"] == summary["validation_valid"] is True and
                len(wire["collection"]["records"]) == summary["collection_record_count"],
                f"{arm} MCP validation or evidence count differs")
        formal = wire["formal_result"]
        require(packet["formal_status"] == formal["formal"]["grounded_status"] ==
                summary["aspic_grounded_status"] and
                packet["formal_snapshot_digest"] == formal["snapshot_digest"] and
                packet["goal_status"] == summary["authored_goal_status"] ==
                wire["assessment"]["claims"][wire["goal"]]["status"] and
                formal["claim_status"] == summary["formal_goal_status"],
                f"{arm} formal or authored assessment differs")
        require(len(wire["messages"]) == summary["wire_message_count"],
                f"{arm} MCP message count differs")
        requested: list[str] = []
        for index, item in enumerate(wire["messages"]):
            line = item["utf8_line"].encode("utf-8")
            require(item["direction"] in {"client_to_server", "server_to_client"} and
                    line.endswith(b"\n") and item["sha256"] == digest(line),
                    f"{arm} MCP message {index} differs")
            message = json.loads(line)
            require(message.get("jsonrpc") == "2.0", f"{arm} MCP message {index} is not JSON-RPC 2.0")
            if item["direction"] == "client_to_server" and message.get("method") == "tools/call":
                requested.append(message["params"]["name"])
        require(requested == ["eal_validate", "eal_collect", "eal_reason", "eal_explain",
                              "eal_compile_aspic"], f"{arm} MCP tool call sequence differs")
        prepared = read(RESULTS / "preparations" / f"{arm}.json")
        expected_packet = None if arm == "b_control" else digest(packet_path.read_bytes())
        require(prepared["packet_sha256"] == expected_packet,
                f"{arm} packet exposure differs from assignment")
        exposure[arm] = {"host_mcp_messages": len(wire["messages"]),
                         "packet_delivered": expected_packet is not None,
                         "packet_sha256": expected_packet}
    require(read(RESULTS / "pre-b-control-mcp-summary.json")["source_sha256"] ==
            read(RESULTS / "pre-b-treatment-mcp-summary.json")["source_sha256"],
            "B host MCP acquisitions used different EAL sources")
    return exposure


def rerun_assessor() -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    assessor = HERE / "materials" / "assessor" / "assess.py"
    with tempfile.TemporaryDirectory(prefix="architecture-extension-replay-") as directory:
        for name, (source, stage) in CASES.items():
            output = Path(directory) / f"{name}.json"
            arm = "a_eal" if name == "a" else name
            command = [sys.executable, str(assessor), "--candidate", str(source),
                       "--stage", stage, "--arm", arm, "--output", str(output)]
            result = subprocess.run(command, cwd=REPOSITORY, capture_output=True, text=True,
                                    timeout=240, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            require(result.returncode == 0 and output.exists(),
                    f"{name} fixed assessor failed: {result.stderr[-1500:]}")
            actual = read(output)
            prior = read(RESULTS / "assessments" / f"{name}.json")
            for key in ("schema_version", "arm", "stage", "source_digest", "source_files",
                        "findings", "case_effect_calls", "architecture"):
                require(actual[key] == prior[key], f"{name} assessor {key} differs")
            for key in ("status", "exit_code", "tests_run"):
                require(actual["candidate_suite"][key] == prior["candidate_suite"][key],
                        f"{name} candidate suite {key} differs")
            for key in ("status", "exit_code"):
                require(actual["probe_execution"][key] == prior["probe_execution"][key],
                        f"{name} fixed probe {key} differs")
            outputs[name] = {
                "source_digest": actual["source_digest"],
                "findings": {key: value["status"] for key, value in actual["findings"].items()},
                "candidate_suite_status": actual["candidate_suite"]["status"],
                "candidate_suite_tests": actual["candidate_suite"]["tests_run"],
            }
    return outputs


def check_complexity() -> dict[str, Any]:
    reports = {name: collect_complexity(source / "fulfilment")
               for name, (source, _) in CASES.items()}
    reports["a"]["comparison"] = compare_complexity(reports["baseline"], reports["a"])
    for arm in ("b_control", "b_treatment"):
        reports[arm]["comparison"] = compare_complexity(reports["a"], reports[arm])
    for name, actual in reports.items():
        require(actual == read(RESULTS / "metrics" / f"{name}.json"),
                f"{name} cognitive complexity report differs from recomputation")
    return {name: {"total": report["total"], "function_count": report["function_count"]}
            for name, report in reports.items()}


def check_visualisation() -> str:
    exported = read(RESULTS / "aspic-view.json")
    require(exported.get("schema") == "aspic-view/1", "ASPIC+ export schema version differs")
    try:
        from jsonschema import Draft202012Validator, exceptions as schema_errors
    except ModuleNotFoundError:
        return "skipped: jsonschema is not installed"
    # The captured export predates the typed /2 availability issues. Preserve
    # its original contract instead of reinterpreting free-form diagnostics.
    schema = read(REPOSITORY / "docs" / "aspic-view-v1.schema.json")
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(exported)
    except (schema_errors.SchemaError, schema_errors.ValidationError) as exc:
        raise ValueError(f"ASPIC+ export fails schema validation: {exc.message}") from exc
    return "valid against docs/aspic-view-v1.schema.json"


def replay() -> dict[str, Any]:
    checks: tuple[tuple[str, Callable[[], Any]], ...] = (
        ("freeze", check_freeze), ("source_chain", check_source_chain),
        ("mcp_exposure", check_wire), ("assessor", rerun_assessor),
        ("complexity", check_complexity), ("visualisation_schema", check_visualisation),
    )
    report: dict[str, Any] = {"schema": "architecture-extension-replay/1", "checks": {}, "errors": []}
    for name, check in checks:
        try:
            report["checks"][name] = check()
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, subprocess.TimeoutExpired) as exc:
            report["errors"].append(f"{name}: {type(exc).__name__}: {exc}")
    report["ok"] = not report["errors"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the structured replay report")
    args = parser.parse_args()
    report = replay()
    if args.json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        for name, result in report["checks"].items():
            print(f"{name}: {result if isinstance(result, str) else 'verified'}")
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Retained local experiment replay " + ("passed" if report["ok"] else "failed"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
