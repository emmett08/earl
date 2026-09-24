# Stage A explanation review comparison (96-call developmental study)

Two AI agents independently scored the same 48 exposed Stage A prompt/response/reference
triples against the frozen [R/M/N/B rubric](negative-96-stage-a-explanation-rubric-20260924.md)
(SHA-256 `e8e59d827d2bdfac50921f51b2bd8cf865e794637dcfd2e1adcb58379f67f7cc`).
Both retain every attempted slot. The first review is
[`negative-96-stage-a-explanation-ai-review.json`](negative-96-stage-a-explanation-ai-review.json)
(SHA-256 `ac6a8949d1d3343719967cd9137d13eb8ffc7e9ce5a72a0403779481496efce0`);
the second is
[`negative-96-stage-a-explanation-second-criteria-review.json`](negative-96-stage-a-explanation-second-criteria-review.json)
(SHA-256 `2b05c0912b74f64abc6f21e3dc4ca62a2199407dedc4c99ecfdae05ace471490`).

The reviews agree on all 48 parse, three-status exactness, text-fidelity and
accepted-fidelity decisions. Each identifies 47 strict parses, 13 exact status
maps and the **same one** faithful and accepted explanation (item
`be93031c4a284a69c93c855e`). No third pass is needed to decide that binary
endpoint. This is agent review of synthetic, author-constructed cases, not human
adjudication or evidence of physical truth.

Ten cases differ on subcriteria: `R` in 2, `M` in 1, `N` in 8 and `B` in 6.
The exact exposed prompts, responses, references and both frozen diagnoses are
in the [de-identified disagreement packet](negative-96-stage-a-criteria-disagreement-packet.json)
(SHA-256 `9ff929bc63ab185cefcd651f264b348bd0e2c25d3338891960e8a46fa2c010ab`).
The main judgement differences are whether an unquoted but readable
explanation in invalid JSON can receive individual criterion scores, and
whether omitting complete sampled coverage/calibration fails `N` as well as
the decisive-mechanism criterion `M`. Both reviewers reject its final accepted
decision. No original rating was overwritten or reconciled away.

The second agent first scored a separate
[categorical rubric](eal2-negative-96-stage-a-explanation-rubric-20260924.md)
in [`eal2-negative-96-stage-a-explanations-reviewer-fixture24.json`](eal2-negative-96-stage-a-explanations-reviewer-fixture24.json)
(SHA-256 `8d28081821f17a61d621cec36762a51236df4a492088381ffeeaa0ae683d5c22`):
2 `faithful`, 8 `incomplete`, 38 `materially_false`. Those categories are a
distinct exploratory diagnostic and must not be pooled with the frozen rubric's
binary endpoint. Before the second R/M/N/B pass, the agent had seen the first
reviewer's aggregate counts and root/view summary, but not its case ratings or
the arm/root linkage. The 96 calls had begun before either explanation rubric
was written. The source view was visible in the exact prompt to both reviewers.
