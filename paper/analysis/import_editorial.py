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
    args = ap.parse_args()
    target = ROOT / "review/editorial"
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in NAMES:
        raw = (args.article / "analysis" / name).read_bytes()
        filename = name + ".gz" if name.endswith("coverage.json") else name
        saved = gzip.compress(raw, mtime=0) if filename.endswith(".gz") else raw
        (target / filename).write_bytes(saved)
        files["editorial/" + filename] = {"sha256": digest(saved), "source_sha256": digest(raw),
                                          "source_path": "analysis/" + name, "bytes": len(saved)}
    for source, name in [("followup-final-artifact-manifest.json", "root-article-final-artifact-manifest.json"),
                         ("followup-profile-manuscript-binding.json", "root-article-figure15-placement.json")]:
        raw = (args.article / "analysis" / source).read_bytes()
        (ROOT / "review" / name).write_bytes(raw)
        files[name] = {"sha256": digest(raw), "source_sha256": digest(raw),
                       "source_path": "analysis/" + source, "bytes": len(raw)}
    manifest = {"schema": "eal-jss-imported-root-editorial/1", "files": files,
                "root_article_pdf_sha256": digest((args.article / "eal-handover-data-story.pdf").read_bytes()),
                "root_article_md_sha256": digest((args.article / "article.md").read_bytes()),
                "scope": "These imported editorial and placement receipts bind the canonical root article and its exact figure assets. They do not certify the newly typeset JSS wrapper; the separate manuscript/submission proofs cover that output.",
                "coverage_storage": "Coverage JSON is gzip-compressed with exact original uncompressed bytes and source hash retained. Per-unit frozen copies and rendered page caches are not imported; this is an original completed-review receipt, not a claim of re-running its validator in the JSS folder."}
    (target / "import-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Imported {len(files)} canonical-root receipts ({sum(x['bytes'] for x in files.values())} bytes), with distinct journal proof scope.")


if __name__ == "__main__":
    main()
