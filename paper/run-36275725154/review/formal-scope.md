# Mathematical and executable verification scope

The manuscript's only proved mathematical step is a finite order-statistic
identity. For (n>0), let (k=\lceil 0.95n\rceil). Sorting the (n) attempted
latencies gives (t_{(k)}\le L) exactly when at least (k) of those latencies
satisfy (t_i\le L). The forward direction follows because the first (k)
sorted observations do so; the reverse follows because the (k)th smallest
must then be at most (L). Ties and any finite (L) do not change this
equivalence. The statement is mathematical; the Python implementations are
covered by independent-source crosschecks and tests, not a mechanised proof.

| Proposed obligation | Disposition | Reason |
| --- | --- | --- |
| Order-statistic/count equivalence | Hand proof in the manuscript and above | Elementary exact finite-set lemma, with explicit (n>0) domain. |
| Collector and independent oracle compute the same threshold | Tested-only | The workflow crosschecks raw rows; no Lean refinement proof of Python, parsing and data acquisition exists. |
| Archive parsing and paired counts | Tested-only | The digest-bound audit checks all 1,440 identities, 36 cell summaries and 30 paired summaries; a checksum is not a proof of data truth. |
| Engineering validity of the threshold and case selection | Empirical/contextual | Formal logic cannot settle whether (200\,\mathrm{ms}), 1% errors and 100 attempts fit an operational service. |
| EAL notation or checker causes a population improvement | Not established | The development design bundles interventions and lacks held-out sampling and repeated sessions. |

The pseudocode states integrity obligations for a reproducible analysis; it
does not claim program verification. This bounded formal scope makes the
ordinary deterministic checker and model-authored final status separate objects.
