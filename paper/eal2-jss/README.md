# EAL/2 journal article draft

This directory holds a research-article draft for the *Journal of Systems and
Software* (JSS). It is an author-review draft, not a submitted or accepted
manuscript. The historical relay and notation records remain pinned to
`2b0815f111f831bf237f600cf9e65f28eca0403e`. The later host, family,
checker and offline records are described at
`d78836b8fd769c236c646f263246e7728a488922`. The amended 96-, 960- and
800-call records were merged in [PR #8](https://github.com/emmett08/earl/pull/8)
at `b9177df`. Main revision `3b497d` includes the bias-agent study's 0.1.1
amendment, separate matched-format and topology follow-ups, and a human-trial
protocol. The current 0.1.2 amendment and zero-call freezes follow PR #9's
EAL/2 source change.

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
| Earlier 96-, 960- and 800-call designs | `benchmarks/protocols/INV-EAL-NEGATIVE-REVISION-001.json`, `INV-EAL-MECHANISMS-001.json`, `INV-EAL-DEPLOYMENT-001.json`; their version 0.1.0 human-adjudication protocols remain unrun. The full fixed-source factorial written for the 800 design is 768, giving 1,184 with its other stages; the separately versioned amendment uses a balanced 384-cell fraction and does not add grammar syntax |
| Negative-revision developmental schedule | `benchmarks/experiments/negative-revision-96/`, `benchmarks/results/2026-09-24-negative-revision-96-developmental/` and the separate explanation review archive; 96 completed calls, 24/24 finite EAL/comparator parity cases, 1/48 strictly faithful and correctly accepted one-shot explanations by two exploratory AI reviews under criteria frozen during the campaign before reviewer exposure; eight selected roots from one generated scaffold |
| Mechanism developmental schedule and result | `benchmarks/experiments/mechanisms-960/` and `benchmarks/results/eal2-960-campaign-20260924.tar.gz`; 960 assigned/attempted, 942 strict completions, four malformed, fourteen provider failures, 460 exact available-information statuses and 130 admitted false supports on selected synthetic roots; 11 response-less requests have unknown charges |
| Deployment developmental schedule and result | `benchmarks/experiments/deployment-800/`, `benchmarks/results/2026-09-24-deployment-800-a3-developmental/a3-terminal.tar.gz`, `docs/eal2-study-amendment-20260924.md` and `docs/eal2-grammar-decision-20260924.md`; 800 completed assigned slots in 804 actual requests, 290/384 fixed-source exact statuses, 0/32 valid final authored products and 320 unavailable recipient packets. A1/A2/C1 stopped diagnostic attempts are separate and not pooled |
| Deployment exploratory explanation reviews | `docs/reviews/deployment-800-a3-*` and the archived postcall review frame; two isolated AI reviewers agreed 4/48 preselected actual-prompt responses faithful, all in raw-source cases. All 16 checked-host statuses in this subset matched their synthetic reference, but none of the sixteen recipient explanations was rated faithful; not a human quality estimate |
| Prospective bias attribution and agent comparison | `benchmarks/experiments/bias-mechanisms/PROTOCOL.md`, `AMENDMENT-0.1.1.md`, `AMENDMENT-0.1.2.md` and `RUN_STATUS.md`; 12 synthetic families with four dependent variants, three model classes, two Stage A topologies, 288 assigned model--case--route cells and 432 planned API calls. At main `3b497d`, static source validation passed 48/48 with zero diagnostics and thirteen offline tests passed. Versions 0.1.0 and 0.1.1 remain zero-call history and fail current material checks after PR #9 changed `src/eal`. Current 0.1.2 pilot and full freezes in `benchmarks/results/2026-09-24-bias-agent-zero-call-0.1.2/` retain 72 and 432 planned calls, with internal SHA-256 values `67e651ecd2bc3a053689d3f32078267294f15b80ef3e9b5c7f699856232fa9e5` and `5109b7b7c6704723cd42b50aff2622d3e764c595f0b365b0d810ae647fcbb752`; their material checks pin the current grammar, all `src/eal` Python modules, scorer, base protocol and both amendments. A no-key connectivity preflight timed out before any paid call. No response ledger or model result exists. Raw agent judgements are primary; the author-labelled gate is an oracle-assisted diagnostic. Human causal benefit requires a separate randomised engineer study |
| Matched format and equal-allocation follow-ups | `benchmarks/experiments/bias-followups/` and `benchmarks/results/2026-09-24-bias-followups-zero-call/`; checked EAL/2 versus mechanically derived typed JSON and two general critics versus mechanism/rival critics, with two assigned calls per cell. The exposed 12 families yield 128 pilot and 768 full planned calls, frozen at internal SHA-256 `1d543e38827ee95ec7e17535ff6c1777d60e9a967d7677d1be696d88de05b678` and `1f790f06b2078a6244e9d7039b9a51f43e503df81dd71cc303e23d74dcdc68f2`. Five offline tests passed; endpoint preflight timed out before credential lookup, so there are no model calls or performance results. Actual billed compute and input length may differ |
| Human decision trial protocol | `benchmarks/experiments/bias-human-trial/`; six assistance arms crossed with fluent/plain wording, with staged pre/post packets and descriptive scoring. Four synthetic administrative tests passed. New independent case review, ethics arrangements, recruitment, power analysis and preregistration are needed; no participants or human outcomes exist |

The amendment document is a pre-run design record at its stated audit cut. The
later terminal result archives and this manuscript report the amended runs;
its earlier "unmeasured" statements are not the status of those later runs.

The tables count attempted calls. Revisions and repeated conditions within a
root are dependent. A scheduled decision slot may have more than one paid API
attempt under a separately declared retry rule; the ledgers retain both.
Full-information agreement and correctness under the observations supplied
are different endpoints. The 661 repository tests reported in PR #4 and
newer implementation checks are regression tests, not a model or human
comprehension result.
The article intentionally makes no significance or equivalence claim.
The developmental studies use author-created synthetic records and AI reviews,
not authenticated cluster evidence or masked human adjudication. Provider model
charges omit initial fixture authoring, source review, acquisition and host
work, so total cost per correctly accepted and faithfully explained decision
is unavailable.

## Argument and visual decisions

EAL/2 began as a way to help a person question a fluent AI answer by exposing
the claim, grounds, inference, assumptions and objections. The paper now
separates that human-facing purpose from the demonstrated host checks and from
the prospective experiment. An inaccurate or unjustified argument is not, by
itself, evidence of a particular human cognitive bias. The study therefore
requires cue exposure, an opportunity, evidence of uptake, a predicted
directional signature, a discriminating contrast and serious rival accounts;
it scores false bias attribution and agent-induced engineering errors alongside
correct detection. Model cue sensitivity tests concern the model system. A
randomised human study would be needed to show improved human decisions.

The preferred current result claim is that EAL/2 supplies a bounded, inspectable
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
The finite negative-finding task uses existing typed methods, claim premises
and targeted objections. The language review found no need to change EAL/2
grammar for these campaigns or to add ASPIC+ machinery. If a future task
requires default rules, implicit attacks or preferences, a versioned host
method could consume a separately specified finite argumentation profile.
Its typed inputs, construction and defeat semantics, trace and binding to
EAL claims would need explicit validation and an engineering use case.

The amended 96 and 960 schedules show substantial raw interpretation and
source-authoring failures on selected synthetic records. The fresh 800-slot
fixed-source host and native routes retained 240/240 checked statuses by
construction, whereas direct interpretation retained 50/144; all 32 final
authored sources failed the exposed executable contract, so none of the 320
recipient packets had an accepted status. These are different estimands and
cannot be combined into a notation benefit. Four response-less first requests
in the 800 schedule were retried identically, raising actual API requests to
804. An exploratory 48-response AI review found four faithful explanations,
all in the raw subset. Configured model charges, retries and latency are reported in the result
archives; human effort, independent human explanation adjudication and all-in
cost per faithfully correct accepted decision remain unavailable.

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
