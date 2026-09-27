#!/usr/bin/env python3
"""Bounded, exact-arithmetic evaluator of a conditional technical-debt scenario.

The model is equation (2) of the supplied technical-debt paper. This command
checks a *supplied scenario*. It does not infer work propagation or future
demand from source code and cannot validate the reference's service equivalence.

With no arguments, read the EAL command-tool request on stdin and return its
observation envelope. ``--scenario`` emits a bare result for local inspection.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = Path(__file__).resolve().parent / "scenarios"
SCENARIO_SCHEMA = "technical-debt-scenario/1"
RESULT_SCHEMA = "technical-debt-result/1"
TOOL = "technical_debt"
VERSION = "1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE_BYTES = 65_536
MAX_CATEGORIES = 8
MAX_PERIODS = 120
MAX_NUMBER = 10**9
MAX_OUTPUT = 10**15
REQUIRED_TOP = ("basis", "boundary", "demand_categories", "lambda", "actual",
                "reference", "remediation")
BOUNDARY_KEYS = ("system", "required_service", "reference", "period", "currency")
IMPLEMENTATION_KEYS = ("work_categories", "M", "B", "c", "ell")
REMEDIATION_KEYS = ("P", "H", "delta")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _object(value: Any, label: str, allowed: set[str]) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be a JSON object")
    extras = sorted(set(value) - allowed)
    if extras:
        raise ValueError(f"Unexpected {label} keys: {extras}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 240 or "\x00" in value:
        raise ValueError(f"{label} must be a non-empty bounded string")
    return value


def _names(value: Any, label: str) -> list[str]:
    if (type(value) is not list or not 1 <= len(value) <= MAX_CATEGORIES
            or any(not isinstance(item, str) or not item or len(item) > 80 for item in value)
            or len(set(value)) != len(value)):
        raise ValueError(f"{label} needs 1–{MAX_CATEGORIES} distinct names")
    return value


def _number(value: Any, label: str, *, positive: bool = False) -> Fraction:
    if type(value) not in (int, float, Decimal):
        raise ValueError(f"{label} must be a JSON number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    decimal = Decimal(str(value))
    if not decimal.is_finite() or decimal.adjusted() > 9 or decimal.as_tuple().exponent < -18:
        raise ValueError(f"{label} exceeds the numeric precision/range bound")
    if decimal < 0 or decimal > MAX_NUMBER or (positive and decimal <= 0):
        raise ValueError(f"{label} is outside its non-negative range")
    return Fraction(decimal)


def _vector(value: Any, size: int, label: str) -> list[Fraction]:
    if type(value) is not list or len(value) != size:
        raise ValueError(f"{label} must contain {size} entries")
    return [_number(item, f"{label}[{i}]") for i, item in enumerate(value)]


def _matrix(value: Any, rows: int, columns: int, label: str) -> list[list[Fraction]]:
    if type(value) is not list or len(value) != rows:
        raise ValueError(f"{label} must contain {rows} rows")
    return [_vector(row, columns, f"{label}[{i}]") for i, row in enumerate(value)]


def _missing(scenario: dict[str, Any]) -> list[str]:
    missing = [name for name in REQUIRED_TOP if name not in scenario or scenario[name] is None]
    for parent, fields in (("boundary", BOUNDARY_KEYS), ("actual", IMPLEMENTATION_KEYS),
                           ("reference", IMPLEMENTATION_KEYS), ("remediation", REMEDIATION_KEYS)):
        obj = scenario.get(parent)
        if parent in missing:
            missing.extend(f"{parent}.{field}" for field in fields)
        elif type(obj) is dict:
            missing.extend(f"{parent}.{field}" for field in fields
                           if field not in obj or obj[field] is None)
    if scenario.get("basis") == "empirical" and not scenario.get("candidate_sha256"):
        missing.append("candidate_sha256")
    return sorted(set(missing))


def _solve(matrix: list[list[Fraction]], right: list[Fraction]) -> list[Fraction]:
    """Exact Gaussian elimination, with non-zero partial pivoting."""
    n = len(right)
    a = [row[:] + [right[i]] for i, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(a[row][column]))
        if not a[pivot][column]:
            raise ValueError("I-B is singular: no global stability certificate")
        a[column], a[pivot] = a[pivot], a[column]
        factor = a[column][column]
        for row in range(column + 1, n):
            ratio = a[row][column] / factor
            for index in range(column, n + 1):
                a[row][index] -= ratio * a[column][index]
    result = [Fraction(0) for _ in range(n)]
    for row in range(n - 1, -1, -1):
        result[row] = (a[row][n] - sum(a[row][j] * result[j]
                                      for j in range(row + 1, n))) / a[row][row]
    return result


def _fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _approx(value: Fraction, label: str) -> float:
    if abs(value) > MAX_OUTPUT:
        raise ValueError(f"{label} exceeds bounded output magnitude")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} is not a finite output")
    return result


def _implementation(value: Any, name: str, demand_count: int) -> dict[str, Any]:
    data = _object(value, name, set(IMPLEMENTATION_KEYS))
    categories = _names(data["work_categories"], f"{name}.work_categories")
    n = len(categories)
    return {"categories": categories,
            "M": _matrix(data["M"], n, demand_count, f"{name}.M"),
            "B": _matrix(data["B"], n, n, f"{name}.B"),
            "c": _vector(data["c"], n, f"{name}.c"),
            "ell": _number(data["ell"], f"{name}.ell")}


def _cost(implementation: dict[str, Any], demand: list[Fraction], name: str
          ) -> tuple[Fraction, dict[str, Any]]:
    b, m, c = (implementation[key] for key in ("B", "M", "c"))
    n = len(c)
    operator = [[(Fraction(i == j) - b[i][j]) for j in range(n)] for i in range(n)]
    # For B >= 0, a strictly positive w with (I-B)w = 1 gives a constructive
    # global stability proof: ||B||_w=max_i(Bw)_i/w_i<1, hence rho(B)<1.
    witness = _solve(operator, [Fraction(1)] * n)
    if any(item <= 0 for item in witness):
        raise ValueError(f"{name}.B is not certified globally subcritical")
    beta = max(sum(b[i][j] * witness[j] for j in range(n)) / witness[i]
               for i in range(n))
    if beta < 0 or beta >= 1:
        raise ValueError(f"{name}.B is not certified globally subcritical")
    initial = [sum(m[i][j] * demand[j] for j in range(len(demand))) for i in range(n)]
    work = _solve(operator, initial)
    if any(item < 0 for item in work):
        raise ValueError(f"{name} computed negative work")
    residual = max((abs(initial[i] - sum(operator[i][j] * work[j]
                                         for j in range(n))) for i in range(n)), default=Fraction(0))
    cost = sum(c[i] * work[i] for i in range(n)) + implementation["ell"]
    return cost, {"weighted_norm_beta": _approx(beta, f"{name}.beta"),
                  "weighted_norm_beta_exact": _fraction(beta),
                  "positive_witness_exact": [_fraction(item) for item in witness],
                  "linear_solve_residual_max_abs": _approx(residual, f"{name}.residual")}


def evaluate(scenario: Any, input_sha256: str, context: dict[str, Any] | None = None
             ) -> dict[str, Any]:
    data = _object(scenario, "scenario", set(REQUIRED_TOP) | {"schema", "candidate_sha256"})
    if data.get("schema") != SCENARIO_SCHEMA:
        raise ValueError(f"scenario.schema must equal {SCENARIO_SCHEMA}")
    if "basis" in data and data["basis"] not in {"synthetic", "hypothetical", "empirical"}:
        raise ValueError("basis must be synthetic, hypothetical, or empirical")
    if "candidate_sha256" in data and data["candidate_sha256"] is not None:
        if not isinstance(data["candidate_sha256"], str) or not SHA256.fullmatch(data["candidate_sha256"]):
            raise ValueError("candidate_sha256 must be a lowercase SHA-256 hex digest")
        if context and context.get("candidate_sha256") and data["candidate_sha256"] != context["candidate_sha256"]:
            raise ValueError("Scenario candidate SHA-256 differs from assessed candidate")
    for parent, fields in (("boundary", BOUNDARY_KEYS), ("actual", IMPLEMENTATION_KEYS),
                           ("reference", IMPLEMENTATION_KEYS), ("remediation", REMEDIATION_KEYS)):
        obj = data.get(parent)
        if obj is not None:
            _object(obj, parent, set(fields))
    missing = _missing(data)
    if data.get("basis") == "empirical" and not (context and context.get("candidate_sha256")):
        missing.append("context.candidate_sha256")
    missing = sorted(set(missing))
    common = {"schema": RESULT_SCHEMA, "basis": data.get("basis"),
              "input_sha256": input_sha256, "candidate_sha256": data.get("candidate_sha256")}
    if missing:
        return {**common, "status": "not_estimable", "missing_fields": missing,
                "interpretation": "No technical-debt valuation or empirical debt reduction follows from missing inputs."}
    boundary = data["boundary"]
    for key in BOUNDARY_KEYS:
        _text(boundary[key], f"boundary.{key}")
    demand_names = _names(data["demand_categories"], "demand_categories")
    demand = _vector(data["lambda"], len(demand_names), "lambda")
    actual = _implementation(data["actual"], "actual", len(demand))
    reference = _implementation(data["reference"], "reference", len(demand))
    remedy = data["remediation"]
    principal = _number(remedy["P"], "remediation.P")
    horizon = remedy["H"]
    if type(horizon) is not int or not 0 <= horizon <= MAX_PERIODS:
        raise ValueError(f"remediation.H must be an integer from 0 to {MAX_PERIODS}")
    delta = _number(remedy["delta"], "remediation.delta", positive=True)
    if delta > 1:
        raise ValueError("remediation.delta must be <= 1")
    cost_a, stability_a = _cost(actual, demand, "actual")
    cost_r, stability_r = _cost(reference, demand, "reference")
    j = cost_a - cost_r
    geometric = sum((delta**t for t in range(horizon)), Fraction(0))
    principal_pv = delta**horizon * principal
    interest_pv = geometric * j
    total = principal_pv + interest_pv
    quantities = {"actual_period_cost": cost_a, "reference_period_cost": cost_r,
                  "J": j, "principal_pv": principal_pv, "interest_pv": interest_pv,
                  "D_H": total, "discount_sum": geometric}
    return {**common, "status": "estimated", "missing_fields": [],
            "units": {"cost": boundary["currency"], "period": boundary["period"]},
            **{key: _approx(value, key) for key, value in quantities.items()},
            "exact": {key: _fraction(value) for key, value in quantities.items()},
            "stability": {"actual": stability_a, "reference": stability_r,
                          "certificate": "B>=0; (I-B)w=1 has w>0; max_i (Bw)_i/w_i<1"},
            "interpretation": ("Conditional scenario valuation only. The computation does not validate demand, "
                               "work attribution, unit costs, service equivalence, or future prediction.")}


def _read_scenario(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Scenario must be a regular non-symlink file of at most 65536 bytes")
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Scenario exceeds input bound")
    data = json.loads(raw, object_pairs_hook=_unique_object, parse_float=Decimal,
                      parse_constant=_reject_constant)
    return data, hashlib.sha256(raw).hexdigest()


def _scenario_path(relative: Any) -> Path:
    if not isinstance(relative, str) or len(relative) > 300 or not relative:
        raise ValueError("scenario_path must be a bounded repository-relative path")
    parts = Path(relative).parts
    if Path(relative).is_absolute() or ".." in parts or any(part in ("", ".") for part in parts):
        raise ValueError("scenario_path must not escape the repository")
    path = ROOT.joinpath(*parts)
    if not path.resolve().is_relative_to(SCENARIOS.resolve()):
        raise ValueError("scenario_path is outside the v3 technical-debt scenarios")
    return path


def collect(request: Any) -> dict[str, Any]:
    expected_keys = {"evidence_id", "environment", "tool", "tool_version", "input", "context"}
    item = _object(request, "request", expected_keys)
    if set(item) != expected_keys or item["tool"] != TOOL or item["tool_version"] != VERSION:
        raise ValueError("Unexpected technical-debt tool request")
    _text(item["evidence_id"], "evidence_id")
    _text(item["environment"], "environment")
    context = _object(item["context"], "context", {"experiment", "stage", "candidate_sha256"})
    if (context.get("experiment") != "architecture-extension-v3"
            or context.get("stage") not in {"pre-A", "post-A", "post-B"}):
        raise ValueError("Unexpected experiment or stage")
    if "candidate_sha256" in context and (not isinstance(context["candidate_sha256"], str)
                                          or not SHA256.fullmatch(context["candidate_sha256"])):
        raise ValueError("Invalid candidate SHA-256 in context")
    acquisition = _object(item["input"], "input", {"scenario_path", "expected_sha256"})
    if set(acquisition) != {"scenario_path", "expected_sha256"}:
        raise ValueError("input must name and pin one scenario")
    expected = acquisition["expected_sha256"]
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise ValueError("expected_sha256 must be lowercase SHA-256 hex")
    scenario, actual_hash = _read_scenario(_scenario_path(acquisition["scenario_path"]))
    if actual_hash != expected:
        raise ValueError("Scenario content differs from expected SHA-256")
    result = evaluate(scenario, actual_hash, context)
    if result["status"] == "estimated":
        # The exact fractions and positive vectors remain reproducible through
        # --scenario. Keep the agent-facing observation short and content-bound.
        audit = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        result["audit_sha256"] = hashlib.sha256(audit.encode("utf-8")).hexdigest()
        result.pop("exact")
        for arm in ("actual", "reference"):
            result["stability"][arm].pop("positive_witness_exact")
    now = datetime.now(timezone.utc).isoformat()
    return {"value": result, "observed_at": now, "context": context,
            "request": {key: item[key] for key in ("tool", "tool_version", "input", "context")},
            "details": {"schema": RESULT_SCHEMA, "input_sha256": actual_hash}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, help="Print bare result outside the EAL tool protocol")
    arguments = parser.parse_args()
    try:
        if arguments.scenario:
            scenario, digest = _read_scenario(arguments.scenario)
            result = evaluate(scenario, digest)
        else:
            request = json.load(sys.stdin, object_pairs_hook=_unique_object,
                                parse_float=Decimal, parse_constant=_reject_constant)
            result = collect(request)
        print(json.dumps(result, allow_nan=False, separators=(",", ":")))
        return 0
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError,
            json.JSONDecodeError) as exc:
        print(f"Technical-debt collection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
