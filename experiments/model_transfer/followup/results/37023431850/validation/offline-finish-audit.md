# Offline finish archive audit

Status: **passed**. 5819 byte-identity, provenance and status checks; 0 failures.

Finished workflow run **37038229027**, artifact **11241339312**. Exact original private ZIP: `earl-followup-37038229027-original-finish.zip`, **4,135,583 bytes**, SHA-256 `c442a8579f3abc68b79908d66e5de19953aa5dc976ac1f5785c49f9157786811`.

All 1,933 original export members remain in the finished archive. Exactly 1,931 are byte-identical; only `pipeline-status.json` and `restore-receipt.json` changed as authorized. Exactly three derived members were added: `completed-labels.json`, `annotated-rows.json` and `analysis-annotated.json`. All 1,936 finished payloads match their extracted files; both archives have unique member names and pass CRC integrity checks.

| Verified status | Value |
|---|---|
| Pipeline state | `processing_complete` |
| Original collection | `complete` |
| Scientific analysis | `pending_annotation` |
| Pending annotation sessions | 6 |
| Planning | `not_applicable_to_diagnostics` |
| Evaluation available | false |
| Original API attempts | 128 |
| Original configured API cost | USD 0.0204097 |

Completed labels match the sanctioned final labels byte-for-byte, SHA-256 `7718c5f4b0e78fa9ef35e6b89ceec525781d876bf0e44d7e15f38f72d45241d1`. Annotated rows match the audited local import byte-for-byte, SHA-256 `6d88aa0f7680ccd23759a447b33ba7d6fb29d30f4dc13e4e051a64835acca7b5`.

The finished analysis equals the audited local analysis except four metadata paths: `rows_source`, processing revision, Python version and implementation digest. No outcome, annotation, count, score, resource, comparison, inference scope or scientific status changed. The finish processing commit also retains all 63 frozen collection module fingerprints.

Collection revision: `054c27354e1d3ed15d9c1c20f4b2110169b84a4e`. Offline processing revision: `777ab4c2f5b0ed2165d662992db0413d82dde14a`. The restore receipt binds the exact source export SHA-256 `c6e409e56258bd888cf7dea538adc3517afc14cb44a63f3a20dda808d2a135ff`.

Limits:

- All original and finished archive payloads were hashed and compared without semantic answer recoding, label-file parsing or calibration/key interpretation. Opaque key/calibration payloads were included in byte equality only.
- The exact private finished ZIP was read without modification. Archive identity, extraction identity and retained payload identity are local cryptographic checks, not a newly performed provider or billing audit.
- The workflow run/artifact association and test/build result were supplied by the parent. The archive audit verifies the provided filename, exact 4,135,583-byte size, SHA-256, contents and processing metadata; it does not independently fetch GitHub Actions logs.
- Processing provenance correctly differs from the live collection provenance. The analysis path and processing revision/Python/implementation fingerprint are expected environment metadata differences; every other analysis value matches the previously audited local analysis.
- processing_complete describes completion of offline importing/reporting. Scientific analysis remains pending_annotation for six ambiguous communicated-verdict assessments; all six are coded contradictory, so all recipient primary outcomes are nevertheless determined under the frozen conjunction rule.
- The inherited outcome counts remain conditional on supplied AI semantic labels. This audit does not establish calibration validity, semantic coding accuracy, factual explanation accuracy, human validation, superiority, population inference or a newly supported evaluation.
- Configured API cost remains USD 0.0204097 for the original 128 attempts. It ignores cached-input discounts and excludes coder/research/adoption costs; the finish run added no model participant requests.
