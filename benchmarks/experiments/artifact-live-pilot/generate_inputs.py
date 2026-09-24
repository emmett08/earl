"""Write fixed, synthetic EAL/2 pilot observations and the private oracle manifest.

The runtime passes a root's brief, source and observation values to the model.
The `expected` entries in the manifest are reserved for scoring and never form
part of a model prompt. This script performs no inference and makes no API calls.
"""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
NOW = "2026-09-24T12:00:00Z"
RECENT = "2026-09-24T11:59:00Z"
STALE = "2026-09-24T10:59:00Z"


def binding(tool: str, filename: str, value: dict, observed_at: str = RECENT):
    return {"tool": tool, "filename": filename, "value": value, "observed_at": observed_at}


def vent_model(gain: float):
    return {
        "variables": {
            "valve_drive": {"intercept": 3, "coefficients": {}, "noise": 0},
            "vent_load": {"intercept": 1, "coefficients": {"valve_drive": gain}, "noise": 0},
        },
        "intervention": {"variable": "valve_drive", "value": 5},
        "outcome": "vent_load",
    }


ROOTS = [
    {
        "id": "asset_direction",
        "brief": "An AH-73 air-handler technician in North-1 needs a bounded judgement about the r17 warm-restart direction bench record. Match the unit, firmware and programme exactly. A fixture-alignment notice directly challenges the bench result; a notice for another matter does not. State the status of the recorded-direction claim and the decisive reason.",
        "claim": "recorded_direction", "context": {"facility": "North-1", "unit": "AH-73"},
        "states": [
            ("matching_record", "supported", [
                binding("probe_reader", "observations/test_ah73.json", {"unit": "AH-73", "drive_firmware": "r17", "programme": "warm_restart", "direction": "forward", "pass": True}),
                binding("alignment_reader", "observations/alignment_none.json", {"unit": "AH-73", "finding": "none"}),
            ]),
            ("different_unit", "unsupported", [
                binding("probe_reader", "observations/test_ah74.json", {"unit": "AH-74", "drive_firmware": "r17", "programme": "warm_restart", "direction": "forward", "pass": True}),
                binding("alignment_reader", "observations/alignment_none.json", {"unit": "AH-73", "finding": "none"}),
            ]),
            ("repeat_ah73", "supported", [
                binding("probe_reader", "observations/test_ah73_repeat.json", {"unit": "AH-73", "drive_firmware": "r17", "programme": "warm_restart", "direction": "forward", "pass": True, "repeat_id": "R2"}),
                binding("alignment_reader", "observations/alignment_none.json", {"unit": "AH-73", "finding": "none"}),
            ]),
        ],
    },
    {
        "id": "vent_model",
        "brief": "A synthetic affine model for vent-controller-6 recipe R5 relates valve_drive to a dimensionless vent_load index. Judge whether intervention valve_drive = 5 predicts vent_load no greater than 8, using the current submitted model and retaining its supplied exogenous noise. Models may be revised between recipient decisions; this is a calculation conditional on the model rather than a test of the hardware. Give the claim status and decisive calculation.",
        "claim": "intervention_within_limit", "context": {"fixture": "vent-controller-6", "recipe": "R5"},
        "states": [
            ("gain_one", "supported", [
                binding("model_reader", "observations/gain_one.json", vent_model(1)),
            ]),
            ("gain_two", "unsupported", [
                binding("model_reader", "observations/gain_two.json", vent_model(2)),
            ]),
            ("gain_one_point_two", "supported", [
                binding("model_reader", "observations/gain_one_point_two.json", vent_model(1.2)),
            ]),
        ],
    },
    {
        "id": "calibration_assumption",
        "brief": "For dosing rig DX-14 run S6, a bench record gives a maximum dosing error and a C-88 characterisation is validated for the assessment interval. A drift alert challenges whether that characterisation applies to this run; a distinct secondary reference can answer the alert. Judge the limited dosing-error claim under the recorded reference assumption. Give its status and the decisive reason.",
        "claim": "bounded_dosing_error", "context": {"rig": "DX-14", "run": "S6"},
        "states": [
            ("initial_characterisation", "supported", [
                binding("flow_reader", "observations/flow.json", {"run": "S6", "max_error_pct": 1.8}),
                binding("certificate_reader", "observations/certificate.json", {"rig": "DX-14", "calibration_id": "C-88", "passed": True}),
                binding("drift_reader", "observations/drift_none.json", {"rig": "DX-14", "finding": "none"}),
                binding("crosscheck_reader", "observations/crosscheck_none.json", {"rig": "DX-14", "finding": "none"}),
            ]),
            ("drift_characterisation", "contested", [
                binding("flow_reader", "observations/flow.json", {"run": "S6", "max_error_pct": 1.8}),
                binding("certificate_reader", "observations/certificate.json", {"rig": "DX-14", "calibration_id": "C-88", "passed": True}),
                binding("drift_reader", "observations/drift_alert.json", {"rig": "DX-14", "finding": "offset_drift"}),
                binding("crosscheck_reader", "observations/crosscheck_none.json", {"rig": "DX-14", "finding": "none"}),
            ]),
            ("separate_characterisation", "supported", [
                binding("flow_reader", "observations/flow.json", {"run": "S6", "max_error_pct": 1.8}),
                binding("certificate_reader", "observations/certificate.json", {"rig": "DX-14", "calibration_id": "C-88", "passed": True}),
                binding("drift_reader", "observations/drift_alert.json", {"rig": "DX-14", "finding": "offset_drift"}),
                binding("crosscheck_reader", "observations/crosscheck_agrees.json", {"rig": "DX-14", "finding": "separate_reference_agrees"}),
            ]),
        ],
    },
    {
        "id": "loop_preconditions",
        "brief": "For hydraulic loop HL-5 run Q17, a provisional continuation decision requires a recorded step settling time no greater than 120 ms, a current REF-31 calibration record and a completed negative inspection explicitly covering distinct positions J1, J2, J3 and J4. A count of four or a completion flag does not establish coverage when one position was inspected twice and another omitted. Judge the joint preconditions from the submitted records and their acquisition times; give the claim status and decisive reason.",
        "claim": "continuation_preconditions", "context": {"loop": "HL-5", "run": "Q17"},
        "states": [
            ("complete_inspection", "supported", [
                binding("step_reader", "observations/step.json", {"run": "Q17", "settling_ms": 109}),
                binding("reference_reader", "observations/reference_recent.json", {"run": "Q17", "reference_id": "REF-31", "calibrated": True}),
                binding("wiring_reader", "observations/inspection_complete.json", {"run": "Q17", "finding": "no_reversal_observed", "checked_connectors": 4, "inspection_complete": True, "positions": {"J1": "clear", "J2": "clear", "J3": "clear", "J4": "clear"}}),
            ]),
            ("partial_inspection", "unsupported", [
                binding("step_reader", "observations/step.json", {"run": "Q17", "settling_ms": 109}),
                binding("reference_reader", "observations/reference_recent.json", {"run": "Q17", "reference_id": "REF-31", "calibrated": True}),
                binding("wiring_reader", "observations/inspection_partial.json", {"run": "Q17", "finding": "no_reversal_observed", "checked_connectors": 4, "inspection_complete": True, "positions": {"J1": "clear", "J2": "clear", "J3": "clear", "J3_repeat": "clear"}}),
            ]),
            ("complete_reinspection", "supported", [
                binding("step_reader", "observations/step.json", {"run": "Q17", "settling_ms": 109}),
                binding("reference_reader", "observations/reference_recent.json", {"run": "Q17", "reference_id": "REF-31", "calibrated": True}),
                binding("wiring_reader", "observations/inspection_repeat.json", {"run": "Q17", "finding": "no_reversal_observed", "checked_connectors": 4, "inspection_complete": True, "positions": {"J1": "clear", "J2": "clear", "J3": "clear", "J4": "clear"}, "inspection_id": "R2"}),
            ]),
        ],
    },
]


