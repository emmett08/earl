#!/usr/bin/env python3
"""Deterministic development experiment for adverse evidence and revision.

The oracle is stated independently of EAL execution. These synthetic cases
are exposed development fixtures, not model calls or an estimate of benefit.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.semantics import validate

COUNTER = ROOT / "arguments/negative-revision/counterexample.eal"
CLOSURE = ROOT / "arguments/negative-revision/closure.eal"
OUTPUT = ROOT / "benchmarks/results/2026-09-23-negative-revisions/lifecycle.json"
CONTEXT = {"site": "test-rig-9"}
NOW = "2040-01-31T08:30:00Z"
COLLECTED = "2040-01-31T08:20:00Z"
QUERY = {"start": 0, "end": 12, "max_gap": 4,
         "property": {"operator": "lt", "value": 1}, "semantics": "sampled",
         "detector_contract": {"maximum_detection_limit": 0.1, "minimum_sensitivity": 0.9}}
FULL_CLEAR = [{"time": 0, "value": 0.5}, {"time": 4, "value": 0.6},
              {"time": 8, "value": 0.8}, {"time": 12, "value": 0.7}]
PARTIAL_WITNESS = [{"time": 4, "value": 1.2}]


def observation(program, name: str, value: dict) -> dict:
    evidence = program.evidence[name]
    tool = program.tools[evidence.tool]
    return {"evidence_id": name, "source_digest": program.source_digest,
            "tool": tool.name, "tool_version": tool.version, "mode": tool.mode,
            "evidence_kind": evidence.kind, "environment": evidence.environment,
            "environment_fingerprint": environment_fingerprint(evidence.environment, CONTEXT),
            "input_digest": canonical_digest(evidence.input), "collected_at": COLLECTED,
            "run_id": "synthetic-negative-revision", "status": "ok", "value": value,
            "data_digest": canonical_digest(value)}


def trace(mode: str, events: list[dict], *, scope: str = "vibration-interval-9",
          detection_limit: float = 0.05, sensitivity: float = 0.95) -> dict:
    payload = {"mode": mode, **deepcopy(QUERY), "events": deepcopy(events)}
    if mode == "non_detection":
        payload["calibration"] = {"detection_limit": detection_limit,
                                  "sensitivity_lower_bound": sensitivity}
    return {"schema": "EAL/typed-input/1", "method": "engineering/sampled-negative/1",
            "subject": "rig-9", "quantity": "dimensionless", "unit": "1", "scope": scope,
            "valid_from": "2040-01-31T08:00:00Z", "valid_until": "2040-01-31T09:00:00Z",
            "payload": payload}


def rows_spec() -> list[dict]:
    """Expected states were declared from the question/coverage/attack contract."""
    counter = [
        ("initial_tests", None, False, True, "supported", "unsupported"),
        ("single_matching_test", None, False, True, "supported", "unsupported"),
        ("partial_witness", trace("counterexample", PARTIAL_WITNESS), False, True, "contested", "supported"),
        ("tests_wrong_property", trace("counterexample", PARTIAL_WITNESS), False, True, "unsupported", "supported"),
        ("wrong_scope_same_value", trace("counterexample", PARTIAL_WITNESS, scope="other-interval"), False, True, "supported", "unsupported"),
        ("partial_no_violation", trace("counterexample", [{"time": 4, "value": 0.8}]), False, True, "supported", "unsupported"),
        ("restore_witness", trace("counterexample", PARTIAL_WITNESS), False, True, "contested", "supported"),
        ("independent_defence", trace("counterexample", PARTIAL_WITNESS), True, True, "supported", "supported"),
        ("defence_wrong_sample", trace("counterexample", PARTIAL_WITNESS), True, True, "contested", "supported"),
        ("withdraw_defence", trace("counterexample", PARTIAL_WITNESS), False, True, "contested", "supported"),
        ("retract_witness", None, False, True, "supported", "unsupported"),
        ("one_route_unlinked", trace("counterexample", PARTIAL_WITNESS), False, False, "supported", "supported"),
    ]
    closure = [
        ("complete_clear", trace("non_detection", FULL_CLEAR), "supported"),
        ("partial_clear", trace("non_detection", FULL_CLEAR[:-1]), "unsupported"),
        ("wrong_scope_clear", trace("non_detection", FULL_CLEAR, scope="other-interval"), "unsupported"),
        ("insensitive_detector", trace("non_detection", FULL_CLEAR, sensitivity=0.6), "unsupported"),
        ("high_detection_limit", trace("non_detection", FULL_CLEAR, detection_limit=0.5), "unsupported"),
        ("complete_with_violation", trace("non_detection", [*FULL_CLEAR[:2], {"time": 8, "value": 1.2}, FULL_CLEAR[3]]), "unsupported"),
        ("empty_search", trace("non_detection", []), "unsupported"),
        ("missing_search", None, "unsupported"),
    ]
    return ([{"track": "counterexample", "step": step, "trace": value, "defence": defence,
             "linked": linked, "expected": {"property_supported": parent, "violating_sample": negative}}
            for step, value, defence, linked, parent, negative in counter] +
            [{"track": "closure", "step": step, "trace": value,
              "expected": {"qualified_absence": status, "proceed_within_sampled_contract": status}}
             for step, value, status in closure])


def unlinked_source(source: str) -> str:
    """A negative claim with no challenge to the surviving second route."""
    return "\n".join(line for line in source.splitlines()
                     if not line.startswith("objection challenge_second ")
                     and not line.startswith("objection independent_defence_second ")) + "\n"


def independent_reference(item: dict) -> dict[str, str]:
    """Small separately written checker for the two fixed authored graphs.

    This is deliberately a domain-specific comparator. It has neither a parser
    nor the generic EAL graph evaluator, and cannot test authoring advantage.
    """
    observed = item["trace"]
    track = item["track"]
    negative = False
    if observed is not None:
        payload = observed["payload"]
        points = payload["events"]
        matched = (observed["scope"] == "vibration-interval-9"
                   and observed["subject"] == "rig-9"
                   and observed["method"] == "engineering/sampled-negative/1"
                   and all(payload.get(key) == value for key, value in QUERY.items())
                   and payload.get("mode") == ("counterexample" if track == "counterexample" else "non_detection")
                   and bool(points) and all(0 <= point["time"] <= 12 for point in points)
                   and all(left["time"] < right["time"] for left, right in zip(points, points[1:])))
        if matched:
            violation = any(point["value"] >= 1 for point in points)
            if track == "counterexample":
                negative = violation
            else:
                complete = (points[0]["time"] == 0 and points[-1]["time"] == 12
                            and all(right["time"] - left["time"] <= 4
                                    for left, right in zip(points, points[1:])))
                calibration = payload.get("calibration", {})
                capable = (calibration.get("detection_limit", float("inf")) <= 0.1
                           and calibration.get("sensitivity_lower_bound", -1) >= 0.9)
                negative = complete and capable and not violation
    if track == "counterexample":
        if item["step"] == "tests_wrong_property":
            parent = "unsupported"
        else:
            defence_eligible = item["defence"] and item["step"] != "defence_wrong_sample"
            parent = ("contested" if negative and item["linked"] and not defence_eligible
                      else "supported")
        return {"violating_sample": "supported" if negative else "unsupported",
                "property_supported": parent}
    return {"qualified_absence": "supported" if negative else "unsupported",
            "proceed_within_sampled_contract": "supported" if negative else "unsupported"}


def mechanism_reference(item: dict) -> tuple[str, dict[str, str]]:
    step = item["step"]
    if item["trace"] is None:
        method = "not_run"
    elif step in {"partial_witness", "tests_wrong_property", "restore_witness",
                  "independent_defence", "defence_wrong_sample", "withdraw_defence",
                  "one_route_unlinked", "complete_clear"}:
        method = "supported"
    else:
        method = "unsupported"
    if item["track"] == "closure":
        return method, {}
    challenge = ("defeated" if step == "independent_defence" else "active"
                 if step in {"partial_witness", "tests_wrong_property", "restore_witness",
                             "defence_wrong_sample", "withdraw_defence", "one_route_unlinked"}
                 else "inactive")
    expected = {"challenge_first": challenge,
                "independent_defence_first": "active" if step == "independent_defence" else "inactive"}
    if item["linked"]:
        expected.update(challenge_second=challenge,
                        independent_defence_second="active" if step == "independent_defence" else "inactive")
    return method, expected


def run() -> dict:
    from eal.sampled_negative import sampled_negative_registry
    from eal.modes import assess_mode

    registry = sampled_negative_registry()
    scripts = {"counterexample": COUNTER.read_text(), "closure": CLOSURE.read_text()}
    legacy_input = {key: deepcopy(QUERY[key]) for key in ("start", "end", "max_gap", "property", "semantics")}
    legacy_input["events"] = deepcopy(PARTIAL_WITNESS)
    old_method = assess_mode("temporal/1", [{"id": "trace_record", "kind": "trace", "value": legacy_input}], [])
    output = []
    for item in rows_spec():
        track, step = item["track"], item["step"]
        source = scripts[track] if item.get("linked", True) else unlinked_source(scripts[track])
        program = parse(source)
        errors = validate(program, registry=registry)
        if errors:
            raise ValueError(f"{track}/{step}: {errors}")
        values = ({"first_record": {"passed": True, "subject": "rig-9", "scope": "vibration-interval-9",
                                    "property": {"operator": "lt", "value": 1}},
                   "second_record": {"passed": True, "subject": "rig-9", "scope": "vibration-interval-9",
                                     "property": {"operator": "lt", "value": 1}}}
                  if track == "counterexample" else {})
        if step == "single_matching_test":
            values.pop("second_record")
        if step == "tests_wrong_property":
            values["first_record"]["property"]["value"] = 2
            values["second_record"]["property"]["value"] = 2
        if item["trace"] is not None:
            values["trace_record"] = item["trace"]
        if item.get("defence"):
            values["defence_record"] = {"independently_explained": True, "subject": "rig-9",
                                        "scope": "vibration-interval-9",
                                        "sample_time": 8 if step == "defence_wrong_sample" else 4}
        records = {name: observation(program, name, value) for name, value in values.items()}
        assessed = evaluate(program, records, now=NOW, context=CONTEXT, registry=registry)
        actual = {key: assessed["claims"][key]["status"] for key in item["expected"]}
        if not assessed["valid"]:
            raise ValueError(f"{track}/{step}: {assessed['diagnostics']}")
        negative_route = ("negative_route" if track == "counterexample" else "absence_route")
        route = assessed["arguments"][negative_route]
        reference = independent_reference(item)
        method_expected, objections_expected = mechanism_reference(item)
        method_actual = route["reasoning_result"]["status"] if "reasoning_result" in route else None
        objections_actual = {key: value["status"] for key, value in assessed["objections"].items()}
        output.append({"track": track, "step": step, "source_sha256": sha256(source.encode()).hexdigest(),
                       "records_sha256": canonical_digest(records), "expected": item["expected"],
                       "reference": reference, "actual": actual,
                       "passes_oracle": (actual == item["expected"] == reference
                                         and method_actual == method_expected
                                         and objections_actual == objections_expected),
                       "expected_method_status": method_expected, "method_status": method_actual,
                       "binding_status": route.get("reasoning_result", {}).get("binding", {}).get("status"),
                       "expected_objections": objections_expected, "objections": objections_actual})
    return {"schema": "EAL/negative-revision-result/1", "study_type": "deterministic-developmental",
            "source_sha256": {track: sha256(source.encode()).hexdigest() for track, source in scripts.items()},
            "method_registry_fingerprint": registry.fingerprint, "cases": output,
            "legacy_temporal_partial_witness": {"status": old_method["status"],
                                                 "violation_count": old_method.get("details", {}).get("violation_count"),
                                                 "coverage": old_method.get("details", {}).get("coverage")},
            "passed": sum(row["passes_oracle"] for row in output), "total": len(output),
            "interpretation": "Fixed synthetic observations match an explicit oracle and a narrow independent checker. The old temporal/1 method detects the partial witness in details but marks the method unsupported. No model calls, physical authentication, general equal-checker comparison, authoring benefit or population transfer is measured."}


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to replace retained result: {OUTPUT}")
    result = run()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"],
                      "output": str(OUTPUT)}, indent=2))
    if result["passed"] != result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
