# Follow-up report figures

Both figures have been rendered from the final sanctioned endpoint data.
Mechanical and independent numerical checks pass. Both current independent
agent semantic reviews accept the figures; no provisional or mock primary
outcomes were rendered. Exact assets and hashes are recorded in
`validation/final-production-receipt.json`. Human interpretation benefit
remains unmeasured by agent screening.

The input contract is `inputs/final-analysis.schema.json`. Retain the approved
sanitized export as `inputs/final-analysis-for-figures.json`. The figure builder
accepts exactly 120 recipient cells with final endpoint fields and no response
text. It does not interpret answers, adjudicate codes, or open task/scorer/plan,
calibration-key or coder-output files.

The source collection audit excerpt retains the provenance of 128 actual API
attempts: 8 donors, 120 recipients, 40 matched position groups and 40 equal EAL/conventional
model-visible packets. Preliminary canonical-only counts are excluded from this
retained excerpt and are not used as primary results.

Rebuild from this production directory:

```bash
python3 reproduction/build_report_figures.py --input inputs/final-analysis-for-figures.json --render
python3 reproduction/make_final_size_previews.py
```

The two figures are the complete primary-outcome cell matrix and a
comparison of separate canonical/whole-verdict/primary endpoint counts with
contradiction diagnostics, with unresolved whole verdicts distinguished from
unresolved primary endpoints. A contradictory explanation can determinately
fail the conjunction despite an unresolved whole verdict. All counts retain forty positions per context,
eight common-donor task clusters and one repeat. References are authored
synthetic states; model outputs are observed; endpoint labels are derived final
AI codes. Factual grounding is unassessed. No superiority, population reliability,
human benefit, or stochastic repeatability claim is supported.

The figures use include-ready TikZ, selectable Latin Modern text, a 160 mm maximum
width, 9 pt labels and 0.4 pt stroke floor. Each has a separate caption/alt file,
schema-valid specification, vector PDF, PNG preview, mechanical audit and an
independent semantic review. Caption and alt bytes are declared dependencies.
The independent semantic review is a separate step after the builder renders
the exact final inputs; successful rendering does not assert review acceptance.
Colour, greyscale and final-size inspection follows actual rendering; manuscript
placement must be inspected by the report assembler.

Python dependencies are recorded in `reproduction/requirements.txt`. TeX rendering
also requires `latexmk`, `pdflatex`, TikZ, Latin Modern and Poppler. Bundled production
tools are copied unchanged from design-evidence-visualisation.

The audit records bind absolute canonical production paths. Byte-identical
copies elsewhere preserve the original build records; a fresh render elsewhere
needs fresh audits and reviews for that location and PDF hash. Omitting
`--render` regenerates source, specification, captions, alt text and tabulations
without replacing the accepted vector artifacts. Rendering can change PDF
metadata hashes even when the visible output is identical.
