"""Replay the fixed checks against all retained coding-session snapshots.

Usage, from the repository root:
    python3 experiments/architecture_extension/replay.py
"""

from __future__ import annotations

import hashlib
import difflib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "materials" / "assessor"))
from assess import assess, digest  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transition_patch(before: Path, after: Path) -> str:
    files = sorted(set(path.relative_to(before) for path in before.rglob("*.py")) |
                   set(path.relative_to(after) for path in after.rglob("*.py")))
    chunks = []
    for rel in files:
        old = (before / rel).read_text().splitlines(keepends=True) if (before / rel).exists() else []
        new = (after / rel).read_text().splitlines(keepends=True) if (after / rel).exists() else []
        chunks.extend(difflib.unified_diff(old, new,
                      fromfile="a/" + str(rel) if old else "/dev/null",
                      tofile="b/" + str(rel) if new else "/dev/null"))
    return "".join(chunks)


def replay() -> int:
    report = json.loads((ROOT / "results" / "observations.json").read_text())
    freeze = json.loads((ROOT / "materials" / "freeze-b.json").read_text())
    errors: list[str] = []
    for rel, expected in freeze["files"].items():
        path = ROOT / rel
        if not path.is_file() or sha(path) != expected:
            errors.append(f"frozen material changed: {rel}")
    if sha(ROOT / "architecture.eal") != sha(ROOT / "materials/prompts/b_eal_context.eal"):
        errors.append("treatment EAL context differs from the pre-run source")
    common = (ROOT / "materials/prompts/b_common.md").read_text()
    control_prompt = (ROOT / "results/exact_prompts/b_no_eal_task.md").read_text()
    treatment_prompt = (ROOT / "results/exact_prompts/b_eal_task.md").read_text()
    treatment_expected = (common + "\n\nThe following EAL/2 architecture argument is in your context. "
                          "Read it as a scoped, defeasible design argument while implementing the feature.\n\n"
                          "```eal\n" + (ROOT / "materials/prompts/b_eal_context.eal").read_text() + "\n```\n")
    if control_prompt != common:
        errors.append("B control prompt differs from frozen common feature brief")
    if treatment_prompt != treatment_expected:
        errors.append("B treatment prompt does not equal common brief plus frozen EAL wrapper")
    if report["provenance"]["baseline_sha256"] != digest(ROOT / "materials/base"):
        errors.append("baseline digest changed")
    a_digest = report["cases"]["a_no_eal"]["source_sha256"]
    for key, kind in (("a_no_eal", "a"), ("b_no_eal", "b"), ("b_eal", "b")):
        recorded = report["cases"][key]
        path = ROOT / "results" / "snapshots" / key
        observed = assess(path, kind)
        if observed["source_sha256"] != recorded["source_sha256"]:
            errors.append(f"source digest changed: {key}")
        for check_id, prior in recorded["checks"].items():
            current = observed["checks"].get(check_id)
            if current is None or current["passed"] != prior["passed"]:
                errors.append(f"check mismatch: {key}/{check_id}")
        prompt = ROOT / "results/exact_prompts" / ("a_task.md" if key == "a_no_eal" else f"{key}_task.md")
        if sha(prompt) != recorded["prompt_sha256"]:
            errors.append(f"prompt digest changed: {key}")
        print(f"{key}: {sum(c['passed'] for c in observed['checks'].values())}/{len(observed['checks'])} checks, "
              f"suite exit {observed['suite_exit']}, source {observed['source_sha256']}")
    for key in ("b_no_eal", "b_eal"):
        if report["cases"][key]["start_sha256"] != a_digest:
            errors.append(f"B start digest differs from A: {key}")
    for key, before in (("a_no_eal", ROOT / "materials/base"),
                        ("b_no_eal", ROOT / "results/snapshots/a_no_eal"),
                        ("b_eal", ROOT / "results/snapshots/a_no_eal")):
        after = ROOT / "results/snapshots" / key
        if transition_patch(before, after) != (ROOT / "results" / f"{key}.patch").read_text():
            errors.append(f"transition patch differs from retained snapshots: {key}")
    if report["cases"]["b_eal"]["prompt_sha256"] != sha(ROOT / "results/exact_prompts/b_eal_task.md"):
        errors.append("treatment prompt mismatch")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Replay matched the retained observations and frozen materials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(replay())
