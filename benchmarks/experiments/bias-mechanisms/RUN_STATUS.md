# Run status — 24 September 2026 (UTC)

The 48 author-created EAL/2 sources (twelve mechanisms × four case classes)
all passed parse and static semantic validation against the reconstructed
exact-main grammar and `src/eal` implementation: **48/48**, zero diagnostics.
This checks source structure and references. No EAL host acquired the
synthetic process records or established a human cognitive mechanism.

Eight offline unit tests passed, covering the 72/432-call schedule and common
requests, freeze tampering, refusal/incomplete responses, role-gate limits,
ledger retention and redaction, missing usage, pending-call no-retry behaviour,
analysis and the exclusive execution lock. The no-key API preflight timed out after four
seconds (`<urlopen error timed out>`), so execution stopped before key lookup
and before a paid request. **Paid calls: 0. Model results: none.** No model or
topology can be ranked from this run.

The frozen pilot check contains eight cases and 72 planned calls, SHA-256
`4623418bc80a5e9bdc4bce5154e4cb2656a3fdc88e945bcf553cbcf1158d75cd`,
with a conservative $1.4933 reservation under the $5 cap. The full check
contains 48 cases and 432 planned calls, SHA-256
`1684c165caa7306456c49efd919756df90425b85261916275571fbbf8f6e4df0`,
with a conservative $8.9688 reservation under the $25 cumulative cap. The
exact frozen JSON files are archived as deterministic gzip members in
`benchmarks/results/2026-09-24-bias-agent-zero-call/`. Both decompress to plans
that pass `run.load_freeze` against the current source. No paid-call ledger
exists. After any source edit, regenerate freezes and record the new digests.
A pilot subset must retain request identity with its full schedule before import.

The present 48-case matrix balances some order features between families but
has no paired cue or presentation swap within a family. It cannot identify
susceptibility to irrelevant authority, order or author stance. Such
perturbations and independently adjudicated human cases are separate future
experiments. The author-labelled evidence gate can mechanically prevent strong
attribution on constructed negatives; report raw assertions, gate effects,
positive-case recall and coverage separately if paid calls become possible.
