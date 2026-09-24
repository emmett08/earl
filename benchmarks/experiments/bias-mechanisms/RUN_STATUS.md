# Run status — 24 September 2026 (UTC)

**Paid calls: 0. Model outcomes: none.** The unauthenticated, no-key endpoint
preflight timed out before key lookup. No agent topology or model can be
ranked from this record, and no human bias mitigation has been observed.

The original 0.1.0 pilot and full frozen schedules remain in
`benchmarks/results/2026-09-24-bias-agent-zero-call/` unchanged. Their internal
digests are `4623418bc80a5e9bdc4bce5154e4cb2656a3fdc88e945bcf553cbcf1158d75cd`
and `1684c165caa7306456c49efd919756df90425b85261916275571fbbf8f6e4df0`.
They reveal the private case class in the model input and do not pass the
current source-material check. No calls used either plan.

The pre-call amendment `AMENDMENT-0.1.1.md` removes the case-class labels,
aligns EAL source topology, varies option identifiers, removes a confounded
missing-link record, scores raw agent output first, and separates the private
role-evidence gate as an oracle-assisted diagnostic. It also prevents two
partially grounded analysts from combining their citations into a falsely
complete process chain and requires a finished pilot before the full schedule.
The twelve families and four case classes remain author-created synthetic
material. The generic candidate objection in each source is an authored
question, not an EAL host assessment or a true human bias attribution.

The amended `pilot-freeze-0.1.1.json.gz` has eight cases, 72 planned calls,
internal SHA-256
`ddff588b8b619397ad052fd2fae20b03012267b7a35dbccbd6325bd2d2fc3f72`,
and a conservative USD 1.5201 reservation under its USD 5 cap. The amended
`full-freeze-0.1.1.json.gz` has 48 cases, 432 planned calls, internal SHA-256
`28d1610056b3c68f12d2d4f73445096211cc505b60a11169288552e45163690e`,
and a USD 9.1531 reservation under its USD 25 cumulative cap. The archive
README records exact compressed and uncompressed file hashes. Both amended
plans decompressed and passed `run.load_freeze` against the 0.1.1 source and
parser at that revision, including 48/48 EAL/2 parse and static semantic
checks with zero diagnostics. PR #9 subsequently changed `src/eal`, so the
old material closure fails against current main. This establishes source
structure only; no host acquired the
synthetic process records or evaluated a person's cognition.

Thirteen offline tests pass. They exercise the amended request boundary,
source scaffold, option mapping, raw and gated scores, citation synthesis,
analyst-level errors, frozen schedule, ledger redaction and non-retry, pilot
completion, and concurrent ledger locks. The 48-case matrix still lacks paired
irrelevant-cue, fluency, material-evidence, valid-argument and prompt-boundary
controls. Stage B/C and independently adjudicated human cases are specified
future work, not findings from these zero-call plans.

## Pre-call amendment 0.1.2 on main `3b497d`

`AMENDMENT-0.1.2.md` records the source-code provenance change before any
paid call. It retains the 0.1.1 prompts, cases, response contract, scoring,
models, arms, seed and caps, while pinning the current grammar, every
`src/eal` Python module and both amendments. The new freeze declares
`protocol_version: "0.1.2"`; 0.1.0 and 0.1.1 archives retain their original
bytes and remain historical. The 48/48 generated EAL/2 sources again parsed
and passed static semantic validation with zero diagnostics against the
reconstructed current main. Thirteen offline tests passed. No EAL host
acquisition or paid OpenAI call occurred; model outcomes remain absent. The
unauthenticated four-second endpoint preflight again timed out before key
lookup, so the 0.1.2 schedule did not begin.

The new archive is
`benchmarks/results/2026-09-24-bias-agent-zero-call-0.1.2/`. Its
`pilot-freeze-0.1.2.json.gz` holds eight cases and 72 planned calls, internal
SHA-256 `67e651ecd2bc3a053689d3f32078267294f15b80ef3e9b5c7f699856232fa9e5`,
with a conservative USD 1.5201 reserve under the USD 5 cap. The
`full-freeze-0.1.2.json.gz` holds 48 cases and 432 planned calls, internal
SHA-256 `5109b7b7c6704723cd42b50aff2622d3e764c595f0b365b0d810ae647fcbb752`,
with a USD 9.1531 reserve under the USD 25 cumulative cap. Both compressed
members were decompressed and verified with `run.load_freeze` against current
materials; the archive README records their exact JSON and gzip hashes. The
72-call pilot is part of the full schedule only if it completes unchanged.
