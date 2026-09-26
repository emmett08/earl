"""Compare EAL/2 and an independently authored typed rule evaluator.

The cases are synthetic development fixtures. They are paired controls for
implementation behaviour, not independent samples of engineering work.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import time
from typing import Callable

from experiments.composition_revision import baseline


ARMS = ("eal", "typed_rule")
SCHEMA = "eal2-composition-revision/1"
STATUSES = {"supported", "unsupported", "contested", "out_of_scope", "unavailable"}


def _bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_bytes(value))


def _validate(fixture: dict) -> list[dict]:
    if not isinstance(fixture, dict) or fixture.get("schema") != SCHEMA:
        raise ValueError("Unknown composition fixture contract")
    cases = fixture.get("cases")
    if (not isinstance(cases, list) or not cases or not isinstance(fixture.get("context"), dict)
            or not isinstance(fixture.get("base_time"), str)):
        raise ValueError("The fixture must have at least one case")
    previous: dict[str, dict] = {}
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", case["id"])
                or case["id"] in previous
                or not isinstance(case.get("observations"), dict)
                or set(case["observations"]) - set(baseline.EVIDENCE)
                or not isinstance(case.get("expected"), dict)
                or set(case["expected"]) != set(baseline.CLAIMS)
                or not all(isinstance(name, str) and isinstance(status, str)
                           and status in STATUSES for name, status in case["expected"].items())):
            raise ValueError("Cases need unique IDs, observations and complete expected statuses")
        affected = case.get("affected")
        if (not isinstance(affected, list) or any(not isinstance(name, str) for name in affected)
                or len(set(affected)) != len(affected)
                or any(name not in case["expected"] for name in affected)):
            raise ValueError(f"Invalid affected claims for {case['id']}")
        predecessor = case.get("revision_of")
        if predecessor is None:
            if affected:
                raise ValueError("An initial case cannot specify changed claims")
        else:
            if predecessor not in previous:
                raise ValueError(f"Revision {case['id']} must follow its predecessor")
            before = previous[predecessor]["expected"]
            if set(before) != set(case["expected"]):
                raise ValueError("A revision must specify the same claims as its predecessor")
            changed = {name for name in before if before[name] != case["expected"][name]}
            if set(affected) != changed:
                raise ValueError(f"Independent affected set disagrees with expected statuses in {case['id']}")
        previous[case["id"]] = case
    return cases


def freeze_fixture(path: Path, output: Path) -> dict:
    """Retain the exact independently supplied case bytes before execution."""
    raw = path.read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Case fixture exceeds 16 MiB")
    fixture = json.loads(raw)
    cases = _validate(fixture)
    manifest = {"schema": "eal2-composition-freeze/1",
                "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                "canonical_fixture_sha256": _digest(fixture),
                "cases": [{"id": case["id"], "case_sha256": _digest(case)} for case in cases]}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(_bytes(manifest).decode("utf-8"))
    return manifest


def load_frozen_fixture(path: Path, manifest_path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Case fixture exceeds 16 MiB")
    fixture = json.loads(raw)
    cases = _validate(fixture)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != "eal2-composition-freeze/1"
            or manifest.get("fixture_sha256") != hashlib.sha256(raw).hexdigest()
            or manifest.get("canonical_fixture_sha256") != _digest(fixture)
            or manifest.get("cases") != [{"id": case["id"], "case_sha256": _digest(case)}
                                         for case in cases]):
        raise ValueError("Case fixture differs from its frozen manifest")
    return fixture, manifest


def _trial(case: dict, arm: str, evaluator: Callable[[dict, str], dict]) -> dict:
    row = {"case_id": case["id"], "arm": arm, "case_sha256": _digest(case),
           "state": "failed", "claims": None, "elapsed_seconds": None}
    started = time.perf_counter()
    try:
        response = evaluator(case, arm)
        claims = response["claims"]
        seconds = response["elapsed_seconds"]
        if (not isinstance(claims, dict) or
                any(claims.get(name) not in STATUSES for name in case["expected"]) or
                type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0 or
                not isinstance(response.get("source_digest"), str) or
                len(response["source_digest"]) != 64):
            raise ValueError("Evaluator returned an incomplete or invalid assessment")
        row.update(state="complete", claims=claims, evaluator_seconds=seconds,
                   source_digest=response["source_digest"],
                   argument_statuses=response.get("argument_statuses", {}),
                   evidence_statuses=response.get("evidence_statuses", {}))
    except Exception as exc:
        row["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        row["attempt_seconds"] = time.perf_counter() - started
        if row["state"] == "complete":
            row["elapsed_seconds"] = row["attempt_seconds"]
    return row


def summarise(fixture: dict, trials: list[dict]) -> dict:
    """Score all assigned pairs, including failures, against pre-stated statuses."""
    cases = _validate(fixture)
    lookup = {(row["case_id"], row["arm"]): row for row in trials}
    assignments = {(case["id"], arm) for case in cases for arm in ARMS}
    if len(lookup) != len(trials) or set(lookup) != assignments:
        raise ValueError("Each case needs exactly one retained assignment per arm")
    rows = []
    scores = {}
    for case in cases:
        for arm in ARMS:
            trial = lookup[case["id"], arm]
            if trial["case_sha256"] != _digest(case):
                raise ValueError("Retained assignment does not match its case")
            complete = trial["state"] == "complete"
            actual = trial["claims"] if complete else None
            expected = case["expected"]
            correct = complete and all(actual.get(name) == status for name, status in expected.items())
            false_support = ([name for name, status in expected.items()
                              if actual.get(name) == "supported" and status != "supported"]
                             if complete else [])
            predecessor = case.get("revision_of")
            changed = None
            if predecessor is not None and complete:
                previous = lookup[predecessor, arm]
                if previous["state"] == "complete":
                    changed = sorted(name for name in expected
                                     if actual.get(name) != previous["claims"].get(name))
            affected_correct = changed == sorted(case["affected"]) if changed is not None else None
            rows.append({**trial, "expected": expected, "correct": correct,
                         "false_support_claims": false_support,
                         "expected_affected": sorted(case["affected"]) if predecessor else None,
                         "actual_affected": changed, "affected_correct": affected_correct,
                         "stale_claims": sorted(set(case["affected"]) - set(changed)) if changed is not None else [],
                         "spurious_changes": sorted(set(changed) - set(case["affected"])) if changed is not None else []})
            scores[case["id"], arm] = correct
    by_arm = {arm: [row for row in rows if row["arm"] == arm] for arm in ARMS}
    cells = {}
    for arm, values in by_arm.items():
        measured = [row["elapsed_seconds"] for row in values if row["state"] == "complete"]
        evaluations = [row["evaluator_seconds"] for row in values if row["state"] == "complete"]
        revision_rows = [row for row in values if row["expected_affected"] is not None]
        digests = sorted({row["source_digest"] for row in values if row["state"] == "complete"})
        cells[arm] = {"assigned": len(values), "completed": sum(row["state"] == "complete" for row in values),
                      "failed": sum(row["state"] == "failed" for row in values),
                      "correct": sum(row["correct"] for row in values),
                      "false_support_cases": sum(bool(row["false_support_claims"]) for row in values),
                      "false_support_claims": sum(len(row["false_support_claims"]) for row in values),
                      "revisions_assigned": len(revision_rows),
                      "revisions_correct": sum(row["affected_correct"] is True for row in revision_rows),
                      "revisions_unscored": sum(row["affected_correct"] is None for row in revision_rows),
                      "median_elapsed_seconds_completed": statistics.median(measured) if measured else None,
                      "elapsed_seconds_completed_total": sum(measured),
                      "median_evaluation_seconds_completed": (statistics.median(evaluations)
                                                               if evaluations else None),
                      "source_digests": digests, "source_digest_stable": len(digests) <= 1}
    pairs = Counter((scores[case["id"], "eal"], scores[case["id"], "typed_rule"])
                    for case in cases)
    return {"schema": "eal2-composition-comparison/1", "fixture_sha256": _digest(fixture),
            "assigned_pairs": len(cases), "assigned_trials": len(rows), "cells": cells,
            "paired_correctness": {"both_correct": pairs[True, True],
                                   "eal_only_correct": pairs[True, False],
                                   "typed_rule_only_correct": pairs[False, True],
                                   "both_incorrect": pairs[False, False]},
            "trials": rows, "cost": {"model_tokens": 0, "model_usd": 0.0,
                                      "total_cost_usd": None, "human_authoring_time": None},
            "interpretation": ("Synthetic development cases; outcomes describe this fixture and these implementations. "
                               "Cases and revisions share a common root and are not independent task samples. "
                               "Timing is descriptive of this local execution, including different setup costs. "
                               "No authoring, review, paid model, field or held-out superiority claim follows.")}


def run(output: Path, *, fixture: dict | None = None,
        evaluator: Callable[[dict, str], dict] | None = None,
        external_freeze: dict | None = None, fixture_bytes: bytes | None = None) -> dict:
    if fixture is None or evaluator is None:
        from experiments.composition_revision.study import load_cases, run_arm
        fixture = load_cases() if fixture is None else fixture
        evaluator = run_arm if evaluator is None else evaluator
    cases = _validate(fixture)
    if external_freeze is not None:
        if (fixture_bytes is None or
                external_freeze.get("fixture_sha256") != hashlib.sha256(fixture_bytes).hexdigest() or
                external_freeze.get("canonical_fixture_sha256") != _digest(fixture) or
                json.loads(fixture_bytes) != fixture):
            raise ValueError("External fixture differs from its frozen manifest")
    output.mkdir(parents=True, exist_ok=False)
    (output / "fixture.json").write_bytes(fixture_bytes if fixture_bytes is not None else _bytes(fixture))
    # Alternate first arm to avoid assigning every cold assessment to EAL.
    schedule = [(case, arm) for index, case in enumerate(cases)
                for arm in (ARMS if index % 2 == 0 else ARMS[::-1])]
    manifest = {"schema": "eal2-composition-assignments/1", "fixture_sha256": _digest(fixture),
                "external_freeze": external_freeze,
                "assignments": [{"case_id": case["id"], "arm": arm,
                                 "case_sha256": _digest(case)} for case, arm in schedule]}
    _write(output / "manifest.json", manifest)
    trials = []
    for case, arm in schedule:
        execution_case = {**case, "context": case.get("context", fixture["context"]),
                          "assessed_at": case.get("assessed_at", fixture["base_time"]),
                          "observed_at": case.get("observed_at", fixture["base_time"])}
        trial = _trial(case, arm, lambda _case, _arm: evaluator(execution_case, _arm))
        _write(output / "trials" / case["id"] / f"{arm}.json", trial)
        trials.append(trial)
    summary = summarise(fixture, trials)
    _write(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freezing = commands.add_parser("freeze", help="Freeze external fixture bytes and case hashes before execution")
    freezing.add_argument("--fixture", required=True, type=Path)
    freezing.add_argument("--output", required=True, type=Path)
    running = commands.add_parser("run", help="Execute both arms on every assigned case")
    running.add_argument("--output", required=True, type=Path)
    running.add_argument("--fixture", type=Path, help="Independently selected cases in the same fixture schema")
    running.add_argument("--freeze", type=Path, help="Previously written freeze manifest for external cases")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze_fixture(args.fixture, args.output)
        return
    if bool(args.fixture) != bool(args.freeze):
        parser.error("External execution requires both --fixture and its --freeze manifest")
    if args.fixture:
        fixture, frozen = load_frozen_fixture(args.fixture, args.freeze)
        summary = run(args.output, fixture=fixture, external_freeze=frozen,
                      fixture_bytes=args.fixture.read_bytes())
    else:
        summary = run(args.output)
    for arm, cell in summary["cells"].items():
        print(f"{arm}: {cell['correct']}/{cell['assigned']} exact cases; "
              f"{cell['revisions_correct']}/{cell['revisions_assigned']} affected sets; "
              f"{cell['failed']} failed assignments")
    if any(cell["failed"] or cell["correct"] != cell["assigned"] or
           cell["revisions_correct"] != cell["revisions_assigned"] for cell in summary["cells"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
