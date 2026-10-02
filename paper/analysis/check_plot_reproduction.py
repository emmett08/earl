#!/usr/bin/env python3
"""Recreate exact plot sources in isolation; leave accepted PDFs untouched."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / "review/article-import.json").read_text())
    compared = {}
    with tempfile.TemporaryDirectory(prefix="eal-jss-plot-reproduction-") as directory:
        work = Path(directory)
        for name in ["analysis", "tables", "reproduction", "followup-analysis"]:
            if (ROOT / name).is_dir():
                shutil.copytree(ROOT / name, work / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
        (work / "figures").mkdir()
        (work / "captions").mkdir()
        shutil.copyfile(ROOT / "figures/alternative-text.json", work / "figures/alternative-text.json")
        subprocess.run([sys.executable, str(work / "reproduction/build_figures.py")], check=True)
        if "15-reference-undetermined-profiles" in manifest["figure_ids"]:
            subprocess.run([sys.executable, str(work / "reproduction/build_followup_figures.py")], check=True)
        for name in manifest["figure_ids"]:
            for rel in [f"figures/{name}.tikz.tex", f"captions/{name}.caption.txt", f"{name}.spec.json"]:
                assert (work / rel).read_bytes() == (ROOT / rel).read_bytes(), f"Non-reproducible plot source: {rel}"
                compared[rel] = digest(ROOT / rel)
    proof = {"schema": "eal-jss-plot-reproduction/1", "figure_ids": manifest["figure_ids"],
             "files_reproduced_exactly": compared,
             "scope": "Exact deterministic source, caption and specification reproduction in a disposable directory. Accepted vector PDFs and their original exact reviews are unchanged."}
    (ROOT / "review/plot-reproduction.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Exactly reproduced {len(manifest['figure_ids'])} plot sources, captions and specifications in isolation.")


if __name__ == "__main__":
    main()
