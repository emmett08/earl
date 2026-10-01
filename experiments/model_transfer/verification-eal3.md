Historical package 3.0.0 verification. Current composition checks are in [the 3.1.0 record](verification-eal31.md).

# EAL/3 verification

Package **3.0.0**, source **EAL/3**, model-transfer protocol **7.0.0**,
handover protocol **2.0.0**. Maintained source generators, the authoring demo,
discovery, current plans and documentation use EAL/3. New model-transfer collection
requires `source_language: EAL/3`; its execution contract pins source language,
implementation, dependencies and plan identity. Current plans also identify
protocol 7.0.0. Earlier experiments retain their own headers, results and hashes.

[Machine-readable verification](validation/eal3-language.json) records these checks.

| Check | Observed result |
|---|---|
| Complete repository check | `make check`: 1,029 tests passed, ANTLR 4.13.2 generated sources verified, validator self-test and both scientific protocols passed, CLI/MCP example passed. |
| Version promotion | Five whole assessments differ only in source hash, language label and dialectic description; all other fields, including diagnostics, are equal. Version rejection and new-run guards are tested. |
| Principal scripted rehearsal, isolated directory | 384 sequences, 4,224 sessions, 6,528 synthetic attempts and 4,224 annotated answers; 83 calibration checks. Raw rows unchanged and resources reconstructed. |
| Stored assessment references | All 192 isolated principal stores passed SQLite integrity checks; all 4,224 referenced collection/assessment records were present. |
| Component diagnostic rehearsal | 56 sessions, 66 synthetic attempts, 27 calibration checks; annotation and reconstruction passed. |
| Cadence diagnostic rehearsal | 36 sessions, 42 synthetic attempts, 23 calibration checks; annotation and reconstruction passed. |
| Complete cadence calibration | 215 checks passed across the 18 cases and eleven snapshots. |
| Developer handover | Maintained synthetic demo and complete paired workflow exercised by the repository tests using EAL/3 source. |
| Distribution | 3.0.0 wheel and source archive built. |

The first principal rehearsal in the browser-shared workspace retained a
missing-collection failure: 4,223 submitted answers and one failed session. A
subsequent storage check found 392 absent referenced records and one malformed
SQLite store. Accounting and annotation checks alone did not detect that loss.
That run is not used as evidence of intact observation storage. Its summary is
retained alongside the fresh isolated run; no earlier request or failed session
was replayed in place. The cause is unconfirmed. The isolated run had zero absent
references and no database integrity errors. Keep mutable SQLite experiment
stores in an isolated directory with consistent filesystem semantics when also
using a browser preview.

Reproduce the current software checks from the repository root:

```sh
make check
make build
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/plan.json --output /tmp/eal3-principal
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/diagnostic-plan.json --output /tmp/eal3-diagnostic
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/cadence-diagnostic-plan.json --output /tmp/eal3-cadence-diagnostic
python -m experiments.model_transfer.runner --plan experiments/model_transfer/cadence-plan.json --calibrate-only --output /tmp/eal3-cadence-calibration
```

Use fresh output paths. No paid model requests were made. Scripted answers, usage
and costs are synthetic; these checks establish no EAL/3 model-performance or
human-authoring benefit. Retained statistical-method checks remain labelled by
their original implementation in [the EAL/2 record](verification.md).
