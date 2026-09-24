# Prospective synthetic cohort: brief-level reference decisions

This selected developmental cohort consists of three new engineering task roots
and three consecutive evidence revisions per root. It is separate from the
four-root `artifact-live-pilot`, whose frozen inputs and measured outcomes remain
historical evidence. The nine expected outcomes below were fixed from the
ordinary task rules before any new model response. `reference_oracle.py` reads
the JSON acquisition envelopes and applies those rules without parsing EAL/2.
`validate_fixtures.py` tests agreement with the EAL/2 interpreter; agreement
does not establish the truth of a self-reported acquisition or the physical
validity of an authored rationale.

| Root | First | Adverse revision | Later revision | Brief-level decision |
| --- | --- | --- | --- | --- |
| PX-42 stage provenance | supported | unsupported | supported | The pinned build and staged artifact digests first match, then differ, then match in a fresh stage record. |
| TC-9 thermal soak | supported | unsupported | supported | The qualifying log becomes older than the brief's 15-minute limit, then a fresh qualifying repeat is supplied. |
| NS-9 failover | supported | contested | supported | A current switch-buffer alert challenges the matching test; a separate packet trace attributes that alert to the test generator. |

The test's claims concern *the submitted records under the stipulated task
rules*. A `signature_verified` or `pull_verified` flag is a value returned by a
synthetic reader, not independent authentication of a real deployment. The
NS-9 answer is an authored defeasible response to a specific alert, not a
general proof that the network path is healthy. The tasks are intentionally
small, selected, and synthetic, and their expected statuses have **not** been
masked and adjudicated by two independent human reviewers. This cohort is fit
for developmental integration and discrepancy analysis. A confirmatory live
campaign must first obtain and retain separate human source-fidelity review,
freeze all arms and prompts, and validate an equal-capability comparator.

For each root the sampling unit is the root. The three revisions are repeated
observations of that root; nine state scores are not nine independent tasks.
The exact statuses and rationales are scoring data and must never be inserted
into prompts, retrieved snippets, skill content or checked result packets.
