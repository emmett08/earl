"""Materialise the fixed prospective synthetic inputs without making API calls.

The expected decisions were recorded in REFERENCE.md and reference_oracle.py
before source validation or model responses. Existing differing inputs abort.
"""

from __future__ import annotations

import json
from pathlib import Path

from reference_oracle import brief_status


HERE = Path(__file__).resolve().parent
NOW = "2026-09-24T12:00:00Z"


def entry(tool: str, filename: str, value: dict, at: str = "2026-09-24T11:58:00Z") -> dict:
    return {"tool": tool, "filename": filename, "value": value, "observed_at": at}


ROOTS = [
    {
        "id": "release_provenance", "claim": "stage_matches_build",
        "context": {"release": "PX-42", "lane": "West-2"},
        "brief": "The PX-42 b64 candidate is pinned to digest sha256:8c4a for the West-2 staging lane. Judge whether the current signed-build record and staged-pull record both identify that exact candidate, with their respective verification flags true. Each record must be acquired within one hour of 12:00 UTC. Treat a differing digest as a mismatch even if the staged item is labelled PX-42. The judgement concerns submitted records, not an independently authenticated deployment. Give the claim status and decisive reason.",
        "states": [
            ("matching_stage", "supported", [
                entry("build_reader", "observations/build_b64.json", {"release": "PX-42", "revision": "b64", "digest": "sha256:8c4a", "signature_verified": True}),
                entry("stage_reader", "observations/stage_match.json", {"release": "PX-42", "lane": "West-2", "digest": "sha256:8c4a", "pull_verified": True}),
            ]),
            ("digest_mismatch", "unsupported", [
                entry("build_reader", "observations/build_b64.json", {"release": "PX-42", "revision": "b64", "digest": "sha256:8c4a", "signature_verified": True}),
                entry("stage_reader", "observations/stage_other_digest.json", {"release": "PX-42", "lane": "West-2", "digest": "sha256:fb90", "pull_verified": True}),
            ]),
            ("matching_repull", "supported", [
                entry("build_reader", "observations/build_b64.json", {"release": "PX-42", "revision": "b64", "digest": "sha256:8c4a", "signature_verified": True}),
                entry("stage_reader", "observations/stage_repull.json", {"release": "PX-42", "lane": "West-2", "digest": "sha256:8c4a", "pull_verified": True, "pull_id": "R2"}, at="2026-09-24T11:59:00Z"),
            ]),
        ],
        "tamper": [
            ("wrong_build_revision", "unsupported", [
                entry("build_reader", "observations/build_b65.json", {"release": "PX-42", "revision": "b65", "digest": "sha256:8c4a", "signature_verified": True}),
                entry("stage_reader", "observations/stage_match.json", {"release": "PX-42", "lane": "West-2", "digest": "sha256:8c4a", "pull_verified": True}),
            ]),
        ],
    },
    {
        "id": "thermal_soak", "claim": "soak_preconditions",
        "context": {"rig": "TC-9", "run": "H4"},
        "brief": "For TC-9 run H4, judge whether the submitted K2 thermal-soak log reports a valid sensor calibration, a peak no greater than 82 C and a dwell at least 30 minutes. The log must have been acquired no more than 15 minutes before 12:00 UTC; a previously qualifying but stale record does not establish the current recorded preconditions. This judgement concerns the submitted log, not a physical cycle independently verified. Give the status and decisive reason.",
        "states": [
            ("recent_qualifying", "supported", [
                entry("soak_reader", "observations/soak_recent.json", {"rig": "TC-9", "run": "H4", "sensor": "K2", "calibration_valid": True, "peak_c": 79, "dwell_min": 34}, at="2026-09-24T11:53:00Z"),
            ]),
            ("stale_qualifying", "unsupported", [
                entry("soak_reader", "observations/soak_stale.json", {"rig": "TC-9", "run": "H4", "sensor": "K2", "calibration_valid": True, "peak_c": 79, "dwell_min": 34}, at="2026-09-24T11:40:00Z"),
            ]),
            ("fresh_repeat", "supported", [
                entry("soak_reader", "observations/soak_repeat.json", {"rig": "TC-9", "run": "H4", "sensor": "K2", "calibration_valid": True, "peak_c": 80, "dwell_min": 31, "repeat_id": "R2"}, at="2026-09-24T11:58:00Z"),
            ]),
        ],
        "tamper": [
            ("future_timestamp", "unsupported", [
                entry("soak_reader", "observations/soak_future.json", {"rig": "TC-9", "run": "H4", "sensor": "K2", "calibration_valid": True, "peak_c": 79, "dwell_min": 34}, at="2026-09-24T12:01:00Z"),
            ]),
        ],
    },
    {
        "id": "network_failover", "claim": "bounded_failover",
        "context": {"switch": "NS-9", "profile": "dual_uplink_A"},
        "brief": "For switch NS-9 under profile dual_uplink_A, judge the bounded submitted failover claim from a current passing loaded test: load at least 70 percent and switchover no more than 250 ms. Test and alert records must be acquired within 30 minutes of 12:00 UTC. A current NS-9 switch-buffer overrun alert challenges the otherwise qualifying test. A separate current packet trace for the same profile attributing that alert to the test generator answers this specific challenge. A trace for another profile does not. Give the status and decisive reason, limited to the records.",
        "states": [
            ("qualifying_test", "supported", [
                entry("failover_reader", "observations/test.json", {"switch": "NS-9", "profile": "dual_uplink_A", "switchover_ms": 187, "load_pct": 72, "pass": True}),
                entry("buffer_alert_reader", "observations/alert_none.json", {"switch": "NS-9", "finding": "none"}),
                entry("packet_trace_reader", "observations/trace_none.json", {"switch": "NS-9", "profile": "dual_uplink_A", "finding": "none"}),
            ]),
            ("buffer_challenge", "contested", [
                entry("failover_reader", "observations/test.json", {"switch": "NS-9", "profile": "dual_uplink_A", "switchover_ms": 187, "load_pct": 72, "pass": True}),
                entry("buffer_alert_reader", "observations/alert_overrun.json", {"switch": "NS-9", "finding": "switch_buffer_overrun"}),
                entry("packet_trace_reader", "observations/trace_none.json", {"switch": "NS-9", "profile": "dual_uplink_A", "finding": "none"}),
            ]),
            ("separate_trace", "supported", [
                entry("failover_reader", "observations/test.json", {"switch": "NS-9", "profile": "dual_uplink_A", "switchover_ms": 187, "load_pct": 72, "pass": True}),
                entry("buffer_alert_reader", "observations/alert_overrun.json", {"switch": "NS-9", "finding": "switch_buffer_overrun"}),
                entry("packet_trace_reader", "observations/trace_generator.json", {"switch": "NS-9", "profile": "dual_uplink_A", "finding": "alert_from_test_generator"}, at="2026-09-24T11:59:00Z"),
            ]),
        ],
        "tamper": [
            ("unrelated_trace", "contested", [
                entry("failover_reader", "observations/test.json", {"switch": "NS-9", "profile": "dual_uplink_A", "switchover_ms": 187, "load_pct": 72, "pass": True}),
                entry("buffer_alert_reader", "observations/alert_overrun.json", {"switch": "NS-9", "finding": "switch_buffer_overrun"}),
                entry("packet_trace_reader", "observations/trace_other_profile.json", {"switch": "NS-9", "profile": "single_uplink_B", "finding": "alert_from_test_generator"}, at="2026-09-24T11:59:00Z"),
            ]),
            ("stale_alert", "supported", [
                entry("failover_reader", "observations/test.json", {"switch": "NS-9", "profile": "dual_uplink_A", "switchover_ms": 187, "load_pct": 72, "pass": True}),
                entry("buffer_alert_reader", "observations/alert_stale.json", {"switch": "NS-9", "finding": "switch_buffer_overrun"}, at="2026-09-24T11:20:00Z"),
                entry("packet_trace_reader", "observations/trace_none.json", {"switch": "NS-9", "profile": "dual_uplink_A", "finding": "none"}),
            ]),
            ("stale_answer", "contested", [
                entry("failover_reader", "observations/test.json", {"switch": "NS-9", "profile": "dual_uplink_A", "switchover_ms": 187, "load_pct": 72, "pass": True}),
                entry("buffer_alert_reader", "observations/alert_overrun.json", {"switch": "NS-9", "finding": "switch_buffer_overrun"}),
                entry("packet_trace_reader", "observations/trace_stale.json", {"switch": "NS-9", "profile": "dual_uplink_A", "finding": "alert_from_test_generator"}, at="2026-09-24T11:20:00Z"),
            ]),
        ],
    },
]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"Refusing to overwrite differing frozen fixture {path}")
    path.write_text(content, encoding="utf-8")


