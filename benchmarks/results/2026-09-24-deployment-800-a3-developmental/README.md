# Fresh A3 800-assignment developmental deployment study

The separately frozen A3 run reached its terminal `complete` state on 24
September 2026. All **800 assigned slots completed**: 384 fixed source, 96
linked author turns and 320 isolated recipients. Four no-response HTTP 500
first requests used the predeclared single identical retry, so the experiment
made **804 actual API requests**. Both requests, latency and conservative
unknown-billing reserves remain in the ledger. No final assigned slot failed.
The A1, A2 and C1 stopped diagnostics are archived separately and are not
pooled into the A3 outcome denominators.

| A3 exposure | Assigned/completed | Actual requests | Exact reference status | Strict false support | Configured model US$ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed direct prompt | 144/144 | 145 | 50/144 | 0 | 0.45068700 |
| Fixed host owned packet | 144/144 | 146 | 144/144 | 0 | 0.11696200 |
| Fixed native function request | 96/96 | 97 | 96/96 | 0 | 0.06334020 |
| Linked author turns | 96/96 | 96 | Not a status task | Not applicable | 0.42032954 |
| Recipients of authored candidates | 320/320 | 320 | 0/320 accepted | 0 | 0.11518580 |
| **Total** | **800/800** | **804** | **290 exact accepted statuses** | **0 under strict parser** | **1.16650454** |

Fixed direct exact status by recipient model: Luna **2/48**, GPT-4.1 nano
**2/48**, Sol **46/48**. Host status is supplied by the checked adapter in
the host owned and native arms; those 240 exact statuses are an integrity check
of host delivery, not independent model reasoning. All 96 native calls yielded
the expected function request. Strict false support counts only an accepted
parsed `supported` status against a non-supported reference. It does not score
free-form misleading language in malformed responses. Median assigned-slot
latency was 9.794 s direct, 9.782 s host owned, 9.226 s native, 15.726 s
author and 8.925 s authored recipient; these are observed provider-inclusive
durations, not a projected production latency.

All 32 author chains reached their third turn. Turn 1 changed the authored
source in 32/32 groups and turn 2 in 21/32. Two independent unmasked AI reviews
agreed that **32/32 final sources violate the executable source contract**;
their readable-intent criterion disagreements remain recorded. All 320 actual
recipient host packets consequently said `unavailable`, so none yielded an
accepted status. Ninety-three recipient responses matched the requested JSON
shape and 227 did not, but every recipient `accepted_status` is null. Zero
accepted recipients must not be described as 320 wrong status labels. The
predeclared 48-explanation sample was reviewed independently by two AI agents,
separate from the source review and the exact-status counts. Both rated **4/48
faithful and 44/48 unfaithful**, with the same four IDs (E11, E17, E23, E27).
All four were sampled fixed direct Sol responses; 0/16 sampled checked-host
responses and 0/16 authored-recipient responses were faithful. Seventeen of
48 sampled responses met the strict recipient JSON shape. There were no
overall rating disagreements, but the reviewers differed on some individual
scope, status, evidence, objection and qualification criteria; the criterion
disagreements remain unadjudicated. The 48 predeclared items and actual prompts
can reveal treatment and do not establish a full-population fidelity rate.
Two separate host-packet supplements agreed that all 96 root/state replays
from the 32 final authored sources returned `unavailable` and supplied no
accepted domain status.

Reported usage for A3 is 968,533 input tokens, of which 45,808 were cached,
and 112,900 output tokens; the adapter reports zero reasoning tokens. The
configured-rate model charge of US$1.16650454 plus US$0.14565120 reserved for
the four no-usage first requests yields US$1.31215574 conservatively accounted
for A3. The reserve is not an invoice; unknown actual charges and cache-write
premiums may differ. A3 author calls alone account for US$0.42032954 in the
configured charge. Earlier diagnostics have separately reported known model
charges of US$0.0216019 (A1), US$0.1793467 (A2) and US$0.5556279 (C1),
with unknown failed-call charges; three successful capability probes total
US$0.0011817 at configured rates. Initial synthetic fixture authoring, AI and
human review time, acquisition costs, host compute and reconciled provider
billing were not measured. Thus **all-in cost per correct accepted decision is
unavailable**; dividing the A3 model charge by its 290 exact statuses would
mix host supplied statuses with missing source/explanation qualification.

