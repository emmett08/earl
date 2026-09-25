# Figure design and verification

Applied skill: `design-evidence-visualisation`. The figures are exact TikZ drawings with selectable vector text. No generated raster imagery is used for scientific quantities. The score below is a design judgement, not measured reader performance.

Candidate scores use 1–5 scales: claim coverage (35%), information economy (20%), reading order (15%), resistance to misinterpretation (20%) and reproducibility (10%). Five structurally different candidates were considered for each figure. Scores are weighted means; the selected form also had to fit the manuscript's actual evidence.

## Figure 1: typed correspondence

Purpose: show which proposition fields must correspond to the supplied observation, including interval containment and unit conversion. Evidence: implementation contracts and the constructed pressure example. Status: explanatory, not empirical.

| Candidate | Coverage | Economy | Reading | Misinterpretation | Reproduction | Weighted score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Paired field correspondence, selected | 5 | 4 | 5 | 5 | 5 | 4.80 |
| Commuting unit-conversion diagram | 3 | 5 | 4 | 4 | 5 | 3.95 |
| Nested validity-interval geometry | 3 | 5 | 5 | 4 | 5 | 4.10 |
| Constraint incidence matrix | 5 | 3 | 3 | 4 | 5 | 4.10 |
| Evidence provenance braid | 3 | 3 | 3 | 3 | 4 | 3.10 |

The chosen figure exposes five correspondences in one reading pass. Its bottom equation gives the result-unit conversion; the method name fixes the computational interpretation. The caption states that assignment metadata and the effect size are stipulated. Generic box-and-arrow architecture would obscure the relations that are actually checked.

## Figure 2: finite-report decision region

Purpose: expose inclusive performance thresholds while keeping ineligible evidence separate from demonstrated threshold failure. Evidence: the synthetic API example and original oracle's availability distinction. Status: formal rule geometry with two stipulated points.

| Candidate | Coverage | Economy | Reading | Misinterpretation | Reproduction | Weighted score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conditional acceptance region, selected | 5 | 5 | 5 | 4 | 5 | 4.80 |
| Truth-table lattice | 5 | 3 | 3 | 5 | 5 | 4.30 |
| Predicate incidence matrix | 4 | 4 | 3 | 4 | 5 | 3.95 |
| Logical formula with aligned substitutions | 4 | 5 | 3 | 4 | 5 | 4.15 |
| Counterexample cut-set composition | 4 | 3 | 3 | 4 | 4 | 3.65 |

This is a specialist decision-region diagram, not a generic chart of measurements. The origin is visible, units are stated and the complete inclusive boundary is drawn. Request count is fixed by the caption's condition. The unavailable state lies outside the performance coordinate plane. It does not mean a large latency or error rate.

## Figure 3: paired experimental outcomes

Purpose: show case-paired agreement, directional discrepancies and completion exposure for all six models. Evidence: historical version-2 scorer replay; every matrix entry is generated from `results/summary.json`. Status: descriptive empirical result.

| Candidate | Coverage | Economy | Reading | Misinterpretation | Reproduction | Weighted score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Canonical 2-by-2 contingency matrices, selected | 5 | 5 | 4 | 5 | 5 | 4.85 |
| Case-by-condition binary incidence atlas | 5 | 2 | 2 | 4 | 5 | 3.80 |
| Paired difference dot display | 3 | 5 | 5 | 3 | 5 | 3.90 |
| Alluvial outcome braid | 4 | 3 | 3 | 3 | 4 | 3.45 |
| Discordance-only arithmetic decomposition | 3 | 5 | 4 | 3 | 5 | 3.75 |

The canonical matrix retains the off-diagonal counts needed for the paired difference and the agreement cells that a difference alone would hide. Completed-pair denominators and the caption prevent the zero-execution model from appearing to have produced 40 observed pairs of wrong answers. The GPT-5.4 full model has a mathematically zero realised-yield difference in the absence of completed answers; no equivalence interpretation is permitted.

## Render checks

Sources declare a 160 mm target width. The reproducible repository renderer adds a 2 mm border to the 156 mm drawing; figures are included at 160 mm in the paper. Text is 8–9 pt with larger bold headings, one dark teal accent and direct labels. The visualisation skill's independent renderer also compiled every exact source and checked embedded fonts, single-page output, width and selectable text. Its 1.5 mm border produced 159 mm previews.

All three 300 dpi previews were visually inspected: no collision, clipping, overlapping mathematical labels or missing glyphs was found. Direct numeric labels and bracket positions preserve every distinction in greyscale; accent colour is redundant. Final paper pages were inspected after compilation. Validation commands and build outcome are in `validation.txt`.
