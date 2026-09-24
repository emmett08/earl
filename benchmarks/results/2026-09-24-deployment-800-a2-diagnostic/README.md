# A2 stopped diagnostic, 24 September 2026

Amendment A2 was frozen with 800 assigned calls after the separate stopped A1
configuration probe. A2 stopped after its first 128 assigned fixed-source
attempts: 127 completed, while `deployment-0125` (Sol, EAL, initial state,
native function request) returned HTTP 500 with no reported usage. The unknown
billing for that failed request is retained as such. No A2 request was retried.

The 127 completed requests used 253,942 reported input tokens, 1,087 cached
input tokens and 7,860 output tokens. Configured-rate spend was US$0.1793467,
excluding the unknown charge and any cache-write premium. Ninety-one of the
127 yielded the exact reference status; one yielded false support under the
predefined status rule. These are stopped diagnostic observations and are not
an 800-call result. The author and recipient stages were not reached in A2.

The archive `stopped-a2.tar.gz` contains the exact freeze, attempt ledger and
read-only analysis. Its SHA256 is
`b436338301bf50988bd92659a591189928ccd3a1dcde7678a2d8c83496b03f07`.
The freeze digest is
`d60a61a9c1e28f1ef712a8da6c8bceb04f8a8da4b7ea9ce1781f50a2fdb6a4d2`.

An independently audited continuation, if executed, can attempt only the 672
never-sent slots in the same frozen allocation. It must preserve all 128 A2
rows, including the failure, and report its separate provenance and unknown
billing reserve. The A1 stopped configuration diagnostic and three capability
probes remain outside this cohort.
