# Evidence figure design and audit

All five figures derive from `run/summary.json` and the 1,440 retained `run/trials/*/trial.json` records in the Actions ZIP for run 36275725154. The generator asserts the 40-case, six-model, six-arm assignment ledger, all complete trial states, six EAL–validator paired contrasts, the 19 reference-unavailable cases per model, and known cost coverage before writing. These are descriptive views of the reviewed development suite. The comparisons do not establish efficacy on a sampled task population, an isolated EAL notation effect, or a causal decomposition of prompt, collection and validation.

The figures use a 160 mm coordinate span and render to about 162 mm including the standalone PDF border and wrapper whitespace. The target declaration is 161 mm so the renderer's one-millimetre tolerance covers the latter. Text remains at or above 7 pt in the source. One warm accent distinguishes wrong outcomes and false support, with direction and direct labels carrying the same distinction in greyscale. No drawn blocks or circles occur. All data labels are live TeX text; font embedding and one-page PDF checks are automated. No plot is a generic bar, line, scatter or heat-map chart.

## Figure 1 — coverage ledger (`fig1-assignment`)

Primary job: expose the assigned/completed denominator in each model–arm cell so an accuracy ratio cannot silently omit a failed trial. On first reading the reader sees an entirely filled, balanced 6×6 factorial; on inspection, each cell is 40/40, and the total is 1,440/1,440 with zero failures and zero unattempted. Model names are shortened on the plate; the manuscript identifies pinned snapshots. The array represents incidence and completion, not outcome quality or independence across cases. At 160 mm, six headers and six model labels remain readable.

| Candidate | E | F | S | P | R | O | Total | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Open factorial ledger with exact counts | 4.2 | 4.5 | 5.0 | 4.5 | 4.5 | 4.0 | 4.49 | Chosen: exposes every analysis denominator without a colour key. |
| Nested Cartesian cardinality brackets | 3.8 | 4.0 | 5.0 | 4.7 | 4.6 | 3.5 | 4.25 | Compresses the total but hides individual cell completion. |
| Index-set factorisation glyph | 3.3 | 3.5 | 5.0 | 4.7 | 4.7 | 3.5 | 3.98 | Precisely states the 40×6×6 product, yet omits the cell-level missingness check. |
| Case-by-cell registration strip | 3.6 | 4.0 | 5.0 | 2.4 | 2.5 | 3.7 | 3.75 | The 1,440 visible strokes cost more attention than the uniform result warrants. |
| Permutation weave of model and arm strands | 3.5 | 3.6 | 4.2 | 3.1 | 3.5 | 4.3 | 3.67 | Incidence can be seen, but 36 contacts cannot carry the completion values economically. |

## Figure 2 — trial-level correctness (`fig2-correctness`)

Primary job: show all 1,440 full-answer correctness outcomes while retaining correspondence of case positions across arms and models. The first reading reveals variation concentrated in the nano snapshots; close reading identifies recurrent difficult case positions rather than interpreting 36 aggregate rates as independent samples. Every upright tick is a correct completed answer; every slanted tick is an incorrect completed answer. The 40 case IDs are sorted lexically, without presenting lexical order as experimental time. Trial marks are individual observations rather than a shaded heat-map cell. A mark says nothing about error mechanism or generalisation.

| Candidate | E | F | S | P | R | O | Total | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Case-aligned orientation traces | 4.8 | 4.7 | 5.0 | 3.8 | 4.2 | 4.2 | 4.62 | Chosen: preserves both 36 rates and common case identity. |
| Exact 6×6 numerator array | 4.0 | 4.1 | 5.0 | 4.8 | 4.7 | 3.4 | 4.34 | Compact, but loses whether arms miss the same cases. |
| Six rank signatures with case cutouts | 3.8 | 4.0 | 4.8 | 3.5 | 3.6 | 4.0 | 4.01 | Sorting by result would destroy the fixed cross-arm case registration. |
| Fault-set notation by model | 3.6 | 3.9 | 5.0 | 3.2 | 4.1 | 3.5 | 3.96 | Exact set notation is too dense for the 36 groups. |
| Paired overlap tiles for each case | 4.0 | 4.2 | 4.5 | 2.8 | 2.9 | 4.0 | 3.92 | Multiple arm intersections would need ambiguous occlusion. |

## Figure 3 — EAL–validator pairing (`fig3-paired`)

Primary job: expose off-diagonal case discordance that marginal accuracy conceals. Each exact 2×2 paired-count matrix is oriented with EAL correctness as rows and validator correctness as columns. Thus 4.1 nano has 21 jointly correct, six EAL-only correct, two validator-only correct and 11 jointly incorrect; 5.4 nano has 33, three, three and one respectively. Four other snapshots have 40 jointly correct and no discordance. Matrices are unshaded contingency arrays, not heat maps. They support finite-suite paired contrasts without making a population-level superiority or equivalence claim.