def _json(path: Path, obj: dict) -> None:
    _write(path, json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def _state(root: dict, name: str, expected: str, bindings: list[dict]) -> dict:
    root_dir = HERE / "roots" / root["id"]
    lines = []
    paths = {}
    for item in bindings:
        envelope = {
            "context": root["context"], "observed_at": item["observed_at"],
            "request": {"context": root["context"], "input": {}, "mode": "deterministic",
                        "tool": item["tool"], "tool_version": "1"},
            "value": item["value"],
        }
        _json(root_dir / item["filename"], envelope)
        paths[item["tool"]] = f"roots/{root['id']}/{item['filename']}"
        lines.extend([f"[tools.{item['tool']}]", 'kind = "json_file"',
                      f'path = "{item["filename"]}"', 'version = "1"',
                      'mode = "deterministic"', ""])
    relative = f"roots/{root['id']}/states/{name}.toml"
    _write(HERE / relative, "\n".join(lines))
    return {"id": name, "expected": expected, "registry": relative,
            "checker_evidence": paths,
            "review": {"status": "pending_independent_human_review", "reviewers": [],
                       "adjudicated_at": None, "scope": "Synthetic submitted records at the fixed assessment time",
                       "rationale": ""}}


def main() -> None:
    manifest = {
        "schema": "eal2-cross-model-delivery/1",
        "cohort_status": "developmental_unreviewed",
        "external_review_required_before_confirmatory_calls": True,
        "effort": {"status": "unmeasured", "common": None, "arms": {}},
        "roots": [],
    }
    for root in ROOTS:
        source = HERE / "roots" / root["id"] / "source.eal"
        if not source.exists():
            raise FileNotFoundError(source)
        item = {key: root[key] for key in ("id", "brief", "claim", "context")}
        item.update({"now": NOW, "source": f"roots/{root['id']}/source.eal",
                     "graph": f"benchmarks/equal_checker_graphs/{root['id']}.json",
                     "states": [], "tamper": []})
        for name, expected, bindings in root["states"]:
            state = _state(root, name, expected, bindings)
            actual, reason = brief_status(item, state)
            assert actual == expected
            state["review"]["rationale"] = reason
            item["states"].append(state)
        for name, expected, bindings in root["tamper"]:
            tamper = _state(root, name, expected, bindings)
            actual, reason = brief_status(item, tamper)
            assert actual == expected
            tamper["review"]["rationale"] = reason
            tamper["kind"] = {
                "wrong_build_revision": "wrong_revision",
                "future_timestamp": "future_acquisition",
                "unrelated_trace": "wrong_profile",
                "stale_alert": "stale_optional_objection",
                "stale_answer": "stale_optional_answer",
            }[name]
            item["tamper"].append(tamper)
        manifest["roots"].append(item)
    _json(HERE / "manifest.json", manifest)


if __name__ == "__main__":
    main()
