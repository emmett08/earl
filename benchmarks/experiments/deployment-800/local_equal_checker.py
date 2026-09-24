"""Independent finite graph assessment with route-targeted objections.

Uses the generic comparator's separate JSON acquisition/predicate checks, not
the EAL interpreter or source AST. The local rule rejects only the targeted
positive route when an active objection has no adequate answer; another sound
route remains independent. This finite profile is not full ASPIC+ semantics.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from benchmarks.equal_checker import (  # Independent of src/eal.
    CheckResult, CheckerInputError, _conjunction, _envelope, _require,
    _timestamp, load_state, validate_graph as validate_base,
)
import json


def validate_graph(graph: Mapping[str, Any]) -> None:
    validate_base(graph)
    routes = {route["id"] for route in graph["routes"]}
    if len(routes) != len(graph["routes"]):
        raise CheckerInputError("Positive route IDs must be distinct")
    objections = graph.get("objections", [])
    if len({obj["id"] for obj in objections}) != len(objections):
        raise CheckerInputError("Objection IDs must be distinct")
    for obj in objections:
        if obj.get("target_route") not in routes:
            raise CheckerInputError("Each objection needs an existing target_route")


def evaluate(graph: Mapping[str, Any], evidence: Mapping[str, Any], now: str) -> CheckResult:
    validate_graph(graph)
    _require(isinstance(evidence, Mapping), "evidence must be a named mapping")
    instant = _timestamp(now)
    scope = {key: spec["equals"] for key, spec in graph["scope"].items()}
    envelopes = []
    for name, contract in graph["evidence"].items():
        ok, reason = _envelope(name, contract, evidence.get(name), scope, instant)
        envelopes.append({"record": name, "ok": ok, "reason": reason})
    available = {item["record"]: item for item in envelopes}
    routes = []
    for route in graph["routes"]:
        ok, checks = _conjunction(route["all"], evidence, available)
        routes.append({"id": route["id"], "ok": ok, "checks": checks})
    objections = []
    for obj in graph.get("objections", []):
        active, checks = _conjunction(obj["when"], evidence, available)
        answers = []
        if active:
            for answer in obj.get("answers", []):
                ok, answer_checks = _conjunction(answer["all"], evidence, available)
                answers.append({"id": answer["id"], "ok": ok, "checks": answer_checks})
        objections.append({"id": obj["id"], "target_route": obj["target_route"],
                           "active": active, "answered": active and any(a["ok"] for a in answers),
                           "checks": checks, "answers": answers})
    open_by_route = {obj["target_route"] for obj in objections if obj["active"] and not obj["answered"]}
    sound_routes = [route["id"] for route in routes if route["ok"] and route["id"] not in open_by_route]
    if sound_routes:
        status = "supported"
        reason = "Usable unchallenged or answered route: " + ", ".join(sound_routes)
    elif any(route["ok"] for route in routes):
        status = "contested"
        reason = "All usable positive routes have active unanswered objections"
    else:
        status = "unsupported"
        reason = "No usable positive route"
    trace = {"evidence": envelopes, "routes": routes, "objections": objections,
             "sound_routes": sound_routes, "reason": reason}
    return CheckResult(graph["id"], graph["claim"], scope, status, trace)


def parity_suite(fixtures: Path, graph_dir: Path) -> dict[str, Any]:
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    entries, attacks = [], []
    for root in manifest["roots"]:
        graph = json.loads((graph_dir / f'{root["id"]}.json').read_text(encoding="utf-8"))
        validate_graph(graph)
        for state in root["states"]:
            records = load_state(root, state, fixtures)
            actual = evaluate(graph, records, root["now"])
            entries.append({"root": root["id"], "state": state["id"],
                            "expected": state["expected"], "actual": actual.status,
                            "pass": state["expected"] == actual.status})
            # Attack both independent test acquisitions. Wrong identity and
            # unavailable positive records cannot become support merely due
            # to an open objection or a forged answer.
            for attack in ("wrong_scope", "wrong_tool", "stale", "future", "missing"):
                changed = deepcopy(records)
                for name in ("primary_reader", "alternate_reader"):
                    if attack == "wrong_scope":
                        changed[name]["request"]["context"] = {"wrong": "asset"}
                    elif attack == "wrong_tool":
                        changed[name]["request"]["tool"] = "other_reader"
                    elif attack == "stale":
                        changed[name]["observed_at"] = "2000-01-01T00:00:00Z"
                    elif attack == "future":
                        changed[name]["observed_at"] = "2999-01-01T00:00:00Z"
                    else:
                        changed.pop(name)
                outcome = evaluate(graph, changed, root["now"])
                attacks.append({"root": root["id"], "state": state["id"],
                                "attack": attack, "actual": outcome.status,
                                "pass": outcome.status == "unsupported"})
    return {"cases_total": len(entries), "parity": sum(row["pass"] for row in entries),
            "tamper_total": len(attacks), "tamper_pass": sum(row["pass"] for row in attacks),
            "entries": entries, "attacks": attacks}
