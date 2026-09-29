#!/usr/bin/env python3
"""Make the article's auditable, offline evidence snapshot from the retained ZIP.

No API calls. The session rows, corpus and small contracts are byte-preserved.
API calls are projected to accounting/configuration fields; provider payloads and
duplicated request text are omitted. Full initial prompts/answers/events remain
in annotated-rows.json.gz. All source hashes refer to uncompressed archive bytes.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = "0c1b8f5af0990f04c20564ffffee9c103ac47cbcab7ca940639225d80bb32d23"
COPY = ["annotated-rows.json", "cases.json", "plan.json", "protocol.json",
        "provenance.json", "execution-contract.json", "segments.json",
        "analysis-annotated.json", "information-report.json", "pipeline-status.json",
        "calibration.json", "restore-receipt.json"]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    assert digest(args.archive.read_bytes()) == ARCHIVE_SHA, "Wrong retained ZIP"
    directory = ROOT / "data"
    directory.mkdir(exist_ok=True)
    manifest = {"schema": "earl-jss-evidence/1", "run_id": "984bd05d-6366-41c3-b9ae-ee8766835b08",
                "collection_run": 36477862213, "processing_run": 36492423435,
                "artifact_id": 11001997190, "archive_sha256": ARCHIVE_SHA,
                "collection_revision": "d52e2bd0898ed519253aedbbc8e002e493dd64d2",
                "processing_revision": "31a3cba769948e123a59ca35c54c5135ad005f54",
                "source_files": {}, "files": {}}
    with zipfile.ZipFile(args.archive) as archive:
        for name in COPY:
            raw = archive.read(name)
            manifest["source_files"][name] = digest(raw)
            compressed = gzip.compress(raw, mtime=0)
            output = name + ".gz"
            (directory / output).write_bytes(compressed)
            manifest["files"][output] = digest(compressed)
        raw = archive.read("calls.json")
        manifest["source_files"]["calls.json"] = digest(raw)
        calls = []
        for call in json.loads(raw):
            record = {k: v for k, v in call.items() if k not in {"request", "response"}}
            record["usage"] = call["response"]["usage"]
            record["model"] = call["request"]["model"]
            record["request_config"] = {k: v for k, v in call["request"].items()
                                        if k not in {"input", "tools"}}
            calls.append(record)
        projected = json.dumps(calls, sort_keys=True, separators=(",", ":")).encode()
        compressed = gzip.compress(projected, mtime=0)
        (directory / "call-accounting.json.gz").write_bytes(compressed)
        manifest["files"]["call-accounting.json.gz"] = digest(compressed)
        manifest["projection"] = {
            "source": "calls.json", "output": "call-accounting.json.gz",
            "retained": "All top-level fields except request/response; response.usage; request.model; request fields except input/tools",
            "omitted": "Duplicated request messages, tool definitions and provider response payloads; full initial prompts, final answers and session tool events remain in annotated rows"}
        for name in ["rows.json", "completed-labels.json"]:
            manifest["source_files"][name] = digest(archive.read(name))
        source_name = "sequences/block-0000.eal/project/argument.eal"
        source = archive.read(source_name)
        (ROOT / "listings" / "retained-argument.eal").write_bytes(source)
        manifest["retained_listing_source"] = source_name
        manifest["retained_listing_sha256"] = digest(source)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Retained {len(manifest['files'])} evidence files; ZIP and source hashes recorded.")


if __name__ == "__main__":
    main()
