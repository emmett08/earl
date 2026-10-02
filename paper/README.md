# JSS review article: the completed EAL/3 handover pilot

Read [manuscript.pdf](manuscript.pdf). The maintained journal source is [manuscript.tex](manuscript.tex), the imported canonical prose is [article.md](article.md), and [jss-submission.zip](jss-submission.zip) is a separately compiled, flat Elsevier source bundle. The Elsevier class and numeric style remain unmodified; their source and licence are retained under `vendor/`.

This is one completed pilot: 192 paired blocks, 384 sequences, 4,224 sessions and 5,442 API attempts. Collection run [36985062352](https://github.com/emmett08/earl/actions/runs/36985062352) and offline finish run [36997861629](https://github.com/emmett08/earl/actions/runs/36997861629) share identity `45488cb5-624e-4267-b12c-97fe503ff4d1`. The collection revision is `c0974bc6bb6a2df30d1423b6248bfc51b4d2a9d7`; finish is `cea2b59e686d57e0c071924f184b497919ec91a7`. The finish artifact is `11222114140`, and the exact ZIP SHA-256 is `491df25b38bd22554143c0e146a7ac547d0686ea1022b1c9bf87b6093482b69a`.

Coding supplies an entry for all 4,224 answers: 4,199 resolved decisions and 25 ambiguous interpretations. The AI codes have no independent human validation or measured error rate. Conditional recipient reference-match bounds are 97.19–97.86% for EAL and 38.49–39.01% for ordinary. Donor-inclusive tokens are 1,980,029 and 2,982,385 respectively: 33.61% fewer EAL tokens. The comparison bundles information delivery, evidence management and host computation. It establishes neither a notation-only effect nor net adoption cost savings.

## Reproduction

Numerical checks use Python 3.11+ and the standard library. Parser checks require the repository package; figure contract checks need `jsonschema`. PDF compilation needs `latexmk`, pdfLaTeX, Latin Modern, listings, geometry, microtype, longtable, xurl and the standard packages named in the source. Rebuilding standalone vector figures additionally needs NumPy, pandas, TikZ/PGFPlots, PyMuPDF and the dependencies documented by `reproduction/figure-tools/`.

From the repository root:

| Command | Result |
|---|---|
| `make -C paper reproduce` | Recompute point counts, paired ratios, tables and independent reference decisions; derive the actual EAL/3 listing excerpt. |
| `make -C paper reproduce-plots` | Recreate current plot sources, captions and specifications byte-for-byte in a disposable directory, preserving accepted PDF review bindings. |
| `make -C paper check` | Verify data hashes, every label/text/quote join, all scores and API attempts, two Bernstein radii, parser round trips and exact imported figure bindings. |
| `make -C paper pdf` | Run checks and compile the journal manuscript with the retained, exactly reviewed vector figures. |
| `make -C paper submission` | Independently compile the flat source bundle before packaging it. |

These commands perform no model collection or workflow dispatch. `analysis/reproduce.py --check` runs numerical checks without the repository package or LaTeX. The resource interval remains explicitly attributed to the retained stratified delta/Welch implementation; point counts and the bounded quality radii are independently recomputed.

`data/manifest.json` records source identities and hashes. Compressed annotated rows, cases, contracts, frozen labels and mapping retain original archive bytes. `call-accounting.json.gz` projects accounting, configuration, usage, cost and timing fields from all 5,442 calls; duplicated provider payloads and request text are omitted. Full initial prompts, final answers and session evidence events remain in the annotated rows. With the exact finish ZIP available, `python paper/analysis/extract_archive.py PATH_TO_ZIP` recreates this compact snapshot and rejects other archives.

The original six archives are part of the separate full research package. The journal source ZIP contains sources, figures, listing, class/style, highlights and author-review notes; it is not the full research-data archive.

## Separate supplemental measurement review

`followup/measurement/` retains the 169 masked answers, private join mapping, two reviewer records, adjudication inputs/result, supplemental summary/report and compressed derived rows. Their manifest binds all original file hashes and the immutable primary finish snapshot. The derived alternative has six targeted amendments and 19 remaining ambiguities; EAL recipient totals are 1,871 matches, 42 mismatches and seven unresolved. Primary codes, figures and inference still use the 25-ambiguity finish snapshot.

`make -C paper check-supplemental` calls the repository's `scripts/review_pilot_measurement.py` review function against a temporary byte-identical decompression of the primary rows. It reconstructs the supplemental summary, verifies every quotation and join, and checks the six amendments while proving all raw answers, API attempt identities and original resource totals remain unchanged. AI-review agreement and adjudication remain conditional measurements rather than independent human validation.

## Canonical prose and figures

`analysis/sync_article.py ARTICLE_DIRECTORY` imports the latest `article.md` and Pandoc-generated `article.tex` into the preserved journal wrapper. It also copies the figures, their exact source inputs and audit contracts. Run it after changing the canonical article, then run `make -C paper submission`. The wrapper adds a parser-validated retained source excerpt and author-review declarations. It preserves the completed pilot's numerical and scientific qualifications.

The current vector PDFs retain their original exact file hashes and semantic reviews. `analysis/check_figures.py` checks copied bytes, specification inputs, audit provenance hashes and bound final/prototype PDFs using relative declared input identities. Original absolute build locations remain in the retained audit records. Reusing those reviews does not certify new renderings or journal-page placement. Journal placement is covered separately by `review/verification.md` and `review/manuscript-proof.json`.

Editable plotting generators are retained in `reproduction/`. In a disposable copy, `python reproduction/build_figures.py --render` rebuilds the original fourteen figure calculations and their declared alternatives. Rebuilt PDFs have new exact bytes and need new review bindings before replacing the retained accepted figures. The new reference-state figure is independently generated by `reproduction/build_followup_figures.py` when its current source inputs are included.

Authorship, affiliations, funding, competing interests, oversight and a durable public data statement require actual author review. The package is a review draft, contains identifying project links, and makes no claim of completed journal-specific submission compliance. No submission or publication is performed.

`analysis/import_editorial.py ARTICLE_DIRECTORY` imports compact receipts for the canonical root article under `review/editorial/`. Their manifest distinguishes that 26-page article's editorial and figure-placement proof from the separate 24-page journal proof. The coverage JSON preserves exact source bytes in gzip. Rendered journal-page inspection caches are excluded from version control and are unnecessary for normal checks.