| Candidate | E | F | S | P | R | O | Total | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Six unshaded paired contingency matrices | 4.8 | 5.0 | 5.0 | 4.6 | 4.5 | 3.8 | 4.79 | Chosen: the off-diagonal cells make directional disagreement explicit. |
| Four-outcome algebraic decomposition | 4.2 | 4.7 | 5.0 | 4.1 | 4.4 | 3.5 | 4.46 | Exact, but less immediate as a paired comparison. |
| Symmetric-difference set plate | 4.1 | 4.4 | 4.8 | 3.6 | 4.0 | 4.0 | 4.25 | Highlights disagreement but masks jointly wrong cases. |
| Case-specific agreement braid | 4.3 | 4.5 | 4.9 | 2.8 | 3.1 | 4.2 | 4.20 | Retains identities at substantial visual cost. |
| Exact discordance fraction pairs | 3.7 | 4.0 | 5.0 | 4.2 | 4.5 | 3.6 | 4.16 | Net differences conceal the 3:3 discordance at 5.4 nano. |

## Figure 4 — reference-unavailable fate (`fig4-false-support`)

Primary job: distinguish a false assertion of failed checks from a false assertion of support when the independent reference is unavailable. The source denominator is 19 reference-unavailable cases per model. For 4.1 nano, EAL reports unavailable/unsupported/supported on 6/13/0 and the validator on 2/10/7. For 5.4 nano, both report 15/4/0. Across the two nano snapshots, EAL converts 17 unavailable cases to unsupported, while the validator converts 14 to unsupported and seven to supported. Each tally stroke is one case; direct status headings and three orientations preserve meaning in greyscale. The seven false supports are 7/31 of the 4.1-nano reference non-supported cases (19 unavailable plus 12 unsupported) when that broader safety denominator is stated; the fate plate itself conditions on the 19 unavailable references.

| Candidate | E | F | S | P | R | O | Total | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Three-status orientation tallies | 4.7 | 4.9 | 5.0 | 4.1 | 4.5 | 4.0 | 4.70 | Chosen: keeps false support and erroneous unsupported judgement separate. |
| Exact ternary outcome vectors | 4.1 | 4.6 | 5.0 | 4.5 | 4.6 | 3.7 | 4.47 | Exact numerals, but the distribution is harder to scan. |
| Negative-space false-support cut | 3.9 | 4.1 | 4.8 | 4.0 | 4.2 | 4.2 | 4.18 | Overemphasises seven supports while losing the 31 unsupported conversions across two snapshots. |
| Case-ID exception register | 4.0 | 4.3 | 5.0 | 2.9 | 3.4 | 3.5 | 4.08 | Auditable, but 38 identifiers cannot fit at article width. |
| Dual counterfactual status planes | 4.2 | 4.3 | 4.5 | 3.0 | 3.3 | 4.2 | 4.08 | A plane risks implying metric distance among three categorical statuses. |

## Figure 5 — resource ledger (`fig5-resource`)

Primary job: present the observed EAL/validator latency and estimated API-call cost alongside their arithmetic ratios, without suggesting a speed or cost benefit. Trial time is the median of 40 completed trials in each cell. Cost is total known model-call USD divided by 40, shown as milli-USD per assigned trial; there are zero unknown-cost calls in these cells. Ratios use unrounded source numbers and `≈` signals rounded displayed inputs. The comparison is descriptive for this run and does not isolate EAL notation from protocol and route differences.

| Candidate | E | F | S | P | R | O | Total | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Aligned pair-and-ratio ledger | 4.5 | 4.7 | 5.0 | 4.8 | 4.8 | 3.6 | 4.67 | Chosen: preserves units, both observed operands and the comparison. |
| Folded cost–time budget equation | 4.0 | 4.2 | 4.7 | 4.2 | 4.3 | 4.1 | 4.25 | Attractive for one model, but cumbersome across six. |
| Ratio-only symbolic signatures | 3.7 | 4.0 | 5.0 | 4.6 | 4.6 | 3.5 | 4.21 | Hides the absolute resource level and rounding check. |
| Six paired resource balance glyphs | 4.1 | 4.1 | 4.3 | 3.8 | 4.0 | 4.3 | 4.11 | Angles imply an unearned common scale between seconds and dollars. |
| Resource interval partitions | 3.8 | 3.9 | 4.5 | 3.2 | 3.5 | 4.0 | 3.88 | Partition area could be misread as calibrated burden. |

The scores use the skill's weighted six criteria: explanatory gain E (0.30), evidential force F (0.25), semantic fidelity S (0.20), perceptual economy P (0.10), reproduction R (0.10), and productive originality O (0.05). Totals are weighted sums rounded to two decimal places. Generic bars, lines, scatters, coloured heat maps, flowcharts and node-link diagrams were eliminated before this shortlist because they add conventional magnitude or process implications without preserving the relevant case pairing.

## Reproduction and final inspection

From the repository root:

```sh
python3 paper/run-36275725154/analysis/make_figures.py --zip /path/to/api-experiment-36275725154-1.zip
```

This writes five `.tikz.tex` sources and five vector PDFs into `paper/run-36275725154/figures/`. The generated PDF uses `latexmk`, `standalone`, `tikz`, `amsmath`, `xcolor`, `lmodern`, `pdfinfo` and `pdffonts`; the script checks page count and font embedding. The skill renderer independently compiled the same five sources and checked selectable text. All five 300 dpi previews were inspected at full and thumbnail scale: the case strokes remain distinct, the legend is separate from the last data row, matrix entries do not collide, each 19-case fate sum is legible, and cost ratios use an approximate-equality sign to account for rounded operands. Required manuscript preamble: `\usepackage{tikz,amsmath,xcolor}`. Captions belong in the manuscript and must describe the respective conditioning denominators.
