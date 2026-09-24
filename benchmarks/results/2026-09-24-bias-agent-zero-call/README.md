# EAL/2 bias-agent zero-call archive

These are the exact frozen schedules produced on 24 September 2026 from
`benchmarks/experiments/bias-mechanisms/` against main revision
`b9177df83019691f6c7fd4f95cee5e4766b57111` plus the new study files.
The OpenAI endpoint was unreachable in this execution environment before key
lookup. No provider call, response, charge or response ledger exists. This
archive contains planned inputs, not experimental model outcomes.

| Member | Cases | Planned calls | Internal `freeze_sha256` | Compressed SHA-256 |
| --- | ---: | ---: | --- | --- |
| `pilot-freeze.json.gz` | 8 | 72 | `4623418bc80a5e9bdc4bce5154e4cb2656a3fdc88e945bcf553cbcf1158d75cd` | `88af6e7a3ccd0a4d6731352afc6fc30422a46383b87ed73fc73d1bf3a8863c98` |
| `full-freeze.json.gz` | 48 | 432 | `1684c165caa7306456c49efd919756df90425b85261916275571fbbf8f6e4df0` | `094d0839ceca5112c4e808df2e3d206bfd92288c4e42714bfb0bfe496f589218` |

The uncompressed JSON SHA-256 values are
`f21142ae01b1df8aa95c2f4a5cef6aaa162baa43855294556835d4f10845404a`
for the pilot and
`13f0185c71c5227356761a36b7275be86020c7d17994db9aa8530450ef98bec6`
for the full plan. The runner's internal digest covers canonical JSON fields
other than `freeze_sha256`; the file hash covers exact serialised bytes.

From the repository root, decompress each member to a protected local path,
then use `run.load_freeze` or the documented `execute` command. The runner
regenerates the expected calls and checks material hashes before sending a
request. The material set includes the analyser and study protocol. A source,
scorer or protocol edit invalidates these schedules. The pilot ledger can be
imported into the full schedule only when its requests are identical, as
verified by the runner. The study README gives the exact execution and
analysis commands, budgets and stop rules.
