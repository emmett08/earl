# Corrected model-requested route, 24 September 2026

These two **developmental, route-only** campaigns test a corrected second turn
after a model requests a bounded EAL assessment from a fixed candidate menu.
The host validates the request, supplies a checked claim packet and owns the
final status. The recipient must return one strict claim-answer JSON object.
This is text routing, not native MCP tool use or the parameterised family
retriever. The user's authorised provider calls completed; no calls were made
to produce these read-only archives.

| Archive (SHA-256) | Frozen cases | Valid host routes and consistent recipient answers before explanation review | Model calls | Input / output tokens | Configured-rate model cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| `route-v2-pilot-36.tar.gz` (`2edb91e478a0f3957e8cf564e9878df5d3df31613f3af250d11fdb6b51feae3d`) | 36 | 27 | 63 | 46,902 / 3,239 | US$0.0553942 |
| `route-v2-cohort-27.tar.gz` (`899b303b0887d78e8461028d1cbd39c3b311c1732d19a8cb63bf2fe97436941a`) | 27 | 24 | 51 | 37,009 / 2,627 | US$0.0422800 |
| **Total** | **63** | **51** | **114** | **83,911 / 5,866** | **US$0.0976742** |

Every scheduled attempt completed with zero retries, failed attempts or calls
of unknown usage. Output tokens include 1,220 reported Sol reasoning tokens;
cached input tokens were zero. The pilot freeze digest is
`78e859ece4e05dcffcc0594d12f39b08356087a3fa18e55cadf4463951db468d`;
the newer cohort digest is
`0aed399243f68d420eaa07ebcd063909e7d4899bdaf91ccfabb9ed2102de2640`.
Each archive holds the exact `freeze.json` and `ledger.json`, plus independent
read-only `audit.json`, stricter `analysis.v2.json` and a copy of the original
frozen `src/eal/server.py` under `frozen-source/`. The archives use fixed tar
metadata and gzip timestamp.

| Model | Pilot valid route / 12 | New cohort valid route / 9 | Combined valid recipient answer / 21 | Recipient or final false support | Configured-rate model cost, both cohorts | Per-case API seconds median / nearest-rank p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-4.1 nano | 3 | 6 | 9 | 0 | US$0.0027389 | 11.179 / 19.116 |
| GPT-6 Luna | 12 | 9 | 21 | 0 | US$0.0038713 | 18.507 / 41.590 |
| GPT-6 Sol, high reasoning | 12 | 9 | 21 | 0 | US$0.0910640 | 18.589 / 26.791 |

Nano's twelve other first turns were refused by the host: nine selected an
incorrect or unauthorised request and three were malformed. They are failed
route decisions, not safe negative answers. Every one of the 51 accepted
routes had a parseable recipient verdict agreeing with the checked final
status and a nonempty explanation. The host statuses matched the singly
authored reference in these 51 cases, including 17 adverse states; no
recipient status contradicted the host. This is **pre-review consistency**:
the explanations have not been independently adjudicated for faithfulness.

The two schedules reproduce the exact first-turn messages and reference
states of the 63 corresponding `skill_route` cases in the earlier
[`cross-model-live` archives](../2026-09-24-cross-model-live/README.md).
The old second turn retained a conflicting operation-request system message
and had 63/63 malformed final responses. The corrected route yielded 51/63
consistent answer objects, while nano still missed twelve first-turn routes.
The first-turn outputs are separate model samples, so this comparison
diagnoses the procedure; it is not a population estimate or a claim that the
model learned from the earlier run. The menu still prefixes the correct
artifact description, and all expected statuses come from synthetic,
singly authored cases. The equal checker matched the host on the frozen
states, without an independent masked oracle review.

The recorded per-case API-time sums are 580.123 and 498.055 seconds; the two
campaigns ran concurrently, so these are not elapsed wall times. The local
routed host assessment sums are approximately 1.118 and 0.875 seconds.
Configured-rate costs are estimates, not provider invoices. Source authoring,
independent review, acquisition, host compute, and semantic explanation
review costs were not measured; **total cost per faithful, correctly accepted
decision is unavailable**. The original source-tree `src/eal/server.py` was
changed only after both paid ledgers were terminal. Its frozen version was
recovered from [PR head `d78836b8`](https://github.com/emmett08/earl/blob/d78836b8fd769c236c646f263246e7728a488922/src/eal/server.py),
and the archived copy matches both freezes' SHA-256
`1a62c0e5e9f7e20c9817b4323f7f447fbfc9935592a4979b65ca0b783a209cd9`.
The remaining frozen material hashes match the current snapshot. The freeze
does not record dependency package versions, so full environment reproduction
requires separately pinning those versions.

To inspect without another provider call, extract either archive and run:

```bash
PYTHONPATH=src:scripts python scripts/audit_cross_model_ledger.py /path/to/extracted-run
PYTHONPATH=src:scripts python scripts/analyse_cross_model_campaign_v2.py /path/to/extracted-run
```

The archived reports were generated from copies of terminal ledgers. The
read-only forensic audit checks the frozen schedule, subcall prompts,
returned model identity, retained usage and configured-rate cost, routed
packet, recipient schema and final verdict. It does not review whether an
explanation faithfully traces the checked evidence.
