#!/usr/bin/env python3
"""Resolve a manual package release to a versioned commit already on main."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import tomllib
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
COMMIT = re.compile(r"[0-9a-f]{40}")


class Release(NamedTuple):
    version: str
    commit: str


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, check=True,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _runtime_version(root: Path) -> str:
    module = ast.parse((root / "src/eal/__init__.py").read_text(encoding="utf-8"))
    assignments = [
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
    ]
    if (len(assignments) != 1 or not isinstance(assignments[0].value, ast.Constant)
            or not isinstance(assignments[0].value.value, str)):
        raise ValueError("eal.__version__ must have one literal string assignment")
    return assignments[0].value.value


def validate_release(root: Path, tag: str, dispatch_ref: str, dispatch_sha: str) -> Release:
    """Fetch only the named tag and main, then validate the checked-out release."""
    if TAG.fullmatch(tag) is None:
        raise ValueError("release_tag must be a stable vMAJOR.MINOR.PATCH tag")
    tag_ref = f"refs/tags/{tag}"
    if dispatch_ref != tag_ref:
        raise ValueError("dispatch this workflow on the same release tag as release_tag")
    if COMMIT.fullmatch(dispatch_sha) is None:
        raise ValueError("dispatch SHA must be a full GitHub commit SHA")
    if _git(root, "rev-parse", "--verify", "HEAD^{commit}") != dispatch_sha:
        raise ValueError("checkout does not match the immutable dispatch commit")

    # A moved existing tag makes fetch fail instead of silently replacing it.
    # These are local read-only mirrors: this workflow never pushes a Git ref.
    _git(root, "fetch", "--no-tags", "origin", f"{tag_ref}:{tag_ref}",
         "+refs/heads/main:refs/remotes/origin/main")
    commit = _git(root, "rev-parse", "--verify", f"{tag_ref}^{{commit}}")
    if commit != dispatch_sha:
        raise ValueError("release tag no longer resolves to the dispatch commit")
    _git(root, "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")

    version = tag[1:]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project["name"] != "engineering-argument-language":
        raise ValueError("release project must be engineering-argument-language")
    if project["version"] != version or _runtime_version(root) != version:
        raise ValueError("release tag, project.version and eal.__version__ must agree")
    return Release(version, commit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_tag")
    parser.add_argument("--dispatch-ref", required=True)
    parser.add_argument("--dispatch-sha", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        release = validate_release(ROOT, args.release_tag, args.dispatch_ref, args.dispatch_sha)
    except (ValueError, KeyError, OSError, SyntaxError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"release validation failed: {error}\n")
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"version={release.version}\ncommit={release.commit}\n")
    print(json.dumps(release._asdict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
