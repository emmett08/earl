# Negative-revision 96-call developmental run, 24 September 2026

The exact immutable inputs, all raw responses, returned model identity, usage,
per-call diagnostics and analysis are in `campaign-96.tar.gz` (SHA256
`e43bc02c967fb1bab5db625234430d94f7f23e1ee93fb1ea38b85953a8bf28c3`).
Freeze SHA256 field:
`b5ffb48c39aa542ab171a20c81f0f6bcb7af03f230ad411f13b9d8048f378e25`.
The frozen material-map SHA256
`5914050546ec197ed92a1217353007b2b9f7499eb0cfd5f3d4594c97222914c5`
matches the second AI fixture reviewer gate at
`docs/reviews/eal2-negative-revision-96-second-ai-review.json`. Raw ledger
file SHA256:
`da2173ea14346f05e76308c07ab5786b77d1517c3055ecc6857b628081cc98ca`.

The original `INV-EAL-NEGATIVE-REVISION-001/0.1.0` is a specified, unrun
protocol on merged main. This run is the explicitly amended, selected-family
`0.2.0-dependent-family-developmental` implementation. It assigned 48 Stage A
one-shot calls and 48 Stage B three-turn authoring calls on eight selected
synthetic briefs, one pinned `gpt-4.1-nano-2025-04-14` snapshot. All **96/96**
completed, with zero retries and provider failures. Summed usage was 174,260
input tokens, 52,608 of them cached, and 31,795 output tokens. Configured-rate
cost was **$0.0261984**, median API time **10.89 s**, and summed API time
**1,108.86 s**. These are model charges only; human authoring/review,
acquisition and deployed review cost remain unmeasured.

| Stage and view | All three claim labels exact | Whole three-state roots exact | False support cases | Invalid response or authored source |
| --- | ---: | ---: | ---: | ---: |
| A, raw EAL | 10/24 | 0/8 | 9/24 | 0/24 |
| A, equivalent generic JSON | 3/24 | 0/8 | 7/24 | 1/24 |
| B, authored EAL | 0/24 | 0/8 | unavailable: 0 accepted sources | 24/24 |
| B, authored generic JSON | 0/24 | 0/8 | unavailable: 0 accepted sources | 24/24 |

On the **adverse state**, neither raw view supplied all three exact labels on
any of the eight roots; each produced six cases with at least one false
`supported` claim. EAL's greater Stage A pointwise exact count occurred in
the covered and invalidation states; canonical message JSON had median 6,310.5
UTF-8 bytes for EAL against 3,698 for generic JSON, so this is a rendering-bundle result.
It does not establish a general EAL syntax advantage or safety improvement.

Stage B exposed an authoring-interface problem. All 24 EAL submissions failed
syntax. The system prompt omitted a complete runnable EAL grammar example;
none of the submitted sources began with the required exact language header.
All 24 generic submissions were well-formed JSON with the requested top-level
keys, but made `positive_routes` an array of route objects while the checker
required literal reader ID strings. The checker repeatedly returned
`TypeError: unhashable type: 'dict'`, which did not explain that type contract.
The frozen three-turn results stand as failures of the supplied authoring
interfaces. They cannot discriminate EAL authoring against an equally
specified generic authoring route. A repaired comparison needs a new protocol,
complete matched format examples, typed validation diagnostics, and fresh
independently authored briefs.

The eight roots share a single author and generated scaffold despite several
graph and coverage variants. Their references received a second AI rule
review, not masked independent human adjudication. Synthetic acquisition and
the conveyor's asserted supersession are not authenticated engineering
history. The checked EAL and independent JSON results matched all 24 authored
states and paired pre-call tamper controls; that confirms only this bounded
implementation agreement.

All 48 Stage A explanations received two independent AI readings under the
same rubric frozen before either reviewer saw model responses (rubric SHA256
`e8e59d827d2bdfac50921f51b2bd8cf865e794637dcfd2e1adcb58379f67f7cc`).
Both reviewers found 47 parse-valid responses, 13 exact three-claim maps,
and exactly **one** text-faithful and accepted-faithful response, the same
EAL-view case. The binary endpoints agreed on all 48 cases. Their criterion
decisions differed on 10 cases (R: 2, M: 1, N: 8, B: 6), preserved as separate
ratings with a disagreement packet; no post-hoc consensus replaced them.
Under a distinct, earlier categorical rubric, the second reviewer found two
faithful responses. This is a sensitivity reading, not the same endpoint.
One reviewer saw the other's aggregate only after composing all item ratings
but before freezing the first categorical report; neither saw the other's
per-item labels before freezing its strict-rubric report. Prompts exposed
the representation, and both reviewers saw the synthetic reference. This is
post-call, AI-only exploratory scoring, not masked human adjudication.

The exact prompt-and-response packet, separate arm/root linkage, both rubrics,
three frozen review files and the disagreements are preserved in
`explanation-review.tar.gz` (SHA256
`74f7fc22fc1e6991409ccd3aa79f39fbec7f9c28e300e41603b649b335a484e1`).
Its packet canonical SHA256 is
`c82633deb4fb52032e9419d15bcfdde96207592693fb1e33fd699074c85277a2`;
the internal manifest binds every member to its file hash and the terminal
ledger. No population confidence interval or all-in cost per correct accepted
decision follows because authoring and review effort was not measured.
