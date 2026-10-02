#!/usr/bin/env python3
"""Import compact receipts for the canonical root article, with explicit scope."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["followup-hermeneutic-manifest.json", "followup-hermeneutic-coverage.json",
         "followup-hermeneutic-review.md", "followup-hermeneutic-style-sheet.md",
         "followup-hermeneutic-reinterpretation.md", "followup-hermeneutic-validator.txt",
         "followup-hermeneutic-proof-identity.json", "followup-hermeneutic-completion.json",
         "followup-hermeneutic-semantic-regression.json", "followup-hermeneutic-independent-temporal-check.json"]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("article", type=Path)
    ap.add_argument("--stage", help="Distinct current-stage receipt folder; retains previous review receipts")
    ap.add_argument("--receipt", action="append", help="Explicit article-relative current-stage receipt; repeat as needed")
    ap.add_argument("--artifact-manifest", default="analysis/followup-final-artifact-manifest.json")
    ap.add_argument("--placement-receipt", default="analysis/followup-profile-manuscript-binding.json")
    args = ap.parse_args()
    article = args.article.resolve()
    assert not args.stage or args.stage.replace("-", "").replace("_", "").isalnum(), "Invalid stage name"
    target = ROOT / "review/editorial" / args.stage if args.stage else ROOT / "review/editorial"
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    receipts = args.receipt or ["analysis/" + name for name in NAMES]
    assert len(receipts) == len(set(receipts)), "Duplicate receipt paths"
    for source in receipts:
        source_path = article / source
        assert source_path.resolve().is_relative_to(article), "Receipt outside article"
        name = source_path.name
        raw = source_path.read_bytes()
        filename = name + ".gz" if name.endswith("coverage.json") else name
        saved = gzip.compress(raw, mtime=0) if filename.endswith(".gz") else raw
        (target / filename).write_bytes(saved)
        rel = str((target / filename).relative_to(ROOT / "review"))
        assert rel not in files, "Receipt filename collision"
        files[rel] = {"sha256": digest(saved), "source_sha256": digest(raw),
                      "source_path": source, "bytes": len(saved)}
    artifact_name = f"root-article-{args.stage}-final-artifact-manifest.json" if args.stage else "root-article-final-artifact-manifest.json"
    placement_name = f"root-article-{args.stage}-placement.json" if args.stage else "root-article-figure15-placement.json"
    for source, name in [(args.artifact_manifest, artifact_name),
                         (args.placement_receipt, placement_name)]:
        source_path = article / source
        assert source_path.resolve().is_relative_to(article), "Receipt outside article"
        raw = source_path.read_bytes()
        (ROOT / "review" / name).write_bytes(raw)
        files[name] = {"sha256": digest(raw), "source_sha256": digest(raw),
                       "source_path": source, "bytes": len(raw)}
    manifest = {"schema": "eal-jss-imported-root-editorial/2", "stage": args.stage or "historical-followup", "files": files,
                "root_article_pdf_sha256": digest((article / "eal-handover-data-story.pdf").read_bytes()),
                "root_article_md_sha256": digest((article / "article.md").read_bytes()),
                "scope": "These imported editorial and placement receipts bind the canonical root article and its exact figure assets. They do not certify the newly typeset JSS wrapper; the separate manuscript/submission proofs cover that output.",
                "coverage_storage": "Coverage JSON is gzip-compressed with exact original uncompressed bytes and source hash retained. Per-unit frozen copies and rendered page caches are not imported. Each source receipt retains its declared scope; importing it does not rerun its review or validator in the JSS folder."}
    manifest_path = target / "import-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    current = {"schema": "eal-jss-current-root-editorial/1", "stage": manifest["stage"],
               "manifest_path": str(manifest_path.relative_to(ROOT / "review")),
               "manifest_sha256": digest(manifest_path.read_bytes())}
    (ROOT / "review/editorial/current-import.json").write_text(json.dumps(current, indent=2) + "\n")
    print(f"Imported {len(files)} canonical-root receipts ({sum(x['bytes'] for x in files.values())} bytes), with distinct journal proof scope.")


if __name__ == "__main__":
    main()
