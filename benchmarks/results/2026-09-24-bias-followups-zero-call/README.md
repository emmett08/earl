# Zero-call developmental follow-up schedules

These are new version 0.1.0 frozen request plans, not model observations.
They reuse the exposed 12 author-created Stage A families. The source and
protocol are under `benchmarks/experiments/bias-followups/`; that directory's
`RUN_STATUS.md` records the endpoint timeout before credential lookup. No
provider-response ledger exists.

| File | Cases | Calls | Internal SHA-256 | Exact JSON SHA-256 | Compressed SHA-256 | Conservative reserve |
|---|---:|---:|---|---|---|---:|
| `pilot-freeze.json.gz` | 8 | 128 | `1d543e38827ee95ec7e17535ff6c1777d60e9a967d7677d1be696d88de05b678` | `acad11a24c426074425d6604989d17e38060d9121f8ae55be126b16044c901d6` | `c90406f2e56b7264b11c75bea40026e75ea7718366155dad8ffd95d661e8183d` | US$2.0363 |
| `full-freeze.json.gz` | 48 | 768 | `1f790f06b2078a6244e9d7039b9a51f43e503df81dd71cc303e23d74dcdc68f2` | `253993de0702c2d220fc4161e2fabca96ab784e1783bb6396ae4103b154e7b39` | `04064b49c7c930bf0f95ed3fee2658398f0845df67d38b81d3b9c768e37dd870` | US$12.3126 |

The internal hash is the `freeze_sha256` field over the canonical JSON object
without that field. The exact JSON hash covers the decompressed UTF-8 file
including formatting and terminal newline; the compressed hash covers the
gzip file with deterministic timestamp zero. All 128 pilot request hashes
were checked against the full plan. The full plan includes the pilot calls;
they must not be charged twice. `load_freeze` verifies pinned material hashes,
reconstructs every request and rejects modified plan files.

For authorised execution, decompress the files to protected paths and follow
`benchmarks/experiments/bias-followups/README.md`. Keep API credentials,
response ledgers and any human trial material outside Git. The logged
endpoint timeout yielded zero model calls and zero actual provider charges.
