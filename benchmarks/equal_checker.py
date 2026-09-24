"""Independent, deliberately bounded argument-graph comparator.

The JSON graphs are authored from ordinary briefs, not generated from EAL
source or its AST. This module does not import the EAL package. A graph states
its own acquisition contract, alternative positive routes, and objections
with alternative answers. Only the predicate operations listed in
``_PREDICATES`` are supported; unrecognised operations fail validation.

This checker is a comparator for synthetic studies, not a replacement for the
full EAL/2 language. An agreement on selected fixtures is parity on those
fixtures only. Graphs require independent review before confirmatory use.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import tomllib
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "generic-argument-graph/1"
_PREDICATES = {"eq", "lte", "gte", "is_true", "has_keys_equal", "affine_at_most"}
DEFAULT_GRAPH_DIR = Path(__file__).with_name("equal_checker_graphs")
DEFAULT_FIXTURES = Path(__file__).parent / "experiments" / "artifact-live-pilot"


class CheckerInputError(ValueError):
    """The graph, assessment time, or caller's evidence mapping is malformed."""


@dataclasses.dataclass(frozen=True)
class CheckResult:
    root: str
    claim: str
    scope: dict[str, Any]
    status: str
    trace: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _require(condition: bool, description: str) -> None:
    if not condition:
        raise CheckerInputError(description)


def _timestamp(value: Any) -> datetime:
    _require(isinstance(value, str), "timestamp must be an ISO-8601 string")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckerInputError(f"invalid timestamp {value!r}") from exc
    _require(instant.utcoffset() is not None, "timestamp must have a time-zone offset")
    return instant


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _lookup(record: Mapping[str, Any], path: list[str]) -> tuple[bool, Any]:
    current: Any = record
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return False, None
        current = current[key]
    return True, current


def _strict_equal(left: Any, right: Any) -> bool:
    # Python treats True == 1, including inside nested dictionaries and lists.
    # Acquisition identity must compare every nested leaf with its JSON type.
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) or isinstance(right, dict):
        return (isinstance(left, dict) and isinstance(right, dict)
                and left.keys() == right.keys()
                and all(_strict_equal(left[key], right[key]) for key in right))
    if isinstance(left, list) or isinstance(right, list):
        return (isinstance(left, list) and isinstance(right, list)
                and len(left) == len(right)
                and all(_strict_equal(a, b) for a, b in zip(left, right)))
    if _number(left) is not None and _number(right) is not None:
        return _number(left) == _number(right)
    return type(left) is type(right) and left == right


def _strict_mapping_equal(left: Any, right: Mapping[str, Any]) -> bool:
    return isinstance(left, dict) and _strict_equal(left, dict(right))


def _validate_predicate(predicate: Any, evidence: Mapping[str, Any]) -> None:
    _require(isinstance(predicate, dict), "each predicate must be an object")
    op = predicate.get("op")
    _require(op in _PREDICATES, f"unsupported predicate operation {op!r}")
    record = predicate.get("record")
    _require(isinstance(record, str) and record in evidence,
             f"predicate refers to undeclared record {record!r}")
    if op == "affine_at_most":
        intervention = predicate.get("intervention")
        _require(isinstance(intervention, dict)
                 and isinstance(intervention.get("variable"), str)
                 and _number(intervention.get("value")) is not None,
                 "affine_at_most requires a numeric intervention")
        _require(isinstance(predicate.get("outcome"), str)
                 and _number(predicate.get("limit")) is not None,
                 "affine_at_most requires an outcome and numeric limit")
    else:
        path = predicate.get("path")
        _require(isinstance(path, list) and bool(path)
                 and all(isinstance(part, str) and part for part in path),
                 f"{op} requires a nonempty string path")
        if op in {"eq", "lte", "gte"}:
            _require("value" in predicate, f"{op} requires a value")
        if op in {"lte", "gte"}:
            _require(_number(predicate["value"]) is not None,
                     f"{op} requires a finite numeric value")
        if op == "has_keys_equal":
            _require(isinstance(predicate.get("keys"), dict)
                     and bool(predicate["keys"])
                     and all(isinstance(key, str) for key in predicate["keys"]),
                     "has_keys_equal requires named keys and expected values")


