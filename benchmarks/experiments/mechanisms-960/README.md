# EAL/2 mechanism study: developmental execution and continuations

The original `INV-EAL-MECHANISMS-001` version 0.1.0 specified 960 one-shot model calls and 192 deterministic executions; it was unrun. This directory makes the same **24 roots × 10 content arms × 2 notation views × 2 reference renderings** executable under a distinct developmental amendment. It does not rename an earlier pilot result or alter EAL/2 grammar. The exact original protocol was retained at Git blob `8c7cb62e9d8efc96b6005688d574e4a6a1c043d9` in the merged PR #7 history.

`fixtures/` contains 24 new ordinary synthetic questions in four families, each with paired valid and binding-invalidated submitted observations. Six roots use explicit eligibility predicates; six use RMS, causal contrast, Wilson bound, affine counterfactual, finite abduction and analogy; six use sampled positive counterexamples or coverage-qualified non-detection; six use different authored objection/defence topologies. The per-root genealogy is in `fixtures/README.md`. The source is canonicalised and the JSON view is parsed from the same EAL/2 intermediate representation. Their meaning equality is checked before any request. Within-family roots share author and code, so their outcomes are dependent selected cases rather than a random population sample.

The ten arms, for each root and display combination, are exactly:

| Arm | Supplied beyond source, scope and time |
| --- | --- |
| `valid_raw_no_proposal` | admissible raw observations |
| `invalid_raw_no_proposal` | one perturbed observation, no proposal |
| `wrong_proposal_only` | deliberately wrong proposal, no observations |
| `wrong_proposal_valid_raw` | wrong proposal and admissible observations |
| `correct_proposal_valid_raw` | correct proposal and admissible observations |
| `wrong_proposal_invalid_raw` | wrong proposal and perturbed observations |
| `wrong_proposal_valid_raw_eligibility` | wrong proposal, valid raw and eligibility result without a final status |
| `wrong_proposal_valid_raw_method` | wrong proposal, valid raw and method output without argument status |
| `wrong_proposal_valid_raw_status` | wrong proposal, valid raw and a full finite checked status |
| `wrong_proposal_invalid_raw_forged_status` | wrong proposal, invalid raw and a bare earlier wrong verdict with mismatched identity |

The wrong proposal is `out_of_scope` in every root, despite a matching supplied context. This ensures it is wrong under valid, invalid and absent-record references. It is conspicuously implausible; adoption differences cannot estimate susceptibility to subtler false-support proposals. The bare earlier verdict repeats the valid root status and lacks the current source/record identity. Intermediate packets have source, semantic graph, record, claim, context and time IDs, but do not supply a final label; the checked-status packet's label comes from local `ReasoningService` execution. Its explanatory basis remains authored. The EAL/2 and standalone checker parity gate is distinct from the model's tool-free judgement. No prompt exposes reference-rule fields or expected status labels except the deliberately supplied proposal or checked/bare verdict arm.

The compact reference has the finite EAL/2 rules needed by these roots. The historical-length arm prepends **that same compact core** and then includes three much longer EAL/2 documents. It changes wording, salience and added material as well as length; the paired contrast is a prompt-rendering effect, not an isolated causal estimate of token count or attention. The model receives no native tool calls, persistent session or repairs. Strict JSON status/basis scoring keeps malformed answers and API failures in attempted denominators. `wrong_proposal_only` is scored against the unavailable-record reference (`unsupported`); an apparent agreement with hidden full data is recorded separately and never counted as available-information justification. Root is the aggregation unit; 960 calls are not independent engineering tasks.

Before paid calls, `freeze()` checks all 24 parse–format–parse representations, 960 exact message hashes, a conservative configured-rate reservation and **192 deterministic executions**. Those executions are 24 roots × four variants (`intact`, `wrong_scope`, `stale_replayed`, `hash_tampered`) × EAL and a separately coded brief-rule checker. Wrong-scope and stale variants prevent source support; a common synthetic identity gate refuses the hash-tampered verdict. The two checker paths were written in the same fixture project, and their common gate cannot authenticate external physical acquisition. Parity is a conditional implementation check, not independent human adjudication or proof that either authored warrant describes a real system.

An independent masked AI reviewer derives 48 statuses and checks brief-to-source fidelity without seeing authored labels or model outputs; another reviewer audits prompts and checker parity. Their exact reports and a separate attestation bound to the freeze hash must exist in the output directory before `--execute`. These are **AI-assisted developmental reviews**, not two masked human reviewers required by the old proposed confirmatory protocol. Any unresolved source-to-brief mismatch blocks paid calls. The original protocol's signed synthetic acquisition log has not been implemented as an authenticated external source; digest binding only detects specified local changes. For this reason the run cannot confirm the old system-level or EAL-specific superiority claims even when all calls complete.

`provider-nano.toml` pins a GPT-4.1 nano alias, response snapshot, temperature zero and official configured rates of $0.10 input/$0.40 output per million tokens. It reads the user's credential from `OPENAI_API_TOKEN` at request time and never writes its value. `plan.json` caps six simultaneous requests and $5.00 of conservative *configured-rate* reservation; it is not an invoice or provider-enforced spending ceiling. Each scheduled request is written as `pending` before dispatch. Provider failure, unknown billing and unexpected response model stop later batches, with no retry. An interrupted pending request cannot silently resume. The preflight reservation is recomputed and frozen with all source and runner hashes before execution.

