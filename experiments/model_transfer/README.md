# Low-cost live model transfer pilot

This automated pilot measures fresh-session reuse of existing EAL/2 knowledge
on six synthetic engineering cases. It uses real API model responses. It does
not recruit or impersonate human developers. The separate
[developer study](../transfer_study/README.md) measures developer workflows.

## Model and tool configurations

| Recipient | Dedicated reasoning configuration | Native function calls |
| --- | --- | --- |
| `gpt-4.1-nano-2025-04-14` | No reasoning parameter; non-reasoning model family | Disabled |
| `gpt-4.1-nano-2025-04-14` | No reasoning parameter; non-reasoning model family | Enabled |
| `gpt-5-nano-2025-08-07` | `reasoning.effort: low` | Disabled |
| `gpt-5-nano-2025-08-07` | `reasoning.effort: low` | Enabled |

Both models support function calling; disabling it tests operation without
native tool access, not an intrinsic incapacity. Reasoning is varied between
model families, so the result cannot isolate a causal effect of reasoning.
EAL collection and assessment remain available in the EAL arm in every cell:
that is the offloading behaviour being tested.

Each configuration runs both ordinary prompting and EAL-assisted prompting on
six cases: fresh positive/negative evidence, expired evidence followed by a
positive/negative measurement, missing measurement, and an ended assumption.
The cases use `structured/1`; findings do not cover all EAL reasoning modes.

There are **48 sequences and 96 sessions** (24 EAL/ordinary matched
comparisons). Three cases use the plain model as donor and three the reasoning
model, giving both same-model and cross-model transfers. Initial sessions have
native tool access in both arms. Native tools are varied in the recipient
session. Sequence order is shuffled using the recorded seed.

Both arms receive the same engineering specification and collector interface.
The EAL arm additionally starts with a source expressing that specification
and a TOML binding. Initial registration time is recorded, but authoring time
is outside this already-authored-knowledge pilot. These bounds differ from the
human study, which includes authoring effort.

The first model may persist project notes in either arm. The later model sees
only project files, its question and, in the EAL arm, the runtime assessment.
Earlier chat and function-call results are not copied into its conversation.
No runbook or curated result cache is supplied to ordinary prompting. The
collector state and oracle stay outside the model-visible project. EAL is
reinstantiated from persistent storage when preparing each session.

## Outcomes and limits

The primary descriptive score is exact agreement on both `decision` and
`basis` against a direct calculation from the engineering specification.
The oracle never reads EAL status. A missing measurement or expired assumption
requires `undetermined`; an observed failing criterion gives `not_ready`.
Decision-only agreement and qualified-unavailable answers are also reported.
This is task completion against the full-information reference; a recipient
reporting insufficient available evidence is not thereby making a false claim. Free-text explanations are retained
but are not assessed by this closed-label scorer.

Report every planned sequence, failed/incomplete attempt, unrun sequence,
initial/later elapsed time, setup time, API tokens (including reported reasoning
tokens), estimated cost, native tool calls and EAL reuse/recollection. A model
without native tools may lack enough current evidence to resolve a refreshed
case; report its qualified answer separately from exact task completion.
The treatment effect includes EAL's external evidence access and assessment.

Six cases are reused across configurations. No significance test, independent
sample count based on calls, human-effort claim, population model-class claim
or superiority conclusion is justified. This pilot identifies operational
failures and differences worth testing on more varied independent tasks.

## Execution and spending

The default plan permits at most three API calls per session and 4,096 output
tokens per request, with 32,768 request bytes. The ledger reserves a conservative
input/output cost before each call, retains reservations when usage is unknown,
and stops before the next reservation would exceed **USD 2**. Prices are
recorded in `plan.json`; billing remains the provider's authoritative amount.
All attempts, including incomplete reasoning output, count. There are no hidden
retries or fallbacks to different models. Authentication, quota and unavailable
model errors stop the run and retain the planned denominator.

Run from the repository root with `OPENAI_API_KEY` supplied securely:

```sh
python -m pip install -e .
python -m experiments.model_transfer.runner \
  --output experiments/model_transfer/runs/live
```

Alternatively, manually dispatch the existing **EAL tests** workflow on the
experiment branch with `model_transfer=true`. It uses the single repository
secret `OPENAI_API_KEY`, runs repository checks first, then retains the complete
experiment directory as a workflow artifact even if execution fails. The live
job has a 45-minute limit; a timeout can leave a partial dataset. Ordinary
manual test runs keep `model_transfer=false` and incur no API calls.

```sh
gh workflow run test.yml --repo emmett08/earl \
  --ref feature/cross-session-transfer-experiment -f model_transfer=true
```

Inspect `report.json`, `rows.json`, `calls.json`, and each sequence's session
records and `initial-files.json`. New runs require new directories. Credentials
and HTTP authorisation headers are excluded from these records.

## Verification and sources

`tests/test_model_transfer.py` checks the six independent oracle outcomes,
EAL reuse/expiry, native-tool masking, reasoning-item replay within a session,
fresh later conversations, natural note persistence, budget reservations,
incomplete responses and full denominators after a fatal provider error.
A scripted transport is used only for these software checks.

Provider capabilities, snapshots, pricing and continuation requirements were
checked on 28 September 2026 against the official documentation:

- [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano): USD 0.10 input / 0.40 output per million tokens.
- [GPT-5 nano](https://developers.openai.com/api/docs/models/gpt-5-nano): USD 0.05 input / 0.40 output per million tokens.
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling) and [reasoning](https://developers.openai.com/api/docs/guides/reasoning): preserve output reasoning items when returning tool results within a session.
- [Deprecations](https://developers.openai.com/api/docs/deprecations): listed shutdown dates are 23 October 2026 for GPT-4.1 nano and 11 December 2026 for GPT-5 nano. Availability for this account still needs a live check; the runner never silently substitutes a model.

The [protocol](protocol.json) records the scope, measurement assumptions and
implementation checks. No live comparative result is included until execution
with a configured provider succeeds.
