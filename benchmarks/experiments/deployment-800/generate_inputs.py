#!/usr/bin/env python3
"""Materialise eight new synthetic deployment briefs and independent graph files.

The prose briefs and numerical contracts below are the declared task sampling
frame. Generated files are immutable once written; a change needs a new cohort.
This is single-author synthetic material pending unmasked independent AI review.
"""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
NOW = "2026-09-24T12:00:00Z"
AT = "2026-09-24T11:58:00Z"

# The eight subjects, acquisition contracts and engineering warrants are
# different. They share the controlled three-state support/challenge/answer
# structure required by the registered pilot; this limits generalisation.
ROOTS = [
    dict(id="battery_bus", asset="BB-17", trial="peak-load-P7", claim="bus_margin",
         subject="battery bus", outcome="at least 80 A load, a 45--55 V bus and module temperature at most 70 C",
         primary=[("load_a", ">=", 80), ("bus_voltage_v", ">=", 45),
                  ("bus_voltage_v", "<=", 55), ("module_temp_c", "<=", 70)],
         values={"load_a": 86, "bus_voltage_v": 49.2, "module_temp_c": 67},
         alert="primary_probe_overheat", answer="alarm_from_test_injection", alt_adverse=True),
    dict(id="sql_backup", asset="DB-41", trial="restore-R8", claim="restore_record",
         subject="database restore", outcome="snapshot B481, WAL end B500 and at least 1000 restored rows",
         primary=[("snapshot_lsn", "==", "B481"), ("wal_end_lsn", "==", "B500"),
                  ("restored_rows", ">=", 1000)],
         values={"snapshot_lsn": "B481", "wal_end_lsn": "B500", "restored_rows": 1023},
         alert="primary_wal_segment_missing", answer="independent_replay_index_complete", alt_adverse=False),
    dict(id="robot_estop", asset="RX-12", trial="stop-test-E3", claim="estop_record",
         subject="robot emergency-stop", outcome="stop p99 at most 110 ms, full monitored coverage and no bypass",
         primary=[("stop_p99_ms", "<=", 110), ("coverage_pct", ">=", 100),
                  ("bypass", "==", False)],
         values={"stop_p99_ms": 103, "coverage_pct": 100, "bypass": False},
         alert="primary_interlock_bypass", answer="harness_only_event", alt_adverse=False),
    dict(id="water_dose", asset="WT-63", trial="dose-check-D6", claim="dose_record",
         subject="water-treatment dosing", outcome="pH between 6.5 and 8.5, dose at most 4 mg/L and at least 24 samples",
         primary=[("ph", ">=", 6.5), ("ph", "<=", 8.5),
                  ("dose_mg_l", "<=", 4), ("samples", ">=", 24)],
         values={"ph": 7.1, "dose_mg_l": 3.5, "samples": 24},
         alert="primary_sensor_contamination", answer="independent_lab_assay_agrees", alt_adverse=True),
    dict(id="payment_replay", asset="PAY-21", trial="duplicate-D2", claim="idempotency_record",
         subject="payment replay", outcome="at least four replay attempts on key K9 and no duplicate charge",
         primary=[("retry_key", "==", "K9"), ("attempt_count", ">=", 4),
                  ("duplicate_charges", "==", 0)],
         values={"retry_key": "K9", "attempt_count": 4, "duplicate_charges": 0},
         alert="primary_ledger_divergence", answer="independent_settlement_reconciled", alt_adverse=False),
    dict(id="rail_switch", asset="RS-19", trial="throw-T4", claim="interlock_record",
         subject="rail switch interlock", outcome="throw in at most 3000 ms, clearance at least 12 mm and a locked sensor",
         primary=[("throw_ms", "<=", 3000), ("clearance_mm", ">=", 12),
                  ("locked", "==", True)],
         values={"throw_ms": 2800, "clearance_mm": 15, "locked": True},
         alert="primary_turnout_lock_fault", answer="separate_contact_inspection_clear", alt_adverse=True),
    dict(id="batch_pipeline", asset="ETL-44", trial="batch-B7", claim="batch_record",
         subject="data pipeline", outcome="at least 5000 processed rows, zero reported gaps and matching checkpoint digest",
         primary=[("processed_rows", ">=", 5000), ("gap_count", "==", 0),
                  ("checkpoint_digest", "==", "sha256:a43f")],
         values={"processed_rows": 5000, "gap_count": 0, "checkpoint_digest": "sha256:a43f"},
         alert="primary_downstream_gap", answer="independent_replay_digest_matches", alt_adverse=False),
    dict(id="solar_inverter", asset="INV-31", trial="peak-P5", claim="inverter_record",
         subject="solar inverter", outcome="harmonic distortion at most 5%, temperature at most 85 C and output at least 30 kW",
         primary=[("thd_pct", "<=", 5), ("internal_temp_c", "<=", 85),
                  ("output_kw", ">=", 30)],
         values={"thd_pct": 4.2, "internal_temp_c": 82, "output_kw": 32},
         alert="primary_uncommanded_derating", answer="separate_module_test_clear", alt_adverse=True),
]


def literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _put(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != contents:
        raise ValueError(f"Existing input changed; create a new cohort: {path}")
    path.write_text(contents, encoding="utf-8")


def _json(path: Path, value: object, *, sort_keys: bool = True) -> None:
    _put(path, json.dumps(value, sort_keys=sort_keys, indent=2, ensure_ascii=False) + "\n")


def envelope(tool: str, context: dict, value: dict, at: str = AT) -> dict:
    return {"context": context, "observed_at": at,
            "request": {"context": context, "input": {}, "mode": "deterministic",
                        "tool": tool, "tool_version": "1"}, "value": value}


def source(root: dict) -> str:
    terms = "\n".join(f"  require {literal(field)} {op} {literal(value)};"
                      for field, op, value in root["primary"])
    return f'''language "EAL/2";
environment run_scope {{
  require "asset" == {literal(root["asset"])};
  require "trial" == {literal(root["trial"])};
}}
tool primary_reader {{ version "1"; mode deterministic; }}
tool alternate_reader {{ version "1"; mode deterministic; }}
tool alert_reader {{ version "1"; mode deterministic; }}
tool resolution_reader {{ version "1"; mode deterministic; }}
evidence primary_record {{
  tool primary_reader; kind test; environment run_scope; max_age 900;
  require "asset" == {literal(root["asset"])};
  require "trial" == {literal(root["trial"])};
{terms}
}}
evidence alternate_record {{
  tool alternate_reader; kind independent_check; environment run_scope; max_age 900;
  require "asset" == {literal(root["asset"])};
  require "trial" == {literal(root["trial"])};
  require "finding" == "independent_qualified";
{terms}
}}
evidence current_alert {{
  tool alert_reader; kind monitoring; environment run_scope; max_age 900;
  require "asset" == {literal(root["asset"])};
  require "finding" == {literal(root["alert"])};
}}
evidence independent_resolution {{
  tool resolution_reader; kind independent_check; environment run_scope; max_age 900;
  require "asset" == {literal(root["asset"])};
  require "trial" == {literal(root["trial"])};
  require "finding" == {literal(root["answer"])};
}}
reasoning submitted_record {{
  method "structured/1";
  rationale "The primary and separately acquired alternative tests independently report the stated finite {root['subject']} result. The current alert challenges only the primary test. The resolution answers that primary alert for this trial. Acquisition records alone do not authenticate the physical system.";
}}
claim {root['claim']} {{
  statement "For {root['asset']} trial {root['trial']}, a qualifying primary or independent alternative test reports {root['outcome']}; the primary test is subject to its specific alert and resolution.";
  environment run_scope;
}}
argument positive_route {{ conclusion {root['claim']}; reasoning submitted_record; evidence primary_record; }}
argument independent_route {{ conclusion {root['claim']}; reasoning submitted_record; evidence alternate_record; }}
objection adverse_finding {{ target argument positive_route; evidence current_alert; }}
objection separate_resolution {{ target objection adverse_finding; evidence independent_resolution; }}
'''


def graph(root: dict) -> dict:
    def predicate(tool: str, field: str, op: str, value: object) -> dict:
        if op == "==":
            return {"op": "eq", "record": tool, "path": ["value", field], "value": value}
        return {"op": {"<=": "lte", ">=": "gte"}[op], "record": tool,
                "path": ["value", field], "value": value}
    scope = {field: {"type": "str", "equals": root[field]} for field in ("asset", "trial")}
    def positive(tool: str) -> list[dict]:
        return ([predicate(tool, field, "==", root[field]) for field in ("asset", "trial")]
                + [predicate(tool, field, op, value) for field, op, value in root["primary"]])
    return {
        "schema": "generic-argument-graph/1", "id": root["id"], "claim": root["claim"],
        "scope": scope, "evidence": {tool: {"tool_version": "1", "mode": "deterministic",
                                                "max_age_seconds": 900}
                                  for tool in ("primary_reader", "alternate_reader", "alert_reader", "resolution_reader")},
        "routes": [{"id": "positive_route", "all": positive("primary_reader")},
                   {"id": "independent_route", "all": positive("alternate_reader") + [
                       predicate("alternate_reader", "finding", "==", "independent_qualified")]}],
        "objections": [{"id": root["alert"],
                        "target_route": "positive_route",
                        "when": [predicate("alert_reader", "asset", "==", root["asset"]),
                                 predicate("alert_reader", "finding", "==", root["alert"])],
                        "answers": [{"id": root["answer"],
                                     "all": [predicate("resolution_reader", "asset", "==", root["asset"]),
                                             predicate("resolution_reader", "trial", "==", root["trial"]),
                                             predicate("resolution_reader", "finding", "==", root["answer"])]}]}],
    }


def make() -> dict:
    manifest = {"schema": "eal2-deployment-800-corpus/1", "now": NOW, "roots": [],
                "review_status": "pending_independent_ai_review_unmasked",
                "provenance": "Synthetic, single-author; labels are intended references, not independent adjudication."}
    for root in ROOTS:
        base = HERE / "roots" / root["id"]
        context = {"asset": root["asset"], "trial": root["trial"]}
        _put(base / "source.eal", source(root))
        # The independent comparator's adversarial fixture suite mutates the
        # first declared evidence product; keep the positive route first.
        _json(HERE / "graphs" / f'{root["id"]}.json', graph(root), sort_keys=False)
        states = []
        for state_id, expected, finding, resolution, alternate in (
            ("initial", "supported", "none", "none", "none"),
            ("adverse", "supported" if root["alt_adverse"] else "contested",
             root["alert"], "none", "independent_qualified" if root["alt_adverse"] else "none"),
            ("restored", "supported", root["alert"], root["answer"], "none"),
        ):
            prefix = f"states/{state_id}"
            records = {
                "primary_reader": envelope("primary_reader", context,
                                           {"asset": root["asset"], "trial": root["trial"], **root["values"]}),
                "alternate_reader": envelope("alternate_reader", context,
                                              {"asset": root["asset"], "trial": root["trial"],
                                               "finding": alternate, **root["values"]}),
                "alert_reader": envelope("alert_reader", context,
                                         {"asset": root["asset"], "finding": finding}),
                "resolution_reader": envelope("resolution_reader", context,
                                              {"asset": root["asset"], "trial": root["trial"],
                                               "finding": resolution}),
            }
            registry = []
            for tool, record in records.items():
                filename = f"{prefix}/{tool}.json"
                _json(base / filename, record)
                registry.append(f'[tools.{tool}]\nkind = "json_file"\nversion = "1"\n'
                                f'mode = "deterministic"\npath = "{filename}"\n')
            _put(base / f"{prefix}.toml", "\n".join(registry))
            states.append({"id": state_id, "registry": f'roots/{root["id"]}/{prefix}.toml',
                           "checker_evidence": {tool: f'roots/{root["id"]}/{prefix}/{tool}.json'
                                                for tool in records}, "expected": expected,
                           "review": {"status": "pending_independent_ai_review_unmasked", "reviewers": [],
                                      "rationale": "Declared finite synthetic brief-level expectation."}})
        brief = (f"For the {root['subject']} {root['asset']} in trial {root['trial']}, assess whether a recent "
                 f"primary or independent alternative test reports {root['outcome']}. The alternative "
                 "must contain the same quantitative observations and an 'independent_qualified' finding. "
                 f"A current '{root['alert']}' monitoring finding challenges the primary test only. "
                 f"A separately collected '{root['answer']}' finding for the same asset and trial "
                 "answers that specific primary challenge. A sound independent alternative route "
                 "can still support the claim while the primary route is challenged. "
                 "Every record must identify this asset and trial where declared, use the named "
                 "collector and be no more than 15 minutes old at 12:00 UTC. The question is about "
                 "the submitted finite test, not a guarantee of current physical behaviour. "
                 "Report the claim status and its decisive evidence and qualification.")
        manifest["roots"].append({"id": root["id"], "claim": root["claim"],
                                  "brief": brief, "context": context, "now": NOW,
                                  "source": f'roots/{root["id"]}/source.eal',
                                  "graph": f'graphs/{root["id"]}.json',
                                  "states": states, "family": root["subject"],
                                  "genealogy": "Eight domain parameterisations of a shared two-route, one-targeted-alert graph generator",
                                  "effort": {"status": "unmeasured"}})
    _json(HERE / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(f"Materialised {len(make()['roots'])} synthetic roots")
