# Prospective runner v1

This is the executable harness for [`../study-v1/plan.json`](../study-v1/plan.json), study `INV-EAL-CI-001`. The plan is `specified_not_ready`. No reviewed case, signer roster, ready execution plan, model matrix, run ledger or efficacy result is included. The worked workflow in `examples/workflow-gate/` is a demonstration and must not be reused as a held-out case.

## Assignment and intervention

The unit is a reviewed case × pinned model snapshot × repetition. The runner reserves **one durable attempt for each of P, T, J and E before the first model call**, randomises order from the frozen seed and never reuses an assignment ID. An interrupted start remains in the denominator. The ledger is append-only, hash-linked JSONL, private mode `0600`; it detects edits, but an independent storage copy is needed to detect wholesale replacement.

Each arm gets the same neutral task, cut, case-specific exact tool input allowlist, two model calls, finite token/time/cost ceilings and a fresh provider session. In call one, P/T select read-only calls; E authors EAL/2 and J authors typed JSON. P/T run the selected command through the reviewed EAL tool registry. E/J invoke the **actual MCP stdio server** with `eal_describe` before authoring and `eal_validate`, `eal_collect`, `eal_reason` and `eal_explain` after authoring. Call two communicates the decision after evidence or the checked packet. E/J display the host-owned status even if the model's final prose disagrees; the disagreement is retained for independent scoring. Tool failures, invalid source, wrong family, missing packets and provider failures remain failed assigned attempts.

J uses `eal2-ci-json-frontend/1`: a strict typed JSON spelling of direct EAL/2 declarations. It compiles into EAL/2 source, checks a parse–format–parse semantic round trip, then uses the **same** MCP checker and method registry as E. This version excludes EAL patterns and applications **for both E and J**. The initial prompt gives E the current language discovery contract, and J that contract plus the JSON schema and a generic example. Every model prompt, contract digest, model response, collected record, MCP operation and host result is retained in the ledger. The generic example does not contain the target case answer.

The primary runner implements `selected_acquisition`. `fixed_capture` is a separate planned diagnostic and is not implemented in v1; it must not be substituted for a selected-acquisition result. A live GitHub API collector cannot establish what an earlier decision maker could read at a historical cut; retrospective confirmation requires a reviewed immutable historical snapshot adapter and a separate execution receipt. A hash of API bytes alone does not authenticate GitHub or prove availability at the decision cut.

## Stage gate

`pilot`, `retrospective` and `prospective_shadow` fail before ledger reservation unless a separately versioned `eal2-ci-prospective-execution/1` plan has status `ready`, binds the exact study specification digest, lists the exact assignment once, and has a corresponding signed `eal2-ci-prospective-receipts/1` bundle. The gate verifies SHA-256 of every artifact and Ed25519 signatures under an operator-supplied public-key roster, including two independent domain reviewers for cases and references, a security owner for tool isolation, and a method reviewer for arm parity and JSON/EAL differential tests. The review must bind the exact registry, case grants, executed read-only adapter receipts, cut controls, injected policy/source hashes, MCP operation sequence, current language/JSON contracts, model identity and stage-specific analysis or shadow access. These signatures attest review; they do not make a false measurement true. The repository ships no ready bundle or signer keys.

The case JSON schema is `eal2-ci-prospective-case/1` with `id`, `family_id`, the natural `task`, `scope`, UTC `decision_cut`, opaque `reference_id`, `allowed` exact input objects by tool name, and `evidence_grants` binding EAL evidence IDs to tool/environment names. The host rejects source evidence outside those grants before calling MCP. The independent reference stays outside prompts and is scored by masked reviewers; `reference_id` only connects the result to that review.

## Commands

From the repository root, run the synthetic contract suite:

```sh
python -m pytest -q tests/test_prospective_runner_v1.py
```

The suite actually starts MCP stdio and a local command collector, checks E/J typed semantic parity and status authority, and verifies pending-plan rejection and one-attempt ledger behavior. Synthetic fixture outcomes are labelled `ineligible_synthetic_smoke`.

Check a retained ledger without executing any model or tool:

```sh
python benchmarks/prospective-v1/runner_v1.py --verify-ledger /private/study/attempts.jsonl
```

After independent review and freeze, an operator can run one scheduled case/model block with the real stage files and trusted model configuration:

```sh
python benchmarks/prospective-v1/runner_v1.py --run \
  --case /private/study/case.json --model FROZEN_SNAPSHOT_ID \
  --provider /private/study/provider.toml --workspace . \
  --registry /private/study/tools.toml --ledger /private/study/attempts.jsonl \
  --stage pilot --execution /private/study/execution.json \
  --bundle /private/study/receipts.json --receipt-root /private/study \
  --roster /private/study/trusted-public-keys.json
```

These paths are operator inputs, not supplied artifacts. The current plan contains no ready execution, reviewed cases or receipts, so the command must fail closed until the prerequisites exist. `--stage retrospective` additionally needs an independently authenticated historical source and frozen analysis; `--stage prospective_shadow` needs read-only shadow authority. The runner records outcomes; it does not score them as correct or estimate an advantage. Follow the prespecified independent adjudication and family-weighted analysis in the study plan.
