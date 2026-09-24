# Developmental explanation review proposal (2026-09-24)

This is a proposed human review of the two paid, synthetic developmental
campaigns. No independent explanation review has occurred, and these fixtures
have not been independently adjudicated. The review must remain descriptive.
The initial `skill_route` second-turn prompt has a conflicting system
instruction; its outputs must be marked as a routing-procedure failure and
excluded from a clean route-to-answer contrast.

## Frozen-output sample

Select one state per independent root, including both available contested
roots. Among roots with an unsupported state, select two by ascending SHA-256
of `explanation-v1/<freeze_sha256>/<root_id>`; select a supported state for
each remaining root by ascending SHA-256 of
`explanation-v1/<freeze_sha256>/<root_id>/<state_id>`. This rule consults
freeze fields only. Include all 15 condition cells for each selected state.
The resulting 105 outputs contain 45 supported, 30 unsupported and 30
contested cases (three, two and two root/state blocks respectively).

| Run | Root | State | Oracle | Cells |
| --- | --- | --- | --- | ---: |
| 180-case pilot | `calibration_assumption` | `drift_characterisation` | contested | 15 |
| 180-case pilot | `asset_direction` | `different_unit` | unsupported | 15 |
| 180-case pilot | `loop_preconditions` | `complete_inspection` | supported | 15 |
| 180-case pilot | `vent_model` | `gain_one` | supported | 15 |
| 135-case cohort | `network_failover` | `buffer_challenge` | contested | 15 |
| 135-case cohort | `thermal_soak` | `stale_qualifying` | unsupported | 15 |
| 135-case cohort | `release_provenance` | `matching_stage` | supported | 15 |

This selection was documented after some model outputs had already been
observed; it cannot become confirmatory through a later freeze. Seven root
clusters and one state per root do not support population inference or
within-root revision contrasts. A later full 315-output review could improve
coverage, but it would still be a developmental sample of agent-authored
synthetic fixtures.

## Review material and labels

Two reviewers independently receive shuffled IDs, the named claim and scope,
the common raw evidence and source, and a reference rationale prepared from
the case without recipient outputs. They also receive the response's JSON
status and explanation. Hide condition, provider, model, final host/checker
status and prompt route until scoring is locked. Response wording may reveal
its route; record this limit. The reference rationale itself requires a
separate human check because the current oracle is author-supplied.

Each reviewer records whether the explanation uses the right subject, scope
and time; identifies the decisive qualifying or missing evidence; handles
the applicable objection and any answer; and avoids invented observations or
stronger claims. Use `faithful`, `incomplete_but_nonmisleading`,
`materially_false`, `unassessable` and `malformed_or_absent`, with a concrete
reason and the relevant evidence ID. Record a separate `recipient_status`
versus `accepted_status` consistency flag. A contradictory recipient JSON
status cannot yield a correct accepted decision even if prose happens to
describe the evidence correctly. Resolve disagreements by a documented
third-person adjudication without silently changing original labels.

Report the category counts per condition, both reviewers' raw agreement,
adjudicated results and examples selected without hindsight. A ratio with
seven reviewed responses per condition is descriptive. Retain malformed
output and routing failure as outcomes rather than omitting them.

Record each reviewer's elapsed minutes, adjudication minutes and applicable
hourly rates. Keep model usage, known failed-call costs, host/checker compute,
evidence acquisition, original source/family authoring and fixture review as
separate fields; unknown effort and provider invoice totals remain unknown.
Do not report total cost per correct accepted decision until every component
and the strict acceptance rule have been measured and reconciled.
