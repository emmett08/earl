# Independent AI audit of the fresh 800-assignment A3 execution

Date: 2026-09-24. Reviewer: separate AI agent, read-only with respect to the paid freeze, request ledger, analysis and archive. This is an accounting and identity audit, not human adjudication of synthetic truth or explanation faithfulness. The earlier A1/A2/C1 stopped diagnostics are separate and are not pooled into A3.

The exact A3 freeze is SHA-256 `c917a410aad0bdeefda4c2320b374a23cde0d0759057062bb986265a41f920cc` (internal digest `6adcab0e1d342990e81dca3e414799285e4bbf161097d01570dc7f184b6dbfbf`). The terminal ledger is SHA-256 `cdfc6f7401d56cf7ae28506b9e425a5c81907b6dbd71f968287f9fc20eecac82`. Its 800 distinct assigned cases exactly cover the 384 fixed, 96 linked author and 320 recipient slots; every assigned slot completed. The 32 author groups each have three completed turns, and their revision messages include the exact previous raw model response. Each of the 320 recipient messages ends with the exact serialized, claim-bound host packet from its ledger row.

**There were 804 provider requests for 800 assigned slots.** Four first requests returned response-less HTTP 500 at slots `deployment-0021`, `deployment-0023`, `deployment-0028` and `deployment-0367`. Each has one retained retry whose prompt SHA-256 and native-operation SHA-256 are identical to the first request, and each retry completed. There were 800 completed requests, four failed requests and no failed assigned slot. All 96 native-request slots carry the expected root/claim/scope operation-schema digest and recorded accepted native requests. Every request's response model matches the frozen provider identity or its declared snapshot alias; every metered cost recomputes from recorded input, cached-input and output tokens using the frozen rates.

| Observed endpoint | Count |
| --- | ---: |
| Exact fixed statuses | 290/384 |
| Direct fixed exact statuses | 50/144 |
| Host-owned fixed exact statuses | 144/144 |
| Native-request fixed exact statuses | 96/96 |
| Recipient packets unavailable after authored candidate validation | 320/320 |
| Recipient exact statuses | 0/320 |
| False support in the retained accepted-status endpoint | 0 |

Host-owned and native statuses are fixed by the host's checked packet, so their exact counts do not measure independent recipient discovery. The 320 unavailable packets record failed candidate syntax, schema or binding, rather than a supported decision; they remain in the assigned denominator.

The separately sealed post-call AI reviews found all 32 final authored products nonexecutable and unfaithful under their source rubric. The predeclared explanation frame contains 48 outputs, 16 each from fixed direct, fixed host-owned and authored recipient exposures; its selection pins the exact terminal ledger SHA-256 and earlier predeclaration SHA-256 `7e03bee4e828b109b175966c9d442f4e7954f3fcb5a4d7c40574cc7476fd7127`. Two AI reviewers agreed on all 48 ratings and both selected four faithful explanations (`E11`, `E17`, `E23`, `E27`); independent linkage inspection places all four in fixed direct calls. The explanation comparison is SHA-256 `c4313680bd56eddba4787f911073ed9fab20bacc11ec07029bc67cd2a878b5cb`. These unmasked AI reviews are exploratory, and the four ratings do not establish end-to-end accepted, independently adjudicated engineering decisions.

Known configured-rate model cost for all 804 requests is **$1.16650454**. The frozen maximum-cost reservations for the four response-less failed requests sum to **$0.1456512**; actual charges for those requests are unknown. The known cost plus reserve is below the $45 configured cap. Neither provider invoices nor complete acquisition, host, human authoring and review effort is reconciled. The all-in cost per faithfully correct accepted decision remains unavailable.

`benchmarks/results/2026-09-24-deployment-800-a3-developmental/a3-terminal.tar.gz` is **798,033 bytes**, SHA-256 `eabba61eae35a747fbb1fb209b06355ad12ad76126a4e3824b79b9706eab02a9`. Its three members are exactly the source freeze, terminal ledger and analysis bytes. The analysis file is SHA-256 `c546a4b22037c72117b8310ddcfa9537cc0dd99ca609a31898fd2ac5bfec5cd2`; its 800 slots, 804 requests, four retries, token totals, unknown reserve, known configured-rate cost and status counts agree with the independent ledger calculation. Raw failed requests and both successful retries are retained inside the terminal ledger.
