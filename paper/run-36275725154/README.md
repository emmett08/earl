# Run 36275725154: complete six-model development pilot

This is a separate article about the completed 26 September 2026 EAL/2 API
load-test development run. It does not replace `../manuscript.tex`, which analyses
earlier, version-specific experiments.

The source run is [GitHub Actions 36275725154](https://github.com/emmett08/earl/actions/runs/36275725154),
at commit `f8c629f49b5bef6c760de2029f6bc7db0e762a6f`. Download its
[retained artifact](https://github.com/emmett08/earl/actions/runs/36275725154/artifacts/10916929645)
as a ZIP. Its SHA-256 is
`0d1286e661eabb78470a2283d160979d4aae7221f98a086189ee7495124de018`.
The GitHub artifact currently expires on 26 October 2026; preserve an authorised
copy for a lasting raw-data audit.

From this directory:

```sh
make reproduce ARCHIVE=/path/to/api-experiment-36275725154-1.zip
make check
```

The build needs Python 3, `latexmk`, `pdflatex`, BibTeX, `pdfinfo`,
`pdffonts`, and `pdftotext`, with LaTeX packages `algorithm`, `algpseudocode`
(`algorithmicx`), `standalone`, `tikz`, `natbib`, `capt-of`, and the ordinary
maths and font packages used in `manuscript.tex`. A complete TeX Live
installation provides these dependencies.

`analysis/analyse_run.py` checks the ZIP digest, fixed source commit, manifest
coverage, all 1,440 trial identities, summary cells, paired contrasts and known
model-call costs. It regenerates `results/aggregate.json` and the compact
`results/assignments.csv` without copying model transcripts or raw HTTP events
into this paper. `analysis/make_figures.py` regenerates the five data-bound
TikZ sources and rendered vector PDFs. `analysis/check_paper.py` checks the
rendered article, including the exact figure count and pivotal numerical claims.

The 40 cases were deliberately reviewed for development. The article reports
finite-suite observations and proposes a held-out factorial follow-up; it does
not infer population superiority or an EAL-notation effect. The Python audit
and repository tests are executable checks, not a Lean proof of program
refinement. The displayed nearest-rank identity is a mathematical observation;
the application of the threshold to the engineering task remains empirical.
