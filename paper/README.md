# EAL/2 empirical paper

This directory is a fresh starting point for a prospective empirical paper. No manuscript or experimental result is implied by this README. The proposed comparison asks whether EAL/2 with an EAL MCP host improves **correct, evidence-grounded engineering decisions** over equally resourced prose and machine-readable alternatives on sampled real tasks and model classes. An experiment can estimate effects in the sampled conditions; it cannot establish superiority for every language model.

The previous benchmark plans and runner have been removed. The [API load-test example](../examples/api-load-test/README.md) demonstrates one checked argument using synthetic records. The single [live API experiment](../experiments/api_load_test/README.md) supplies a versioned protocol, real HTTP tooling, four pinned models and a Docker workflow. It compares combined systems on one controlled task; implementation and smoke execution alone provide no comparative advantage claim.

## Journal requirements

Target: Elsevier's *Journal of Systems and Software* (JSS). Use the [official Guide for Authors](https://www.sciencedirect.com/journal/journal-of-systems-and-software/publish/guide-for-authors) as the current authority for article type, manuscript preparation, declarations, research data, submission files and submission procedure. The [journal page](https://www.sciencedirect.com/journal/journal-of-systems-and-software) says articles should provide evidence supporting their claims. Recheck the guide before submission; this README does not impose an unverified page or word limit. For research materials, also consult Elsevier's [research data guidelines](https://www.elsevier.com/researcher/author/tools-and-resources/research-data/data-guidelines) and [data statement guidance](https://www.elsevier.com/researcher/author/tools-and-resources/research-data/data-statement).

The paper must identify the software/source version and model/provider versions used in each run, preserve assigned attempts including failures, retain tool requests and receipts, and report outcomes, uncertainty, cost and limits of generalisation. Executable tests establish software behaviour; study results require actual model calls and independently checked cases.

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

Freeze the question, comparators, case selection, source snapshots, model strata, prompt budgets, tool access, outcome adjudication and analysis before observing confirmatory outcomes. Keep a complete one-attempt ledger per assignment and version the full protocol. Treat the single worked EAL/2 example as a demonstration until independent cases and live runs support a population claim. Preserve failed attempts and unpublished or unfavourable outcomes in the analysis.
