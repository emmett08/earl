#!/usr/bin/env python3
"""Check retained editorial bytes and the current canonical article binding."""
from pathlib import Path
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    review = ROOT / "review"
    manifests = sorted((review / "editorial").rglob("import-manifest.json"))
    assert manifests, "No imported canonical editorial receipts"
    count = 0
    for path in manifests:
        manifest = json.loads(path.read_text())
        for rel, item in manifest["files"].items():
            retained = review / rel
            assert retained.resolve().is_relative_to(review), rel
            raw = retained.read_bytes()
            assert digest(raw) == item["sha256"] and len(raw) == item["bytes"], rel
            source = gzip.decompress(raw) if retained.suffix == ".gz" else raw
            assert digest(source) == item["source_sha256"], rel
            count += 1
    current_path = review / "editorial/current-import.json"
    if current_path.is_file():
        current = json.loads(current_path.read_text())
        path = review / current["manifest_path"]
        assert path.resolve().is_relative_to(review), path
        assert digest(path.read_bytes()) == current["manifest_sha256"]
        current_manifest = json.loads(path.read_text())
        article = json.loads((review / "article-import.json").read_text())
        assert current_manifest["root_article_md_sha256"] == article["article_md_sha256"]
        assert current_manifest["root_article_pdf_sha256"] == article["source_article_pdf_sha256"]
        assert current_manifest["stage"] == current["stage"]
    print(f"{count} retained canonical editorial receipts across {len(manifests)} stages: exact hashes passed.")


if __name__ == "__main__":
    main()
