# Cloud Browser evidence captures

These four JPEGs were captured in Cloud Browser while testing the [ASPIC visualiser PR #3](https://github.com/emmett08/aspic_visualisation/pull/3) at commit `606322136e2b960104d965c1b2ac688cb5b9478f`. They are copies of the tested UI captures in that repository. The original v1 graph remains historical; its fresh `/2` re-export classifies predicate mismatches without rewriting old observations.

| Capture | What the tested UI shows | SHA-256 |
| --- | --- | --- |
| [exact-undercut.jpg](exact-undercut.jpg) | A23 attacks the exact A21 `future_debt_reduced` subargument. | `9fef36f32b7d570e5b77973d009f4736a29d521d85dd58cb37651f902e20e51d` |
| [predicate-not-met.jpg](predicate-not-met.jpg) | Both dispatch-failure declarations had valid observations whose `passed == false` predicates were not met. | `20bb3881755cd3cf6e7a6b688c040adc9bc0480fada6e1ee886b97253e2f1275` |
| [synthetic-release-undercut.jpg](synthetic-release-undercut.jpg) | In a simulated refund case, A10 undercuts provisional completion A9; the exact target is inspected. | `25c531e9e9efc14b3cc6b69a5f89c73bfeb87216d93b1873c752cddaced6bfa8` |
| [synthetic-release-predicate.jpg](synthetic-release-predicate.jpg) | The simulated gate’s typed evidence panel; no live payment or AI coding result is implied. | `d25681c4ed66a326cd6b8ebb1b9967edacb3db87c52d9d3e90e6c0455aeaa239` |

The visualiser's original capture provenance and import hashes are in its [`docs/evidence-outcomes/README.md`](https://github.com/emmett08/aspic_visualisation/blob/606322136e2b960104d965c1b2ac688cb5b9478f/docs/evidence-outcomes/README.md). The four copies above are included in the EARL PR so that the paper's evidence can be reviewed with the argument and apparatus.
