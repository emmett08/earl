#!/usr/bin/env python3
"""Build each include-ready figure at its natural physical size, offline."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREAMBLE = r"""\documentclass[10pt,border=1pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{lmodern,amsmath,amssymb,mathtools,bm,xcolor,tikz,pgfplots}
\begin{document}
\input{figure-input.tex}
\end{document}
"""


def main():
    for source in sorted((ROOT / "figures").glob("*.tikz.tex")):
        with tempfile.TemporaryDirectory(prefix="earl-figure-") as directory:
            work = Path(directory)
            shutil.copyfile(source, work / "figure-input.tex")
            (work / "figure.tex").write_text(PREAMBLE)
            result = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "figure.tex"],
                                    cwd=work, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(result.stdout[-10000:])
            log = (work / "figure.log").read_text(errors="replace")
            assert "Overfull" not in log, f"Overfull figure: {source.name}"
            output = source.with_name(source.name.replace(".tikz.tex", ".pdf"))
            shutil.copyfile(work / "figure.pdf", output)
            print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
