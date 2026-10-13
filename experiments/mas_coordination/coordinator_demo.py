"""Prepare fresh, explicitly synthetic inputs for the reusable coordinator.

This creates registered EAL/3 sources and task specifications, without assessing
claims or invoking workers. Synthetic records receive their actual creation
time; no historical assessment clock or production measurement is supplied.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from eal.api_load_methods import registry as api_load_registry
from eal.knowledge import EALKnowledgeBase


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "api-load-test"
API_CLAIMS = ("performance_criteria_met", "performance_criteria_failed")
GENERIC_CLAIMS = ("sample_endpoint_available", "sample_quorum_present")
GENERIC_CONTEXT = {
    "dataset": "synthetic", "deployment": "coordinator-demo", "service": "catalogue-api",
}


AVAILABILITY_COLLECTOR = '''"""Read one pinned synthetic snapshot; observe no deployed service."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from eal.tool_acquisition import strict_json

MAX_BYTES = 16384

def collect(request, raw):
    if not isinstance(request, dict) or set(request) != {
        "evidence_id", "environment", "tool", "tool_version", "input", "context"
    }:
        raise ValueError("Unexpected collection request fields")
    if (request["tool"], request["tool_version"]) != ("synthetic_availability", "1"):
        raise ValueError("Expected synthetic_availability/1")
    if len(raw) > MAX_BYTES:
        raise ValueError("Synthetic snapshot is too large")
    fixture = strict_json(raw.decode("utf-8"))
    if not isinstance(fixture, dict) or set(fixture) != {"schema", "observed_at", "context", "value"}:
        raise ValueError("Unexpected synthetic snapshot fields")
    if fixture["schema"] != "EAL/synthetic-availability-snapshot/1":
        raise ValueError("Unexpected synthetic snapshot schema")
    if request["input"] != {"snapshot": fixture["schema"], "snapshot_sha256": hashlib.sha256(raw).hexdigest()}:
        raise ValueError("Synthetic snapshot identity differs")
    if request["context"] != fixture["context"] or request["context"].get("dataset") != "synthetic":
        raise ValueError("Synthetic snapshot context differs")
    if request["environment"] != "demo":
        raise ValueError("Synthetic snapshot environment differs")
    value = fixture["value"]
    if not isinstance(value, dict) or set(value) != {"heartbeats", "responsive_nodes", "outage_count"}:
        raise ValueError("Unexpected synthetic snapshot values")
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise ValueError("Snapshot counters must be nonnegative integers")
    return {"value": value, "observed_at": fixture["observed_at"], "context": request["context"],
            "request": {key: request[key] for key in ("tool", "tool_version", "input", "context")},
            "details": {"dataset": "synthetic", "snapshot_sha256": request["input"]["snapshot_sha256"]}}

