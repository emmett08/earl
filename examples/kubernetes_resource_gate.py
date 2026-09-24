"""Fail-closed host acceptance policy for the synthetic Kubernetes example.

The EAL/2 evaluator operates on supplied authored attacks. This application
boundary additionally requires a complete acquisition of the mandatory attack
reader and coherent trial identity before reporting an accepted operating basis.
It is a fixture-specific policy, not a general Kubernetes or EAL rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import math
from pathlib import Path

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.runtime import acquisition_request
from eal.semantics import parse_time


SOURCE = (Path(__file__).with_name("kubernetes-resource-revision.eal")).read_text(encoding="utf-8")
PROGRAM = parse(SOURCE)
CLAIM = "provisional_operating_basis"
MANDATORY = frozenset(PROGRAM.evidence)
TRIAL_RECORDS = frozenset({"sampled_responses", "sampled_p99", "sampling_manifest",
                           "telemetry_manifest", "scheduler_snapshot", "monitor_manifest",
                           "observed_contention", "rollout_snapshot"})


def _record_errors(name: str, record: object, context: Mapping, now) -> list[str]:
    """Check an imported observation even when its EAL predicate is negative."""
    if not isinstance(record, Mapping):
        return [f"{name}: mandatory acquisition is missing"]
    evidence = PROGRAM.evidence[name]
    tool = PROGRAM.tools[evidence.tool]
    required = {
        "evidence_id": name,
        "source_digest": PROGRAM.source_digest,
        "tool": tool.name,
        "tool_version": tool.version,
        "mode": tool.mode,
        "evidence_kind": evidence.kind,
        "environment": evidence.environment,
        "environment_fingerprint": environment_fingerprint(evidence.environment, context),
        "input_digest": canonical_digest(evidence.input),
        "acquisition_request": acquisition_request(PROGRAM, name, context),
        "status": "ok",
    }
    errors = [f"{name}: {key} does not match the mandatory acquisition"
              for key, expected in required.items() if record.get(key) != expected]
    if not isinstance(record.get("run_id"), str) or not record["run_id"].strip():
        errors.append(f"{name}: missing acquisition run identifier")
    try:
        age = (now - parse_time(record.get("collected_at"))).total_seconds()
        if not 0 <= age <= evidence.max_age:
            errors.append(f"{name}: observation is future dated or stale")
    except (TypeError, ValueError, OverflowError):
        errors.append(f"{name}: invalid observation time")
    try:
        if canonical_digest(record["value"]) != record.get("data_digest"):
            errors.append(f"{name}: observation digest mismatch")
    except (KeyError, ValueError, TypeError, OverflowError):
        errors.append(f"{name}: missing or invalid observation value")
    return errors


def _coherence_errors(records: Mapping, context: Mapping, now) -> list[str]:
    """Require matching trial, target, node, window and completed monitor query."""
    values = {name: records[name]["value"] for name in MANDATORY}
    if any(not isinstance(value, Mapping) for value in values.values()):
        return ["Mandatory observation values must be objects"]
    sample = values["sampling_manifest"]
    trial = sample.get("trial_id")
    start_text, end_text = sample.get("window_start"), sample.get("window_end")
    errors = []
    if not isinstance(trial, str) or not trial.strip():
        errors.append("Trial identifier is missing")
    try:
        start, end = parse_time(start_text), parse_time(end_text)
        if end - start != timedelta(seconds=300) or end > now or (now - end).total_seconds() > 180:
            errors.append("Trial window is not a recent completed 300-second interval")
    except (TypeError, ValueError, OverflowError):
        errors.append("Trial window has invalid timestamps")
    for name in ("telemetry_manifest", "monitor_manifest", "observed_contention"):
        item = values[name]
        if (item.get("trial_id"), item.get("window_start"), item.get("window_end")) != (
                trial, start_text, end_text):
            errors.append(f"{name}: trial identity or window differs from the response sample")
    for name, manifest_name, series_kind in (
        ("sampled_responses", "sampling_manifest", "response_outcomes"),
        ("sampled_p99", "telemetry_manifest", "p99_ms"),
    ):
        details = records[name].get("details")
        identity = details.get("measurement_identity") if isinstance(details, Mapping) else None
        if not isinstance(identity, Mapping):
            errors.append(f"{name}: measurement identity is missing")
            continue
        manifest = values[manifest_name]
        expected = {
            "trial_id": trial,
            "node_uid": context.get("node_uid"),
            "target_pod_uid": context.get("target_pod_uid"),
            "window_start": start_text,
            "window_end": end_text,
            "series_kind": series_kind,
            "series_id": manifest.get("series_id"),
            "payload_digest": canonical_digest(values[name]),
        }
        if not isinstance(expected["series_id"], str) or not expected["series_id"].strip():
            errors.append(f"{manifest_name}: series identifier is missing")
        if manifest.get("payload_digest") != expected["payload_digest"]:
            errors.append(f"{manifest_name}: series payload digest differs from the measured payload")
        if dict(identity) != expected:
            errors.append(f"{name}: measured payload and series identity differ from the trial manifest")
    for name in TRIAL_RECORDS:
        if records[name].get("collected_at") != end_text:
            errors.append(f"{name}: observation time differs from the completed trial endpoint")
    for name in ("rollout_snapshot", "scheduler_snapshot", "monitor_manifest", "observed_contention"):
        if values[name].get("node_uid") != context.get("node_uid"):
            errors.append(f"{name}: node UID differs from the selected target")
        if values[name].get("target_pod_uid") != context.get("target_pod_uid"):
            errors.append(f"{name}: Pod UID differs from the selected target")
    if sample.get("target_pod_uid") != context.get("target_pod_uid"):
        errors.append("Response sample manifest targets a different Pod")
    if values["telemetry_manifest"].get("target_pod_uid") != context.get("target_pod_uid"):
        errors.append("Latency trace manifest targets a different Pod")
    if values["scheduler_snapshot"].get("sampled_at") != end_text:
        errors.append("Scheduler snapshot is from a different trial endpoint")
    monitor = values["monitor_manifest"]
    contention = values["observed_contention"]
    if monitor.get("complete") is not True or monitor.get("query_complete") is not True:
        errors.append("Monitor interval or query is incomplete")
    if contention.get("query_complete") is not True or not isinstance(monitor.get("query_id"), str) or (
            monitor.get("query_id") != contention.get("query_id")):
        errors.append("Contention reader did not complete the same monitor query")
    finding = contention.get("finding")
    request = contention.get("batch_request_milli")
    usage = contention.get("batch_cpu_milli")
    ratio = contention.get("target_throttled_ratio")
    if (finding not in {"none", "co_tenant_cpu_competition"}
            or any(type(value) is not int or value < 0 for value in (request, usage))
            or isinstance(ratio, bool) or not isinstance(ratio, (int, float))
            or not math.isfinite(ratio) or not 0 <= ratio <= 1):
        errors.append("Contention finding or numeric measurements are invalid")
    else:
        qualifies = request <= 200 and usage >= 2500 and ratio >= 0.20
        if (finding == "co_tenant_cpu_competition") != qualifies:
            errors.append("Contention classification contradicts the submitted measurements")
    return errors


def assess_operating_basis(records: Mapping, context: Mapping, now: str) -> dict:
    """Return `accepted` only for complete, coherent evidence and EAL support.

    `accepted` denotes this synthetic application gate's conditional judgement,
    not independently authenticated observations or future service correctness.
    """
    if not isinstance(records, Mapping) or not isinstance(context, Mapping):
        raise ValueError("records and context must be mappings")
    instant = parse_time(now)
    report = evaluate(PROGRAM, records, context=context, now=now)
    raw_status = report.get("claims", {}).get(CLAIM, {}).get("status", "unresolved")
    errors = []
    if not report["valid"]:
        errors.append("EAL source or assessment is invalid")
    for name in sorted(MANDATORY):
        errors.extend(_record_errors(name, records.get(name), context, instant))
        if name != "observed_contention" and report["evidence"].get(name, {}).get("status") != "available":
            errors.append(f"{name}: mandatory positive evidence is unavailable")
    if not errors:
        errors.extend(_coherence_errors(records, context, instant))
    if errors:
        return {"status": "unresolved", "raw_eal_status": raw_status,
                "claim": CLAIM, "reasons": errors, "report": report}
    contention = records["observed_contention"]["value"]["finding"]
    if contention == "co_tenant_cpu_competition" and (
            report["objections"]["batch_cpu_interference"]["status"] != "active"):
        return {"status": "unresolved", "raw_eal_status": raw_status, "claim": CLAIM,
                "reasons": ["Qualifying contention did not activate the declared objection"], "report": report}
    if contention == "none" and report["objections"]["batch_cpu_interference"]["status"] != "inactive":
        return {"status": "unresolved", "raw_eal_status": raw_status, "claim": CLAIM,
                "reasons": ["Nonfinding disagrees with the declared objection status"], "report": report}
    status = {"supported": "accepted", "contested": "contested", "unsupported": "unsupported",
              "out_of_scope": "unresolved"}.get(raw_status, "unresolved")
    return {"status": status, "raw_eal_status": raw_status, "claim": CLAIM,
            "reasons": ["Mandatory observations and trial identity checked; EAL conclusion is " + raw_status],
            "report": report}
