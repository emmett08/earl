# C1 stopped continuation, 24 September 2026

The separately frozen C1 continuation assigned only the 672 A2 slots not
previously attempted. It stopped after 288 further API attempts: 284 completed
and four returned HTTP 500 without usage. The first three failures were
independent fixed-source calls (indexes 128, 279, 322). Index 456 was the first
linked author turn for `batch_pipeline/eal/luna`; C1 stopped because its later
author turns cannot proceed without that actual prior response. No failed call
was retried and no dependent turn was dispatched.

Together A2 and C1 attempted 416 of the 800 assigned slots: 411 completed,
five failed without usage, and 384 were never attempted. C1 configured-rate
model cost for completed calls is US$0.5556279. Its four failed calls have
unknown billing; US$0.1475456 was reserved for them, including the author
failure, whose `eligible_server_failure` is false and whose row nevertheless
retains `reserved_cost_usd`. A2 contributes US$0.1793467 measured configured
cost and US$0.12672 unknown-billing reserve. The combined conservative
accounted amount is US$1.0092402. It is not an invoice or all-in cost.

`stopped-c1.tar.gz` contains the exact continuation freeze and attempt ledger.
Its SHA256 is
`f43d048420d796852a96a47c0c3226e78577c38f82171962989ef6ea68b654dd`.
The C1 terminal ledger SHA256 is
`df3ed573710dff7b8471257cf2d7d9c48dd7f8c79723ec014e1e39d64322f6b6`.
The signed code/freeze review is
`docs/reviews/eal2-800-c1-continuation-ai-review-20260924.md`.

Any later continuation must preserve both ledgers, exclude every previously
attempted slot and leave the failed author chain structurally unavailable or
account for an explicitly separate repair. The original full-factorial
protocol still has not been executed; this synthetic cohort is developmental.
