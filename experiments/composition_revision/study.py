"""Run either coolant-loop assessor on the same declared synthetic reading set."""
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse

from . import baseline


HERE = Path(__file__).resolve().parent
SOURCE_PATH = HERE / "cooling.eal"
CASES_PATH = HERE / "cases.json"
SCHEMA = "eal2-composition-revision/1"
BASE_TIME = "2026-09-23T12:00:00Z"
CONTEXT = {"loop_id": "coolant-loop-A", "load_kw": 8}
Arm = Literal["eal", "typed_rule"]


def load_cases() -> dict[str, Any]:
    """Load reviewed expected statuses, including explicit revision effects."""
    document = json.loads(CASES_PATH.read_text())
    if document.get("schema") != SCHEMA or document.get("base_time") != BASE_TIME or document.get("context") != CONTEXT:
        raise ValueError("Unknown composition/revision fixture contract")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Expected nonempty synthetic case list")
    prior: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in prior:
            raise ValueError("Case IDs must be unique nonempty strings")
        if not isinstance(case.get("observations"), dict) or set(case["observations"]) - set(baseline.EVIDENCE):
            raise ValueError(f"Case {case['id']} has an invalid reading set")
        if set(case.get("expected", {})) != set(baseline.CLAIMS):
            raise ValueError(f"Case {case['id']} needs independent expected statuses for every claim")
        predecessor = prior.get(case.get("revision_of"))
        if case.get("revision_of") is not None and predecessor is None:
            raise ValueError(f"Case {case['id']} has a missing predecessor")
        affected = {name for name in baseline.CLAIMS
                    if predecessor is not None and predecessor["expected"][name] != case["expected"][name]}
        if set(case.get("affected", ())) != affected:
            raise ValueError(f"Case {case['id']} has an inconsistent expected revision effect")
        prior[case["id"]] = case
    return document


def _record(name: str, value: dict[str, Any], *, source_digest: str,
            kind: str, requested_input: Any, context: dict[str, Any],
            observed_at: str = BASE_TIME) -> dict[str, Any]:
    acquisition = {"tool": baseline.TOOL, "tool_version": baseline.TOOL_VERSION,
                   "input": requested_input, "context": context}
    request = {"evidence_id": name, "environment": baseline.ENVIRONMENT, **acquisition}
    return {"evidence_id": name, "source_digest": source_digest,
            "tool": baseline.TOOL, "tool_version": baseline.TOOL_VERSION,
            "tool_binding_digest": "0" * 64, "evidence_kind": kind,
            "environment": baseline.ENVIRONMENT,
            "environment_fingerprint": environment_fingerprint(baseline.ENVIRONMENT, context),
            "input_digest": canonical_digest(requested_input), "input": requested_input,
            "context": context, "acquisition_request": acquisition,
            "acquisition_request_digest": canonical_digest(acquisition),
            "request_digest": canonical_digest(request),
            "collected_at": observed_at, "run_id": "synthetic-" + name,
            "status": "ok", "value": value, "data_digest": canonical_digest(value)}


def run_arm(case: dict[str, Any], arm: Arm) -> dict[str, Any]:
    """Time one assessment; parsing and fixture-envelope construction are excluded.

    Arms read equivalent measurement values, original observation time and
    context. Source/configuration digests differ because their declarations
    are independent. Callers should retain a failed arm as an assigned failure.
    """
    if arm not in ("eal", "typed_rule"):
        raise ValueError(f"Unknown comparison arm {arm!r}")
    context = case.get("context", CONTEXT)
    assessed_at = case.get("assessed_at", BASE_TIME)
    observed_at = case.get("observed_at", BASE_TIME)
    observations = case["observations"]
    if arm == "eal":
        program = parse(SOURCE_PATH.read_text())
        source_digest = program.source_digest
        specs = {name: (item.kind, item.input) for name, item in program.evidence.items()}
    else:
        source_digest = baseline.CONFIG_DIGEST
        specs = {name: (item.kind, item.request) for name, item in baseline.EVIDENCE.items()}
    if set(observations) - set(specs):
        raise ValueError("Unknown evidence ID in synthetic reading set")
    records = {name: _record(name, value, source_digest=source_digest,
                             kind=specs[name][0], requested_input=specs[name][1], context=context,
                             observed_at=observed_at)
               for name, value in observations.items()}
    started = perf_counter()
    if arm == "eal":
        result = evaluate(program, records, now=assessed_at, context=context)
        if not result["valid"]:
            raise ValueError(f"Invalid EAL programme: {result['diagnostics']}")
        claims = {name: item["status"] for name, item in result["claims"].items()}
        arguments = {name: item["status"] for name, item in result["arguments"].items()}
        evidence = {name: item["status"] for name, item in result["evidence"].items()}
        objections = {name: item["status"] for name, item in result["objections"].items()}
    else:
        result = baseline.evaluate(records, now=assessed_at, context=context)
        claims, arguments, evidence, objections = (result[key] for key in
                                                    ("claims", "arguments", "evidence", "objections"))
    seconds = perf_counter() - started
    return {"claims": claims, "argument_statuses": arguments,
            "evidence_statuses": evidence, "objection_statuses": objections,
            "elapsed_seconds": seconds, "source_digest": source_digest}
