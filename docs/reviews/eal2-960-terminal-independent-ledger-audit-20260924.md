# Independent AI audit of the terminal 960-slot execution

Date: 2026-09-24. Reviewer: separate AI agent, read-only with respect to the four paid ledgers, frozen inputs, composite and archive. This review recomputed identities, classifications and configured-rate cost without importing the campaign runner or consolidator. It is not human adjudication of the synthetic reference.

## Exact inputs and disposition

| Segment | Attempt indexes | Terminal ledger SHA-256 | Completed | Malformed | Failed |
| --- | ---: | --- | ---: | ---: | ---: |
| Original | 0–131 | `9cb880af12042dfc953775cf430d9cfcca8217c3d439790e725716c2418e5c66` | 131 | 0 | 1 |
| A2 | 132–467 | `4f5714c777f9ec4cedaf84e2dc06981a0c2273be0e407c963c2cb446781ce550` | 330 | 2 | 4 |
| A3 | 468–725 | `ce9e5a298c223df00acefb5b3b6e14cb204b84679d1cb146b264136e0e214129` | 249 | 1 | 8 |
| A4 | 726–959 | `7581405c5c8007fa1d939acdcbccd99f139285758d3ee9ea86e650842ba8346e` | 232 | 1 | 1 |
| Total | 0–959 | | **942** | **4** | **14** |

All 960 assignment indexes and case IDs occur exactly once. Each row's case ID and prompt SHA-256 match the original frozen schedule; continuation freeze prompt hashes match the same slots. No failed slot was retried. The 960 response classifications recompute from the frozen available-information and full-information references, including **130 false supports** against the available-information reference, 460 available-information exact statuses and 505 full-information agreements. The 11 response-less failed attempts with unknown actual charges are indexes `129, 138, 142, 377, 474, 479, 567, 629, 685, 698, 724`. Three other failed attempts carried metered responses.

Known configured-rate model cost for the 960 assigned decisions independently sums to **$0.2840583**. The three separate probes cost **$0.0000069** and are outside the 960 decisions. The frozen maximum-cost reserves for the 11 response-less attempts sum to **$0.0301785**; these are budget reservations, not measured charges. Known costs plus this reserve remain under the $5 configured cap. No provider invoice or complete authoring/review labour accounting was available, so all-in cost per faithfully correct accepted decision cannot be computed.

## Composite and raw archive

The analysis-only composite ledger's 960 parsed rows equal the four source ledgers concatenated in order. Its `composition.json` names 12 exact source SHA-256 values, all of which match the retained source files. The composite ledger is SHA-256 `fad5c932e9cd2aab590ff5d1414e1159eb9d84b6ab45e2dd0c952a1a3e978c4f`, composition is `924a418b5b8ad06ed3ffe64744df3537ae2428112bb0fe10d4d180281cbfa9ed`, and analysis is `eea77b0eb8e2d36ec89f4532748a6d266b2b71465f7216c9f26fa7cdb7e06cf0`. The composite freeze is byte-identical to the original frozen schedule and is omitted as a duplicate inside the archive.

`benchmarks/results/eal2-960-campaign-20260924.tar.gz` is **9,657,787 bytes**, SHA-256 `6c55806f2e27cde1d4f2e7bc55d11893afc14e95309fed0578f7c10f2ba58900`. Its adjacent manifest is SHA-256 `27987802ba3ffe2c0a6a6105a0fa2fe62735e3a571933ac042a7c4753251e8e5`. The archive has exactly 90 listed payload files plus an identical copy of the adjacent manifest. Every member's uncompressed size and SHA-256 matches the manifest; the four raw ledgers, three probes, A4 review attestation and composite analysis match the source files exactly. Member names are unique and stay within the archive. No attempt or failure record was omitted.

This is a developmental synthetic schedule with author-specified statuses and a separate but same-author Python comparison. The checks establish retention, frozen identity and internal accounting, not physical truth or an EAL-specific causal advantage.