def validate_graph(graph: Mapping[str, Any]) -> None:
    _require(isinstance(graph, Mapping), "graph must be an object")
    _require(graph.get("schema") == SCHEMA, f"graph schema must be {SCHEMA}")
    for name in ("id", "claim"):
        _require(isinstance(graph.get(name), str) and bool(graph[name]),
                 f"graph requires a nonempty {name}")
    scope = graph.get("scope")
    _require(isinstance(scope, dict) and bool(scope), "graph requires typed scope")
    for key, spec in scope.items():
        _require(isinstance(key, str) and isinstance(spec, dict)
                 and spec.get("type") in {"str", "int", "bool"}
                 and "equals" in spec, f"invalid scope definition {key!r}")
        expected_type = {"str": str, "int": int, "bool": bool}[spec["type"]]
        _require(type(spec["equals"]) is expected_type,
                 f"scope {key!r} has a value of the wrong type")
    evidence = graph.get("evidence")
    _require(isinstance(evidence, dict) and bool(evidence), "graph needs evidence contracts")
    for name, spec in evidence.items():
        _require(isinstance(name, str) and bool(name) and isinstance(spec, dict),
                 "invalid evidence contract")
        _require(isinstance(spec.get("tool_version"), str)
                 and isinstance(spec.get("mode"), str)
                 and type(spec.get("max_age_seconds")) is int
                 and spec["max_age_seconds"] >= 0,
                 f"invalid acquisition contract for {name!r}")
        _require(isinstance(spec.get("input", {}), dict),
                 f"invalid acquisition input for {name!r}")
    routes = graph.get("routes")
    _require(isinstance(routes, list) and bool(routes), "graph needs positive routes")
    for route in routes:
        _require(isinstance(route, dict) and isinstance(route.get("id"), str)
                 and isinstance(route.get("all"), list) and bool(route["all"]),
                 "route needs an id and a nonempty conjunction")
        for predicate in route["all"]:
            _validate_predicate(predicate, evidence)
    objections = graph.get("objections", [])
    _require(isinstance(objections, list), "objections must be a list")
    for objection in objections:
        _require(isinstance(objection, dict) and isinstance(objection.get("id"), str)
                 and isinstance(objection.get("when"), list) and bool(objection["when"])
                 and isinstance(objection.get("answers", []), list),
                 "objection needs an id, conditions and optional alternative answers")
        for predicate in objection["when"]:
            _validate_predicate(predicate, evidence)
        for answer in objection.get("answers", []):
            _require(isinstance(answer, dict) and isinstance(answer.get("id"), str)
                     and isinstance(answer.get("all"), list) and bool(answer["all"]),
                     "answer needs an id and a nonempty conjunction")
            for predicate in answer["all"]:
                _validate_predicate(predicate, evidence)


def _envelope(name: str, contract: Mapping[str, Any], record: Any,
              scope: Mapping[str, Any], now: datetime) -> tuple[bool, str]:
    if not isinstance(record, dict):
        return False, f"{name}: missing or malformed acquisition record"
    request = record.get("request")
    if (not _strict_mapping_equal(record.get("context"), scope)
            or not isinstance(request, dict)
            or not _strict_mapping_equal(request.get("context"), scope)
            or request.get("tool") != name
            or request.get("tool_version") != contract["tool_version"]
            or request.get("mode") != contract["mode"]
            or not _strict_equal(request.get("input"), contract.get("input", {}))):
        return False, f"{name}: collection identity, context, or request mismatch"
    if not isinstance(record.get("value"), dict):
        return False, f"{name}: missing structured value"
    try:
        stamp = _timestamp(record.get("observed_at"))
    except CheckerInputError:
        return False, f"{name}: invalid acquisition time"
    age = (now - stamp).total_seconds()
    if age < 0 or age > contract["max_age_seconds"]:
        return False, f"{name}: evidence outside the permitted time interval"
    return True, f"{name}: acquisition identity, scope and time match"


