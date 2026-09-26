"""Run finite, no-model argument semantics and changing-evidence controls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse


HERE = Path(__file__).resolve().parent


def _observation(program, name: str, value: dict, context: dict, instant: str) -> dict:
    declaration = program.evidence[name]
    tool = program.tools[declaration.tool]
    acquisition = {"tool": tool.name, "tool_version": tool.version,
                   "input": declaration.input, "context": context}
    request = {"evidence_id": name, "environment": declaration.environment, **acquisition}
    return {"evidence_id": name, "source_digest": program.source_digest,
            "tool": tool.name, "tool_version": tool.version, "tool_binding_digest": "0" * 64,
            "evidence_kind": declaration.kind, "environment": declaration.environment,
            "environment_fingerprint": environment_fingerprint(declaration.environment, context),
            "input_digest": canonical_digest(declaration.input), "input": declaration.input,
            "context": context, "acquisition_request": acquisition,
            "acquisition_request_digest": canonical_digest(acquisition),
            "request_digest": canonical_digest(request), "collected_at": instant,
            "run_id": "fixture-" + name, "status": "ok", "value": value,
            "data_digest": canonical_digest(value)}


def run(output: Path) -> dict:
    """Retain every assigned control and independently stated expected status."""
    output.mkdir(parents=True, exist_ok=False)
    source = (HERE / "composition.eal").read_text()
    fixture_bytes = (HERE / "composition-cases.json").read_bytes()
    fixture = json.loads(fixture_bytes)
    if fixture["schema"] != "eal-api-composition-controls/1":
        raise ValueError("Unrecognised composition control contract")
    program = parse(source)
    observed_at = fixture["assessed_at"]
    rows = []
    for case in fixture["cases"]:
        context = case.get("context", fixture["context"])
        records = {name: _observation(program, name, value, fixture["context"], observed_at)
                   for name, value in case["observations"].items()}
        started = time.monotonic()
        assessment = evaluate(program, records, now=case.get("assessed_at", observed_at), context=context)
        seconds = time.monotonic() - started
        actual = {name: assessment["claims"][name]["status"] for name in case["expected"]}
        rows.append({"id": case["id"], "expected": case["expected"], "actual": actual,
                     "correct": actual == case["expected"], "seconds": seconds,
                     "source_digest": program.source_digest,
                     "evidence_statuses": {name: item["status"] for name, item in assessment["evidence"].items()},
                     "argument_statuses": {name: item["status"] for name, item in assessment["arguments"].items()}})
    result = {"schema": "eal-api-composition-result/1", "source_digest": program.source_digest,
              "case_fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
              "assigned": len(rows), "correct": sum(row["correct"] for row in rows), "trials": rows,
              "scope": "Finite synthetic bench semantics; no model or empirical performance inference."}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.output)
    print(f"{report['correct']}/{report['assigned']} semantic controls matched")
    if report["correct"] != report["assigned"]:
        raise SystemExit(1)
