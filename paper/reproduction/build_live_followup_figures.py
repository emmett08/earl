"""Rebuild the two live follow-up figures from retained sanitized production inputs.

Run from any directory. The canonical production tree retains its original stems
and reviewed specification identities; this wrapper supplies the manuscript's
stable figure filenames without changing the numerical or graphical source.
"""

from pathlib import Path
import argparse
import shutil
import subprocess
import sys


ARTICLE = Path(__file__).resolve().parents[1]
PRODUCTION = ARTICLE / "reproduction" / "live-followup-figure-production"
STEMS = {
    "01-primary-outcome-cells": "16-followup-primary-outcome-cells",
    "02-endpoint-separation": "17-followup-endpoint-separation",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Also render PNG proof images")
    args = parser.parse_args()
    builder = PRODUCTION / "reproduction" / "build_report_figures.py"
    if not builder.is_file():
        raise FileNotFoundError(f"Missing retained canonical production tree: {builder}")
    command = [sys.executable, str(builder), "--input", "inputs/final-analysis-for-figures.json"]
    if args.render:
        command.append("--render")
    subprocess.run(command, cwd=PRODUCTION, check=True)
    (ARTICLE / "figures").mkdir(exist_ok=True)
    (ARTICLE / "captions").mkdir(exist_ok=True)
    for original, manuscript in STEMS.items():
        for extension in [".pdf", ".tikz.tex", ".spec.json", ".audit.json", ".review.json", ".png"]:
            if args.render and extension == ".review.json":
                (ARTICLE / "figures" / (manuscript + extension)).unlink(missing_ok=True)
                continue
            source = PRODUCTION / (original + extension)
            if source.exists():
                shutil.copy2(source, ARTICLE / "figures" / (manuscript + extension))
            elif extension in [".pdf", ".tikz.tex", ".spec.json"]:
                raise FileNotFoundError(source)
        for extension in [".caption.txt", ".alt.txt"]:
            source = PRODUCTION / "captions" / (original + extension)
            shutil.copy2(source, ARTICLE / "captions" / (manuscript + extension))
    if args.render:
        print("Rendered PDFs need a fresh review against their regenerated hashes; historical review files were not copied.")


if __name__ == "__main__":
    main()