def write_json(path: Path, value: dict, *, replace_existing: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != data and not replace_existing:
        raise ValueError(f"Existing fixture would change: {path}")
    path.write_text(data, encoding="utf-8")


def main():
    manifest = {"schema": "eal2-artifact-live-pilot/1", "roots": []}
    for root in ROOTS:
        root_dir = HERE / "roots" / root["id"]
        if not (root_dir / "source.eal").is_file():
            raise FileNotFoundError(root_dir / "source.eal")
        item = {key: root[key] for key in ("id", "brief", "claim", "context")}
        item["source"] = f"roots/{root['id']}/source.eal"
        item["now"] = NOW
        if "method_factory" in root:
            item["method_factory"] = root["method_factory"]
        item["states"] = []
        for name, expected, bindings in root["states"]:
            registry_relative = f"roots/{root['id']}/states/{name}.toml"
            registry = root_dir / "states" / f"{name}.toml"
            registry.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for entry in bindings:
                envelope = {
                    "context": root["context"], "observed_at": entry["observed_at"],
                    "request": {"context": root["context"], "input": {}, "mode": "deterministic",
                                "tool": entry["tool"], "tool_version": "1"},
                    "value": entry["value"],
                }
                write_json(root_dir / entry["filename"], envelope,
                           replace_existing=root["id"] == "loop_preconditions")
                lines.extend([f"[tools.{entry['tool']}]", 'kind = "json_file"',
                              f'path = "{entry["filename"]}"', 'version = "1"',
                              'mode = "deterministic"', ""])
            content = "\n".join(lines)
            if registry.exists() and registry.read_text(encoding="utf-8") != content:
                raise ValueError(f"Existing registry would change: {registry}")
            registry.write_text(content, encoding="utf-8")
            item["states"].append({"id": name, "registry": registry_relative, "expected": expected})
        manifest["roots"].append(item)
    write_json(HERE / "manifest.json", manifest, replace_existing=True)


if __name__ == "__main__":
    main()
