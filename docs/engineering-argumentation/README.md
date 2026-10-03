# Engineering argumentation with AI agents

Read [the typeset article](engineering-argumentation.pdf). The complete [LaTeX source](engineering-argumentation.tex) contains the argument, numbered references and two comparison tables, and includes the [TikZ figure](figures/decision-sufficiency.tikz.tex) and its [caption](figures/decision-sufficiency.caption.tex).

The maintained prose remains in [the Markdown article](../engineering-argumentation-ai-agents.md). `reproduction/typeset.py` converts that prose and its references into the complete LaTeX source; edit the Markdown before regenerating. The PDF uses A4 pages, a 155 mm text width and Latin Modern at 11 pt. The figure and both tables have separate short captions.

From the repository root:

```sh
make -C docs/engineering-argumentation pdf
```

Regeneration requires Python 3 and Pandoc. Compilation requires `latexmk`, pdfLaTeX, Latin Modern, TikZ/PGFPlots and the standard packages declared in the preamble. The committed LaTeX can also be compiled directly, without Pandoc:

```sh
cd docs/engineering-argumentation
latexmk -pdf -interaction=nonstopmode -halt-on-error engineering-argumentation.tex
```

The figure uses stipulated loss functions and hypothetical compatible ranges to illustrate when the same action remains preferable throughout the remaining uncertainty. These are not measured results or confidence intervals. [Retained inputs](figures/decision-sufficiency.inputs.json), [exact calculations](figures/calculate_sufficiency.py) and [derived values](figures/decision-sufficiency.values.json) make the construction reproducible. Run `python3 figures/calculate_sufficiency.py` from this directory to regenerate the included figure source and values.

The [figure specification](figures/decision-sufficiency.spec.json) records its scope and standalone build recipe, using the repository's existing figure tools. The retained [mechanical audit](figures/decision-sufficiency.audit.json) and [independent semantic review](figures/decision-sufficiency.review.json) refer to the committed standalone PDF and its exact inputs. From this directory, check that association with:

```sh
python3 ../../paper/reproduction/figure-tools/scripts/figure_review.py \
  figures/decision-sufficiency.review.json \
  --spec figures/decision-sufficiency.spec.json \
  --audit figures/decision-sufficiency.audit.json --check-files
```

A changed model or caption requires renewed figure review. Rebuilding the standalone figure regenerates its audit; the review must then refer to the new artefacts. Compiling the article alone leaves those records unchanged.

The article's runtime and empirical statements remain bounded by the current EAL/3 documentation and retained studies. This document changes no language, API or observation-schema contract.
