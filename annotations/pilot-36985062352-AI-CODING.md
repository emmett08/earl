# AI assessment of the EAL/3 principal pilot

The user authorised AI coding and continuation on 2 October 2026, after collection
and masked export. This is a post-collection measurement amendment, not a
prospectively registered human assessment. Collection remains protocol **7.0.0**,
package **3.2.4**, at commit `c0974bc6bb6a2df30d1423b6248bfc51b4d2a9d7`.

Source run: `36985062352`. Masked artefact: `11220136900`; full export artefact:
`11220466284`. The original masked `items.json` has SHA-256
`b3d3c4def9abd3110e9b8e072edd87b368f23328aaf872b911eefb868bb0cf2e`.
All 4,224 item identifiers and answer texts are retained in the completed labels,
with exact supporting quotes and coding notes. Collection records, requests,
assignments, reference keys, thresholds and budgets are unchanged.

## Coding and rechecks

Coding uses only the masked answers and their exported rubric. It identifies the
decision communicated, not the decision that task facts ought to imply. A wrong
numerical comparison or mistaken readiness rule is retained for separate
correctness scoring. Historical assessments, route-level decisions, general
rules and hypothetical future outcomes are distinguished from the current
overall verdict.

The existing conservative aid in `scripts/code_pilot_annotations.py` supplies
provisional candidates. A second scan checks every answer for first-category and
prominent-heading disagreement, multiple category words, negation, and uncertainty
synonyms. Broader adverse clause checks examine apparently competing current
statements, including cases skipped by the initial aid. The AI reviewed 392
distinct flagged answers in full. This includes all 270 initially unresolved
candidates, the adverse-review candidates, and further category/scope checks.
Two erroneous affirmative rule candidates were corrected to `undetermined`.

Every provisional ambiguity was rechecked in the context of the entire answer.
Thirteen initially retained ambiguities were resolved on this additional pass.
An explicit correction and revised final verdict can replace an earlier verdict.
A parenthetical `undetermined` can qualify natural-language "not ready" as
withheld confirmation when the body consistently adopts an unknown verdict;
this does not equate the literal code `not_ready` with `undetermined`. Explicit
rejection of a negative code also distinguishes withheld confirmation from a
negative assessment. An unknown component or evidence aspect is not an unknown
overall task decision. These distinctions apply to communicated wording without
consulting the reference key. Review histories preserve changed adjudications.

The adverse pass found eight additional unresolved conflicts missed by the
initial aid. All remaining conflicts were rechecked and retain `ambiguous`:
competing adopted current overall verdicts without a clear correction or scope
distinction cannot be made determinate by choosing a preferred reading.

| Code | Answers |
|---|---:|
| `ready` | 2,259 |
| `not_ready` | 827 |
| `undetermined` | 1,113 |
| `ambiguous` | 25 |
| `no_answer` | 0 |
| Total | 4,224 |

The previous pilot's 31 ambiguities are a different collection; the counts are
not a paired improvement estimate. The aim of the rechecks is to remove avoidable
coding uncertainty while preserving genuine conflicts.

## Reproduction and validation

The frozen adjudications record answer hashes, exact quotes, notes, review passes
and changed decisions. `scripts/code_reviewed_annotations.py` combines those
reviews with the retained provisional aid, repeats the all-answer screens, and
rejects changed source hashes, missing required reviews, invalid categories,
inexact quotes, duplicate or unknown identifiers, and inconsistent codes for
identical answers. The audit records these checks for every item. The labels
retain AI assessor provenance and hashes of the source, both scripts, and reviews.

```bash
python scripts/code_reviewed_annotations.py /path/to/items.json \
  annotations/pilot-36985062352-ai-adjudications.json /tmp/reproduced-labels.json \
  --audit /tmp/reproduced-audit.json
```

These are AI-authored rules with AI semantic adjudication and rechecks. They are
not independent human validation, independent model calls for every answer, or
an empirical assessor-error estimate. The exact serving model identifier is not
exposed. No additional provider requests were purchased for coding. Metadata was
masked before label freeze, but answer wording can reveal a workflow and the AI
has prior project context. Correlated coding errors remain possible.

## Continuation

Dispatch **EAL experiment → finish** on the commit containing the labels, with
source artefact `11220466284` and labels path
`annotations/pilot-36985062352-ai-labels.json`. Import, analysis and allocation
planning use the retained observations without model calls. The 25 ambiguous
answers remain unresolved scores and retain their uncertainty in analysis;
processing success does not establish a supported evaluation allocation.

Continue to a fresh bounded evaluation only if the current planner produces a
supported `evaluation-plan.json`. Do not increase spending or change scoring to
make an allocation qualify. Independent human adjudication of the retained
conflicts and validation of a sample of resolved labels could reduce assessment
uncertainty, but must remain distinct from this AI-only measurement.
