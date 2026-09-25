# Nano failure diagnosis: figure selection and audit

The figure separates correct assessment by the EAL host from correct final
communication by GPT-4.1-nano. Its population is the 40 EAL/MCP assignments in
run 36176588712, plan 3.1.0. It reports the preserved run and does not predict
the effects of subsequent interface or runner changes.

## Semantic contract

Within five seconds, a reader should see that only three assignments produced
fully correct final answers despite correct assessments in every attempted
assignment. Inspection should distinguish an incorrect completed answer, failure
to complete the response protocol within six calls, and an assignment skipped
after the runner stopped.

The arithmetic terms are mutually exclusive and exhaustive. The first two terms
form the 16 completed assignments; the first three form the 30 attempted
assignments. The top brace associates successful assessment with those 30
assignments. The status and operation annotations describe subsets, not additional
disjoint terms. The operation omission concerns the first response after a
successful assessment; it is not asserted to be the only error in each failed
conversation. The provider error occurred in the plain-validator condition and
triggered stopping across all six conditions. It was not an EAL host failure.

The numbers, plus signs and braces encode only cardinality and membership.
Distances, left-to-right order, colour and line width encode no elapsed time,
probability, causal sequence or effect size. The layout is designed at 160 mm
for the manuscript's 160 mm text block. Its single accent is redundant with the
direct label `correct`; every relation remains readable in greyscale.

## Ranked alternatives

Criteria, each scored from 0 to 5: explanatory gain (G, weight 0.30), evidential
force (E, 0.25), semantic fidelity (F, 0.20), perceptual economy (P, 0.10),
reproduction quality (R, 0.10), and productive originality (O, 0.05).

| Rank | Form | G | E | F | P | R | O | Weighted total | Reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Arithmetic decomposition with nested grouping braces | 5 | 5 | 5 | 4 | 4 | 4 | 4.75 | Preserves all 40 assignments and makes the distinction between assessment and final response explicit. |
| 2 | Identity-preserving correspondence between tool outputs and final outcomes | 4.5 | 4.5 | 5 | 3 | 4 | 3 | 4.33 | Exposes the difference between tools and answers, but repeated correspondence marks obscure the unattempted assignments. |
| 3 | Projection from detailed diagnostics onto the recorded outcome categories | 4 | 4 | 4.5 | 4 | 4 | 4 | 4.10 | Reveals what a single accuracy score discards, but its projection notation requires additional explanation. |
| 4 | Boolean eligibility conditions with cuts at failed requirements | 3.5 | 3.5 | 4.5 | 3 | 4.5 | 3 | 3.73 | Distinguishes protocol and decision requirements, but overlapping deficiencies complicate exhaustive counting. |
| 5 | Aligned excerpts showing correct tool data and mismatched final fields | 3 | 4 | 5 | 2 | 3 | 3 | 3.55 | Provides inspectable examples, but text density limits its account of the complete assignment population. |

The winning form uses a familiar mathematical equality to preserve the complete
denominator. Its grouping braces show two nested subsets without suggesting a
workflow. The alternative forms have genuinely different encodings; none is a
recolouring or rotation of the selected layout. Generic bars, flows, boxes and
circles were excluded before ranking.

## Source and reproduction

The source archive is `api-experiment-36176588712-1.zip`. Its run summary provides
the assignment partition. Transcript and tool-packet replay supplies the finer
diagnostics. `analysis/make_diagnosis_figure.py` reads the generated
`results/nano-diagnosis.json`; it checks conservation of the partition and
successful-assessment counts before writing the include-ready TikZ file.

The figure source is `figures/nano-failure-diagnosis.tikz.tex`; its paired PDF is
rendered from that exact file. Both are repository artefacts. The source requires
`amsmath`, `amssymb`, `xcolor` and `tikz`, with no additional TikZ libraries or
manuscript macros. Captions remain in the manuscript.

## Rendering and inspection

The canonical `design-evidence-visualisation` renderer compiled the exact source
with pdfLaTeX, checked one page, embedded fonts and selectable text, and produced
a 300 dpi preview. The rendered width is 159.0 mm against the 160 mm declaration.
The preview was inspected for arithmetic, bracket extents, annotation placement,
clipping and legibility. The large equation provides the primary reading; the
smallest annotation text is 8 pt. A separately rendered greyscale preview was
also inspected: the correct-answer accent remains legible and the direct label
preserves its meaning. Neither preview contains clipped strokes or colliding
labels. Manuscript-page inspection is recorded with the completed paper
validation.

Proposed caption: **Diagnostic decomposition of the later nano EAL/MCP run.**
The equality retains all 40 assigned cases. Braces group the completed and
attempted subsets; every attempted case received an assessment agreeing with
the reference. Twelve of the 13 incorrect completed answers had a wrong status.
The 14 failed conversations exhausted six model calls, and 13 initially omitted
the operation field after assessment. A provider HTTP 503 in plain-validator
triggered the runner's stop, leaving ten EAL/MCP assignments and 56 assignments
across all conditions unattempted. The annotations describe recorded outcomes
and do not identify the separate contribution of prompt length or output format.
