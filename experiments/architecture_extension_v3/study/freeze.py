"""Create and verify a pre-run SHA-256 manifest and random clone allocation.

Run `create` only after the v3 host, EAL source, tool bindings and workflow
stabilise, and before *any* v3 coding output exists. The command refuses to
overwrite either allocation or manifest. Run `verify` before every session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


STUDY = Path(__file__).resolve().parent
REPO = STUDY.parents[2]
V3 = STUDY.parent
BASE = REPO / "experiments/architecture_extension_v2/results/snapshots/a"
V2_PROBE = REPO / "experiments/architecture_extension_v2/materials/assessor/probe.py"
V2_COMPLEXITY = REPO / "experiments/architecture_extension_v2/metrics/cognitive_complexity.py"
MANIFEST = STUDY / "freeze.json"
ALLOCATION = STUDY / "allocation.json"
REQUIRED = (
    V3 / "host.py",
    V3 / "snapshot_probe.py",
    V3 / "argument.eal",
    V3 / "tool.toml",
    REPO / ".github/workflows/architecture-extension-v3.yml",
    V2_PROBE,
    V2_COMPLEXITY,
    STUDY / "PROTOCOL.md",
    STUDY / "task-bank.json",
    STUDY / "assess.py",
    REPO / "grammar/EAL.g4",
    REPO / "pyproject.toml",
)


def tracked_inputs() -> list[Path]:
    for path in REQUIRED:
        if not path.is_file():
            raise RuntimeError(f"required pre-run input is missing: {path}")
    if not ALLOCATION.is_file():
        raise RuntimeError("allocation.json must be created before computing the manifest")
    paths: set[Path] = set(REQUIRED)
    paths.update(
        p for p in STUDY.rglob("*") if p.is_file() and p.name != "freeze.json"
        and not any(part in {"__pycache__", ".pytest_cache"} for part in p.relative_to(STUDY).parts)
        and p.suffix in {".py", ".md", ".json", ".toml", ".eal"}
    )
    paths.update(
        p for p in V3.rglob("*") if p.is_file() and STUDY not in p.parents
        and not any(part in {"results", "work", "__pycache__", ".pytest_cache"}
                    for part in p.relative_to(V3).parts)
        and p.suffix in {".py", ".toml", ".eal"}
    )
    paths.update((V3 / "release_gate/cases").rglob("*.json"))
    paths.update((V3 / "technical_debt/scenarios").rglob("*.json"))
    # Reporting prose and generated transcripts are deliberately excluded;
    # immutable source, argument, registry and executable scoring inputs remain.
    # A report can be written after runs without silently changing the trial.
    paths.update(
        p for p in BASE.rglob("*") if p.is_file()
        and (p.suffix == ".py" or p.name == "ARCHITECTURE.md")
        and "__pycache__" not in p.relative_to(BASE).parts
    )
    paths.update(
        p for p in (REPO / "src/eal").rglob("*") if p.is_file()
        and "__pycache__" not in p.relative_to(REPO / "src/eal").parts
        and (p.suffix == ".py" or ("generated" in p.parts and p.suffix in {".tokens", ".interp"}))
    )
    return sorted(paths, key=lambda p: p.relative_to(REPO).as_posix())


def inventory() -> tuple[list[dict[str, object]], str]:
    files: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for path in tracked_inputs():
        name = path.relative_to(REPO).as_posix()
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": value})
        digest.update(name.encode("utf-8") + b"\0" + value.encode("ascii") + b"\n")
    return files, digest.hexdigest()


def allocation(seed: str) -> dict[str, object]:
    rng = random.Random(int(seed, 16))
    assignments: dict[str, dict[str, str]] = {}
    for family in ("R", "W"):
        arms = ["P0", "P1", "P2"]
        rng.shuffle(arms)
        assignments[family] = {f"{family}-K{index}": arm
                               for index, arm in enumerate(arms, 1)}
    return {"schema_version": "architecture-extension-v3/allocation/1",
            "seed_hex": seed,
            "algorithm": "Python random.Random(seed_as_hex_integer).shuffle P0,P1,P2 in family order R,W; map to family-K1,K2,K3",
            "family_clone_assignment": assignments,
            "stage_order": ["B", "C", "D"],
            "note": "Conditions are assigned to clones, not job start times; stages are sequential within a clone."}


def create() -> None:
    if MANIFEST.exists() or ALLOCATION.exists():
        raise RuntimeError("freeze already exists or partial allocation exists; never overwrite a pre-run assignment")
    for path in REQUIRED:
        if not path.is_file():
            raise RuntimeError(f"required pre-run input is missing: {path}")
    ALLOCATION.write_text(json.dumps(allocation(secrets.token_hex(32)), sort_keys=True, indent=2) + "\n")
    try:
        files, tree = inventory()
        data = {
            "schema_version": "architecture-extension-v3/freeze/1",
            "status": "pre-run-inputs-only",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version.split()[0],
            "digest_recipe": "sorted repository-relative UTF-8 path,NUL,file SHA-256 hex,LF",
            "tree_sha256": tree,
            "files": files,
            "excluded": ["freeze.json (self-reference)", "results/work and runtime caches"],
            "coding_outcomes_observed": False,
        }
        MANIFEST.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    except BaseException:
        ALLOCATION.unlink(missing_ok=True)
        raise
    print(json.dumps({"status": "created", "tree_sha256": tree, "files": len(files),
                      "allocation": str(ALLOCATION.relative_to(REPO))}, sort_keys=True))


def verify() -> None:
    if not MANIFEST.is_file():
        raise RuntimeError("missing freeze.json; run create before any coding session")
    expected = json.loads(MANIFEST.read_text())
    files, tree = inventory()
    if expected.get("files") != files or expected.get("tree_sha256") != tree:
        raise RuntimeError("frozen input files changed or were added/removed")
    schedule = json.loads(ALLOCATION.read_text())
    if schedule != allocation(schedule["seed_hex"]):
        raise RuntimeError("frozen arm allocation does not match its seed and algorithm")
    print(json.dumps({"status": "verified", "tree_sha256": tree, "files": len(files)}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "verify"))
    args = parser.parse_args()
    create() if args.action == "create" else verify()


if __name__ == "__main__":
    main()
