"""Host-only adapter for the corrected, pinned refund assessor.

The coding clone contains only ``source/`` and its current feature brief.
Keep this adapter and the imported v3/v2 probes outside the agent mount.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path


STUDY = Path(__file__).resolve().parents[3] / "study"
sys.path.insert(0, str(STUDY))
from assess import assess as corrected_assess  # noqa: E402


def assess(source: Path, stage: str) -> dict:
    if stage not in {"B", "C", "D"}:
        raise ValueError("unknown stage")
    if not source.is_dir() or source.is_symlink() or not (source / "fulfilment").is_dir():
        raise ValueError("candidate source/fulfilment package missing")
    raw = corrected_assess(source, "R", stage)
    checks = [{"id": name, **finding} for name, finding in raw["findings"].items()]
    return {
        "system": "fulfilment", "stage": stage,
        "source_sha256": raw["source_sha256"],
        "assessor_schema": raw["schema_version"],
        "valid": raw["invalid"] == 0,
        "invalid_kind": "candidate_source" if raw["invalid"] else None,
        "passed": raw["passed"], "failed": raw["failed"],
        "invalid": raw["invalid"], "total": len(checks), "checks": checks,
        "findings": raw["findings"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage", choices=("B", "C", "D"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = assess(args.source, args.stage)
    except ValueError as exc:
        result = {"system": "fulfilment", "stage": args.stage,
                  "source_sha256": None, "valid": False,
                  "invalid_kind": "candidate_source", "passed": 0, "failed": 0,
                  "invalid": 1, "total": 1,
                  "findings": {"candidate.source": {"status": "invalid", "detail": str(exc)}},
                  "checks": [{"id": "candidate.source", "status": "invalid", "detail": str(exc)}]}
    except Exception as exc:
        result = {"system": "fulfilment", "stage": args.stage,
                  "source_sha256": None, "valid": False,
                  "invalid_kind": "assessor_error", "passed": 0, "failed": 0,
                  "invalid": 1, "total": 1,
                  "findings": {"host.assessor-error": {"status": "invalid", "detail": f"{type(exc).__name__}: {exc}"}},
                  "checks": [{"id": "host.assessor-error", "status": "invalid", "detail": f"{type(exc).__name__}: {exc}"}],
                  "error": f"{type(exc).__name__}: {exc}",
                  "traceback": traceback.format_exc()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 2 if result.get("invalid_kind") == "assessor_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
