# Independent AI review: mechanisms-960 A4 exact freeze

Date: 2026-09-24. Reviewer: `/root/repo_publish`, separate from the A4
template author and campaign runner. Decision: **accept the exact saved A4
freeze for a separate probe and paid execution**, subject to its frozen stops.

| Reviewed object | SHA-256 |
| --- | --- |
| `scripts/continue_mechanisms_960_a4.py` | `18c3cedc41dfd3d8d42531bd1f9f6082d47c0d05de1d8793ea865ab8a740f23d` |
| Saved A4 `freeze.json` | `8f7910b1334a45d8f9df3ec33212d47dc079060c1371a65959bcb838df31abd0` |
| A4 semantic freeze | `0da0b96efc128f41a523819dfbcee70489639da28cf6197abeae9589a9c0eebd` |
| Terminal A3 ledger | `ce9e5a298c223df00acefb5b3b6e14cb204b84679d1cb146b264136e0e214129` |

I independently recomputed `prepare()` and `verify()` against the original,
A2 and A3 source directories and obtained the saved A4 freeze exactly. The
read-only composite validates the prior 726 unique original-order assignments
0–725, their frozen prompt hashes, parsed scores, model identity, response
usage, configured costs and separate A2/A3 probe records. The A3 stop occurred
after a complete two-slot batch at its eighth new failure; the previous batch
had not crossed its stop rule. A4 assigns precisely the untouched 234 original
indices 726–959, with original prompt hashes, at concurrency one. The A4
ledger was `frozen` with zero attempts and no probe when reviewed.

The prior 13 failed slots, of which 11 have unknown actual charges, remain in
their original ledgers. A4 never retries them. The A4 runner records a pending
row before each send, checks every resolved row and exact prefix on re-entry,
rejects a pending or terminal ledger, and reserves unknown failed-call cost.
A separately metered and model-identity-checked probe is required before
study calls. A4 can continue after only the two specified `ProviderError`
forms: response-less or an accepted-model, metered, length-limited response.
Other errors stop after the current attempt. Three consecutive or 24 total
new A4 provider failures stop subsequent dispatches; the threshold applies
to A4 only, while earlier failures remain in the final composite. A4 uses the
original `$5` configured-rate cap, checked against the still-unattempted
frozen reserve before every send.

The full conservative envelope is `$1.1102357` under that `$5` cap: prior
known model cost `$0.2169070`, prior probes `$0.0000046`, 11 unknown-charge
reservations `$0.0301785`, A4 probe reserve `$0.0004672`, and the remaining
234 prompt reserves `$0.8626784`. Unknown invoice charges are not measured
zeros. I invoked the paid gate without an attestation and confirmed it failed
before a provider load or call. This review report and its exact-file
attestation must remain bound to the saved freeze before probing.

The broad response-less `ProviderError` allowance does not prove every such
failure was transient HTTP 5xx. The original 24 roots and references are
synthetic and author constructed; this operational sign-off does not add human
adjudication or establish a language-specific advantage. No model outcomes
were inspected to select the A4 suffix. Any change to frozen scripts, source
ledgers, probes, prompt hashes or provider identity invalidates this approval.
