#!/usr/bin/env python3
"""Check exact imported figures without invalidating their retained reviews.

Audits preserve their original absolute build locations. Relocation is checked
through declared relative input names and exact hashes, never by rewriting an
old audit/review to suggest that it reviewed a new rendering or manuscript.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reproduction/figure-tools/scripts"))
from figure_spec import validate_spec


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / "review/article-import.json").read_text())
    for rel, sha in manifest["files"].items():
        assert digest(ROOT / rel) == sha, f"Imported file changed: {rel}"
    for name in manifest["figure_ids"]:
        contract_root = ROOT / manifest.get("figure_contract_roots", {}).get(name, ".")
        assert contract_root.resolve().is_relative_to(ROOT), name
        spec_path = ROOT / manifest.get("figure_spec_paths", {}).get(name, name + ".spec.json")
        spec = json.loads(spec_path.read_text())
        errors = validate_spec(spec, base_dir=contract_root, check_files=True)
        assert not errors, errors
        review_path = ROOT / f"figures/{name}.review.json"
        audit_path = ROOT / f"figures/{name}.audit.json"
        review = json.loads(review_path.read_text())
        audit = json.loads(audit_path.read_text())
        assert review["decision"] == "accept" and audit["ok"] is True
        assert not audit.get("errors")
        assert review["spec_sha256"] == digest(spec_path)
        assert review["audit_sha256"] == digest(audit_path)
        for item in review["artifacts"]:
            assert digest(contract_root / item["path"]) == item["sha256"], item["path"]
        assert digest(ROOT / f"figures/{name}.pdf") == digest(contract_root / spec["build"]["outputs"]["pdf"]), name
        for role, path in {"specification": spec_path,
                           "source": contract_root / spec["build"]["source"],
                           "pdf": contract_root / spec["build"]["outputs"]["pdf"]}.items():
            assert audit["provenance"][role]["sha256"] == digest(path), role
        inputs = {item["declared_path"]: item["sha256"]
                  for item in audit["declared_local_files"]}
        required = {spec["build"]["source"], *spec["build"].get("dependencies", []),
                    *(item["path"] for item in spec["inputs"] if "path" in item)}
        for rel in required:
            assert rel in inputs and digest(contract_root / rel) == inputs[rel], rel
    print(f"{len(manifest['figure_ids'])} exact imported figure PDFs, specifications, source/input hashes and retained review bindings: passed.")


if __name__ == "__main__":
    main()
