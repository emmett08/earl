# Verification record

Scope: the replacement JSS review article for retained run `984bd05d-6366-41c3-b9ae-ee8766835b08`, collected on 28 September 2026. Verification covers this manuscript and its reproduction package. It does not certify independent assessor validity, real-project effectiveness or journal acceptance.

## Evidence reconciliation

- The original finished archive was checked against SHA-256 `0c1b8f5af0990f04c20564ffffee9c103ac47cbcab7ca940639225d80bb32d23` before extraction. All 13 retained gzip files have recorded checksums; copied JSON contents are byte-identical after decompression. The accounting projection and its omitted fields are documented.
- All 384 sequences, 192 paired blocks, 4,224 sessions and 5,453 distinct API attempts reconcile. Each of 48 strata has four paired repetitions. Donors have tools enabled; recipient masks and per-call model identifiers match their recorded configuration. No unassigned or double-counted attempt remains.
- A separate article implementation recomputes all task reference decisions from the six cases' rules, scopes, dated facts and timelines. It agrees with the authored expected decisions and every retained reference. Every derived decision correctness value agrees with its saved score.
- The code recomputes 1,876/17/27 EAL recipient correct/incorrect/unknown outcomes and 746/1,173/1 ordinary outcomes, retaining all denominators. It reconciles 31 ambiguous codes across all sessions, including three donors.
- Input, output, cached and reasoning token counts, acquisitions, reuses and costs agree with the retained report. The article reconstructs the 35.0548778% aggregate input-plus-output reduction and all plot coordinates from those receipts. Cached and reasoning tokens are not added twice.
- The empirical Bernstein radii are independently recalculated from whole-pair envelopes. The approximate resource interval is explicitly retained from the revision-bound implementation; a second independently developed resource-interval estimator is not claimed.
- `analysis/reproduce.py --check` detects stale generated outputs. No collected answer, reference, budget, run identity or source contract was modified.

## Language example and build

- The full example is byte-preserved from `sequences/block-0000.eal/project/argument.eal` in the finished archive. It passes the current EAL/2 parser and validation with the experiment's registered method contract.
- Canonical formatting preserves the parsed semantic representation. The printed reasoning/argument excerpt is extracted from that formatting and checked for exact equality. It is described as an excerpt, not a standalone complete program.
- The syntax-highlighting keyword set equals the literal keyword set in `grammar/EAL.g4`. Keywords use bold teal, strings neutral grey and comments italic grey. Both the code listing and the inline method selector are highlighted. EAL/2 is kept distinct from EARL/6.1, package version and protocol version.
- The article builds with the pinned official Elsevier 3.4 class and numeric bibliography style. The final build has no undefined citations/references, overfull boxes, underfull boxes or LaTeX warnings. The abstract has 214 whitespace-delimited words; five highlight entries each fit within 85 characters.
- The flat 29-file source bundle was built in a separate temporary directory, compiled independently and checked for its file hashes. The text of all 15 PDF pages is identical to the repository build. The source ZIP contains no nested paths.

## Figure and page review

All five include-ready TikZ sources passed the evidence-visualisation renderer's source checks, physical-width checks, font-embedding checks and selectable-text checks. They use no global resizing. Figure text is 8.5 pt at natural size. Rendered widths are 158.8 mm (case correctness), 147.2 mm (session profiles), 150.1 mm (paired ratios), 147.6 mm (cumulative tokens) and 147.6 mm (coding sensitivity), all within the declared 160 mm maximum and manuscript text width.

Each figure was visually inspected in colour and greyscale. All 15 integrated article pages were rendered and inspected; later layout changes were re-rendered and inspected on affected pages. The listing and tables remain legible, captions specify units and uncertainty, and the numeric resource table appears with the results before the references. Observed production defects were repaired: a clipped sensitivity annotation, an overlapping ratio label, a cumulative-plot legend covering data, initially crowded legend spacing, unbreakable long identifiers, collapsed spaces in command names and a resource table stranded after the references.

The plots retain the unfavourable paired token observation, all task/configuration outcomes and all ambiguous-code envelopes. The sensitivity region uses labelled hypothetical error allowances and is not presented as collected data. Greyscale preserves arms/models through shape, position and dash pattern. No rasterised plot, generated observation, illustrative confidence interval or decorative process diagram substitutes for evidence.

## Source and interpretation review

The cited related-work and statistical claims were checked against primary publication pages or papers: PAL (PMLR), Logic-LM (ACL Anthology), ReAct (authors' arXiv paper), Lost in the Middle (ACL Anthology), LLM-as-a-Judge (authors' arXiv paper), Maurer–Pontil (Theorem 11 in the paper), Deng and colleagues (authors' paper and ACM record), and SACM 2.3 (OMG). Bibliographic metadata, page ranges and available DOIs were checked. No claim is made that those studies validate this experiment's labels or external validity.

The manuscript consistently identifies the whole-workflow information-delivery asymmetry, dependent recipient trajectories, selected synthetic tasks, model-family confounding, post-collection AI coding and blocked prospective allocation. The unconditional field name `measurement_status: complete` in a retained decision-report subsection is not used to override the explicit 31 unresolved annotations or the planner's blockers. The frozen plan's 21,600-second runtime limit is distinguished from the older descriptive protocol value and the 6,000-second job allowance.

The software verification attached to successful processing run 36492423435 previously passed 966 tests with one skip. This paper-only replacement changes no measured implementation and does not claim a new run of that entire software suite. Relevant new verification is the complete offline data audit, language-example validation, figure checks and both article builds.

Remaining author decisions and scientific limitations are listed in `author-review.md`. They are not concealed by a successful build.
