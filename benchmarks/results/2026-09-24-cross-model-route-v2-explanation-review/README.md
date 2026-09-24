# Route-v2 developmental explanation review (2026-09-24)

This is a complete 63-output, two-agent explanation review of the corrected `skill-route-second-turn/2` pilot and cohort ledgers. It is **not human adjudication**. The seven roots, 21 selected states, their observations and oracle statuses are synthetic, author-supplied material; the review cannot establish field correctness, general model capability or population effects.

## Provenance and frozen sample

| Campaign | Route-v2 cases | Route freeze SHA-256 | Original raw-case freeze SHA-256 |
| --- | ---: | --- | --- |
| Pilot | 36 | `78e859ece4e05dcffcc0594d12f39b08356087a3fa18e55cadf4463951db468d` | `3d6a33d88720772f63255a1fac1210c05717b08fe4b49d7900a176920939529d` |
| Cohort | 27 | `0aed399243f68d420eaa07ebcd063909e7d4899bdaf91ccfabb9ed2102de2640` | `b8f9cf8fa03ac03c446c94d4e32287edbc0f45fcf4360c00195046375b8e13ef` |

The corresponding route ledgers were terminal `complete` at 36/36 and 27/27 before extraction. Their complete frozen inputs and ledgers are in `../2026-09-24-cross-model-route-v2/`; the original 180/135 campaign freezes are in `../2026-09-24-cross-model-live/`. The extractor checked the exact freeze identities, case/ledger index and prompt hashes, source digest, revision, author oracle, and imported observation IDs, contexts, times and values. It used the task/source from the original raw case and the actual host packet delivered in the corrected final call. The review packet includes every final output, including 12 malformed request echoes with no delivered host packet. Its order and opaque IDs were fixed from frozen case identity rather than response contents.

`extract_review.py` is the exact extraction code used with the four campaign directories adjacent to its original working directory. To replay from archives, extract the two route tarballs as `paid-route-v2-pilot-final` and `paid-route-v2-cohort-final`, and the original tarballs as `paid-pilot-alias-v2` and `paid-cohort-alias-v2`, under a common parent. Place the script in a fresh `route-v2-explanation-review-v1/` child of that parent, then run it there. It refuses to overwrite an existing reviewer packet. `packet_manifest.json` records the generated packet and hidden-linkage hashes; `HASHES.sha256` covers this archive.

## Review and result

The rubric in `RUBRIC.md` was fixed before scoring final outputs. Both agents used `reviewer_items.json`, which contains source, evidence, oracle, actual delivered host packet and recipient final text/status, but omits model and arm identity. `arm_model_linkage.json` was separate and unread during individual scoring. The original labels are preserved in `reviewer_a.json` and `reviewer_b.json`; `raw_agreement.json` records disagreements without altering them. The root agent resolved four disagreements in `adjudication.json` after both sets of labels were locked. The resolution is another **agent judgement**, not a human review.

| Label | Reviewer A | Reviewer B | Root agent resolution |
| --- | ---: | ---: | ---: |
| Faithful | 13 | 11 | **11** |
| Incomplete but nonmisleading | 35 | 39 | **38** |
| Materially false | 3 | 1 | **2** |
| Malformed or absent | 12 | 12 | **12** |
| Total | 63 | 63 | **63** |

The raw reviews agree on 59/63 exact categories and 61/63 binary faithful labels; the descriptive category Cohen's κ is approximately 0.891. All 51 valid recipient JSON statuses matched both the author-supplied oracle and the actually delivered host status. A correct status does not imply a faithful explanation: a generic “host accepted the route” statement often omits the decisive record, objection, or conditional calculation. The four disagreement IDs and root reasons are explicit in `adjudication.json`.

The reviewers recorded approximately 2.413 and 2.950 elapsed minutes respectively. Those times measure only agent review, not original source authoring, fixture adjudication, evidence acquisition, model/API expense, host/checker computation or any human time. They cannot support a total cost per correct accepted decision. The packet is a developmental sample of these exact synthetic cases and route-v2 final outputs.