def _predicate(predicate: Mapping[str, Any], evidence: Mapping[str, Any],
               availability: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    op = predicate["op"]
    record_name = predicate["record"]
    if not availability[record_name]["ok"]:
        return {"op": op, "record": record_name, "ok": False,
                "reason": availability[record_name]["reason"]}
    record = evidence[record_name]
    if op == "affine_at_most":
        intervention = predicate["intervention"]
        output_name = predicate["outcome"]
        value = record["value"]
        if (not isinstance(value.get("intervention"), dict)
                or value["intervention"].get("variable") != intervention["variable"]
                or _number(value["intervention"].get("value")) != _number(intervention["value"])
                or value.get("outcome") != output_name):
            return {"op": op, "record": predicate["record"], "ok": False,
                    "reason": "model does not describe the specified intervention and outcome"}
        variables = value.get("variables")
        equation = variables.get(output_name) if isinstance(variables, dict) else None
        terms = equation.get("coefficients") if isinstance(equation, dict) else None
        coefficient = terms.get(intervention["variable"]) if isinstance(terms, dict) else None
        intercept = _number(equation.get("intercept")) if isinstance(equation, dict) else None
        noise = _number(equation.get("noise")) if isinstance(equation, dict) else None
        gain = _number(coefficient)
        if intercept is None or gain is None or noise is None:
            return {"op": op, "record": predicate["record"], "ok": False,
                    "reason": "affine model lacks finite coefficients, intercept, or supplied noise"}
        predicted = intercept + gain * _number(intervention["value"]) + noise
        ok = predicted <= _number(predicate["limit"])
        return {"op": op, "record": predicate["record"], "ok": ok,
                "reason": f"conditional prediction {predicted} <= {predicate['limit']}"}
    exists, actual = _lookup(record, predicate["path"])
    if not exists:
        return {"op": op, "record": predicate["record"], "ok": False,
                "reason": f"missing {'.'.join(predicate['path'])}"}
    if op == "eq":
        ok = _strict_equal(actual, predicate["value"])
    elif op == "is_true":
        ok = actual is True
    elif op in {"lte", "gte"}:
        number = _number(actual)
        bound = _number(predicate["value"])
        ok = number is not None and (number <= bound if op == "lte" else number >= bound)
    else:  # has_keys_equal, an explicit bounded negative finding
        ok = isinstance(actual, dict) and all(
            key in actual and _strict_equal(actual[key], expected)
            for key, expected in predicate["keys"].items())
    return {"op": op, "record": predicate["record"], "ok": ok,
            "reason": f"{'.'.join(predicate['path'])} {op} "
                      f"{predicate.get('value', predicate.get('keys', True))!r}"}


def _conjunction(predicates: list[dict], evidence: Mapping[str, Any],
                 availability: Mapping[str, Mapping[str, Any]]) -> tuple[bool, list[dict]]:
    checks = [_predicate(item, evidence, availability) for item in predicates]
    return all(check["ok"] for check in checks), checks


def evaluate(graph: Mapping[str, Any], evidence: Mapping[str, Any], now: str) -> CheckResult:
    """Check one independently authored graph against one evidence state.

    Malformed graph/caller inputs raise ``CheckerInputError``. A missing,
    stale, wrong-scope or wrong-tool observation cannot satisfy a condition:
    positive routes fail when they need it, objections become inactive when
    their records are unavailable, and unavailable answers cannot discharge
    an active objection. This matches the bounded optional-record contract.
    """
    validate_graph(graph)
    _require(isinstance(evidence, Mapping), "evidence must be a named mapping")
    assessment_time = _timestamp(now)
    scope = {key: spec["equals"] for key, spec in graph["scope"].items()}
    envelopes = []
    for name, contract in graph["evidence"].items():
        ok, reason = _envelope(name, contract, evidence.get(name), scope, assessment_time)
        envelopes.append({"record": name, "ok": ok, "reason": reason})
    availability = {item["record"]: item for item in envelopes}
    trace: dict[str, Any] = {"evidence": envelopes, "routes": [],
                             "objections": [], "reason": ""}
    for route in graph["routes"]:
        ok, checks = _conjunction(route["all"], evidence, availability)
        trace["routes"].append({"id": route["id"], "ok": ok, "checks": checks})
    if not any(route["ok"] for route in trace["routes"]):
        failed = [check["reason"] for route in trace["routes"]
                  for check in route["checks"] if not check["ok"]]
        trace["reason"] = "; ".join(failed)
        return CheckResult(graph["id"], graph["claim"], scope, "unsupported", trace)
    for objection in graph.get("objections", []):
        active, checks = _conjunction(objection["when"], evidence, availability)
        answers = []
        if active:
            for answer in objection.get("answers", []):
                ok, answer_checks = _conjunction(answer["all"], evidence, availability)
                answers.append({"id": answer["id"], "ok": ok, "checks": answer_checks})
        answered = active and any(answer["ok"] for answer in answers)
        trace["objections"].append({"id": objection["id"], "active": active,
                                    "answered": answered, "checks": checks,
                                    "answers": answers})
    open_objections = [item["id"] for item in trace["objections"]
                       if item["active"] and not item["answered"]]
    if open_objections:
        trace["reason"] = "Unanswered objection: " + ", ".join(open_objections)
        status = "contested"
    else:
        accepted = [route["id"] for route in trace["routes"] if route["ok"]]
        trace["reason"] = "Accepted positive route: " + ", ".join(accepted)
        status = "supported"
    return CheckResult(graph["id"], graph["claim"], scope, status, trace)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_for_root(root_id: str, graph_dir: Path = DEFAULT_GRAPH_DIR) -> dict[str, Any]:
    """Load a separate, hand-authored JSON graph by a safe root identifier."""
    _require(isinstance(root_id, str) and bool(root_id)
             and all(char.isascii() and (char.isalnum() or char == "_") for char in root_id),
             "invalid root identifier")
    graph = json.loads((Path(graph_dir) / f"{root_id}.json").read_text(encoding="utf-8"))
    validate_graph(graph)
    _require(graph["id"] == root_id, "graph root identity mismatch")
    return graph


def load_state(root: Mapping[str, Any], state: Mapping[str, Any],
               fixtures: Path = DEFAULT_FIXTURES) -> dict[str, Any]:
    """Load independent observation products named by an existing frozen registry.

    The registry supplies filenames only. EAL source is not read or parsed.
    """
    if "checker_evidence" in state:
        bindings = state["checker_evidence"]
        source_dir = fixtures.resolve()
        _require(isinstance(bindings, dict) and bool(bindings),
                 "checker_evidence must be a named mapping")
    else:
        registry_path = (fixtures / state["registry"]).resolve()
        source_dir = (fixtures / root["source"]).resolve().parent
        _require(registry_path.is_relative_to(fixtures.resolve()), "registry escapes fixtures")
        registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
        _require(isinstance(registry.get("tools"), dict), "registry lacks tools")
        bindings = {name: binding["path"] for name, binding in registry["tools"].items()}
    records = {}
    for name, relative_path in bindings.items():
        path = (source_dir / relative_path).resolve()
        _require(path.is_relative_to(fixtures.resolve()), "observation escapes fixtures")
        records[name] = json.loads(path.read_text(encoding="utf-8"))
    return records


def evidence_for_state(root_id: str, state_id: str,
                       fixtures: Path = DEFAULT_FIXTURES) -> dict[str, Any]:
    """Find a manifest state and load its JSON observation products."""
    fixtures = Path(fixtures)
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    for root in manifest["roots"]:
        if root["id"] == root_id:
            for state in root["states"] + root.get("tamper", []):
                if state["id"] == state_id:
                    return load_state(root, state, fixtures)
    raise CheckerInputError(f"unknown root/state {root_id!r}/{state_id!r}")


def parity_suite(fixtures: Path = DEFAULT_FIXTURES,
                 graph_dir: Path = DEFAULT_GRAPH_DIR) -> dict[str, Any]:
    """Report parity and deterministic tamper checks without calling EAL.

    Expected labels in the manifest are comparison targets, not checker input.
    Extra challenge states outside the scored twelve are labelled separately.
    """
    fixtures, graph_dir = Path(fixtures), Path(graph_dir)
    manifest_path = fixtures / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    tamper: list[dict[str, Any]] = []
    fixture_tamper: list[dict[str, Any]] = []
    for root in manifest["roots"]:
        graph_path = graph_dir / f"{root['id']}.json"
        graph = graph_for_root(root["id"], graph_dir)
        _require(graph["id"] == root["id"] and graph["claim"] == root["claim"],
                 "graph and manifest identity mismatch")
        for state in root["states"]:
            evidence = load_state(root, state, fixtures)
            result = evaluate(graph, evidence, root["now"])
            entries.append({"root": root["id"], "state": state["id"],
                            "status": result.status, "expected": state["expected"],
                            "pass": result.status == state["expected"],
                            "trace": result.trace,
                            "evidence_sha256": hashlib.sha256(json.dumps(
                                evidence, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False).encode("utf-8")).hexdigest(),
                            "graph_sha256": sha256(graph_path),
                            "source_sha256": sha256(fixtures / root["source"])})
            for attack in ("wrong_scope", "wrong_tool", "stale", "future", "missing"):
                altered = json.loads(json.dumps(evidence))
                key = next(iter(graph["evidence"]))
                if attack == "wrong_scope":
                    altered[key]["request"]["context"] = {"wrong": "subject"}
                elif attack == "wrong_tool":
                    altered[key]["request"]["tool"] = "unrelated_reader"
                elif attack == "stale":
                    altered[key]["observed_at"] = "2000-01-01T00:00:00Z"
                elif attack == "future":
                    altered[key]["observed_at"] = "2999-01-01T00:00:00Z"
                else:
                    del altered[key]
                checked = evaluate(graph, altered, root["now"])
                tamper.append({"root": root["id"], "state": state["id"],
                               "attack": attack, "status": checked.status,
                               "pass": checked.status == "unsupported"})
        for state in root.get("tamper", []):
            evidence = load_state(root, state, fixtures)
            checked = evaluate(graph, evidence, root["now"])
            fixture_tamper.append({"root": root["id"], "state": state["id"],
                                   "kind": state.get("kind"),
                                   "status": checked.status, "expected": state["expected"],
                                   "pass": checked.status == state["expected"],
                                   "trace": checked.trace})
    return {"schema": "generic-checker-parity/1", "manifest_sha256": sha256(manifest_path),
            "checker_sha256": sha256(Path(__file__)),
            "cases": entries, "tamper": tamper, "fixture_tamper": fixture_tamper,
            "parity": sum(item["pass"] for item in entries),
            "cases_total": len(entries),
            "tamper_pass": sum(item["pass"] for item in tamper),
            "tamper_total": len(tamper),
            "fixture_tamper_pass": sum(item["pass"] for item in fixture_tamper),
            "fixture_tamper_total": len(fixture_tamper),
            "passed": all(item["pass"] for item in entries + tamper + fixture_tamper)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--graphs", type=Path, default=DEFAULT_GRAPH_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = parity_suite(args.fixtures, args.graphs)
    data = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
