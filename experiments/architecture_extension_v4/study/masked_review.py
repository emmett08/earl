"""Prepare independently masked source-review packets after a completed run.

The release directory has opaque candidate and sequence IDs only. The arm,
block and clone mapping lives in a *separate host-only file* supplied by the
caller. This script never manufactures review judgements.

Example::

    python masked_review.py --results /retained/v4-run \
      --output /review-release --mapping-output /host-only/review-map.json
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
from pathlib import Path
from typing import Any

from runner_capture import copy_source, digest, json_write, tree_digest, tree_entries


HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "systems"
SCHEMA = "architecture-extension-v4/masked-review/1"
STAGES = {"B", "C", "D"}
ARMS = {"P0", "P1", "P2"}
UNMASK = (
    ("treatment-label", re.compile(r"(?<![\w])P[012](?![\w])", re.IGNORECASE)),
    ("eal-treatment-label", re.compile(r"\bEAL\s*/\s*2\b|\bEAL\s+packet\b", re.IGNORECASE)),
    ("experiment-label", re.compile(r"\b(?:assignment|treatment)\s+arm\b|\b(?:plain|formal)\s+(?:evidence|argument)\s+packet\b", re.IGNORECASE)),
    ("host-path", re.compile(r"architecture_extension_v4/study|agent-visible|agent\.jsonl", re.IGNORECASE)),
)

COMMON = {
    "coherent_state": "Identify all writers of the same state and whether a single authority governs the change.",
    "effect_boundary": "Trace irreversible effects, replay identity and failure recovery through the declared boundary.",
    "change_locality": "Name any duplicated business rule that would require coordinated future edits; repeated syntax alone is insufficient.",
    "reachable_paths": "Check whether apparently obsolete code remains reachable through public calls, imports or callbacks.",
}
SYSTEM = {
    "fulfilment": {
        "shipment_and_stock": "Trace allocation, source warehouse and shipment history through the current feature.",
        "payment_and_events": "Trace payment effects and completed-event persistence across retry or partial failure.",
    },
    "entitlement": {
        "seat_ownership": "Trace account-scoped capacity, assignment and historical command identity.",
        "issuer_uncertainty": "At D, inspect whether an issuer timeout can conceal a committed token and how duplicates are excluded.",
    },
    "reservation": {
        "active_interval_index": "Trace half-open interval conflicts against current active bookings under one lock.",
        "bundle_identity": "Trace bundle booking IDs, atomic updates and historical command replay across moves and cancellations.",
    },
}


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _source_leak(source: Path) -> list[str]:
    alerts: list[str] = []
    for row in tree_entries(source):
        relative = row["path"]
        path = source / relative
        if any(pattern.search(relative) for _, pattern in UNMASK):
            alerts.append(f"{relative}: treatment-like filename")
        if row["bytes"] > 1_000_000:
            alerts.append(f"{relative}: unusually large source file needs manual masking review")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            alerts.append(f"{relative}: undecodable source file needs manual masking review")
            continue
        for label, pattern in UNMASK:
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                alerts.append(f"{relative}:{line}: {label}")
    return alerts


def _preflight(results: Path, fixtures: Path, allow_smoke: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    smoke = summary.get("smoke_only") is True
    status = summary.get("status")
    if smoke:
        if not allow_smoke or status != "completed_smoke_only":
            raise ValueError("synthetic smoke run requires --allow-smoke-for-test and completed status")
    elif status != "complete_acquisition":
        raise ValueError("masked review requires a completed acquisition")
    episodes = summary.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("run contains no retained episodes")
    checked = []
    seen = set()
    for row in episodes:
        if not isinstance(row, dict):
            raise ValueError("malformed episode row")
        system, block, clone, stage, arm = (row.get(k) for k in ("system", "block", "clone", "stage", "arm"))
        if system not in SYSTEM or stage not in STAGES or arm not in ARMS or any(
                not isinstance(s, str) or not s or "/" in s or s in {".", ".."}
                for s in (system, block, clone)):
            raise ValueError("malformed system, block, clone, stage or arm")
        key = (block, clone, stage)
        if key in seen:
            raise ValueError(f"duplicate episode identity: {key}")
        seen.add(key)
        episode = results / "blocks" / block / clone / stage
        source = episode / "source"
        baseline = fixtures / system / "source"
        brief = fixtures / system / "features" / f"{stage}.md"
        retained = json.loads((episode / "episode.json").read_text(encoding="utf-8"))
        if any(retained.get(field) != row.get(field) for field in
               ("system", "block", "clone", "arm", "stage", "output_source_tree_sha256")):
            raise ValueError(f"summary and retained episode differ: {key}")
        if not brief.is_file() or brief.is_symlink():
            raise ValueError(f"missing frozen current brief: {system}-{stage}")
        actual = tree_digest(tree_entries(source))
        if actual != row.get("output_source_tree_sha256"):
            raise ValueError(f"candidate source digest mismatch: {key}")
        baseline_sha = tree_digest(tree_entries(baseline))
        initial = json.loads((episode / "input.json").read_text(encoding="utf-8"))
        if initial.get("brief_sha256") != digest(brief):
            raise ValueError(f"current brief differs from retained episode: {key}")
        if stage == "B" and initial.get("source_tree_sha256") != baseline_sha:
            raise ValueError(f"B input differs from frozen baseline: {key}")
        leaks = _source_leak(source)
        if leaks:
            raise ValueError(f"possible candidate-source unmasking in {key}: " + "; ".join(leaks[:12]))
        checked.append({"row": row, "source": source, "baseline": baseline, "brief": brief,
                        "candidate_sha256": actual, "baseline_sha256": baseline_sha})
    # A completed unit is a B→C→D lineage; no arm may be changed mid-sequence.
    lineages: dict[tuple[str, str], set[str]] = {}
    for item in checked:
        row = item["row"]
        key = (row["block"], row["clone"])
        lineages.setdefault(key, set()).add(row["stage"])
        if any(other["row"]["arm"] != row["arm"] or other["row"]["system"] != row["system"]
               for other in checked if (other["row"]["block"], other["row"]["clone"]) == key):
            raise ValueError(f"lineage changed arm or system: {key}")
    if any(stages != STAGES for stages in lineages.values()):
        raise ValueError("incomplete B→C→D lineage cannot be packaged as a completed review")
    return summary, checked


def _blank_case(item: dict[str, Any]) -> dict[str, Any]:
    anchors = {**COMMON, **SYSTEM[item["system"]]}
    return {"candidate_id": item["candidate_id"], "sequence_id": item["sequence_id"],
            "system": item["system"], "stage": item["stage"],
            "source_tree_sha256": item["candidate_sha256"],
            "reviewed_at_utc": None,
            "findings": {name: {"status": None, "locations": [], "mechanism": "",
                                "alternative_reading": "", "severity": None}
                         for name in anchors},
            "additional_findings": [], "overall_architecture_judgement": None,
            "overall_rationale": ""}


def _rubric(system: str) -> str:
    parts = ["# Masked architecture source review", "",
             "Compare candidate/ with baseline/ for the current brief in CURRENT-FEATURE.md. "
             "Treat prior behaviour as cumulative. Record source findings before viewing any behavioural assessment. "
             "Do not infer the intervention from code style or process terminology.", "",
             "For each anchor, set status to `present` (a concern is evidenced), "
             "`absent` (examined, no concern found), or `unresolved`; include precise file/line "
             "locations, a mechanism, a plausible alternative reading, and severity "
             "(`critical`, `major`, `minor`, or null). Preserve uncertainty. "
             "A working test suite alone does not establish architecture quality. "
             "No composite score is computed from these judgements.", "", "## Common anchors", ""]
    for name, description in COMMON.items():
        parts.append(f"- `{name}`: {description}")
    parts += ["", f"## {system.title()} anchors", ""]
    for name, description in SYSTEM[system].items():
        parts.append(f"- `{name}`: {description}")
    parts += ["", "Record any additional concrete concern in `additional_findings`. "
              "Two reviewers work independently. A third reviewer adjudicates only after "
              "both original reports are sealed; original findings remain retained.", ""]
    return "\n".join(parts)


def prepare(results: Path, fixtures: Path, output: Path, mapping_output: Path,
            allow_smoke: bool = False) -> dict[str, Any]:
    results, fixtures, output, mapping_output = (p.resolve() for p in
                                                  (results, fixtures, output, mapping_output))
    if output.exists() or mapping_output.exists():
        raise FileExistsError("review release and host mapping are single-use outputs")
    if _inside(mapping_output, output) or _inside(output, results) or _inside(mapping_output, results):
        raise ValueError("host mapping and release must remain outside run and separate from each other")
    summary, checked = _preflight(results, fixtures, allow_smoke)
    sequences: dict[tuple[str, str], str] = {}
    prepared: list[dict[str, Any]] = []
    for item in checked:
        row = item["row"]
        lineage = (row["block"], row["clone"])
        sequence = sequences.setdefault(lineage, "sequence-" + secrets.token_hex(10))
        prepared.append({**item, "system": row["system"], "stage": row["stage"],
                         "candidate_id": "case-" + secrets.token_hex(12), "sequence_id": sequence})
    secrets.SystemRandom().shuffle(prepared)
    output.mkdir(parents=True)
    mapping_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for reviewer in ("reviewer-1", "reviewer-2"):
            root = output / reviewer
            (root / "packets").mkdir(parents=True)
            for item in prepared:
                package = root / "packets" / item["candidate_id"]
                package.mkdir()
                candidate_sha, _ = copy_source(item["source"], package / "candidate")
                baseline_sha, _ = copy_source(item["baseline"], package / "baseline")
                if (candidate_sha, baseline_sha) != (item["candidate_sha256"], item["baseline_sha256"]):
                    raise RuntimeError("source changed during review release")
                shutil.copyfile(item["brief"], package / "CURRENT-FEATURE.md")
                (package / "RUBRIC.md").write_text(_rubric(item["system"]), encoding="utf-8")
                json_write(package / "case.json", {"schema": SCHEMA,
                                                   "candidate_id": item["candidate_id"],
                                                   "sequence_id": item["sequence_id"],
                                                   "system": item["system"], "stage": item["stage"],
                                                   "source_tree_sha256": candidate_sha,
                                                   "baseline_tree_sha256": baseline_sha,
                                                   "brief_sha256": digest(item["brief"]),
                                                   "smoke_only": summary["smoke_only"]})
            json_write(root / "form.json", {"schema": SCHEMA, "reviewer_id": None,
                                             "sealed_at_utc": None,
                                             "cases": [_blank_case(item) for item in prepared]})
        json_write(output / "adjudication-template.json", {"schema": SCHEMA,
                    "adjudicator_id": None, "sealed_at_utc": None,
                    "reviewer_1_sealed_sha256": None, "reviewer_2_sealed_sha256": None,
                    "cases": [{"candidate_id": item["candidate_id"],
                               "disagreements": [], "resolution": None,
                               "grounds": "", "unresolved": []}
                              for item in prepared]})
        json_write(output / "release.json", {"schema": SCHEMA,
                    "smoke_only": summary["smoke_only"],
                    "reviewers_required": 2, "adjudicator_required_for_disagreement": True,
                    "cases": [{"candidate_id": item["candidate_id"],
                               "sequence_id": item["sequence_id"], "system": item["system"],
                               "stage": item["stage"], "source_tree_sha256": item["candidate_sha256"]}
                              for item in prepared]})
        mapping = {"schema": SCHEMA, "host_only": True,
                   "review_release": str(output), "source_run": str(results),
                   "cases": [{"candidate_id": item["candidate_id"],
                              "sequence_id": item["sequence_id"], "system": item["system"],
                              "stage": item["stage"], "block": item["row"]["block"],
                              "clone": item["row"]["clone"], "arm": item["row"]["arm"],
                              "source_tree_sha256": item["candidate_sha256"]}
                             for item in prepared]}
        json_write(mapping_output, mapping)
        mapping_output.chmod(0o600)
    except Exception:
        shutil.rmtree(output)
        mapping_output.unlink(missing_ok=True)
        raise
    return {"status": "prepared", "cases": len(prepared), "review_release": str(output),
            "mapping_output": str(mapping_output), "smoke_only": summary["smoke_only"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping-output", type=Path, required=True)
    parser.add_argument("--allow-smoke-for-test", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.results, args.fixtures, args.output,
                             args.mapping_output, args.allow_smoke_for_test), sort_keys=True))


if __name__ == "__main__":
    main()
