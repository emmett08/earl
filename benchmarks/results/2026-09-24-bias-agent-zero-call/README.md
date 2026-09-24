# EAL/2 bias-agent zero-call archive

The original two members below are the exact frozen schedules produced on 24 September 2026 from
`benchmarks/experiments/bias-mechanisms/` against main revision
`b9177df83019691f6c7fd4f95cee5e4766b57111` plus the new study files.
The OpenAI endpoint was unreachable in this execution environment before key
lookup. No provider call, response, charge or response ledger exists. This
archive contains planned inputs, not experimental model outcomes.

The original 0.1.0 input exposed the private variant name in public case IDs
and EAL scope and changed objection topology by variant. Those original
members remain unchanged for provenance and fail the amended runner's material
check. The pre-call `AMENDMENT-0.1.1.md` repairs the leakage and scoring
design; use only its separately named members below for any future run.

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

| Amended member | Cases | Planned calls | Internal `freeze_sha256` | Exact JSON SHA-256 | Compressed SHA-256 |
| --- | ---: | ---: | --- | --- | --- |
| `pilot-freeze-0.1.1.json.gz` | 8 | 72 | `ddff588b8b619397ad052fd2fae20b03012267b7a35dbccbd6325bd2d2fc3f72` | `2e4c05b7b5501f27a94e3730c734884f92f0261b7cd6ca0ff069e99c972edd9e` | `ce45635bc8ea952d4a15701bdacdf5894e9bacd60f9d5899b3c5b99c09a8ff36` |
| `full-freeze-0.1.1.json.gz` | 48 | 432 | `28d1610056b3c68f12d2d4f73445096211cc505b60a11169288552e45163690e` | `65568f8d771cd10cdafe53221c5cc6c4e06e761c9dc669284581347e1dddf6a3` | `47e9a09ec0a3a89c256bc950e9f998dbbb1fea96190c9f497632b2af437954f4` |

The amended plans reserve USD 1.5201 and USD 9.1531 respectively under the
unchanged USD 5 and USD 25 caps. They have passed `run.load_freeze` against
the amended source, including all 48 EAL parser and static semantic checks.

From the repository root, decompress each member to a protected local path,
then use `run.load_freeze` or the documented `execute` command. The runner
regenerates the expected calls and checks material hashes before sending a
request. The material set includes the analyser and study protocol. A source,
scorer, original protocol or 0.1.1 amendment edit invalidates the amended
schedules. The pilot ledger can be
imported into the full schedule only when its requests are identical, as
verified by the runner. The study README gives the exact execution and
analysis commands, budgets and stop rules.
