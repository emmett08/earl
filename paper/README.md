# EAL/2 paper for the Journal of Systems and Software

[Read the manuscript PDF](manuscript.pdf) · [LaTeX source](manuscript.tex) · [Submission checklist](review/submission-status.md)

This author-review manuscript describes EAL/2's implemented evidence binding and defeasible assessment, and reanalyses two supplied API load-test experiments. It includes **four figures**, an exact excerpt of the tested EAL example, generated result tables and separately versioned reproducible datasets. The scientific conclusion is bounded to the recorded systems and development cases.

The historical run assigned 1,200 trials: 628 completed, 131 failed and 441 were not attempted after model-level stops. Every assignment is retained. Replaying the original scorer reproduces every trial score and the full summary. GPT-4.1 full scored 40/40 with EAL/MCP and 36/40 with JSON; all four JSON errors concern failed-check enumeration, while its statuses were correct. GPT-4.1 mini scored 32/40 and 21/40. Different checker access and incomplete execution prevent an isolated notation or general model-capability conclusion.

The later nano-only run assigned 240 trials under plan 3.1.0: 141 completed, 43 failed and 56 were unattempted. Plain-validator scored 11/40 against EAL/MCP's 3/40. All 30 attempted EAL assignments obtained correct assessment packets; 13 final answers were incorrect, 14 conversations exhausted the six-call limit and ten assignments were never dispatched after a provider HTTP 503 stopped execution. The revised rubric and newly acquired observations require separate analysis. These pilots do not establish an EAL accuracy advantage over ordinary validation. Protocol-4 repairs are described as implementation changes checked offline, with no new model-performance result.

## Build and reproduce

From the repository root:

```sh
# Recompute scores, case identities, token costs and generated numerical tables.
python3 paper/analysis/reproduce.py
python3 paper/analysis/reproduce_nano.py

# Regenerate all four vector figures and the manuscript PDF.
make -C paper

# Also check references, overflow, fonts, result cells and error interpretations.
make -C paper check
```

The two historical score replays require Python 3.11+ and only its standard library. The optional [finalisation optimisation analysis](../experiments/api_load_test/OPTIMISATION.md), run with `python paper/analysis/analyse_finalisation.py` from an installed checkout, also imports the current answer contract and requires the project dependencies. It partitions recorded calls after a checked packet and is separate from a new model-performance experiment. Building requires `make`, `latexmk`, `pdflatex`, BibTeX, and the LaTeX packages listed in `manuscript.tex` and `analysis/render_figures.py`, including TikZ, `standalone`, Latin Modern and `natbib`. PDF checks additionally use Poppler's `pdfinfo` and `pdffonts`. The build uses a fixed `SOURCE_DATE_EPOCH`; generated outputs are committed for readers without TeX. See [validation](review/validation.txt) for the tested environment.

No command above makes network requests or provider calls. To run the separately described software tests, install the repository development dependencies and use `python -m pytest -q`; 846 tests passed for the inspected source snapshot.

## Materials and version boundaries

| Material | Location / identity | Meaning |
| --- | --- | --- |
| Software description and tests | Commit `8220e838a8d42922edc0496ff50927c672a1f87d`, package 2.5.0 | Current implementation evidence |
| Historical experiment | Commit `3490076dd78404caa1326d9aae704f964910c4c8`, plan 2.0.0, run schema `/2` | Five conditions, six pinned models, 40 development cases |
| Original archive | [Run 36163505801, attempt 1](https://github.com/emmett08/earl/actions/runs/36163505801), artefact 10879620453 | Actual HTTP observations and provider calls, partial execution |
| Reproduction inputs | `data/` | Raw case rows, all assignments, answers, outcomes and token accounting |
| Historical scorers | `analysis/v2_oracle.py`, `analysis/v2_summary.py` | Byte-identical copies of the run commit, checked against its manifest |
| Nano follow-up | [Run 36176588712, attempt 1](https://github.com/emmett08/earl/actions/runs/36176588712), commit `8220e838a8d42922edc0496ff50927c672a1f87d`, plan 3.1.0 | Six conditions, one pinned model, 40 newly acquired case reports |
| Follow-up inputs and source | `data/nano-v3/`, `analysis/nano_v3_original/` | All 240 assignments, raw cases, response text, host packets, full tool traces and hash-verified original source |
| Regenerated results | `results/` | Full summary, dispositions, costs and component-level errors |
| Figures | `figures/*.tikz.tex` and matching PDFs | Two explanatory figures, empirical paired outcomes and nano failure diagnosis |
| Review records | `review/` | Claim/source map, references, figure choices, validation and submission status |

The current [experiment protocol](../experiments/api_load_test/README.md) changes finalisation and transient-error handling. Its rules must not be substituted for either historical run. The [worked API example](../examples/api-load-test/README.md) contains synthetic teaching records and uses a different freshness limit. It is not an additional pilot observation.

The archive SHA-256 is `bf5b59c340b1c11c85a3e39679bc9cc1bc4521af741f45d9dc5cc1c65cbd8547`, matching GitHub's artefact metadata. `data/provenance.json` contains source-member and curated-file digests. To regenerate the curated files from the exact supplied ZIP:

```sh
python3 paper/analysis/extract_archive.py /path/to/api-experiment-36163505801-1.zip
```

The first extraction retains every assignment and all fields needed for score/cost reproduction, while omitting full provider responses, replay handles and per-call transcripts. Those remain in the original archive, whose Actions retention expires on 25 October 2026. A durable full-archive deposit remains a submission task.

The nano archive SHA-256 is `186adeb144ccaf4c77f5e36165999f3ad203a98bcfc24a7119c68d5c5eb206c5`. Its extraction preserves provider response text once per call, all protocol errors, every model-visible host packet and the complete tool traces. It omits duplicate provider objects and replay handles. Its frozen reference and summary are verified against the original manifest before execution:

```sh
python3 paper/analysis/reproduce_nano.py --extract /path/to/api-experiment-36176588712-1.zip
```

`results/nano-diagnosis.json` supplies the fourth figure and regenerates the counts behind the failure analysis. `results/nano-summary.json` must match the archived summary exactly. The known follow-up cost is USD 0.1146428 over 689 recorded calls; one call has unknown cost, retained separately. Keeping that uncertainty avoids treating an HTTP failure as a known zero charge.

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

The pilots are descriptive reanalyses of existing development runs. No retrospective protocol is represented as preregistered. Keep each run's case pairing, assignment denominator, failure outcomes, provider snapshots and token rates when reproducing its results. Reused case identifiers do not make changed observations and rubrics interchangeable. A confirmatory follow-up needs a frozen question and analysis plan, independent cases, matched validation access and predefined execution rules. Direct host finalisation changes the evaluated system and must remain separate from model-finalised answers.
