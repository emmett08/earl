# JSS article: the retained EAL/2 workflow pilot

Read **[manuscript.pdf](manuscript.pdf)**. The main source is [manuscript.tex](manuscript.tex); **[jss-submission.zip](jss-submission.zip)** is a separately compiled, flat Elsevier source bundle. This folder replaces the earlier API-load-test papers. Their observations are not pooled with this experiment; earlier versions remain in Git history.

The article reports the completed principal collection on 28 September 2026: 192 paired blocks, 384 sequences and 4,224 fresh sessions. Its subject is the whole workflow, including the EAL host's automatic delivery of a checked assessment. Thirty-one AI-coded answers remain ambiguous (28 recipients, three donors). Independent assessor validation and a supported prospective allocation are not complete. Neither the article nor the bundle claims a completed confirmatory study.

## Reproduction, in order

Use the repository revision accompanying this paper. Numerical reproduction needs Python 3.11+ and the standard library. EAL validation additionally needs the repository installed (`python -m pip install -e .` from the repository root; installation may need network access). The builds need `latexmk`, pdfLaTeX, BibTeX, Latin Modern, TikZ/PGFPlots, standalone, listings, microtype, geometry, booktabs, tabularx, xurl and hyperref. The unmodified Elsevier class and numeric bibliography style are included.

From the repository root:

| Order | Command | Purpose and output |
|---|---|---|
| 1 | `make -C paper reproduce` | Verify input hashes; recompute references, correctness, usage, paired bounds and plot coordinates; derive the highlighted EAL excerpt. Produces `results/` and `.tikz.tex` files. |
| 2 | `make -C paper check` | Detect changed data, stale generated outputs, broken pairing, unmatched API attempts, score discrepancies, EAL parse/format differences and highlighting-keyword drift. Writes no data. |
| 3 | `make -C paper pdf` | Repeat checks, compile six natural-size vector figures, then compile `manuscript.pdf` with references. |
| 4 | `make -C paper submission` | Build the article and make a flat source ZIP; compile that ZIP's source independently before packaging it. |

These commands never collect model responses, contact the API or change the frozen experiment budget. No workflow dispatch, annotation import or new labels are needed to reproduce the present article. `python paper/analysis/reproduce.py --check` runs the numerical audit without requiring the repository package or LaTeX. `make -C paper clean` removes only LaTeX intermediate files.

The flat submission ZIP contains the article, vector figures, tables, listing, bibliography, class and style sources, highlights and author-review notes. It is a manuscript source bundle, not the full research-data archive. The repository's `paper/data/`, `analysis/` and annotation records supply the replication materials.

## Evidence and identities

| Item | Identity |
|---|---|
| Frozen run | `984bd05d-6366-41c3-b9ae-ee8766835b08` |
| Collection | [36477862213](https://github.com/emmett08/earl/actions/runs/36477862213), revision `d52e2bd0898ed519253aedbbc8e002e493dd64d2` |
| Corrected annotation export | [36487342999](https://github.com/emmett08/earl/actions/runs/36487342999), artefact `10998924773` |
| Successful offline finishing | [36492423435](https://github.com/emmett08/earl/actions/runs/36492423435), revision `31a3cba769948e123a59ca35c54c5135ad005f54` |
| Finished artefact | [11001997190](https://github.com/emmett08/earl/actions/runs/36492423435/artifacts/11001997190), `experiment-finish-36492423435-1`; scheduled expiry 27 December 2026 |
| Original ZIP SHA-256 | `0c1b8f5af0990f04c20564ffffee9c103ac47cbcab7ca940639225d80bb32d23` |
| Completed-labels SHA-256 | `e0fdfa6aa0b1f37b72334d55a4bfec06c281198ce08483efb0c455b6a7bf43c4` |

`data/manifest.json` identifies every source and retained file. The gzip files preserve the complete annotated rows, corpus, frozen plan/contracts, provenance, calibration, segments and saved reports. Decompressed copied files are byte-identical to their archive counterparts. `call-accounting.json.gz` is an explicit projection of all 5,453 calls: usage, timing, IDs, cost and request configuration remain; duplicated request text, tool definitions and opaque provider response payloads are omitted. Full initial prompts, final answers and session evidence events remain in the annotated rows. This package supports the article's analyses, but does not claim to preserve every byte of the original provider transcript.

If the original ZIP is available, `python paper/analysis/extract_archive.py PATH_TO_ZIP` reconstructs the compact snapshot after verifying the exact archive hash. This is an optional provenance check, not a prerequisite for normal reproduction. The archive path is the sole input; passing another run is rejected. Do not relabel or replace the data merely to satisfy a planner gate.

The annotation procedure and manual semantic decisions are in [AI-CODING.md](../annotations/AI-CODING.md), [the committed labels](../annotations/pilot-36477862213-ai-labels.json) and [the adjudications](../annotations/pilot-36477862213-ai-adjudications.json). The article snapshot also retains per-answer assessor provenance and quotations. These are AI-assisted codes, not independent human labels.

## What the analysis verifies

All expected decisions are recomputed from dated facts and requirement scopes, separately from both saved scores and the host. The script checks 48 strata with four paired repetitions, eleven ordered sessions per sequence, donor tool availability, the model used for each attempt, complete and unique attempt coverage, and recorded usage/cost. It reconstructs all point counts, correctness envelopes, paired token distributions, horizon profiles and resource tables, and compares totals with the frozen report. It independently recalculates the two empirical Bernstein radii. The approximate stratified delta-method resource interval is preserved from the revision-bound report and explicitly attributed to that implementation; it is not claimed to have an independent second estimator here.

The source example is the actual retained cutover argument. The printed excerpt is derived by the current formatter using the experiment's registered reasoning method. Validation checks parse–format–parse semantic identity, exact excerpt equality and equality of the highlighting keyword set with `grammar/EAL.g4`. No EAL/6.1 or EARL grammar is substituted.

## Figures and review

Six figures have include-ready `.tikz.tex` source and vector PDFs under `figures/`. They use retained data except the explicitly assumption-based coding-sensitivity region. The two-panel `estimands-uncertainty` figure distinguishes observed coding bounds from the conditional sampling interval and explains aggregate token normalisation. Its coordinates and labels are generated from the audited results; both correctness interval endpoints are checked against a separate recalculation. Natural-size text is at least 8.5 pt. Colour is supplemented by direct labels, stroke weights, marker shape and dash pattern. [The figure design record](review/figure-design.md) documents alternatives, semantic decisions and selection scores. [The verification record](review/verification.md) records numerical, syntax and visual checks.

The manuscript uses the official Elsevier `elsarticle` 3.4 class and numeric bibliography style, distributed with their source under LPPL; see [vendor/SOURCE.md](vendor/SOURCE.md). This is a review manuscript prepared for JSS, not a claim of acceptance or verified compliance with every current submission requirement. [Author-review notes](review/author-review.md) list the remaining authorship, declarations, availability and scientific decisions. No journal submission or public release is performed by these build commands.
