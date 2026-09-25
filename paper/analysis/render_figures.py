"""Render the exact include-ready TikZ sources using an installed TeX Live."""
from pathlib import Path
import os
import subprocess
import tempfile

PAPER = Path(__file__).resolve().parents[1]
env = {**os.environ, "SOURCE_DATE_EPOCH": "1790366400", "FORCE_SOURCE_DATE": "1"}
for source in sorted((PAPER / "figures").glob("*.tikz.tex")):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        tex = (r"\documentclass[border=2mm]{standalone}" + "\n"
               r"\usepackage{amsmath,amssymb,xcolor,tikz}" + "\n"
               r"\pdfinfoomitdate=1\pdftrailerid{}" + "\n"
               r"\begin{document}" + "\n" + source.read_text() + "\n" + r"\end{document}")
        (root / "figure.tex").write_text(tex)
        result = subprocess.run(["pdflatex", "-halt-on-error", "-interaction=nonstopmode", "figure.tex"],
                                cwd=root, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout[-6000:])
        source.with_name(source.name.replace(".tikz.tex", ".pdf")).write_bytes((root / "figure.pdf").read_bytes())
        print(source.name)
