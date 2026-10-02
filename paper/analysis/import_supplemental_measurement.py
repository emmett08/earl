#!/usr/bin/env python3
"""Retain an explicitly separate supplemental review of the frozen pilot."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["masked-items.json", "private-mapping.json", "reviewer-a.json", "reviewer-b.json",
         "adjudication-items.json", "adjudicator.json", "supplemental-review.json",
         "supplemental-analysis.json", "supplemental-annotated-rows.json", "remaining-masked-packet.json"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path)
    ap.add_argument("--protocol", type=Path)
    args = ap.parse_args()
    target = ROOT / "followup/measurement"
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in NAMES:
        raw = (args.directory / name).read_bytes()
        if name == "supplemental-annotated-rows.json":
            output = name + ".gz"
            saved = gzip.compress(raw, mtime=0)
        else:
            output, saved = name, raw
        (target / output).write_bytes(saved)
        files[output] = {"sha256": hashlib.sha256(saved).hexdigest(),
                         "source_name": name, "source_sha256": hashlib.sha256(raw).hexdigest()}
    if args.protocol:
        output = "supplemental-coding-protocol.md"
        raw = args.protocol.read_bytes()
        (target / output).write_bytes(raw)
        files[output] = {"sha256": hashlib.sha256(raw).hexdigest(), "source_name": args.protocol.name,
                         "source_sha256": hashlib.sha256(raw).hexdigest()}
    baseline = json.loads((ROOT / "data/manifest.json").read_text())
    manifest = {"schema": "eal-jss-supplemental-snapshot/1", "files": files,
                "primary_archive_sha256": baseline["archive_sha256"],
                "primary_annotated_rows_sha256": baseline["source_files"]["annotated-rows.json"],
                "primary_data_unchanged": True,
                "scope": "Alternative AI interpretation of a 169-answer census/sample. Primary finish codes, figures and inference remain immutable and separately identified."}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Retained {len(files)} supplemental measurement files; frozen primary data unchanged.")


if __name__ == "__main__":
    main()
