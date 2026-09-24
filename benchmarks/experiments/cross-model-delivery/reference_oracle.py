"""Brief-level synthetic decisions, independently of EAL parsing and execution.

The rules below were authored from REFERENCE.md and each manifest brief before
any model outputs. They test source fidelity on these nine selected records;
they do not establish physical truth or independent human adjudication.
"""

from __future__ import annotations

import json
import tomllib
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _recent(envelope: dict, now: str, seconds: int) -> bool:
    age = (_timestamp(now) - _timestamp(envelope["observed_at"])).total_seconds()
    return 0 <= age <= seconds


def _records(root: dict, state: dict) -> dict[str, dict]:
    registry = tomllib.loads((HERE / state["registry"]).read_text(encoding="utf-8"))
    parent = (HERE / root["source"]).parent
    return {
        name: json.loads((parent / binding["path"]).read_text(encoding="utf-8"))
        for name, binding in registry["tools"].items()
    }


def brief_status(root: dict, state: dict) -> tuple[str, str]:
    """Apply the ordinary task rule to an acquisition state."""
    records = _records(root, state)
    now = root["now"]
    if root["id"] == "release_provenance":
        build = records["build_reader"]
        stage = records["stage_reader"]
        b = build["value"]
        s = stage["value"]
        if (not _recent(build, now, 3600) or not _recent(stage, now, 3600)
                or b.get("release") != "PX-42" or b.get("revision") != "b64"
                or b.get("digest") != "sha256:8c4a"
                or b.get("signature_verified") is not True
                or s.get("release") != "PX-42" or s.get("lane") != "West-2"
                or s.get("digest") != "sha256:8c4a"
                or s.get("pull_verified") is not True):
            return "unsupported", "The current signed-build and staged-pull records do not both identify the pinned PX-42 b64 digest."
        return "supported", "Both current records identify the pinned PX-42 b64 digest with their stipulated verification flags."
    if root["id"] == "thermal_soak":
        sample = records["soak_reader"]
        v = sample["value"]
        if not _recent(sample, now, 900):
            return "unsupported", "The qualifying soak log is outside the 15-minute acquisition window."
        if (v.get("rig") != "TC-9" or v.get("run") != "H4"
                or v.get("sensor") != "K2" or v.get("calibration_valid") is not True
                or v.get("peak_c", float("inf")) > 82
                or v.get("dwell_min", float("-inf")) < 30):
            return "unsupported", "The fresh log does not satisfy all stated run, sensor, temperature and dwell conditions."
        return "supported", "The fresh H4 log records K2 calibration, a peak no greater than 82 C and a dwell of at least 30 minutes."
    if root["id"] == "network_failover":
        test = records["failover_reader"]
        v = test["value"]
        qualifies = (_recent(test, now, 1800) and v.get("switch") == "NS-9"
                     and v.get("profile") == "dual_uplink_A"
                     and v.get("switchover_ms", float("inf")) <= 250
                     and v.get("load_pct", float("-inf")) >= 70
                     and v.get("pass") is True)
        if not qualifies:
            return "unsupported", "The specified, current loaded-failover test is not present."
        alert = records["buffer_alert_reader"]
        challenged = (_recent(alert, now, 1800)
                      and alert["value"].get("switch") == "NS-9"
                      and alert["value"].get("finding") == "switch_buffer_overrun")
        if challenged:
            trace = records["packet_trace_reader"]
            answered = (_recent(trace, now, 1800)
                        and trace["value"].get("switch") == "NS-9"
                        and trace["value"].get("profile") == "dual_uplink_A"
                        and trace["value"].get("finding") == "alert_from_test_generator")
            if not answered:
                return "contested", "A current switch-buffer alert challenges the otherwise qualifying loaded-failover record."
            return "supported", "The separate packet trace attributes the recorded alert to the test generator."
        return "supported", "The qualifying failover test has no applicable current switch-buffer alert."
    raise ValueError(f"Unknown synthetic root {root['id']!r}")
