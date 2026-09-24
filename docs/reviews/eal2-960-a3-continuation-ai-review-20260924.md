# Independent AI review: mechanisms-960 A3 continuation

Date: 2026-09-24. Reviewer: repository/publication agent, separate from the
campaign author. Decision: **accept this exact frozen continuation for paid
execution**, subject to the recorded stop rules. This reviews scheduling,
identity, ledger, and configured budget; it does not adjudicate model answers.

| Object | SHA-256 |
| --- | --- |
| `scripts/continue_mechanisms_960_a3.py` | `67b56789dd452f9b6f6f69f7f4e005aaee9fd6db0bbd18aee2bed8f61bfb5121` |
| A3 freeze file, `paid-mechanisms-960-continuation-a3-v1/freeze.json` | `dcc17ddb96dae06db28a44a5c94c3be635bf9586245c83a86d724477679a34ea` |
| A3 internal freeze digest | `170ea3d6aec0fd0e2d071fe02968031ffab4ee078f15b1c5480ddbe2d3e1db4f` |
| Original terminal ledger | `9cb880af12042dfc953775cf430d9cfcca8217c3d439790e725716c2418e5c66` |
| A2 terminal ledger | `4f5714c777f9ec4cedaf84e2dc06981a0c2273be0e407c963c2cb446781ce550` |

The A3 ledger was `frozen` with zero attempts. I independently recomputed
`prepare()` and `verify()` from both immutable source runs. The freeze is
deterministic and assigns exactly indices **468–959**, 492 distinct original
prompt hashes in their original order. The prior 468 unique assigned indices
0–467 remain in the original and A2 ledgers. Their states were 461 completed,
two malformed, five failed; no prior failed slot is retried.

The A3 runner uses the read-only composite validator to check every prior
prompt, model response, usage, score and configured cost, including the
metered accepted-model length response at index 467. A fresh separate probe
must have an accepted model and measured usage before A3 assignments. Each
batch persists pending slots before at most two sends, then records every
returned row. Pending rows, prompt mismatches and terminal ledger re-entry
block later sends. Only response-less `ProviderError` and the precisely
checked metered accepted-model length form can remain failed while the next
batch proceeds. I checked the frozen threshold function on three consecutive
eligible failures; it stops, as does an eighth A3 failure. Other failures
stop after the dispatched batch.

The configured dollar envelope is `$1.9436369` against the original `$5`
cap: original known `$0.0398617`, A2 known `$0.1041924`, separate A2 probe
`$0.0000023`, four earlier unknown failed-call reservations `$0.0104468`,
new probe reserve `$0.0004672`, and all remaining case reserves `$1.7886665`.
Actual charges for response-less attempts are unknown, and these reserves
must not be reported as paid invoices. A3's threshold counts new A3 provider
failures separately from five earlier failed observations; the composite
analysis must retain all five earlier failures and both probes outside the
960 assigned decisions.

The accepted response-less `ProviderError` rule does not distinguish HTTP 5xx
from another provider error without a response. It is a frozen operational
rule, so conclusions about recovery from transient errors require caution.
This sign-off is invalid if the runner, freeze, source ledgers, source validator,
or provider identity changes before the first A3 call.
