# Authorised developmental cross-model calls, 24 September 2026

These are **new exploratory schedules**. They do not execute or replace the
specified 96-, 800- or 960-call investigations. The private prompts and
synthetic records were sent to the configured OpenAI models after the user's
explicit approval. The credential is not retained here. Each archive contains
the exact freeze, ordered attempt ledger and audited analysis, including raw
responses, usage, failure records and model identity. No silent retry or
resumption of a stopped freeze is permitted.

## Stopped identity diagnostic

`alias-mismatch-diagnostic.tar.gz` retains a 180-case freeze that stopped after
three attempts: two completed and the third failed the frozen returned-model
identity check. That third GPT-4.1 nano request returned the dated model
identity `gpt-4.1-nano-2025-04-14` and billed 700 input and 42 output tokens
at the configured rates (US$0.0000868). The three attempts together cost
US$0.0050428 under those rates. They are excluded from all later revised-run
estimates. The subsequent schedules explicitly allow that returned identity
for the five nano conditions, and were newly frozen before their calls.

## Revised developmental schedules

The first distinct cohort has 180 scheduled initial recipient cases from four
previously exposed synthetic roots: five routes, three model classes and
twelve related root/state pairs. Its freeze SHA-256 is
`3d6a33d88720772f63255a1fac1210c05717b08fe4b49d7900a176920939529d`.
The second has 135 scheduled cases on three newer but singly authored roots;
its freeze SHA-256 is
`b8f9cf8fa03ac03c446c94d4e32287edbc0f45fcf4360c00195046375b8e13ef`.
The request arm can make one validated second turn. Frozen per-study spending
caps are US$4 at configured rates. A failure is retained in its assigned
attempt denominator. The independent generic checker and EAL interpreter
agreed on every frozen selected synthetic state and the declared tamper
checks, but their common endpoint status is supplied to checked recipients.

The arms compare raw source, a short instruction, model-originated assessment
request, preassessed EAL claim packet and an independently implemented equal
checker packet. The request arm is text JSON against a fixed menu with known
artefact IDs, not native MCP use, finite family resolution or candidate
retrieval. The host owns checked final status. Recipient contradictions must
be reported separately. These roots and their expected statuses lack two
masked independent reviewers. Source and checker parity do not demonstrate
correctness in a physical system or an EAL-specific advantage.

**Interpretation of measured resources:** model usage and elapsed API time are
retained per attempt; configured-rate costs are estimates, not invoices.
Initial source authoring, independent review, live acquisition, host
operations and faithful explanation adjudication were not all measured. Total
cost per *faithful, correctly accepted* decision is therefore unavailable;
neither packet bytes nor provider-only token ratios can substitute for it.

## Completed recipient cohorts

| Archive | Frozen first-call cases | Completed model calls, including routed second turns | Input / output tokens | Configured-rate model cost | Retries and failed attempts |
| --- | ---: | ---: | ---: | ---: | ---: |
| `pilot-180-revised.tar.gz` | 180 | 207 | 257,339 / 25,359 | US$0.3798973 | 0 / 0 |
| `cohort-135-revised.tar.gz` | 135 | 158 | 177,085 / 17,407 | US$0.2558221 | 0 / 0 |

The 180 cases use four exposed synthetic roots; the 135 cases use three newer
but singly authored roots. Every listed first-call case completed. Summed
per-case model API time was 1,923.205 and 1,448.013 seconds, respectively;
the campaigns ran concurrently, so these sums are not elapsed study time or
host/network transport measurements. Per-scenario median/p95 seconds by
nano/Luna/Sol were 7.68/13.50, 8.27/17.25, 11.82/23.40 in the first cohort
and 7.92/16.57, 8.26/21.38, 11.59/20.48 in the second.

| Model | Raw exact status, 21 states | Skill instruction exact status | EAL host final status | Equal checker final status | Recipient contradictions to EAL/equal status |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-4.1 nano | 4/21 | 3/21 | 21/21 | 21/21 | 1/0 among parseable answers; EAL/equal malformed 12/12 |
| GPT-6 Luna | 18/21 | 18/21 | 21/21 | 21/21 | 8/1 |
| GPT-6 Sol, high reasoning | 17/21 | 19/21 | 21/21 | 21/21 | 0/0 |

The checked final labels were already oracle-matched by construction. They
test a host-owned decision boundary, not the model's independent reasoning;
the recipient contradiction and malformed counts show the distinction. In
the seven adverse states per model, raw and instruction routes each produced
one explicit false-supported answer for nano and Luna, and none for Sol.
Malformed text is not counted as a safe negative decision and can hide an
incorrect latent judgement. These small dependent roots do not estimate a
population effect.

The model-requested route made a valid host request in 27/36 first-cohort
cases and 23/27 new-cohort cases. Its **63/63 final outputs were malformed**
under the strict answer schema because the second turn retained a first-turn
system instruction to output another operation request. This is a retained
protocol defect, not evidence that a clean routing skill fails. In particular,
the checked labels of 12/12 or 9/9 for Luna/Sol in this arm are host labels,
not accepted recipient answers. The fixed menu prefixed the correct artefact
description; this route did not test candidate retrieval. A separate,
newly frozen route-only correction is required to evaluate that procedure.

No blinded explanation adjudication or initial human authoring/review effort
was recorded, so faithful-explanation rates and total cost per correctly
accepted decision remain **unavailable**. The raw archive preserves every
response and exact prompt for later review. The read-only `audit.json` within
each archive reports recipient-versus-final consistency and verifies subcall
usage. Reproduce original analysis with
`PYTHONPATH=src:. python scripts/analyse_cross_model_campaign.py <extracted-run-directory>`;
its original runner and analyser were frozen and are preserved in the source
revision. A later scorer correction is separately versioned rather than
rewriting the old schedule or outcomes. The
`stricter-readonly-analysis.tar.gz` archive contains an additional
`analysis.v2.json` for each cohort. It requires a parseable recipient verdict
equal to the checked final verdict before calling a decision consistent;
the resulting counts still precede independent explanation review.
