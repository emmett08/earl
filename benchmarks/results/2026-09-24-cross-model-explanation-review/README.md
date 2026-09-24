# Exploratory explanation review, 24 September 2026

This archive retains a **105-output subset** of the completed 180- and
135-case developmental model campaigns. It is an exploratory review by two
separate model agents, blinded to the arm/model linkage until their files
were complete. It is **not human adjudication** or an independent check of
the seven singly authored synthetic dossiers and their source oracles.

The deterministic selection takes one state from each of seven roots, with
three supported, two unsupported and two contested states. Each selected
state contributes all 15 arm/model cells. The selection rule was documented
after some outputs were observed; the review is not confirmatory. The
`reviewer_items.json` snapshot says `unreviewed` because it was generated
before scoring. `arm_model_linkage.json` was withheld from reviewers.

| Adjudicated category | Outputs |
| --- | ---: |
| Faithful | 49 |
| Incomplete but nonmisleading | 13 |
| Materially false | 4 |
| Malformed or absent | 39 |

The reviewers agreed on the binary faithful judgement for 105/105 outputs
and on the four-way category for 104/105. The one category disagreement is
retained in `adjudication.json`; the source packet omitted the exact prompt
seen by the recipient, so a reference to a “supplied excerpt” could not be
settled as factually false. The recorded resolution classifies it as
incomplete, with **no human arbiter**. Agreement is partly driven by 39
malformed or absent explanations and does not validate the remaining labels.

The sampled faithful counts by arm were raw 16/21, skill instruction 15/21,
EAL host 4/21, equal checker 14/21 and legacy skill route 0/21. These are
descriptions of selected synthetic cases, not generalisable rates. The
legacy route's second turn carried conflicting instructions, and all 63
outputs in the full two campaigns were malformed under the declared schema;
its 0/21 here is a protocol failure. The host and checker supplied their
final statuses; a faithful explanation from a recipient is a separate
outcome. Some host explanations lack enough transitive evidence in the
compact packet, but the review cannot isolate that mechanism from different
recipient prompts and author-supplied fixtures.

The blinded packet included each claim's authored source, raw evidence,
scope and oracle, along with the recipient output. It did not include the
exact recipient-visible prompt. Response wording can also reveal a route,
so arm blinding was imperfect. Full-campaign fidelity, human review effort,
actual provider billing, authoring/review effort and **all-in cost per
correct accepted decision remain unmeasured**. The reported model-agent
review times in the JSON are execution times, not a substitute for those
human costs.

## Files and reproducibility

`reviewer_items.json` contains the seven dossiers and de-identified model
outputs. `arm_model_linkage.json` maps item IDs to arm/model/case and is kept
separate so the review process can be inspected. `reviewer_a.json` and
`reviewer_b.json` retain independent categories, explanations and evidence
references. `adjudication.json` records their agreement, the one category
disagreement and descriptive unblinded counts. `manifest.json` lists raw
SHA-256 digests, source freeze and ledger digests, and the copied source
programmes under `source/`.

The source in `source/extract_cross_model_review_sample.py` builds the
sample from the completed campaign ledgers. The source in
`source/summarise_cross_model_explanation_review.py` verifies item linkage,
reviews and the explicitly recorded category resolution. Recompute the
summary without modifying these inputs:

```sh
python source/summarise_cross_model_explanation_review.py . --output /tmp/recomputed-review.json
cmp /tmp/recomputed-review.json adjudication.json
```

The copied inputs contain synthetic arguments, observations and model
outputs. No API credential is retained. The parent campaigns and their
frozen runner are documented in
`../2026-09-24-cross-model-live/README.md`; the review selection contract is
`../../../docs/cross-model-explanation-review-proposal-20260924.md`.
