# Synthetic mechanism roots (developmental)

`build.py` emits 24 EAL/2 programmes, their parse-derived semantic JSON views,
and `manifest.json`. It does not change EAL/2 grammar. Six selected roots belong
to each of four mechanism families. Each root has a valid import and a partner
whose **measured numerical and test values stay fixed** while one acquisition,
identity, scope or temporal binding changes. `validate_fixtures.py` compares
48 brief-rule decisions with the current EAL runtime. Run from the repository root:

```sh
PYTHONPATH=src python benchmarks/experiments/mechanisms-960/fixtures/build.py
PYTHONPATH=src python benchmarks/experiments/mechanisms-960/fixtures/validate_fixtures.py
```

The 48 local status checks give 24 supported, 18 unsupported and six contested
labels; every EAL source validates and its committed JSON semantic view matches
both the parser and formatted display. The same 48 states also agree when EAL
executes the exact formatted display bytes. The brief-rule checker has separate Python evaluation code and does
not import the EAL parser or evaluator for its decisions. The same author wrote
the briefs, rules and sources, so this is a consistency check, **not** masked
independent adjudication or an independently commissioned equal host. Imported
JSON envelopes assert, rather than authenticate, tool origin and measurements.
An independent reference review and acquisition audit remain required before
claiming the original study's reviewed-root interpretation.

## Root genealogy and distinguishing question

| Root | Distinct task and intervention | Structural feature |
| --- | --- | --- |
| `rollout_admission` | Exact admitted image and rollout generation; reader-version forgery | One identity record |
| `relay_trip_window` | Protective-relay pulse and trip duration; expired commissioning trace | Freshness boundary |
| `chilled_valve_stroke` | Travel and seat-switch conjunction; changed plant | Context binding |
| `edge_config_quorum` | Both named edge zones acknowledge revision; second reader-version forgery | Two-record conjunction |
| `archive_restore_identity` | Separate approved-digest and restore reports for A72 plus duration; wrong restore object | Two-record provenance binding |
| `air_handler_flow` | Operating-point intake flow; point changes with flow held fixed | Point binding |
| `bearing_vibration_rms` | Four signed motor samples and zero-origin RMS; wrong run | Installed RMS contract |
| `sump_pump_trial` | Randomised flow difference; wrong reader version | Causal difference of means |
| `queue_ack_lower_bound` | Wilson lower bound for 397 of 400 acknowledgements; wrong subject | Inductive interval |
| `dryer_intervention` | Dryer-heater intervention in an affine model; stale model | Model-conditional counterfactual |
| `inverter_fault_posterior` | Phase-alert posterior from two faults; changed method version | Finite abduction |
| `fixture_feature_match` | Exact 3/4 fixture-feature match; wrong candidate | Quantified analogy |
| `fuel_particle_nondetection` | Calibrated strict-bound non-detection; wrong trace scope | Complete finite coverage |
| `chiller_flow_counterexample` | Observed flow excursion in L/s with incomplete coverage; wrong reader | Positive breach witness |
| `storage_error_nondetection` | Inclusive block-error bound; stale trace | Calibrated finite non-detection |
| `crane_speed_counterexample` | Equality at a strict crane speed threshold in m/s; wrong crane | Boundary counterexample |
| `reactor_alarm_nondetection` | Fifteen-second concentration coverage; changed episode | Detector and context binding |
| `robot_axis_displacement_counterexample` | Axis displacement breach in mm; interval shortened around same samples | Typed validity interval |
| `packet_loss_generator` | Alert defeated by independent generator-origin diagnosis; wrong origin | Argument attack and premise-backed defence |
| `laser_calibration_defence` | Overwidth report defeated by optics audit; stale audit | Argument attack and fresh defence |
| `database_lease_defence` | Renewal timeout challenged at the reasoning step; wrong diagnosis reader | Reasoning attack and defence |
| `conveyor_jam_challenge` | Jam alarm attacks throughput claim; wrong event | Claim attack; unused diagnosis record |
| `water_loop_pressure_challenge` | Pressure-collapse attack on test reasoning; wrong plant | Reasoning attack without defence |
| `firmware_watchdog_challenge` | Watchdog reset attacks bounded boot run; expired reset | Argument attack without defence |

The prior public vibration, pressure, temporal and failover examples were
inspected while these questions were written; `manifest.json` records each
nearest precedent. Several tasks intentionally share a family rule and source
shape. Different names or thresholds alone cannot establish task independence;
root-level paired analysis must retain family clustering and the selected-corpus
scope. The three unsupported statuses for absent, forged and malformed inputs
should never be interpreted as proof that the engineering proposition is false.

`valid_records` and `invalid_records` are complete synthetic file-import
envelopes keyed by evidence ID. `full_status` carries claim, source digest,
context, assessment time and record digest. `invalid_verdict` repeats the
attractive former valid label with forged source/time/record identity; the host
must reject it before accepting the label. `eligibility_memo` describes record
checks without a claim status. `method_result` reports a calculation and query
for registered numerical methods, or an explicit authored marker for
`structured/1`. The deliberately wrong proposal is `out_of_scope` for every
root, distinct from valid, invalid and absent-record labels. A result packet
still cannot attest its physical inputs.
