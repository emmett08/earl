"""Independent, bounded JSON graph checker for the 96-call negative-finding pilot.

This checker does not import EAL or consume its AST. The formal graph is a
separately frozen representation of the root brief. It checks envelope identity,
age, context, positive alternatives, a partial counterexample, and calibrated
non-detection. It does not authenticate the synthetic observation producer.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any


def _t(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.utcoffset() is None:
        raise ValueError("timezone required")
    return d


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, dict) or isinstance(b, dict):
        return isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
    if isinstance(a, list) or isinstance(b, list):
        return isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _available(record: Any, name: str, graph: dict, now: str, context: dict) -> bool:
    if not isinstance(record, dict):
        return False
    try:
        request = record["request"]
        age = (_t(now) - _t(record["observed_at"])).total_seconds()
        return (record.get("status", "ok") == "ok" and _eq(record.get("context"), context)
                and _eq(request.get("context"), context) and request.get("tool") == name
                and request.get("tool_version") == "1" and request.get("mode") == "deterministic"
                and _eq(request.get("input"), {}) and 0 <= age <= 3600)
    except (KeyError, ValueError, TypeError):
        return False


def evaluate(graph: dict, records: dict, *, now: str, context: dict,
             required_correction: dict | None = None) -> dict:
    if graph.get("schema") != "negative-revision-equal-graph/1":
        raise ValueError("Unsupported graph schema")
    if not _eq(context, graph["context"]):
        return {"bounded_property_supported": "unsupported", "violating_sample": "unsupported", "qualified_absence": "unsupported"}
    subject, scope, bound = graph["subject"], graph["scope"], Decimal(str(graph["bound"]))
    positives = {}
    for name in graph["positive_routes"]:
        rec = records.get(name)
        v = rec.get("value") if _available(rec, name, graph, now, context) else None
        positives[name] = (isinstance(v, dict) and v.get("passed") is True
                         and v.get("subject") == subject and v.get("scope") == scope
                         and v.get("property") == graph["query"]["property"])
    rec = records.get("trace_reader")
    corrected = (required_correction is None or isinstance(rec,dict)
                 and rec.get("synthetic_correction") == required_correction
                 and rec.get("observed_at") == "2040-01-31T08:25:00Z")
    raw = rec.get("value") if corrected and _available(rec, "trace_reader", graph, now, context) else None
    witness = absence = False
    try:
        interval_ok = (_t(raw["valid_from"]) <= _t("2040-01-31T08:00:00Z")
                       and _t(raw["valid_until"]) >= _t("2040-01-31T09:00:00Z")
                       and _t(raw["valid_from"]) < _t(raw["valid_until"]))
    except (KeyError,ValueError,TypeError):
        interval_ok = False
    if isinstance(raw, dict) and set(raw)=={"schema","method","subject","quantity","unit","scope","valid_from","valid_until","payload"} and interval_ok and raw.get("schema") == "EAL/typed-input/1" and raw.get("method") == "engineering/sampled-negative/1" and raw.get("subject") == subject and raw.get("scope") == scope and raw.get("quantity") == graph["quantity"] and raw.get("unit") == graph["unit"]:
        p = raw.get("payload")
        if isinstance(p, dict) and all(_eq(p.get(k), v) for k,v in graph["query"].items() if k != "mode"):
            samples = p.get("events")
            if isinstance(samples, list) and samples and all(type(x) is dict and set(x) == {"time", "value"} and type(x["time"]) in (int,float) and type(x["value"]) in (int,float) for x in samples):
                times = [Decimal(str(x["time"])) for x in samples]
                if all(0 <= t <= 12 for t in times) and all(a < b for a,b in zip(times,times[1:])):
                    violates = any((Decimal(str(x["value"])) >= bound if graph["query"]["property"]["operator"] == "lt"
                                    else Decimal(str(x["value"])) > bound) for x in samples)
                    witness = p.get("mode") == "counterexample" and violates
                    if p.get("mode") == "non_detection":
                        calibration = p.get("calibration")
                        absence = (not violates and times[0] == 0 and times[-1] == 12
                                   and all(b-a <= 4 for a,b in zip(times,times[1:]))
                                   and isinstance(calibration, dict)
                                   and type(calibration.get("detection_limit")) in (int,float)
                                   and type(calibration.get("sensitivity_lower_bound")) in (int,float)
                                   and 0 <= calibration["detection_limit"] <= graph["query"]["detector_contract"]["maximum_detection_limit"] <= float(bound)
                                   and calibration["sensitivity_lower_bound"] >= graph["query"]["detector_contract"]["minimum_sensitivity"] > 0)
    routes = []
    for name, present in positives.items():
        if not present:
            continue
        attacked = witness and any(o == {"target":name,"premise":"violating_sample"} for o in graph["objections"])
        answered = False
        if attacked:
            for defence in graph.get("defences", []):
                if defence != {"target":name,"evidence":"audit_reader"}:
                    continue
                audit = records.get("audit_reader")
                data = audit.get("value") if _available(audit,"audit_reader",graph,now,context) else None
                answered = (isinstance(data,dict) and data.get("independently_explained") is True
                            and data.get("subject") == subject and data.get("scope") == scope
                            and data.get("sample_time") == 4 and data.get("finding") == "sensor_artifact")
        routes.append("contested" if attacked and not answered else "supported")
    if graph.get("absence_positive_route") and absence:
        routes.append("supported")
    parent = "supported" if "supported" in routes else "contested" if "contested" in routes else "unsupported"
    return {"bounded_property_supported": parent,
            "violating_sample": "supported" if witness else "unsupported",
            "qualified_absence": "supported" if absence else "unsupported"}
