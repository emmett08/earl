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
ARCHIVE_SHA = "491df25b38bd22554143c0e146a7ac547d0686ea1022b1c9bf87b6093482b69a"
RUN_ID = "45488cb5-624e-4267-b12c-97fe503ff4d1"
COLLECTION_REVISION = "c0974bc6bb6a2df30d1423b6248bfc51b4d2a9d7"
PROCESSING_REVISION = "cea2b59e686d57e0c071924f184b497919ec91a7"
COPY = ["annotated-rows.json", "cases.json", "plan.json", "protocol.json",
        "provenance.json", "execution-contract.json", "segments.json",
        "analysis-annotated.json", "information-report.json", "pipeline-status.json",
        "calibration.json", "restore-receipt.json", "completed-labels.json"]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    assert digest(args.archive.read_bytes()) == ARCHIVE_SHA, "Wrong retained ZIP"
    directory = ROOT / "data"
    directory.mkdir(exist_ok=True)
    manifest = {"schema": "earl-jss-evidence/1", "run_id": RUN_ID,
                "source_language": "EAL/3", "protocol_version": "7.0.0",
                "collection_run": 36985062352, "processing_run": 36997861629,
                "artifact_id": 11222114140, "archive_sha256": ARCHIVE_SHA,
                "collection_revision": COLLECTION_REVISION,
                "processing_revision": PROCESSING_REVISION,
                "source_files": {}, "files": {}}
    with zipfile.ZipFile(args.archive) as archive:
        provenance = json.loads(archive.read("provenance.json"))
        analysis = json.loads(archive.read("analysis-annotated.json"))
        assert provenance["run_id"] == analysis["practical_decision"]["run_id"] == RUN_ID
        assert provenance["revision"] == COLLECTION_REVISION
        assert provenance["source_language"] == "EAL/3"
        assert provenance["protocol_version"] == "7.0.0"
        assert analysis["processing_provenance"]["revision"] == PROCESSING_REVISION
        assert analysis["processing_provenance"]["package_version"] == "3.2.4"
        manifest["package_version"] = analysis["processing_provenance"]["package_version"]
        for name in COPY:
            raw = archive.read(name)
            manifest["source_files"][name] = digest(raw)
            compressed = gzip.compress(raw, mtime=0)
            output = name + ".gz"
            (directory / output).write_bytes(compressed)
            manifest["files"][output] = digest(compressed)
        # The masked item-to-session mapping permits an independent check that
        # every frozen decision still codes the exact retained answer.
        name = "annotation-bundle/mapping.json"
        raw = archive.read(name)
        manifest["source_files"][name] = digest(raw)
        compressed = gzip.compress(raw, mtime=0)
        output = "annotation-mapping.json.gz"
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
        for name in ["rows.json", "annotation-bundle/items.json"]:
            manifest["source_files"][name] = digest(archive.read(name))
        manifest["annotation_qualification"] = analysis["annotation_provenance"]["qualification"]
        source_name = "sequences/block-0000.eal/project/argument.eal"
        source = archive.read(source_name)
        (ROOT / "listings" / "retained-argument.eal").write_bytes(source)
        manifest["retained_listing_source"] = source_name
        manifest["retained_listing_sha256"] = digest(source)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Retained {len(manifest['files'])} evidence files; ZIP and source hashes recorded.")


if __name__ == "__main__":
    main()
