# EAL/2 journal article draft

This directory holds a research-article draft for the *Journal of Systems and
Software* (JSS). It is an author-review draft, not a submitted or accepted
manuscript. The historical relay and notation records remain pinned to
`2b0815f111f831bf237f600cf9e65f28eca0403e`. The later host, family,
checker and offline records are described at
`d78836b8fd769c236c646f263246e7728a488922`.

## Why this journal

JSS covers software engineering methods and tools, AI in software engineering,
and empirical research methods. Its scope explicitly welcomes negative results
and reproducible materials. A regular research article can combine the EAL/2
design with the bounded empirical diagnostic. *Empirical Software Engineering*
would be a stronger target after independent task sampling and measurement
validation. *SoftwareX* would put more weight on public software availability
and demonstrated research-software impact. These are editorial-fit judgements,
not predictions of acceptance.

The [JSS guide for authors](https://www.sciencedirect.com/journal/journal-of-systems-and-software/publish/guide-for-authors)
specifies a factual abstract of at most 250 words and single-anonymised review.
The abstract is checked against that limit before rendering. The article
uses Elsevier's `elsarticle` class, numbered citations, a separate editable
`highlights.txt` with four highlights below 85 characters each, keywords,
data and code availability, and declarations before the references. The
[publisher's LaTeX instructions](https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions)
ask for a PDF and the complete flat set of source files at submission.
The [publisher's AI policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals)
requires human verification and a separate disclosure immediately before
references. Recheck the journal guide when actually submitting.

The source is built with standard `elsarticle`, `algorithm`,
`algpseudocode`, `listings`, `booktabs`, `array`, `natbib` and `hyperref` packages:

```sh
cd paper/eal2-jss
latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
```

The PDF is a review render from the exact manuscript source. EAL keywords,
strings and comments are syntax-highlighted by a local `listings` language
definition. No external syntax highlighter or shell escape is needed. The
complete listing reproduces `examples/rms.eal` byte for byte.

## Evidence trace

| Manuscript claim | Retained source and boundary |
| --- | --- |
| EAL/2 grammar and typed bindings | `grammar/EAL.g4`, `docs/argument-model.md`, `docs/eal2-design.md`, `examples/rms.eal`; executable profile rather than physical truth |
| RMS origin counterexample | `benchmarks/engineering-v2/suite.json` and its two vibration observations; an intentionally synthetic case |
| Relay 12/12 versus 8/12 | `docs/eal2-relay-results.md` and `benchmarks/results/2026-09-23-relays-recovery/`; preservation of already correct producer answers |
| Notation, correction and irrelevant-record results | `docs/notation-transfer-live-results.md`, `benchmarks/results/2026-09-23-notation-transfer-live/report.json`, raw trial archive and CSVs; five exposed task templates |
| Post-hoc claim-map readout and execution deviation | `docs/notation-transfer-live-results.md`, `format-sensitivity.json`, `execution-notes.md`; explicitly exploratory and amended |
| Earlier checked-packet 48-call blocks | `docs/eal2-artifact-live-results.md`, `docs/eal2-artifact-live-replication-20260924.md`, their two retained trial archives; four selected roots, old packet shape, no new host/family route |
| Claim-scoped delivery | `src/eal/artifacts.py`, `src/eal/host.py`, `src/eal/server.py`, `docs/task-family-host.md`; bounded status, principal and claim grants, historical assessment identity |
| Exact families and retrieval | `src/eal/families.py`, `src/eal/retrieval.py`, `src/eal/routing.py`, `docs/task-families.md`; finite reviewed tuples and lexical suggestions, no model retrieval outcome |
| Independent comparator and cross-model cohorts | `benchmarks/equal_checker.py`, `benchmarks/experiments/cross-model-*.json`, `benchmarks/results/2026-09-24-cross-model-offline/status.json`, `benchmarks/results/2026-09-24-cross-model-live/README.md`, three retained call archives and `stricter-readonly-analysis.tar.gz`; selected offline parity, 315 revised scheduled cases, 365 model calls, checked final labels supplied by construction, route final prompt conflict |
| Exploratory explanation review | `benchmarks/results/2026-09-24-cross-model-explanation-review/`; two AI review passes over 105 selected outputs and seven single-author dossiers, no recipient-specific prompt in the review packet or human-adjudicated fidelity estimate |
| Corrected request route | `benchmarks/results/2026-09-24-cross-model-route-v2/` and `benchmarks/results/2026-09-24-cross-model-route-v2-explanation-review/`; 63 separately frozen attempts, 51 host-accepted and recipient-consistent statuses, 11/63 strict agent-judged faithful explanations; fixed menu, not family retrieval or native MCP; no human review |
| Synthetic Kubernetes contention and exact-family revision | `examples/kubernetes-resource-revision.eal`, `examples/kubernetes-resource-revision/README.md`, `benchmarks/experiments/kubernetes-host-revisions/results.offline.json`; 7/7 author-predeclared operating and 7/7 historical-record statuses, ten single-author retrieval queries, no cluster or model calls; superseded first fixture is under `docs/history/kubernetes-host-revisions-v1/` |
| Paid family selection | `benchmarks/results/2026-09-24-kubernetes-family-selection/README.md` and `family-selection-36.tar.gz`; 36 calls on twelve single-author synthetic tasks, two task-level false supports from an authorised but irrelevant family, no live cluster or independent relevance adjudication |
| Earlier 96-, 960- and 800-call designs | `benchmarks/protocols/INV-EAL-NEGATIVE-REVISION-001.json`, `INV-EAL-MECHANISMS-001.json`, `INV-EAL-DEPLOYMENT-001.json`, `docs/eal2-study-amendment-20260924.md`; specified, unrun, requiring current-contract freezes; the 800-call candidate grammar factor conflicts with the present no-extension scope and changes count if removed |

The tables count attempted calls. Two repetitions per task are dependent.
Full-information agreement and correctness under the observations supplied
are different endpoints. The 661 repository tests reported in PR #4 and
newer implementation checks are regression tests, not a model or human
comprehension result.
The article intentionally makes no significance or equivalence claim.

## Argument and visual decisions

The preferred root claim is that EAL/2 supplies a bounded, inspectable
calculation over authored engineering arguments, and that a host can keep the
checked status authoritative when model prose is inconsistent. The historical
diagnostic separates computed-result transfer from raw-record interpretation.
The newer exact family route is implemented; the two completed cross-model
cohorts tested a fixed artefact menu rather than CandidateIndex family
retrieval. Their checked final labels were supplied by construction, while
recipient communication sometimes contradicted the host. All 63 original
routed final answers were malformed under the frozen prompt conflict. A
separately frozen correction gave 51/63 consistent recipient statuses, but
only 11/63 explanations met an exploratory strict agent review. A stronger
notation-superiority claim has no support from the strict raw-only diagnostic
(4/10 versus 5/10). The JSON comparator can
carry the same typed meaning and remains a credible alternative
representation. The downstream test requires independent briefs, equivalent
operations and separate explanation and cost measurement.

The figure search used the visualisation skill's weighted criteria:
explanatory gain .30, inferential force .25, semantic fidelity .20,
perceptual economy .10, reproduction .10, originality .05. Scores below
are editorial assessments out of five, not measured user outcomes.

| Candidate | Score | Decision |
| --- | ---: | --- |
| Paired discordance glyphs for ten raw-only pairs | 3.85 | Accurate pairing, but the historical results table and the four/zero/one/five sentence give the result more directly |
| Dual-reference correspondence plate | 3.70 | Makes the reference switch visible, but risks implying a general transfer law |
| Origin-match counterfactual plate | 3.65 | Clarifies the worked case, but duplicates the two exact RMS calculations |
| Negative-space admissibility region | 3.10 | May suggest a continuous confidence boundary that the status calculus lacks |
| Braided observation provenance | 2.70 | Adds visual complexity without more inspectable evidence in this article |

The exact table, formulas and syntax-highlighted source provide the clearest
comparison. No figure is included solely to decorate the manuscript. A
reproducible task-level graphic could be warranted after a larger independent
sample provides a distribution rather than five exposed templates.

## Before journal submission

The human author must verify authorship and affiliation, provide a
corresponding-author address, funding and competing-interest statements,
confirm CRediT contributions, and review the AI declaration and every claim.
The repository is private; external reviewers need access, and a public
versioned archive or an explicit access arrangement is needed for the JSS
Open Science option. A new independent study would be needed for a stronger
generalisation or notation-effect article. This draft changes no EAL/2 grammar,
interpreter code or historical result file. Regenerate `manuscript.pdf` after
any source or live-result revision.
