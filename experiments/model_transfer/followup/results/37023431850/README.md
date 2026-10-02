# Completed live evidence-restoration follow-up

Collection run [37023431850](https://github.com/emmett08/earl/actions/runs/37023431850) retained 8 common donors and 120 recipient cells (8 task units, 3 contexts, 5 conditions, one repeat). Model: `gpt-4.1-nano-2025-04-14`; tools disabled. Configured total cost, including donors: USD 0.0204097 against a USD 2 cap. Provider usage is complete. These configured rates are not an invoice or an adoption-cost estimate.

Three separately masked AI assessors qualified on a reviewed, frozen 24-item V4 exercise: 24/24 decisions, 24/24 explanation-consistency codes and 48/48 semantically relevant exact quotes each. V1–V3 exercises had non-unique gold labels and are retained ungraded for qualification. The operational supplement was fixed after collection and before participant coding. This is neither human validation nor a measured assessor-error rate.

Two assessors coded all 128 answers, agreeing on 126 pairs and 252/256 fields. A separately qualified blind third assessor resolved only the two disagreement pairs. Six agreed ambiguous decisions remain recorded with contradictory explanations. All 128 final records have exact retained source text and supporting quotes. Donors are excluded from the quality denominator and included in resource totals.

| Context | Canonical field matches | Known communicated verdict matches | Primary successes | Contradictory explanations | Ambiguous verdicts |
|---|---:|---:|---:|---:|---:|
| Facts | 20/40 | 20/40 | 20/40 | 3 | 3 |
| EAL | 31/40 | 30/40 | 30/40 | 3 | 3 |
| Conventional | 33/40 | 33/40 | 33/40 | 0 | 0 |

The primary endpoint requires both reference agreement and an internally consistent explanation. The six ambiguous verdicts still have known primary failures because explanation consistency is false. The frozen generic reporter retains `pending_annotation` for those six decision codes; collection is complete and every primary cell is determined. Labels must not be coerced to make that status disappear. Factual explanation grounding remains unassessed.

Only 1/24 critical-gap answers met the primary endpoint, compared with 23/24 complete, 22/24 restored-positive, 16/24 restored-negative and 21/24 noncritical-gap answers. These are descriptive matched cells, not 120 independent tasks. No context passed the frozen all-40 feasibility criterion. Availability cause is confounded with fictional task domain. EAL and conventional supplied packets were identical at all 40 matched positions, so their observed contrast cannot identify an EAL-specific effect. The facts contrast also changes the supplied computed verdict. No additional paid collection or principal allocation/evaluation is warranted by this diagnostic run.

`final-labels.json` contains the final reproducible assessor provenance. `coding/` retains administration, independent records, disagreements and adjudication. `derived/` contains deterministic gzip copies of the locally imported rows and analysis with uncompressed SHA256 identities. Raw collection rows were not overwritten. `endpoint-summary.json` and `resource-summary.json` are inspectable summaries. `validation/` records independent checks; `figures/` supplies exact calculations, figure specifications, source and rendering proofs.

The original full Actions archive is preserved in the reproduction package. The public derivative in `raw/` omits only local SQLite signing-key sidecars, retaining every other member byte unchanged; its receipt binds both archive identities and all omitted paths.

Offline [finish run 37038229027](https://github.com/emmett08/earl/actions/runs/37038229027) succeeded at commit `777ab4c2f5b0ed2165d662992db0413d82dde14a`. Verification passed 1,411 tests with one skipped and built the distribution. Artifact `11241339312` has SHA256 `c442a8579f3abc68b79908d66e5de19953aa5dc976ac1f5785c49f9157786811`. An independent archive audit passed 5,819 checks: all 1,933 original members are byte-identical except two approved processing metadata updates; three derived files were added. Its labels and annotated rows match the local audit byte-for-byte. Collection usage, API calls, cost and journals are unchanged. Final pipeline state is `processing_complete`; diagnostic allocation is `not_applicable_to_diagnostics` and no evaluation plan exists. The six ambiguous verdicts keep the generic analysis status `pending_annotation`.
