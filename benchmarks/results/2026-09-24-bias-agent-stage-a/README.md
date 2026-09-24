# EAL/2 bias-agent Stage A developmental run

This archive retains the completed 24 September 2026 Stage A schedule under
pre-continuation amendment 0.1.2. All 432 assigned OpenAI Responses API calls
reached a terminal outcome: 72 pilot assignments and 360 dependent full-run
assignments. The first pilot outcome is the unchanged call retained in the
earlier stopped-run archive; its request ID and request hash matched the new
freeze, so it was imported and not retried.

The amendment was written after that first invalid answer had been inspected.
It changed only execution control: terminal failures stay in the denominator
and independent calls continue. It did not change requests, cases, prompts,
scoring, arms or ceilings. The completed run is therefore developmental and
not a prospectively untouched confirmation.

## Completion and cost

The pilot had 72 terminal outcomes, of which 24 passed response and reference
validation. The complete schedule had 432 terminal outcomes, of which 160
passed. There were 272 invalid outcomes, no unresolved pending call and no
outcome with missing configured cost. Returned identities were
`gpt-4.1-nano-2025-04-14`, `gpt-6-luna` and `gpt-6-sol` without within-entry
identity drift.

The configured uncached-rate estimate across all 432 calls is USD 2.4331466;
it is not an invoice and is below the USD 25 cumulative ceiling. Total serial
request latency recorded by the ledger is 3,686.6752 seconds. The most common
invalidity was a rival option placed in a closed evidence-ID field (145
diagnostics); 89 responses exceeded the 300-character rationale contract and
63 supplied an unknown defeater. These failures are measured system outcomes,
not omitted observations.

## Bounded descriptive results

Across these twelve author-created synthetic families, fully warranted counts
were 0/48 for nano direct and independent, 2/48 for Luna direct versus 0/48
for Luna independent, and 1/48 for Sol direct versus 2/48 for Sol independent.
The corresponding mean within-family paired differences (independent minus
direct) were 0, -0.0417 and 0.0208. The descriptive family-bootstrap intervals
in `full-report.json` include zero for every model. Raw strong false
attribution was zero in each reported cell, but low valid-answer rates and the
oracle-assisted gate preclude treating that as demonstrated safety. These
developmental synthetic results do not establish effects on people, EAL
notation benefits or general model rankings.

## Files and integrity

`COMMANDS.txt` records the exact execution sequence. Ledgers retain all
write-ahead and terminal events, redacted provider responses, identifiers,
usage, latency, validation diagnostics and their hash chains. They contain no
API credential.

| Member | SHA-256 |
| --- | --- |
| `COMMANDS.txt` | `4dd9defd4ea85a9e35b9bcc6488ceea07b64f37772bb2b78b4d379ac1a904bd6` |
| `pilot-freeze-0.1.2.json.gz` | `3d765968ea723a9cdb6a9b7091ebc627c5c3a8d46b386334cad831502e012daa` |
| `pilot-ledger.jsonl` | `991eabcc898c8b4f3293e7d3cf1410b5afc5f873d8d29da947f1ed8d0a8cf9da` |
| `pilot-report.json` | `71fc5f5089d4f94009ffeb8178f70299d8668d7eab6eab54c5dfe48c4f51a4a1` |
| `full-freeze-0.1.2.json.gz` | `07a12ed63f3e6ec600cc2d866fe702a6807fe91532f32177f7e544705064ecac` |
| `full-ledger.jsonl` | `dce6409ddbaa39367101eeacfcbd8449b7809f4cb23a3da1210f367999c9e294` |
| `full-report.json` | `ba2e9facc8585aa8179686cf26607306f19d00256734d395c1c26d277b078fd2` |

The pilot and full internal freeze digests are respectively
`71f160f0fcb28118180bb9b191e720cd95839dc40c44aec3cc4f8e523ea891a5`
and `5c814040ee79627d844d05752ce5684b5984b8d67c2e6c60e87a133dec390c8e`.
