# Handover study verification

Recorded 2026-09-28T13:12:11.576475+00:00 against the implementation in
this commit. These are software and simulation checks, not developer or model
performance observations.

| Check | Command | Observed result |
| --- | --- | --- |
| Repository checks | `make check` | 668 passed, 1 skipped in 38.81s; generated parser verified; synthetic API example passed through CLI and MCP. |
| Focused study checks | `python3 -m pytest tests/test_transfer_study.py tests/test_transfer_inference.py -q` | 20 passed. |
| Package | `make build` | Source distribution and wheel built for 2.14.0. |
| Plan | `python3 -m experiments.transfer_study check-plan experiments/transfer_study/demo/plan.json` | Version 2 plan accepted; one synthetic case and two fixture model IDs. |
| Protocol structure | Updated skill's `scripts/validate_investigation.py experiments/transfer_study/protocol.json` | VALID; status specified; 0 errors, 0 warnings. |
| Whitespace | `git diff --check` | Clean. |

The focused checks exercise assignment replay, illegal transfer identities,
model aliases, shared confirmation developers, fresh conversations, retained
handover and seed integrity, reuse and expiry, failed-call retention and budgets,
late correct answers, nonresponse and withdrawal, scorer independence and
adjudication, and invalid measurements overriding a favourable interval.
The estimator checks include exact enumeration of all 256 eight-pair null
assignments, a known positive effect and worst-case missingness.

## Statistical calibration

```sh
python3 -m experiments.transfer_study.calibration \
  --output experiments/transfer_study/verification/calibration.json
```

The retained [calibration record](calibration.json) contains 5,000 replications
of 120 pairs per scenario, seed 20260928, a 0.10 practical threshold and all
predeclared tolerance checks. Null, positive, adverse, within-pair dependent
and informative-missingness scenarios each covered the true effect in all
5,000 replications. Their marginal 95% Monte Carlo coverage bounds are
[0.98079, 1]. The known +0.60 effect produced a meaningful-benefit decision in
all replications; zero events under the null correspond to Monte Carlo bounds
[0, 0.01921], not a zero error probability. Declared cross-case dependence
withheld every interval. All prespecified checks passed.

These conservative results establish behaviour only in the stated simulation
scenarios. Human reference/scorer validity, exclusive use of recorded tools,
no interference and performance on real tasks remain unverified. Protocol
status is **specified** and implementation status **implemented** because
human scoring calibration is still planned. Structural validation does not
establish scientific adequacy or empirical benefit.
