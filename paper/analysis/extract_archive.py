"""Extract bounded, credential-free analysis inputs from the exact supplied pilot.

No archive code is executed. Raw conversations and tool receipts remain in the
identified original artefact; their bytes are covered by its SHA-256 digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ARCHIVE_SHA256 = "bf5b59c340b1c11c85a3e39679bc9cc1bc4521af741f45d9dc5cc1c65cbd8547"
PAPER = Path(__file__).resolve().parents[1]


def extract(archive: Path, destination: Path) -> None:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError("Archive differs from GitHub artefact 10879620453")
    destination.mkdir(parents=True, exist_ok=True)
    member_hashes = {}
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError("Duplicate archive member")

        def read(name):
            raw = z.read(name)
            member_hashes[name] = hashlib.sha256(raw).hexdigest()
            return json.loads(raw)

        manifest = read("run/manifest.json")
        case_manifest = read("run/case-manifest.json")
        summary = read("run/summary.json")
        completion = read("run/completion.json")
        cases = [read(f"run/cases/{key}/case.json") for key in sorted(case_manifest["cases"])]
        trials = []
        for assignment in manifest["assignments"]:
            original = read(f"run/trials/{assignment['id']}/trial.json")
            # Preserve all assignments, outcomes, answer fields and accounting.
            # Do not duplicate response text, replay handles or provider objects.
            trial = {key: value for key, value in original.items()
                     if key not in {"model_calls", "model_spec"}}
            calls = []
            for original_call in original.get("model_calls", []):
                call = {key: original_call[key] for key in
                        ("turn", "error", "estimated_usd", "seconds") if key in original_call}
                response = original_call.get("response")
                if response:
                    call["response"] = {key: response[key] for key in
                                        ("model", "input_tokens", "output_tokens") if key in response}
                    call["response"]["metadata"] = {
                        key: response.get("metadata", {})[key] for key in
                        ("cached_input_tokens", "reasoning_tokens", "service_tier")
                        if key in response.get("metadata", {})}
                else:
                    call["response"] = None
                calls.append(call)
            trial["model_calls"] = calls
            trials.append(trial)
    payloads = {"historical-manifest.json": manifest, "case-manifest.json": case_manifest,
                "original-summary.json": summary, "completion.json": completion}
    for name, value in payloads.items():
        (destination / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    for name, values in (("cases.jsonl", cases), ("trials.jsonl", trials)):
        (destination / name).write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in values))
    provenance = {
        "schema": "eal-paper-evidence/1", "archive_sha256": digest,
        "github_run_id": 36163505801, "github_run_attempt": 1,
        "github_artifact_id": 10879620453,
        "archive_url": "https://github.com/emmett08/earl/actions/runs/36163505801/artifacts/10879620453",
        "archive_expires_at": "2026-10-25T17:38:02Z",
        "run_commit": manifest["commit"], "protocol": manifest["plan"]["version"],
        "projection": "Every assignment, raw case, final answer, original score and call accounting retained. Response text, replay handles and duplicated model specifications omitted. Original archive retains tool receipts and conversations.",
        "source_member_sha256": member_hashes,
        "derived_file_sha256": {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                                for name in sorted([*payloads, "cases.jsonl", "trials.jsonl"])}
    }
    (destination / "provenance.json").write_text(json.dumps(provenance, sort_keys=True, indent=2) + "\n")
    print(f"Extracted {len(trials)} assignments and {len(cases)} cases from verified archive")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=PAPER / "data")
    args = parser.parse_args()
    extract(args.archive, args.output)
