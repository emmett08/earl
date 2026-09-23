#!/usr/bin/env python3
"""Exercise EAL/2 eligibility and reasoning switches from exposed task fixtures.

These cases were selected after seeing model failures. They are a deterministic
developmental intervention, not new model trials or a population estimate.
The expected statuses below are fixed independently of interpreter execution.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eal.benchmark import load_suite, prepare_task, task_inputs

SUITE = ROOT / "benchmarks/engineering-v2/suite.json"
OUTPUT = ROOT / "benchmarks/results/2026-09-23-evidence-mechanisms/switches.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run() -> dict:
    tasks = {t["id"]: t for t in load_suite(SUITE)["tasks"]}
    names = ("defence-cannot-ground-itself", "registered-rms-wrong-origin",
             "sampled-negative-finding")
    originals = {name: task_inputs(tasks[name], SUITE.parent) for name in names}
    circular, rms, negative = (originals[name] for name in names)

    independent = deepcopy(circular)
    old = "objection instrument_defence { target objection response_challenge; premises response_supported; }"
    new = "objection instrument_defence { target objection response_challenge; premises instrument_fault; }"
    assert circular["source"].count(old) == 1
    independent["source"] = circular["source"].replace(old, new)

    bound = deepcopy(rms)
    assert bound["observations"]["vibration_record"]["value"]["payload"]["origin"] == 0.1
    bound["observations"]["vibration_record"]["value"]["payload"]["origin"] = 0
    no_violation = deepcopy(negative)
    events = no_violation["observations"]["sampled_record"]["value"]["payload"]["events"]
    assert [e["value"] for e in events] == [0.5, 0.6, 1.2, 0.7]
    events[2]["value"] = 0.8

    other_assembly = deepcopy(independent)
    for record in other_assembly["observations"].values():
        assert record["context"]["assembly"] == "regulator-7"
        record["context"]["assembly"] = "other-assembly"
    expired = deepcopy(independent)
    for record in expired["observations"].values():
        record["observed_at"] = "2040-01-31T07:00:00Z"

    # Pairs hold the indicated values or records fixed and alter one feature.
    cases = [
        ("circular_defence", "cycle", names[0], circular,
         {"response_supported": "contested", "instrument_fault": "supported"}),
        ("circular_defence", "independent_premise", names[0], independent,
         {"response_supported": "supported", "instrument_fault": "supported"}),
        ("origin_binding", "wrong_origin", names[1], rms,
         {"vibration_within_limit": "unsupported"}),
        ("origin_binding", "matched_origin", names[1], bound,
         {"vibration_within_limit": "supported"}),
        ("negative_proposition", "violation", names[2], negative,
         {"sampled_property_violated": "supported"}),
        ("negative_proposition", "no_violation", names[2], no_violation,
         {"sampled_property_violated": "unsupported"}),
        ("assembly_scope", "matched_assembly", names[0], independent,
         {"response_supported": "supported", "instrument_fault": "supported"}),
        ("assembly_scope", "other_assembly", names[0], other_assembly,
         {"response_supported": "unsupported", "instrument_fault": "unsupported"}),
        ("freshness", "fresh", names[0], independent,
         {"response_supported": "supported", "instrument_fault": "supported"}),
        ("freshness", "expired", names[0], expired,
         {"response_supported": "unsupported", "instrument_fault": "unsupported"}),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix="eal-evidence-switches-") as tmp:
        for index, (pair, variant, template, inp, expected) in enumerate(cases):
            root = Path(tmp) / str(index)
            root.mkdir()
            (root / "source.eal").write_text(inp["source"])
            (root / "observations.json").write_text(json.dumps(inp["observations"], sort_keys=True))
            task = {**tasks[template], "source": "source.eal", "observations": "observations.json"}
            service, prepared = prepare_task(task, root, root / "runtime")
            validation = service.validate(prepared["source"])
            if not validation["valid"]:
                raise ValueError((pair, variant, validation))
            collection = service.collect(prepared["source"], prepared["context"])
            assessment = service.reason(prepared["source"], prepared["context"],
                                        collection["collection_id"], prepared["now"])
            actual = {name: assessment["claims"][name]["status"] for name in expected}
            rows.append({"pair": pair, "variant": variant, "fixture": template,
                         "source_sha256": sha(inp["source"].encode()),
                         "observations_sha256": sha(json.dumps(inp["observations"], sort_keys=True).encode()),
                         "expected": expected, "actual": actual, "passes_oracle": actual == expected})
    pairs = {name: [r for r in rows if r["pair"] == name]
             for name in {r["pair"] for r in rows}}
    assert len(rows) == 10 and all(len(group) == 2 for group in pairs.values())
    return {"schema": "EAL/evidence-switches-result/1", "study_type": "exploratory-developmental",
            "suite_sha256": sha(SUITE.read_bytes()), "cases": rows,
            "passed": sum(r["passes_oracle"] for r in rows), "total": len(rows),
            "switches": {name: [r["actual"] for r in group] for name, group in sorted(pairs.items())},
            "interpretation": "Deterministic EAL/2 status changes on exposed synthetic fixtures. No model response, provenance authentication, generalisation or EAL-specific advantage over an equivalently equipped checker is measured."}


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to replace retained result: {OUTPUT}")
    result = run()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"],
                      "switches": result["switches"], "output": str(OUTPUT)}, indent=2))
    if result["passed"] != result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
