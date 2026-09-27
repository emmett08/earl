"""Freeze and verify pre-run material bytes for the architecture experiment.

Only the enumerated entries are part of the pre-run contract. The outcome
directories and the paper are intentionally absent because they are written
after agent executions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path(__file__).parent / "materials" / "freeze.json"
IGNORED = {"__pycache__", ".pytest_cache", ".mypy_cache"}


def paths_for(entries: list[str]) -> list[Path]:
    selected: set[Path] = set()
    for entry in entries:
        target = (REPOSITORY / entry).resolve()
        if not target.is_relative_to(REPOSITORY):
            raise ValueError(f"outside repository: {entry}")
        if not target.exists():
            raise FileNotFoundError(entry)
        candidates = target.rglob("*") if target.is_dir() else (target,)
        for path in candidates:
            if path.is_file() and not any(part in IGNORED for part in path.parts):
                selected.add(path)
    return sorted(selected, key=lambda path: path.relative_to(REPOSITORY).as_posix())


def make_record(entries: list[str]) -> tuple[dict[str, str], str]:
    files: dict[str, str] = {}
    tree = hashlib.sha256()
    for path in paths_for(entries):
        name = path.relative_to(REPOSITORY).as_posix()
        data = path.read_bytes()
        files[name] = hashlib.sha256(data).hexdigest()
        tree.update(name.encode("utf-8"))
        tree.update(b"\0")
        tree.update(data)
        tree.update(b"\0")
    return files, tree.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--entry", action="append", default=[], help="repository-relative file or directory")
    parser.add_argument("--model", default=None, help="exposed primary B model identifier")
    parser.add_argument("--effort", default=None, help="exposed primary B reasoning effort")
    args = parser.parse_args()
    if args.action == "create":
        if args.manifest.exists():
            raise SystemExit(f"freeze already exists: {args.manifest}")
        if not args.entry or not args.model or not args.effort:
            parser.error("create needs --entry, --model and --effort")
        files, tree = make_record(args.entry)
        order = ("b_control", "b_treatment") if secrets.randbits(1) == 0 else ("b_treatment", "b_control")
        record = {
            "schema_version": "architecture-extension-freeze/1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entries": args.entry,
            "files": files,
            "tree_sha256": tree,
            "primary_b_model": args.model,
            "primary_b_effort": args.effort,
            "primary_b_order": order,
            "interpretation": "This record freezes material bytes and order; it is not preregistration or causal identification.",
        }
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"manifest": str(args.manifest), "files": len(files), "tree_sha256": tree, "primary_b_order": order}))
    else:
        record = json.loads(args.manifest.read_text(encoding="utf-8"))
        files, tree = make_record(record["entries"])
        if files != record["files"] or tree != record["tree_sha256"]:
            missing = sorted(set(record["files"]) - set(files))
            added = sorted(set(files) - set(record["files"]))
            changed = sorted(name for name in set(files) & set(record["files"]) if files[name] != record["files"][name])
            raise SystemExit(json.dumps({"ok": False, "missing": missing, "added": added, "changed": changed}))
        print(json.dumps({"ok": True, "files": len(files), "tree_sha256": tree}))


if __name__ == "__main__":
    main()
