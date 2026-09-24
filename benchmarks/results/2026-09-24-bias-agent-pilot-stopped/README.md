# EAL/2 bias-agent stopped pilot

The amended 0.1.1 pilot began on 24 September 2026 with the externally
configured `OPENAI_API_KEY`. The endpoint preflight succeeded without sending
the key. The runner then made one paid Responses API call and stopped, as
prespecified, when the returned structured answer failed the experiment's
evidence-reference validation. There was no retry, and the full schedule was
not started.

The attempted condition was the independent-mechanism analyst using the
`luna` plan entry. The provider returned model identity `gpt-6-luna`, response
status `completed`, 1,773 input tokens and 187 output tokens. The configured
uncached-rate estimate is USD 0.0002708; it is not an invoice. The answer
cited rival record `r3` as opportunity evidence and cited rival records in the
evidence list, then selected `r3` as a defeater. Those references violate the
closed identifiers for those fields. The outcome is therefore retained as
`invalid`, not silently repaired or scored as a completed assignment.

The partial analysis contains zero valid calls out of 72 planned calls. It
does not estimate an agent-topology or model effect. Its zero rates are
structural results of the incomplete matrix and must not be interpreted as
observed performance. The one invalid answer is nevertheless retained for
audit, including its fabricated-evidence diagnostic. Manual rationale review
has not been performed.

The ledger has a pending event followed by exactly one terminal outcome. It
contains the redacted provider response, request and response identifiers,
usage, latency, configured cost estimate, validation diagnostics and hash
chain. It contains no API credential. The compressed freeze is byte-identical
to the amended freeze in the zero-call archive.

| Member | SHA-256 |
| --- | --- |
| `pilot-freeze-0.1.1.json.gz` | `ce45635bc8ea952d4a15701bdacdf5894e9bacd60f9d5899b3c5b99c09a8ff36` |
| `pilot-ledger.jsonl` | `d8400a5154d035ee780fbaf70bbcdd6d773d1c3c648204ee172792b3ffa7a296` |
| `pilot-report.json` | `54fc16f86ef9c36b94e47fce251eb54dace01428dc70e8779f491ba319adb5f2` |

The freeze's internal SHA-256 is
`ddff588b8b619397ad052fd2fae20b03012267b7a35dbccbd6325bd2d2fc3f72`.
Do not resume this ledger: the protocol forbids automatic retry after a
terminal invalid response. A future attempt requires provider/billing
reconciliation and a separately documented, newly frozen run decision.
