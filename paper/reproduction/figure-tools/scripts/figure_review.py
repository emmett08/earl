#!/usr/bin/env python3
"""Validate review records and freshness; semantic decisions remain the reviewer's."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_spec import SpecError, load_spec, sha256_file

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "assets" / "figure-review.schema.json"
AGENT_LIMITATION = "Human interpretation benefit remains unmeasured by agent screening."


class ReviewError(ValueError):
    """A review is invalid, incomplete or bound to stale artifacts."""


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"cannot read {label} {path}: {exc}") from exc


def _render_errors(path, role):
    """Check an accessible render, rather than trusting an extension or signature."""
    try:
        if path.suffix.lower() == ".pdf":
            import fitz
            with fitz.open(path) as document:
                if not document.is_pdf or document.needs_pass or len(document) != 1:
                    return ["expected an accessible one-page rendered PDF"]
                document[0].get_pixmap(matrix=fitz.Matrix(.1, .1))
        elif path.suffix.lower() == ".png" and role == "prototype":
            from PIL import Image
            with Image.open(path) as image:
                if image.format != "PNG" or min(image.size) == 0:
                    return ["expected a non-empty rendered PNG"]
                image.verify()
        else:
            return ["expected a rendered PDF or PNG; final_pdf requires PDF"]
    except ImportError:
        return ["render validation requires PyMuPDF for PDF and Pillow for PNG"]
    except Exception as exc:
        return [f"rendered artifact cannot be decoded: {exc}"]
    return []


def validate_review(review, spec_path, audit_path=None, base_dir=None,
                    check_files=True) -> list[str]:
    """Check declarations and bound files, without inferring semantic acceptance.

    Review paths are relative to the specification's project root by default.
    Supplied specification and audit are always read; check_files additionally
    verifies local artifact hashes, render signatures and current source bytes.
    """
    if jsonschema is None:
        return ["jsonschema is required; install it with python3 -m pip install jsonschema"]
    try:
        schema = _read_json(SCHEMA_PATH, "review schema")
        validator = jsonschema.Draft202012Validator(schema)
        errors = [f"review{''.join(f'[{part!r}]' for part in error.absolute_path)}: {error.message}"
                  for error in sorted(validator.iter_errors(review), key=lambda e: str(list(e.absolute_path)))]
    except (ReviewError, jsonschema.SchemaError) as exc:
        return [str(exc)]
    if errors:
        return errors
    spec_path = Path(spec_path).resolve()
    root = Path(base_dir).resolve() if base_dir is not None else spec_path.parent
    try:
        spec = load_spec(spec_path, check_files=check_files)
        spec_hash = sha256_file(spec_path)
    except (OSError, SpecError) as exc:
        return [f"specification: {exc}"]
    if review["figure_id"] != spec["figure_id"]:
        errors.append("figure_id: does not match the current specification")
    if review["spec_sha256"] != spec_hash:
        errors.append("spec_sha256: SHA-256 mismatch; the specification changed")
    reviewer = review["reviewer"]
    if reviewer["scope"] != {"agent": "agent_screening", "human": "reader_test"}[reviewer["kind"]]:
        errors.append("reviewer.scope: agent screening requires an agent; reader testing requires a human")
    if reviewer["kind"] == "agent" and AGENT_LIMITATION not in review["limitations"]:
        errors.append(f"limitations: agent screening must record {AGENT_LIMITATION!r}")

    def resolve(path, owner):
        try:
            actual = (root / path).resolve()
        except (OSError, RuntimeError) as exc:
            errors.append(f"{owner}: cannot resolve local path: {exc}")
            return None
        if ".." in Path(path).parts or not actual.is_relative_to(root):
            errors.append(f"{owner}: path escapes the review project root")
            return None
        return actual

    if "test_evidence" in reviewer:
        evidence = reviewer["test_evidence"]
        actual = resolve(evidence["path"], "reviewer.test_evidence")
        if actual is not None and check_files:
            try:
                if not actual.is_file() or sha256_file(actual) != evidence["sha256"]:
                    errors.append("reviewer.test_evidence: missing file or SHA-256 mismatch")
            except OSError as exc:
                errors.append(f"reviewer.test_evidence: cannot read evidence: {exc}")

    artifacts = {}
    for item in review["artifacts"]:
        owner = f"artifact {item['role']} {item['path']!r}"
        actual = resolve(item["path"], owner)
        if actual is None:
            continue
        key = (item["role"], actual)
        if key in artifacts:
            errors.append(f"{owner}: duplicate role/path")
        artifacts[key] = item
        if not check_files:
            continue
        try:
            if not actual.is_file():
                errors.append(f"{owner}: local file does not exist")
                continue
            if sha256_file(actual) != item["sha256"]:
                errors.append(f"{owner}: SHA-256 mismatch; rendered artifact changed")
            errors.extend(f"{owner}: {error}" for error in _render_errors(actual, item["role"]))
        except OSError as exc:
            errors.append(f"{owner}: cannot read local file: {exc}")
    finals = [item for (role, _), item in artifacts.items() if role == "final_pdf"]
    if len(finals) != 1:
        errors.append("artifacts: exactly one final_pdf is required")
    final = finals[0] if len(finals) == 1 else None
    if final and resolve(final["path"], "final_pdf") != (spec_path.parent / spec["build"]["outputs"]["pdf"]).resolve():
        errors.append("final_pdf: path must match the specification's declared PDF output")
    candidate_ids = [item["id"] for item in review["candidates"]]
    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("candidates: ids must be unique")
    if review["selected_candidate"] not in candidate_ids:
        errors.append("selected_candidate: must name an inspected rendered candidate")
    for candidate in review["candidates"]:
        actual = resolve(candidate["prototype"], f"candidate {candidate['id']!r}")
        if actual is not None and ("prototype", actual) not in artifacts:
            errors.append(f"candidate {candidate['id']!r}: prototype needs a bound role=prototype artifact")

    findings = review["comparison"]["findings"]
    if len({item["id"] for item in findings}) != len(findings):
        errors.append("comparison.findings: ids must be unique")
    if review["decision"] == "accept":
        for finding in findings:
            if finding["disposition"] == "unresolved" or (finding["severity"] == "blocking" and finding["disposition"] != "resolved"):
                errors.append(f"finding {finding['id']!r}: accepted review requires resolution of blocking and unresolved findings")
    dispositions = review["comparison"]["audit_warning_dispositions"]
    indices = [item["index"] for item in dispositions]
    if len(set(indices)) != len(indices):
        errors.append("audit_warning_dispositions: warning indices must be unique")
    if audit_path is None:
        if review["decision"] == "accept":
            errors.append("audit_path: accept requires a current successful mechanical audit")
        if dispositions or "audit_sha256" in review:
            errors.append("audit_path: provide the audit named by the hash or warning dispositions")
        return errors
    try:
        audit = _read_json(audit_path, "mechanical audit")
        if not isinstance(audit, dict):
            raise ReviewError("mechanical audit must be an object")
        if review.get("audit_sha256") != sha256_file(audit_path):
            errors.append("audit_sha256: missing or stale hash of the inspected mechanical audit")
    except (OSError, ReviewError) as exc:
        return errors + [str(exc)]
    provenance = audit.get("provenance", {})
    if audit.get("figure_id", review["figure_id"]) != review["figure_id"]:
        errors.append("audit.figure_id: does not match the reviewed figure")
    expected = {"specification": (spec_path, spec_hash),
                "pdf": ((root / final["path"]).resolve(), final["sha256"]) if final else (None, None),
                "source": ((spec_path.parent / spec["build"]["source"]).resolve(), None)}
    if not isinstance(provenance, dict):
        errors.append("audit.provenance: must be an object")
        provenance = {}
    for label, (path, digest) in expected.items():
        record = provenance.get(label)
        if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
            errors.append(f"audit.provenance.{label}: current path and SHA-256 are required")
            continue
        try:
            if path is not None and Path(record["path"]).resolve() != path:
                errors.append(f"audit.provenance.{label}: path differs from the current declared file")
        except (OSError, RuntimeError) as exc:
            errors.append(f"audit.provenance.{label}: cannot resolve recorded path: {exc}")
        if label == "source" and check_files:
            try:
                digest = sha256_file(path)
            except OSError as exc:
                errors.append(f"audit.provenance.source: cannot read current source: {exc}")
        if digest is not None and record["sha256"] != digest:
            errors.append(f"audit.provenance.{label}: SHA-256 mismatch; audit is stale")
    if check_files:
        for label, record in provenance.items():
            if label in expected:
                continue
            try:
                if not isinstance(record, dict) or sha256_file(record["path"]) != record["sha256"]:
                    errors.append(f"audit.provenance.{label}: missing or changed recorded input")
            except (OSError, KeyError, TypeError) as exc:
                errors.append(f"audit.provenance.{label}: cannot check recorded input: {exc}")
        local_files = audit.get("declared_local_files")
        if not isinstance(local_files, list):
            errors.append("audit.declared_local_files: current declared input manifest is required")
        else:
            paths = set()
            for index, record in enumerate(local_files):
                owner = f"audit.declared_local_files[{index}]"
                try:
                    if (not isinstance(record, dict) or not isinstance(record.get("path"), str)
                            or not isinstance(record.get("sha256"), str)):
                        errors.append(f"{owner}: recorded original path and SHA-256 are required")
                        continue
                    path = Path(record["path"]).resolve()
                    paths.add(path)
                    if sha256_file(path) != record["sha256"]:
                        errors.append(f"{owner}: SHA-256 mismatch; declared local input changed")
                except (OSError, RuntimeError, TypeError) as exc:
                    errors.append(f"{owner}: cannot check recorded original: {exc}")
            required = {spec["build"]["source"], *spec["build"]["dependencies"],
                        *(item["path"] for item in spec["inputs"] if "path" in item)}
            for path in required:
                if (spec_path.parent / path).resolve() not in paths:
                    errors.append(f"audit.declared_local_files: missing currently declared input {path!r}")
    warnings = audit.get("warnings", [])
    typesetting = audit.get("typesetting_warnings", [])
    if not isinstance(warnings, list) or not isinstance(typesetting, list):
        errors.append("audit warnings and typesetting_warnings must be arrays")
        return errors
    available = set(range(len(warnings) + len(typesetting)))
    if any(index not in available for index in indices):
        errors.append("audit_warning_dispositions: index is absent from the current audit")
    if review["decision"] == "accept":
        if audit.get("ok") is not True or audit.get("errors", []):
            errors.append("decision: accept requires a successful mechanical audit without errors")
        if set(indices) != available:
            errors.append("audit_warning_dispositions: accept requires a disposition for every current audit warning")
    return errors


def load_review(path, spec_path, audit_path=None, check_files=True) -> dict:
    """Load a review whose artifact paths are relative to the specification root."""
    review = _read_json(path, "figure review")
    errors = validate_review(review, spec_path, audit_path, check_files=check_files)
    if errors:
        raise ReviewError("\n".join(errors))
    return review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--check-files", action="store_true", help="check current artifact and source files")
    args = parser.parse_args(argv)
    try:
        review = load_review(args.review, args.spec, args.audit, args.check_files)
    except ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"valid": True, "figure_id": review["figure_id"],
                      "declared_decision": review["decision"], "files_checked": args.check_files,
                      "semantic_correctness": "reviewer judgement; not automatically verified",
                      "independence": "declared; not proven"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
