# EAL/2 bias-agent 0.1.2 zero-call archive

These schedules were regenerated on 24 September 2026 from main revision
beginning `3b497d`, after PR #9 changed `src/eal`. The base protocol and
pre-call amendments 0.1.1 and 0.1.2 define the unchanged developmental
design. The 0.1.0 and 0.1.1 archives remain in
`benchmarks/results/2026-09-24-bias-agent-zero-call/` with their original
bytes; they fail current material/version checks and were never used for paid
calls. This archive also has **zero provider calls and zero model outcomes**.

| Member | Cases | Planned calls | Internal `freeze_sha256` | Compressed SHA-256 |
| --- | ---: | ---: | --- | --- |
| `pilot-freeze-0.1.2.json.gz` | 8 | 72 | `67e651ecd2bc3a053689d3f32078267294f15b80ef3e9b5c7f699856232fa9e5` | `41004ca41280bce0c3e49838d7688497c8671768b413ebf2332281b0a081bd4c` |
| `full-freeze-0.1.2.json.gz` | 48 | 432 | `5109b7b7c6704723cd42b50aff2622d3e764c595f0b365b0d810ae647fcbb752` | `c051aa82bfff49bb69b41ce3380a43d51d731c14c1357abbc66069c64e556f07` |

Exact uncompressed JSON SHA-256 values are
`67e779146b05475760169d0efc73a45988190e4631d12175c49703f14787c9c6`
for the pilot and
`372c68e781d55de89832ed5ae739bc165072a4f3aaeac6288151441ef2c8f0f4`
for the full schedule. Gzip members have deterministic time fields. The
internal digest covers canonical plan fields other than `freeze_sha256`, while
the JSON hash covers exact serialised bytes.

Both members decompress and pass `run.load_freeze` against this current
reconstruction. The runner pins the grammar, all Python modules under
`src/eal`, case manifest, runner, analyser, base protocol and both amendments.
It statically parses and validates every generated EAL/2 source before
freezing. These checks do not collect synthetic process records through the
host or establish a cognitive mechanism. The conservative reserves are
USD 1.5201 for the 72-call pilot under its USD 5 cap and USD 9.1531 for the
432-call schedule under its USD 25 cumulative cap. No account charge was
observed or incurred for these archive operations.

Run the pilot before the full schedule. The full runner accepts only an
identical completed pilot ledger, validates every request hash and skips its
72 completed calls. Do not execute an earlier freeze with current source. A
future source, scorer or protocol edit requires a new versioned freeze.
