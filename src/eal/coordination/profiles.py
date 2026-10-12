"""Finite correspondence profiles over operator-registered EAL/3 arguments.

``registered_claims/1`` requires exactly ``context`` and checks selected claim
identity and exact registered context. ``api_load/1`` additionally requires
``workload``, ``criteria`` and ``claim_outputs``. It checks the complete report
workload, freshness and installed finite sample-criteria method. Neither profile
certifies arbitrary question or claim prose.
"""
from __future__ import annotations

import math

from eal.api_load_methods import CONTRACT as API_CONTRACT
from eal.evaluator import canonical_digest
from eal.knowledge import EALKnowledgeBase
from eal.limits import ExecutionLimits
from eal.methods import check_implementation_identity
from eal.runtime import load_method_registry
from eal.store import utc_now

from .contracts import TASK_SCHEMA, TaskSpec, json_object, text, validate_anchor

PROFILE_NAMES = ("registered_claims/1", "api_load/1")
WORKLOAD_FIELDS = {"service", "build_id", "run_id", "concurrent_clients", "dataset"}
CRITERIA = {"minimum_requests": 100, "maximum_sample_p95_ms": 200, "maximum_error_rate_percent": 1}


def validate_requirements(profile, claims, value):
    if profile not in PROFILE_NAMES:
        raise ValueError("Unknown installed coordination profile")
    expected = {"context"} if profile == "registered_claims/1" else {"context", "workload", "criteria", "claim_outputs"}
    if set(value) != expected:
        raise ValueError("Profile requires exactly its declared requirement fields")
    json_object(value["context"], "context", 16384)
    if profile == "registered_claims/1":
        return
    workload, criteria, outputs = value["workload"], value["criteria"], value["claim_outputs"]
    if type(workload) is not dict or set(workload) != WORKLOAD_FIELDS:
        raise ValueError("API workload requires all five identity fields")
    for key in WORKLOAD_FIELDS - {"concurrent_clients"}:
        text(workload[key], key, 128)
    if type(workload["concurrent_clients"]) is not int or workload["concurrent_clients"] < 1:
        raise ValueError("Concurrent clients requires a positive integer")
    if type(value["context"]) is not dict or set(value["context"]) != {"service", "build_id", "dataset"}:
        raise ValueError("API context requires service, build_id and dataset")
    if type(criteria) is not dict or set(criteria) != {*CRITERIA, "evidence_max_age_seconds"}:
        raise ValueError("API criteria require the complete criterion and freshness contract")
    if any(type(number) not in (int, float) or (type(number) is float and not math.isfinite(number)) or not 0 <= number <= 1e100
           for number in criteria.values()) or type(criteria["minimum_requests"]) is not int:
        raise ValueError("API criteria require finite nonnegative numbers and integer request count")
    if type(outputs) is not dict or set(outputs) != set(claims) or any(type(value) is not str or value not in {"passes", "fails"} for value in outputs.values()):
        raise ValueError("API claim_outputs must bind each selected claim to passes or fails")


def knowledge(server):
    return EALKnowledgeBase(server.workspace, server.registry, server.database,
                            method_registry=load_method_registry(server.methods),
                            limits=None if server.limits is None else ExecutionLimits.load(server.limits))


def pin_task(server, task):
    if not isinstance(task, TaskSpec):
        raise TypeError("Task pinning requires a validated TaskSpec")
    entry = knowledge(server).catalogue.get(task.entry_id, include_source=True)
    value = {"schema": TASK_SCHEMA, "task": task.to_dict(), "source_digest": entry["source_digest"],
             "method_registry_fingerprint": entry["method_registry_fingerprint"],
             "registered_context": entry["context"], "pinned_at": utc_now()}
    return {**value, "task_digest": canonical_digest(value)}


