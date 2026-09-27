"""Verify the retained local exercise and rerun every due independent probe.

This replays a collaboration-agent feasibility exercise. It does not turn it
into the credentialed, time-capped workflow experiment.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((HERE / "archive-manifest.json").read_text())
    summary = json.loads((HERE / "summary.json").read_text())
    archive = HERE / "episodes.tar.gz"
    assert sha(archive) == manifest["archive_sha256"] == summary["archive_sha256"]
    assert archive.stat().st_size == manifest["archive_bytes"]
    assert sha(HERE / "archive-manifest.json") == summary["archive_manifest_sha256"]
    assert sha(HERE / "selection.json") == summary["selection_sha256"]
    expected = {item["path"]: item for item in manifest["files"]}
    assert len(expected) == len(manifest["files"])

    with TemporaryDirectory(prefix="architecture-v3-replay-") as temporary:
        root = Path(temporary)
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            assert set(m.name for m in members) == set(expected)
            for member in members:
                assert member.isfile() and not member.issym() and not member.islnk()
                relative = Path(member.name)
                assert not relative.is_absolute() and ".." not in relative.parts
                item = expected[member.name]
                assert member.size == item["bytes"]
                source = tar.extractfile(member)
                assert source is not None
                data = source.read()
                assert len(data) == item["bytes"]
                assert hashlib.sha256(data).hexdigest() == item["sha256"]
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)

        count = 0
        for episode in summary["episodes"]:
            clone, family, arm = (episode[key] for key in ("clone", "family", "arm"))
            assert [stage["stage"] for stage in episode["stages"]] == ["B", "C", "D"]
            for stage in episode["stages"]:
                name = stage["stage"]
                stored = json.loads((root / "assess" / f"{clone}-{name}.json").read_text())
                assert (stored["clone"], stored["family"], stored["arm"]) == (clone, family, arm)
                candidate = root / "candidate" / clone / name
                result = subprocess.run(
                    [sys.executable, str(REPO / "experiments/architecture_extension_v3/study/assess.py"),
                     "--candidate", str(candidate), "--family", family, "--stage", name],
                    cwd=REPO, check=True, capture_output=True, text=True,
                )
                fresh = json.loads(result.stdout)
                assert fresh == stored["assessment"]
                assert fresh["source_sha256"] == stage["assessor_source_sha256"]
                assert stored["snapshot"]["source_tree_sha256"] == stage["snapshot_source_tree_sha256"]
                assert fresh["passed"] == stage["passed"]
                assert fresh["failed"] == stage["failed"]
                assert fresh["invalid"] == stage["invalid"]
                if arm == "P2":
                    metrics = json.loads((root / "host" / clone / name / "metrics.json").read_text())
                    assert sha(root / "host" / clone / name / "mcp-wire.json") == metrics["trace_sha256"]
                    assert metrics["packet_bytes"] == stage["packet_bytes"]
                count += 1
        assert count == 18
        print(json.dumps({"status": "verified", "episodes": count,
                          "archive_sha256": manifest["archive_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
