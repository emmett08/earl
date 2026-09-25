# EAL/2 paper for the Journal of Systems and Software

[Read the manuscript PDF](manuscript.pdf) · [LaTeX source](manuscript.tex) · [Submission checklist](review/submission-status.md)

This author-review manuscript describes EAL/2's implemented evidence binding and defeasible assessment, and reanalyses the supplied historical API load-test experiment. It includes **three figures**, an exact excerpt of the tested EAL example, generated result tables and a reproducible dataset. The scientific conclusion is bounded to the recorded systems and development cases.

The historical run assigned 1,200 trials: 628 completed, 131 failed and 441 were not attempted after model-level stops. Every assignment is retained. Replaying the original scorer reproduces every trial score and the full summary. GPT-4.1 full scored 40/40 with EAL/MCP and 36/40 with JSON; all four JSON errors concern failed-check enumeration, while its statuses were correct. GPT-4.1 mini scored 32/40 and 21/40. Different checker access and incomplete execution prevent an isolated notation or general model-capability conclusion.

## Build and reproduce

From the repository root:

```sh
# Recompute scores, case identities, token costs and generated numerical tables.
python3 paper/analysis/reproduce.py

# Regenerate all three vector figures and the manuscript PDF.
make -C paper

# Also check references, overflow, fonts, result cells and error interpretations.
make -C paper check
```

Analysis requires Python 3.11+ and only its standard library. Building requires `make`, `latexmk`, `pdflatex`, BibTeX, and the LaTeX packages listed in `manuscript.tex` and `analysis/render_figures.py`, including TikZ, `standalone`, Latin Modern and `natbib`. PDF checks additionally use Poppler's `pdfinfo` and `pdffonts`. The build uses a fixed `SOURCE_DATE_EPOCH`; generated outputs are committed for readers without TeX. See [validation](review/validation.txt) for the tested environment.

No command above makes network requests or provider calls. To run the separately described software tests, install the repository development dependencies and use `python -m pytest -q`; 846 tests passed for the inspected source snapshot.

## Materials and version boundaries

| Material | Location / identity | Meaning |
| --- | --- | --- |
| Software description and tests | Commit `8220e838a8d42922edc0496ff50927c672a1f87d`, package 2.5.0 | Current implementation evidence |
| Historical experiment | Commit `3490076dd78404caa1326d9aae704f964910c4c8`, plan 2.0.0, run schema `/2` | Five conditions, six pinned models, 40 development cases |
| Original archive | [Run 36163505801, attempt 1](https://github.com/emmett08/earl/actions/runs/36163505801), artefact 10879620453 | Actual HTTP observations and provider calls, partial execution |
| Reproduction inputs | `data/` | Raw case rows, all assignments, answers, outcomes and token accounting |
| Historical scorers | `analysis/v2_oracle.py`, `analysis/v2_summary.py` | Byte-identical copies of the run commit, checked against its manifest |
| Regenerated results | `results/` | Full summary, dispositions, costs and component-level errors |
| Figures | `figures/*.tikz.tex` and matching PDFs | Two explanatory figures and one empirical paired-outcome figure |
| Review records | `review/` | Claim/source map, references, figure choices, validation and submission status |

The later [experiment protocol](../experiments/api_load_test/README.md) adds a sixth condition and other changes. Its planned assignments and rubric must not be substituted for this historical run. The [worked API example](../examples/api-load-test/README.md) contains synthetic teaching records and uses a different freshness limit. It is not an additional pilot observation.

The archive SHA-256 is `bf5b59c340b1c11c85a3e39679bc9cc1bc4521af741f45d9dc5cc1c65cbd8547`, matching GitHub's artefact metadata. `data/provenance.json` contains source-member and curated-file digests. To regenerate the curated files from the exact supplied ZIP:

```sh
python3 paper/analysis/extract_archive.py /path/to/api-experiment-36163505801-1.zip
```

The extraction retains every assignment and all fields needed for score/cost reproduction, while omitting full provider responses, replay handles and per-call transcripts. Those remain in the original archive, whose Actions retention expires on 25 October 2026. A durable full-archive deposit remains a submission task.

## Journal preparation

Target: Elsevier's *Journal of Systems and Software*. The [official Guide for Authors](https://www.sciencedirect.com/journal/journal-of-systems-and-software/publish/guide-for-authors) is the authority for article type, manuscript preparation, declarations and submission files. Its full text could not be retrieved during this task; the paper does not impose an unverified page limit or claim exact journal-format compliance.

The manuscript uses a single-column review layout. Four highlights are provided in `highlights.txt`. Author metadata, funding, competing interests, contribution statements, AI-assistance disclosure and current journal requirements need author confirmation before submission. [Submission status](review/submission-status.md) records these decisions without inventing declarations. The PR is ready for manuscript review; no journal submission has been made.

## Relevant skills

The following are exact skill names in this project's Codex environment. The first two have repository copies; the others are installed skills discoverable by name. Use them when the corresponding work is done, and distinguish their methods from measured results.

| Work | Skill | Where to find it |
| --- | --- | --- |
| EAL/2 source, semantics, MCP contracts and comparisons | `engineer-argumentation-languages` | [`../skills/engineer-argumentation-languages/SKILL.md`](../skills/engineer-argumentation-languages/SKILL.md) |
| Registered assessment routing and checked status communication | `eal-assessment-routing` | [`../skills/eal-assessment-routing/SKILL.md`](../skills/eal-assessment-routing/SKILL.md) |
| Competing hypotheses, measures, controls and predeclared decisions | `design-scientific-investigations` | Installed Codex skill |
| Estimands, assignment units, uncertainty and model heterogeneity | `analyse-software-engineering-statistics` | Installed Codex skill |
| Explicit dependencies and failure tests for engineering assumptions | `engineering-assumptions` | Installed Codex skill |
| Bounded claims, evidence, warrant and counterevidence | `assess-engineering-epistemic-entitlement` | Installed Codex skill |
| Root claim and rival argument discovery | `argument-discovery` | Installed Codex skill |
| Toulmin reconstruction and local argument repair | `toulmin-argument-reconstruction`, `toulmin-refinement` | Installed Codex skills |
| Verifiable MCP and provider interaction | `verify-live-integrations` | Installed Codex skill |
| Runtime design and maintainable experiment code | `evolve-codebase-architecture` | Installed Codex skill |
| Formal definitions, proofs and computational claims | `write-mathematical-papers`, `formalise-proofs-and-algorithms` | Installed Codex skills |
| Accurate claim-to-source and release review | `assure-first-publication` | Installed Codex skill |
| Evidence-linked figures | `design-evidence-visualisation` | Installed Codex skill |
| Clear technical prose and final wording audit | `write-engineering-analysis`, `audit-engineering-wording`, `humanise-agentic-writing` | Installed Codex skills |
| Rendered manuscript inspection | `pdf` | Installed Codex skill |

## Evidence boundary

The pilot is a descriptive reanalysis of an existing development run. No retrospective protocol is represented as preregistered. Keep the original case pairing, assignment denominator, failure outcomes, provider snapshots and token rates when reproducing its results. A confirmatory follow-up needs a frozen question and analysis plan, independent cases, matched validation access and a stopping rule that distinguishes transient incomplete output from persistent model-configuration failure.
