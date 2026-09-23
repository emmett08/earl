# EAL/2 journal article draft

This directory holds a research-article draft for the *Journal of Systems and
Software* (JSS). It is an author-review draft, not a submitted or accepted
manuscript. The article uses the retained experiment records at repository
revision `2b0815f111f831bf237f600cf9e65f28eca0403e`; the manuscript source
and PDF were prepared after that revision.

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
The abstract here is 224 words under the local word-count check. The article
uses Elsevier's `elsarticle` class, numbered citations, a separate editable
`highlights.txt` with four highlights below 85 characters each, keywords,
data and code availability, and declarations before the references. The
[publisher's LaTeX instructions](https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions)
ask for a PDF and the complete flat set of source files at submission.
The [publisher's AI policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals)
requires human verification and a separate disclosure immediately before
references. Recheck the journal guide when actually submitting.

The source is built with standard `elsarticle`, `algorithm`,
`algpseudocode`, `listings`, `booktabs`, `natbib` and `hyperref` packages:

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

The tables count attempted calls. Two repetitions per task are dependent.
Full-information agreement and correctness under the observations supplied
are different endpoints. The 661 repository tests reported in PR #4 are
implementation regression checks, not a model or human comprehension result.
The article intentionally makes no significance or equivalence claim.

## Argument and visual decisions

The preferred root claim is that EAL/2 supplies a bounded, inspectable
calculation over authored engineering arguments, while the present trials
separate computed-result transfer from raw-record interpretation. This is
supported by the language contract, implementation checks and the exact
finite trial outcomes. A stronger notation-superiority claim is contradicted
by the strict raw-only diagnostic (4/10 versus 5/10); a robust raw-evidence
correction claim is weakened by correct-proposal damage and wrong-scope
responses. The JSON comparator can carry the same typed meaning and remains
a credible alternative representation. The downstream test is an
independent-task, equal-tool-access comparison with separate qualification
scores.

The figure search used the visualisation skill's weighted criteria:
explanatory gain .30, inferential force .25, semantic fidelity .20,
perceptual economy .10, reproduction .10, originality .05. Scores below
are editorial assessments out of five, not measured user outcomes.

| Candidate | Score | Decision |
| --- | ---: | --- |
| Paired discordance glyphs for ten raw-only pairs | 3.85 | Accurate pairing, but Table 1 and the four/zero/one/five sentence give the result more directly |
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
generalisation or notation-effect article. This draft does not change any
EAL/2 grammar, interpreter code or historical result file.
