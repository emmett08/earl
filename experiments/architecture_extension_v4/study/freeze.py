"""Create or verify the immutable v4 apparatus inventory before live calls.

The manifest names every study input byte, including decision cases, hidden
oracles, assignment, prices, runner, EAL implementation and workflow. Results
and transient caches are outside this inventory. A changed apparatus needs a
new registered version; this command intentionally has no overwrite switch.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
V4 = HERE.parent
FREEZE = HERE / "freeze.json"
SCHEMA = "architecture-extension-v4/freeze/1"
EXCLUDED = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", "node_modules", ".venv"}
INDIVIDUAL = (
    REPO / ".github/workflows/architecture-extension-v4.yml",
    REPO / "experiments/architecture_extension_v3/study/assess.py",
    REPO / "experiments/architecture_extension_v2/materials/assessor/probe.py",
    REPO / "pyproject.toml",
)


def _inventory() -> dict[str, str]:
    paths = set(INDIVIDUAL)
    for root in (V4, REPO / "src/eal", REPO / "grammar"):
        if not root.is_dir():
            raise RuntimeError(f"required input directory missing: {root}")
        for path in root.rglob("*"):
            if any(part in EXCLUDED for part in path.relative_to(REPO).parts):
                continue
            if path.is_symlink():
                raise RuntimeError(f"symbolic link in frozen input: {path}")
            if path.is_file() and path != FREEZE and not path.name.endswith(".pyc"):
                paths.add(path)
    if not all(path.is_file() for path in paths):
        raise RuntimeError("required frozen input is missing")
    return {path.relative_to(REPO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def create() -> None:
    if FREEZE.exists():
        raise FileExistsError("freeze already exists; make a new protocol version for any change")
    files = _inventory()
    required = (V4 / "study/manifest.json", V4 / "study/INV-001.json",
                V4 / "study/decision_probe.py", V4 / "study/PROTOCOL.md")
    if any(not item.is_file() for item in required):
        raise RuntimeError("protocol, investigation, manifest or decision probes are incomplete")
    manifest = json.loads(required[0].read_text(encoding="utf-8"))
    if len(manifest.get("blocks", [])) != 9 or manifest.get("replicate_blocks_per_system") != 3:
        raise RuntimeError("the registered 3-system/9-block allocation is incomplete")
    record = {"schema": SCHEMA,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "manifest_sha256": files[required[0].relative_to(REPO).as_posix()],
              "input_files": files,
              "source_commit_before_v4": "1a1bcc2",
              "old_v3_results_retained": True}
    FREEZE.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"FROZEN {len(files)} input files; {hashlib.sha256(FREEZE.read_bytes()).hexdigest()}")


def verify() -> None:
    if not FREEZE.is_file():
        raise RuntimeError("no pre-run freeze exists")
    record = json.loads(FREEZE.read_text(encoding="utf-8"))
    if record.get("schema") != SCHEMA or not isinstance(record.get("input_files"), dict):
        raise RuntimeError("invalid freeze schema")
    current = _inventory()
    registered = record["input_files"]
    if current != registered:
        missing = sorted(set(registered) - set(current))
        extra = sorted(set(current) - set(registered))
        changed = sorted(path for path in set(current) & set(registered)
                         if current[path] != registered[path])
        raise RuntimeError(f"frozen inputs differ: missing={missing}, extra={extra}, changed={changed}")
    manifest_path = (V4 / "study/manifest.json").relative_to(REPO).as_posix()
    if record.get("manifest_sha256") != current.get(manifest_path):
        raise RuntimeError("frozen manifest digest mismatch")
    print(f"VERIFIED {len(current)} frozen input files")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "verify"))
    args = parser.parse_args()
    {"create": create, "verify": verify}[args.action]()


if __name__ == "__main__":
    main()
