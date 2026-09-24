# Brief-level reference decisions for the synthetic live pilot

These finite decisions were specified from ordinary task rules independently of
EAL's parser and evaluator. `reference_oracle.py` implements the brief-level
rules on the submitted JSON values. `validate_fixtures.py` compares those
outputs to the retained manifest and the EAL/2 interpreter. A second masked
review of source fidelity has **not** been completed. This is a developmental
feasibility block, not a confirmatory sample from engineering practice.

| Root | Initial | Adverse | Later state | Brief-level reason |
|---|---|---|---|---|
| AH-73 direction | Supported | Unsupported | Supported | The intermediate pass belongs to AH-74; the later AH-73 repeat again matches the fixed question. |
| Vent controller | Supported | Unsupported | Supported | At drive five, `1 + gain × 5` gives 6, then 11, then 7 under the three submitted models. The calculation does not validate any model. |
| DX-14 dosing | Supported | Contested | Supported | The current C-88 assumption is challenged by an offset-drift alert; a separate reference addresses that alert in the final state. |
| HL-5 preconditions | Supported | Unsupported | Supported | The adverse record reports four checks and completion but repeats J3 and omits J4. The repeat explicitly reports clear results for J1–J4. |

The four roots target distinct operations: exact equipment identity, a
counterfactual calculation in a changing affine model, a challenge to an
assumption with an independently sourced response, and a bounded negative
finding that a dependent decision cannot infer from a reported count with a
duplicated connector identity.
They remain selected,
synthetic tasks. The `expected` statuses are read from the manifest for
scoring and must never be passed into model prompts.