if __name__ == "__main__":
    try:
        request = strict_json(sys.stdin.buffer.read(MAX_BYTES + 1).decode("utf-8"))
        raw = Path(__file__).with_name("availability.json").read_bytes()
        print(json.dumps(collect(request, raw), allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"Synthetic snapshot collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
'''


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _binding(name: str, collector: Path, *argv: str) -> str:
    return (
        f"[tools.{name}]\nkind = \"command\"\nversion = \"1\"\n"
        f"argv = {json.dumps([sys.executable, str(collector), *argv])}\n"
        f"env = {{PYTHONPATH = {json.dumps(str(ROOT / 'src'))}}}\n"
        "timeout_seconds = 10\nmax_output_bytes = 16384\n"
        f"pinned_files = [{{path = {json.dumps(collector.name)}, "
        f"sha256 = {json.dumps(hashlib.sha256(collector.read_bytes()).hexdigest())}}}]\n"
    )


def _availability_source(snapshot_digest: str) -> str:
    inputs = json.dumps({"snapshot": "EAL/synthetic-availability-snapshot/1",
                         "snapshot_sha256": snapshot_digest}, sort_keys=True)
    return '''// Synthetic snapshot with a supported route and an explicit challenge.
language "EAL/3"
environment demo {
  require dataset == "synthetic"
  require deployment == "coordinator-demo"
  require service == "catalogue-api"
}
tool synthetic_availability {
  version "1"
}
context environment demo, tool synthetic_availability, kind snapshot, max_age 86400 {
  evidence heartbeats {
    input INPUT
    require heartbeats >= 3
  }
  evidence quorum {
    input INPUT
    require responsive_nodes >= 2
  }
  evidence outage {
    input INPUT
    require outage_count >= 1
  }
  claim sample_endpoint_available {
    statement "The identified synthetic snapshot supports endpoint availability; recorded outages challenge that heartbeat-based route."
  }
  claim sample_quorum_present {
    statement "The identified synthetic snapshot records at least two responsive nodes; no claim about a deployed system is made."
  }
}
reasoning snapshot_relation {
  method "structured/1"
  rationale "The authored acceptance predicates supply these bounded snapshot claims. This is an explicit argument relation, not a universal availability proof."
}
argument heartbeat_route = [evidence heartbeats] via snapshot_relation => sample_endpoint_available
argument quorum_route = [evidence quorum] via snapshot_relation => sample_quorum_present
objection recorded_outage = [evidence outage] -x> argument heartbeat_route
'''.replace("INPUT", inputs)


def prepare_demo(output: str | Path) -> dict[str, Any]:
    """Create two registered profiles in an empty workspace, preserving prior runs."""
    workspace = Path(output).resolve()
    if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
        raise FileExistsError("Coordinator demo requires an empty output directory")
    workspace.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    generic_context = dict(GENERIC_CONTEXT)

    original_report = (EXAMPLE / "report.json").read_bytes()
    report = json.loads(original_report)
    report["observed_at"] = created_at
    report["run_id"] = "coordinator-synthetic-load-001"
    report_raw = _json_bytes(report)
    report_path = workspace / "report.json"
    report_path.write_bytes(report_raw)
    api_source = (EXAMPLE / "source.eal").read_text(encoding="utf-8")
    api_source = api_source.replace(hashlib.sha256(original_report).hexdigest(),
                                    hashlib.sha256(report_raw).hexdigest())
    api_source = api_source.replace("demo-load-001", report["run_id"])
    (workspace / "api-load.eal").write_text(api_source, encoding="utf-8")
    api_collector = workspace / "collect_results.py"
    shutil.copyfile(EXAMPLE / "collect_results.py", api_collector)

    snapshot = {
        "schema": "EAL/synthetic-availability-snapshot/1", "observed_at": created_at,
        "context": generic_context,
        "value": {"heartbeats": 3, "responsive_nodes": 2, "outage_count": 1},
    }
    snapshot_raw = _json_bytes(snapshot)
    (workspace / "availability.json").write_bytes(snapshot_raw)
    (workspace / "availability.eal").write_text(
        _availability_source(hashlib.sha256(snapshot_raw).hexdigest()), encoding="utf-8")
    availability_collector = workspace / "collect_availability.py"
    availability_collector.write_text(AVAILABILITY_COLLECTOR, encoding="utf-8")

    registry = workspace / "tools.toml"
    registry.write_text(
        _binding("load_test_report", api_collector, "--report", str(report_path))
        + "\n" + _binding("synthetic_availability", availability_collector), encoding="utf-8")
    database = workspace / "knowledge.sqlite"
    knowledge = EALKnowledgeBase(workspace, registry, database,
                                 method_registry=api_load_registry())
    api_context = {key: report[key] for key in ("service", "build_id", "dataset")}
    knowledge.register("api-load.eal", entry_id="api_sample", context=api_context,
                       claims=list(API_CLAIMS), label="current-time synthetic API sample")
    knowledge.register("availability.eal", entry_id="availability_sample", context=generic_context,
                       claims=list(GENERIC_CLAIMS), label="current-time synthetic challenged availability snapshot")

    spec = {
        "schema": "EAL/coordinator-demo/1", "created_at": created_at, "dataset": "synthetic",
        "server": {"workspace": str(workspace), "registry": str(registry), "database": str(database),
                   "methods": "eal.api_load_methods:registry", "limits": None},
        "tasks": [
            {"task_id": "synthetic_api_sample", "question": (
                "Which declared criteria are supported or failed by the identified synthetic API sample? "
                "Keep the report's scope and avoid production conclusions."),
             "entry_id": "api_sample", "claims": list(API_CLAIMS), "profile": "api_load/1",
             "requirements": {"context": api_context,
                 "workload": {key: report[key] for key in (
                     "service", "build_id", "dataset", "run_id", "concurrent_clients")},
                 "criteria": {"minimum_requests": 100, "maximum_sample_p95_ms": 200,
                              "maximum_error_rate_percent": 1, "evidence_max_age_seconds": 86400},
                 "claim_outputs": {API_CLAIMS[0]: "passes", API_CLAIMS[1]: "fails"}}},
            {"task_id": "synthetic_availability_sample", "question": (
                "Assess both registered synthetic-snapshot claims, accounting for the explicit outage objection. "
                "Keep the registered scope and avoid conclusions about a deployed service."),
             "entry_id": "availability_sample", "claims": list(GENERIC_CLAIMS),
             "profile": "registered_claims/1", "requirements": {"context": generic_context}},
        ],
    }
    (workspace / "demo.json").write_bytes(_json_bytes(spec))
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare_demo(args.output), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