Run dry validation and execution with source imports:

```bash
PYTHONPATH=src:scripts python benchmarks/experiments/mechanisms-960/fixtures/validate_fixtures.py
PYTHONPATH=src:scripts python scripts/run_mechanisms_960.py benchmarks/experiments/mechanisms-960/plan.json --output /path/to/new-run
# Only after separate exact-freeze review-attestation.json and credential are present:
PYTHONPATH=src:scripts python scripts/run_mechanisms_960.py benchmarks/experiments/mechanisms-960/plan.json --output /path/to/new-run --execute
PYTHONPATH=src:scripts python scripts/analyse_mechanisms_960.py /path/to/new-run --output /path/to/new-run/analysis.json
```

The read-only analyser verifies case, raw response, strict score, usage and configured cost. It reports every arm/notation/reference cell, root-weighted paired contrasts and the valid-to-invalid sequence. Its provider-only cost omits the time and money for authoring, masked review, evidence acquisition, host execution and deployment. There is no measured all-in cost per correctly accepted decision from this one-shot study.

## Executed campaign, 24 September 2026

The original frozen schedule was attempted in four **separately reviewed, immutable segments**. A provider failure stopped the original six-at-a-time run at index 129 after its batch. A2 retained that failed slot and assigned only indices 132–467. It stopped on a metered incomplete output at 467. A3 assigned 468–725 two at a time and stopped at its prespecified eight new provider failures. A4 assigned 726–959 one at a time. Each continuation preserved every earlier response and failure; **no 960-study request was retried**. These operational amendments arose after observed failures. The resulting 960 assigned positions form a complete schedule for descriptive within-root comparisons, not a clean single-pass execution of the older confirmatory protocol.

| Segment | Original indices | Assigned | Completed | Malformed | Provider failures | Terminal status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Original | 0–131 | 132 | 131 | 0 | 1 | stopped after failed batch |
| A2 | 132–467 | 336 | 330 | 2 | 4 | stopped on metered incomplete output |
| A3 | 468–725 | 258 | 249 | 1 | 8 | stopped at eight new failures |
| A4 | 726–959 | 234 | 232 | 1 | 1 | completed with failures |
| **Total** | **0–959** | **960** | **942** | **4** | **14** | **none untouched** |

The final analysis-only join is `paid-mechanisms-960-composite-final-a4`; its `composition.json` binds the exact four source freezes/ledgers, three separately billed probes and A4 review attestation. The original ledger, A2, A3 and A4 remain independent source records. Eleven failed requests had no response/usage, so their actual charges are **unknown**; a conservative configured-rate reservation of **$0.0301785** is retained rather than imputing zero. Three other failed requests had measured output. Known study model cost at configured rates was **$0.2840583**; the three separate connection probes add **$0.0000069** and are excluded from the 960 decisions. The run used 6,008,007 input tokens (4,812,032 cached) and 110,400 output tokens on metered responses. Median observed attempt duration was 11.07 seconds; the sum of individual durations, 11,777.68 seconds, is not wall-clock elapsed time because some calls overlapped.

The primary strict available-information score was **460/960**. There were **130 false-support outputs** (a `supported` answer where the available-record reference was not supported). An API failure or malformed answer counts as incorrect, with no invented support or non-support label. Counts for each 96-call content arm follow; the conspicuously wrong proposal was `out_of_scope` in all roots.

| Content arm | Correct/96 | False support/96 |
| --- | ---: | ---: |
| Valid raw, no proposal | 78 | 4 |
| Invalid raw, no proposal | 17 | 65 |
| Wrong proposal only | 33 | 12 |
| Wrong proposal with valid raw | 36 | 1 |
| Correct proposal with valid raw | 86 | 0 |
| Wrong proposal with invalid raw | 26 | 29 |
| Wrong proposal, valid raw and eligibility | 47 | 1 |
| Wrong proposal, valid raw and method output | 43 | 0 |
| Wrong proposal, valid raw and checked status | 76 | 0 |
| Wrong proposal, invalid raw and forged status | 18 | 18 |

Across 24 selected roots, the mean of four paired display-cell accuracy differences was +0.6354 for valid versus invalid raw observations, +0.5208 for correct versus wrong proposal with valid raw, +0.4167 for a checked status versus wrong proposal with valid raw, and −0.0833 for forged status versus wrong proposal with invalid raw. EAL versus JSON averaged +0.0292, and compact versus historical-length reference averaged +0.0875 across root/content/display pairs. The historical reference contains the compact core plus other material; these are **selected-case descriptive differences**, without population inference or an isolated length mechanism. Six related roots per family share authoring and implementation. The strong false-support count on invalid raw records shows that merely supplying a reasoning notation or raw tool-like output does not make this recipient a trustworthy acceptor; a host-side equal checker and acquisition controls remain necessary.

The 192 deterministic executions passed the separately coded checker parity gate under the synthetic assumptions. Masked brief/source review and prompt review were conducted by AI agents, without human independently acquired evidence or a human faithful-explanation assessment of the 960 model outputs. The strict `basis` field is a parse requirement, not a validated explanation. Neither actual unknown-charge billing nor authoring, review, acquisition, checker, host and deployment effort was measured. Thus the known model-rate charge cannot be called all-in **cost per correct accepted decision**, and the study does not establish real-world warrant correctness, authenticated evidence, EAL-specific superiority or transfer to an unseen task population.