def check_task(server, anchor):
    """Read and validate current identities without acquisition or reasoning."""
    task = validate_anchor(anchor)

    def result(code=None, detail="Pinned registered source and profile correspond to the task"):
        return {"ok": code is None, "code": code, "detail": detail}

    try:
        kb = knowledge(server)
        if kb.service.method_registry.fingerprint != anchor["method_registry_fingerprint"]:
            return result("criteria_mismatch", "Installed reasoning-method registry changed after task pinning")
        entry = kb.catalogue.get(task.entry_id, include_source=True)
    except KeyError:
        return result("evidence_unavailable", "Registered entry is unavailable")
    except (OSError, ValueError):
        return result("source_changed", "Current registered source or host configuration is unavailable or invalid")
    if entry["source_digest"] != anchor["source_digest"]:
        return result("source_changed", "Registered source changed after task pinning")
    if entry["method_registry_fingerprint"] != anchor["method_registry_fingerprint"]:
        return result("criteria_mismatch", "Installed reasoning-method registry changed after task pinning")
    requirements = task.to_dict()["requirements"]
    if (canonical_digest(entry["context"]) != canonical_digest(anchor["registered_context"])
            or canonical_digest(entry["context"]) != canonical_digest(requirements["context"])):
        return result("context_mismatch", "Registered context differs from the pinned and requested context")
    if set(task.claims) - set(entry["claims"]):
        return result("criteria_mismatch", "Selected task claims are absent from the registered entry")
    if task.profile == "registered_claims/1":
        return result()
    workload, criteria = requirements["workload"], requirements["criteria"]
    if canonical_digest(requirements["context"]) != canonical_digest({key: workload[key] for key in ("service", "build_id", "dataset")}):
        return result("context_mismatch", "Requested context differs from the requested API workload")
    if any(criteria[key] != number for key, number in CRITERIA.items()):
        return result("criteria_mismatch", "Requested criteria differ from the installed API-load method's fixed limits")
    installed = kb.service.method_registry.get(API_CONTRACT.identifier)
    if installed is None:
        return result("criteria_mismatch", "API-load reasoning method is not installed")
    try:
        check_implementation_identity(installed)
        if installed.describe() != API_CONTRACT.describe():
            return result("criteria_mismatch", "Installed API method differs from the profile contract")
        program = kb.service.parse(entry["source"])
        plans = [kb.service.plan(entry["source"], claim) for claim in task.claims]
        for plan in plans:
            evidence_ids = plan["evidence_ids"]
            reasoning_ids = plan["dependencies"]["reasoning"]
            if not evidence_ids or not reasoning_ids:
                return result("criteria_mismatch", "Selected API claim lacks evidence or reasoning bindings")
            for name in evidence_ids:
                evidence = program.evidence[name]
                if evidence.kind != "api_report" or type(evidence.input) is not dict:
                    return result("workload_mismatch", "Selected API evidence lacks a report workload")
                report_digest = evidence.input.get("report_sha256")
                if (set(evidence.input) != {*WORKLOAD_FIELDS, "report_sha256"}
                        or type(report_digest) is not str or len(report_digest) != 64
                        or any(character not in "0123456789abcdef" for character in report_digest)):
                    return result("workload_mismatch", "API evidence must pin the identified report bytes")
                if any(type(evidence.input.get(key)) is not type(value) or evidence.input.get(key) != value
                       for key, value in workload.items()):
                    return result("workload_mismatch", "Evidence input differs from the complete requested workload")
                if evidence.max_age != criteria["evidence_max_age_seconds"]:
                    return result("criteria_mismatch", "Evidence freshness differs from the requested contract")
            if any(program.reasoning[name].method != API_CONTRACT.identifier for name in reasoning_ids):
                return result("criteria_mismatch", "Selected API claim uses another reasoning method")
            output = requirements["claim_outputs"][plan["claim"]]
            direct_routes = [program.arguments[name] for name in plan["dependencies"]["arguments"]
                             if program.arguments[name].conclusion == plan["claim"]]
            if not direct_routes or any(not any(p.path == output and p.operator == "==" and p.expected is True
                                               for p in program.reasoning[argument.reasoning].predicates)
                                        for argument in direct_routes):
                return result("criteria_mismatch", "Selected claim does not bind its requested API method output")
    except (KeyError, ValueError, TypeError):
        return result("criteria_mismatch", "Selected API formal bindings cannot be checked")
    return result()


def validate_answer(anchor, finding, answer):
    """Diagnose a worker answer; never fill its fields or change EAL statuses."""
    task = validate_anchor(anchor)
    errors = []

    def error(path, detail):
        errors.append({"code": "answer_mismatch", "path": path, "detail": detail})

    if type(answer) is not dict or set(answer) != {"task_digest", "finding_id", "claims", "scope", "conclusion", "qualification"}:
        return [{"code": "answer_mismatch", "path": "answer", "detail": "Answer requires exactly its declared fields"}]
    for name in ("task_digest", "finding_id"):
        if answer[name] != finding[name] or (name == "task_digest" and answer[name] != anchor["task_digest"]):
            error(name, "Answer differs from the trusted task finding")
    if answer["qualification"] != "conditional_on_registered_argument":
        error("qualification", "Assessment remains conditional on the registered argument; no proof of prose follows")
    expected_scope = {"context": task.to_dict()["requirements"]["context"], "requirements": task.to_dict()["requirements"]}
    try:
        if canonical_digest(answer["scope"]) != canonical_digest(expected_scope):
            error("scope", "Answer must retain the complete requested context and profile requirements")
    except (TypeError, ValueError):
        error("scope", "Answer scope requires finite JSON")
    rows = finding["assessments"]
    if type(answer["claims"]) is not dict or set(answer["claims"]) != set(task.claims):
        error("claims", "Answer must include exactly the selected claims")
    else:
        for claim in task.claims:
            row = rows.get(claim)
            wanted = {key: None if row is None else row[key] for key in ("assessment_id", "status", "assessed_at")}
            try:
                if type(answer["claims"][claim]) is not dict or canonical_digest(answer["claims"][claim]) != canonical_digest(wanted):
                    error("claims." + claim, "Claim result must match the persisted assessment identity, status and time")
            except (TypeError, ValueError):
                error("claims." + claim, "Claim result requires finite JSON")
    if not finding["check"]["ok"]:
        conclusion = "out_of_scope" if finding["check"]["code"] in {"source_changed", "context_mismatch", "workload_mismatch", "criteria_mismatch"} else "unresolved"
    else:
        conclusion = "assessed" if set(rows) == set(task.claims) else "unresolved"
    if answer["conclusion"] != conclusion:
        error("conclusion", "Conclusion must distinguish existing EAL assessments from scope mismatch and unavailable results")
    return errors
