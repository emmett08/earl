"""Reproduce current-source host cost on the frozen A snapshot.

Each measurement uses a fresh host directory. One warm-up per condition is
discarded; five interleaved repetitions are retained by default. The
candidate source and declared checks are identical in every condition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import tempfile
from typing import Any

import host
from snapshot_probe import digest_file, tree_manifest


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "architecture_extension_v2" / "results" / "snapshots" / "a"


def measure(arm: str, cache: bool, eager: bool, folder: Path) -> dict[str, Any]:
    from argparse import Namespace

    return host.assess(Namespace(baseline=BASE, candidate=BASE, family="R", feature="B",
                                 arm=arm, disable_cache=not cache, eager_explain=eager,
                                 state_dir=folder))


def summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {"median": statistics.median(ordered), "min": ordered[0], "max": ordered[-1]}


def run(repetitions: int) -> dict[str, Any]:
    if not 2 <= repetitions <= 20:
        raise ValueError("repetitions must be from 2 through 20")
    conditions = [("P1", False, False), ("P2", False, False),
                  ("P2", True, False), ("P2", True, True)]

    def label(arm: str, cache: bool, eager: bool) -> str:
        return f"{arm}-{'cache' if cache else 'no-cache'}{'-eager' if eager else ''}"

    raw: dict[str, list[dict[str, Any]]] = {label(arm, cache, eager): []
                                                 for arm, cache, eager in conditions}
    randomiser = random.Random(18394)
    with tempfile.TemporaryDirectory(prefix="architecture-v3-host-benchmark-") as temporary:
        root = Path(temporary)
        index = 0
        for trial in range(-1, repetitions):
            order = conditions[:]
            randomiser.shuffle(order)
            for arm, cache, eager in order:
                index += 1
                result = measure(arm, cache, eager, root / f"run-{index:02d}")
                if trial >= 0:
                    raw[label(arm, cache, eager)].append(result)
    observed = {item["observation_digest"] for entries in raw.values() for item in entries}
    if len(observed) != 1:
        raise ValueError("compared runs did not observe the same candidate findings")
    digest = observed.pop()
    aggregates = {}
    for name, entries in raw.items():
        aggregates[name] = {
            "wall_seconds": summary([row["wall_seconds"] for row in entries]),
            "cpu_seconds": summary([row["host_cpu_seconds"] + row["child_cpu_seconds"]
                                    for row in entries]),
            "tool_exchange_bytes": summary([row["tool_exchange_bytes"] for row in entries]),
            "packet_bytes": sorted({row["packet_bytes"] for row in entries}),
            "mcp_elapsed_seconds": (summary([row["mcp_elapsed_seconds"] for row in entries])
                                    if name.startswith("P2") else None),
        }
    return {"schema": "architecture-v3-host-benchmark/1",
            "workload": "frozen v2 A source, R-B next-feature current-source assessment; visible 16-test suite",
            "source_tree_sha256": tree_manifest(BASE)["tree_sha256"],
            "observation_digest": digest,
            "versions": {"python": platform.python_version(), "platform": platform.platform(),
                         "host_sha256": digest_file(HERE / "host.py"),
                         "collector_sha256": digest_file(HERE / "snapshot_probe.py"),
                         "eal_sha256": digest_file(HERE / "argument.eal"),
                         "registry_sha256": digest_file(HERE / "tool.toml")},
            "design": {"warmups_per_condition": 1, "measured_repetitions": repetitions,
                       "seed": 18394, "fresh_state_per_run": True,
                       "cpu": "host self plus waited child-process rusage; includes MCP server and tools",
                       "no_provider_tokens_or_money": True},
            "aggregates": aggregates,
            "runs": raw}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.repetitions)
    host.write_json(args.output, report)
    print(json.dumps(report["aggregates"], sort_keys=True))


if __name__ == "__main__":
    main()