The study used eight synthetic domain variants sharing one fixture generator,
not independent field deployments. JSON records assert acquisition and do not
authenticate cluster or physical truth. The historical protocol's Stage 1
arithmetic specifies a 768-call full cross while reporting 384; A3 uses a
reviewed 384-call balanced incomplete amendment and cannot estimate the
original full within-block format/instruction interaction. No grammar factor
was included. The original confirmatory 800-call protocol remains unrun.

## Frozen material and independent checks

- `a3-terminal.tar.gz` contains the exact freeze, terminal ledger and read-only
  analysis. SHA256 `eabba61eae35a747fbb1fb209b06355ad12ad76126a4e3824b79b9706eab02a9`.
- Freeze file SHA256 `c917a410aad0bdeefda4c2320b374a23cde0d0759057062bb986265a41f920cc`;
  internal digest `6adcab0e1d342990e81dca3e414799285e4bbf161097d01570dc7f184b6dbfbf`.
  Terminal ledger SHA256 `cdfc6f7401d56cf7ae28506b9e425a5c81907b6dbd71f968287f9fc20eecac82`;
  analysis SHA256 `c546a4b22037c72117b8310ddcfa9537cc0dd99ca609a31898fd2ac5bfec5cd2`.
- `a3-postcall-review-frame.tar.gz` contains all 32 final authored products,
  48 predeclared explanation slots, the private arm linkage and selection
  hashes. SHA256 `642e167b60e1cc59ca2d8f49e13a67b7f80c1a8b5c7320ac8a0d69c9d6c937b0`.
  The separate reviewer copies are byte-identical; actual prompts may reveal
  exposure. Failed/malformed slots remain in the frame.
- `a3-ai-review-records.tar.gz` contains both independently sealed AI author
  source reviews, both author host-packet supplements, both explanation
  reviews, and the three disagreement records. SHA256
  `0054a5394f04dad072e6aca39fd8a0404009ae6513cdda5bbee80fe0ad4fab31`.
  Explanation comparison SHA256
  `c4313680bd56eddba4787f911073ed9fab20bacc11ec07029bc67cd2a878b5cb`;
  host supplement comparison SHA256
  `c3c3c9c41a6f0b8b76b45564ffdc74c0a736b5343c9dbaf6e3e7410dc80cd4dd`.
- The exact A3 runner SHA256 is
  `ec9afdb597022230e839290f9cf0e566acf3724057d6e98098861f9667e9f182`,
  plan `b751ff58bd72e500531729e7449f587c95da087263a1a32ca71801495f72b301`,
  post-call protocol `fbf031ae9e4699a50240497e43b51c811ed91970a5057087513cd9d429933a11`.
  Its independent preflight review is
  `docs/reviews/eal2-800-a3-fresh-run-ai-review-20260924.md`.
- The two independently sealed author-source reviews have SHA256
  `69d7505189af6f055a5bfe56edf9909f353b0cf7b6cb19be8142b6a35724ee4f`
  and `286604caa52fd99b7220e2e159d6c43444126bba7ccf3e653e2a425b9fc93419`;
  `docs/reviews/deployment-800-a3-author-review-comparison.json` preserves
  their criterion disagreements. Their common rating is unfaithful for all 32.

Reanalyse without contacting the provider:

```sh
mkdir -p /tmp/eal2-deployment-800-a3
tar -xzf benchmarks/results/2026-09-24-deployment-800-a3-developmental/a3-terminal.tar.gz -C /tmp/eal2-deployment-800-a3
PYTHONPATH=src:. python benchmarks/experiments/deployment-800/analyse_a3.py /tmp/eal2-deployment-800-a3
```
