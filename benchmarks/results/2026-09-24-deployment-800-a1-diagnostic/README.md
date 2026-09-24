# Stopped 800-call A1 diagnostic

The first frozen A1 allocation started eight concurrent Stage 1 calls. Six
completed, and two assigned GPT-4.1 nano direct calls returned HTTP 400 with
no provider usage record because the A1 study-specific configuration sent an
unsupported `reasoning_effort=none` field. The runner stopped after the first
batch. The two failed calls have unknown billing; the six completed calls total
US$0.0216019 at configured rates. No A1 case was retried or pooled with A2.

`stopped-a1.tar.gz` preserves its original freeze, attempt ledger, plan and
nano configuration. SHA256:
`a2dbf7aa9c01259069449361e2a2ecde365777509c0b3b5893ee326557d58262`.
The A2 capability probe uses a corrected nano configuration and a distinct
freeze. A1 does not count as an 800-call execution.
