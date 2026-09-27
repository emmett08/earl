"""Read one immutable architecture-extension result at its original observation time.

The host executes this pinned command. Its output is an observation of the
checked-in experiment report, not an authentication of the coding sessions or
a proof of the report's English claims.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
REPORT = HERE / "results" / "observations.json"
TREATMENT = HERE / "architecture.eal"
CONTEXT = {"experiment": "architecture-extension-v1", "dataset": "local-fixture"}
CASES = frozenset({"a_no_eal", "b_eal", "b_no_eal"})
CHECKS = frozenset({
    "baseline_contract", "feature_behaviour", "payload_cap", "registry_extension",
    "single_dispatch_path", "single_format_path", "reachable_code", "all_tests",
})
DESIGN_FLAGS = frozenset({
    "randomised_assignment", "longitudinal_followup", "same_feature_control",
    "same_start_snapshot", "comparison_blinded_review",
})
ACQUISITION = ("tool", "tool_version", "input", "context")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON member {key!r}")
        obj[key] = value
    return obj


def _positive_time(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("provenance.observed_at must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid provenance.observed_at timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("provenance.observed_at needs a timezone")
    return value


def _snapshot_sha256(folder: Path) -> str:
    """Recompute the fixed assessor's recorded source-tree identity."""
    if not folder.is_dir():
        raise ValueError("Saved source snapshot is absent")
    digest = hashlib.sha256()
    for file in sorted(folder.rglob("*")):
        if file.is_symlink():
            raise ValueError("Saved source snapshot contains a symbolic link")
        if file.is_file() and "__pycache__" not in file.parts and file.suffix in (".py", ".md"):
            digest.update(str(file.relative_to(folder)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(file.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def collect(request: object, *, report_path: Path = REPORT) -> dict:
    if (type(request) is not dict or set(request) != {"evidence_id", "environment", *ACQUISITION}
            or not isinstance(request["evidence_id"], str)
            or request["environment"] != "notification_study"
            or request["tool"] != "architecture_report"
            or request["tool_version"] != "1"
            or request["context"] != CONTEXT):
        raise ValueError("Unexpected architecture-report request or environment")
    query = request["input"]
    if type(query) is not dict:
        raise ValueError("Input must identify a check or design flag")
    if set(query) == {"case_id", "check_id"}:
        case_id, check_id = query["case_id"], query["check_id"]
        if case_id not in CASES or check_id not in CHECKS:
            raise ValueError("Unknown case or check identifier")
        kind = "check"
    elif set(query) == {"design_flag"}:
        flag = query["design_flag"]
        if flag not in DESIGN_FLAGS:
            raise ValueError("Unknown design flag")
        kind = "design"
    else:
        raise ValueError("Input must identify one exact check or design flag")

    raw = report_path.read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Observation report exceeds 4 MiB")
    document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ValueError(f"Nonfinite JSON number {value}")))
    if type(document) is not dict or document.get("schema") != "architecture-extension-observations/1":
        raise ValueError("Unexpected architecture observation schema")
    provenance = document.get("provenance")
    if type(provenance) is not dict or provenance.get("assessor_version") != "architecture-assessor/1":
        raise ValueError("Missing or unknown assessor identity")
    observed_at = _positive_time(provenance.get("observed_at"))
    source_digest = hashlib.sha256(TREATMENT.read_bytes()).hexdigest()
    if provenance.get("eal_sha256") != source_digest:
        raise ValueError("Experiment's treatment EAL hash differs from frozen source")
    for field in ("baseline_sha256", "a_sha256", "b_eal_sha256", "b_no_eal_sha256"):
        if not isinstance(provenance.get(field), str) or HEX64.fullmatch(provenance[field]) is None:
            raise ValueError(f"Missing or invalid provenance.{field}")
    for field, path in (
        ("baseline_sha256", HERE / "materials/base"),
        ("a_sha256", HERE / "results/snapshots/a_no_eal"),
        ("b_eal_sha256", HERE / "results/snapshots/b_eal"),
        ("b_no_eal_sha256", HERE / "results/snapshots/b_no_eal"),
    ):
        if _snapshot_sha256(path) != provenance[field]:
            raise ValueError(f"Saved source snapshot differs from provenance.{field}")
    for field, path in (
        ("assessor_sha256", HERE / "materials/assessor/assess.py"),
        ("probe_sha256", HERE / "materials/assessor/probe.py"),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != provenance.get(field):
            raise ValueError(f"Saved assessor differs from provenance.{field}")
    cases = document.get("cases")
    if (type(cases) is not dict or any(type(cases.get(name)) is not dict for name in CASES)
            or cases["a_no_eal"].get("start_sha256") != provenance["baseline_sha256"]
            or cases["b_eal"].get("start_sha256") != provenance["a_sha256"]
            or cases["b_no_eal"].get("start_sha256") != provenance["a_sha256"]):
        raise ValueError("Case start snapshots differ from experiment provenance")

    report_digest = hashlib.sha256(raw).hexdigest()
    if kind == "check":
        expected_digest = provenance[{"a_no_eal": "a_sha256", "b_eal": "b_eal_sha256",
                                      "b_no_eal": "b_no_eal_sha256"}[case_id]]
        if cases[case_id].get("source_sha256") != expected_digest:
            raise ValueError("Case source digest differs from experiment provenance")
        checks = cases[case_id].get("checks")
        if type(checks) is not dict or check_id not in checks:
            raise ValueError("Unmeasured or inapplicable check")
        finding = checks[check_id]
        if (type(finding) is not dict or type(finding.get("passed")) is not bool
                or not isinstance(finding.get("detail"), str)
                or not isinstance(finding.get("source"), str)
                or finding.get("command") is not None and not isinstance(finding["command"], str)):
            raise ValueError("Malformed check finding")
        value = {**finding, "case_id": case_id, "check_id": check_id,
                 "report_sha256": report_digest}
    else:
        design = document.get("design")
        if type(design) is not dict or flag not in design:
            raise ValueError("Missing design flag")
        item = design[flag]
        if (type(item) is not dict or type(item.get("passed")) is not bool
                or not isinstance(item.get("detail"), str)):
            raise ValueError("Malformed design flag")
        value = {"passed": item["passed"], "detail": item["detail"],
                 "design_flag": flag, "report_sha256": report_digest}

    return {"value": value, "observed_at": observed_at, "context": CONTEXT,
            "request": {key: request[key] for key in ACQUISITION},
            "details": {"schema": document["schema"], "assessor_version": provenance["assessor_version"],
                        "report_sha256": report_digest, "treatment_eal_sha256": source_digest}}


if __name__ == "__main__":
    try:
        print(json.dumps(collect(json.load(sys.stdin)), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(f"Architecture report collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
