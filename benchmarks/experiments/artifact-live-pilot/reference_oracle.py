"""Small brief-level reference rules, independent of EAL parsing or evaluation.

These rules are an explicit synthetic task definition. They test whether our
formal source preserves that definition on the twelve selected records. They
do not prove that the task definition corresponds to a physical system, and
they have not undergone a second masked human review.
"""

from __future__ import annotations

import json
import tomllib
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _current(record: dict, now: str) -> bool:
    age = (_time(now) - _time(record["observed_at"])).total_seconds()
    return 0 <= age <= 3600


def _records(root: dict, state: dict) -> dict[str, dict]:
    registry = tomllib.loads((HERE / state["registry"]).read_text(encoding="utf-8"))
    parent = (HERE / root["source"]).parent
    return {name: json.loads((parent / binding["path"]).read_text(encoding="utf-8"))
            for name, binding in registry["tools"].items()}


def brief_status(root: dict, state: dict) -> tuple[str, str]:
    """Resolve the ordinary task rule for one synthetic input state."""
    data = _records(root, state)
    name = root["id"]
    now = root["now"]
    if name == "asset_direction":
        test = data["probe_reader"]["value"]
        aligned = (test.get("unit") == "AH-73" and test.get("drive_firmware") == "r17"
                   and test.get("programme") == "warm_restart" and test.get("direction") == "forward"
                   and test.get("pass") is True and _current(data["probe_reader"], now))
        if not aligned:
            return "unsupported", "The exact AH-73 r17 warm-restart test is unavailable."
        notice = data["alignment_reader"]["value"].get("finding") == "fixture_misalignment"
        if notice and _current(data["alignment_reader"], now):
            return "contested", "A current fixture notice challenges the otherwise matching bench test."
        return "supported", "The exact bench test is present and the fixture notice is inactive."
    if name == "vent_model":
        model = data["model_reader"]["value"]
        equations = model["variables"]
        if (not _current(data["model_reader"], now)
                or model["intervention"] != {"variable": "valve_drive", "value": 5}
                or model["outcome"] != "vent_load"):
            return "unsupported", "The current submitted model does not address the specified intervention."
        output = (equations["vent_load"]["intercept"]
                  + equations["vent_load"]["coefficients"]["valve_drive"] * 5
                  + equations["vent_load"]["noise"])
        status = "supported" if output <= 8 else "unsupported"
        return status, f"The model predicts a vent-load index of {output:g} at valve_drive = 5."
    if name == "calibration_assumption":
        flow = data["flow_reader"]["value"]
        certificate = data["certificate_reader"]["value"]
        if (flow.get("run") != "S6" or flow.get("max_error_pct", float("inf")) > 2
                or certificate.get("rig") != "DX-14" or certificate.get("calibration_id") != "C-88"
                or certificate.get("passed") is not True
                or not _current(data["flow_reader"], now)
                or not _current(data["certificate_reader"], now)):
            return "unsupported", "A matching error record and applicable current reference are required."
        drift = (data["drift_reader"]["value"].get("finding") == "offset_drift"
                 and _current(data["drift_reader"], now))
        separate = (data["crosscheck_reader"]["value"].get("finding") == "separate_reference_agrees"
                    and _current(data["crosscheck_reader"], now))
        if drift and not separate:
            return "contested", "A drift alert challenges the reference assumption without a separate confirming check."
        return "supported", "The reference is current; any drift challenge has a separate response."
    if name == "loop_preconditions":
        step = data["step_reader"]["value"]
        reference = data["reference_reader"]["value"]
        if (step.get("run") != "Q17" or step.get("settling_ms", float("inf")) > 120
                or reference.get("run") != "Q17" or reference.get("reference_id") != "REF-31"
                or reference.get("calibrated") is not True
                or not _current(data["step_reader"], now)
                or not _current(data["reference_reader"], now)):
            return "unsupported", "Both the step test and the current REF-31 record are required."
        inspection = data["wiring_reader"]["value"]
        positions = inspection.get("positions")
        covered_positions = (isinstance(positions, dict)
                             and {"J1", "J2", "J3", "J4"} <= set(positions)
                             and all(positions[key] == "clear" for key in ("J1", "J2", "J3", "J4")))
        if (inspection.get("run") != "Q17" or inspection.get("finding") != "no_reversal_observed"
                or inspection.get("checked_connectors") != 4 or inspection.get("inspection_complete") is not True
                or not covered_positions
                or not _current(data["wiring_reader"], now)):
            return "unsupported", "A repeated J3 with J4 omitted does not establish the specified negative finding."
        return "supported", "Both measurements and the explicit J1–J4 negative inspection qualify."
    raise ValueError(f"Unknown independent root {name!r}")
