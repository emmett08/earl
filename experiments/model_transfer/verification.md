# Model-session investigation verification

Protocol **3.1.0**, package **2.15.0**, EAL/2. Packet/model-context schemas remain
`/2`; the primary plan/report use `/3`; the diagnostic plan uses `/1`.
These records concern software and measurement instruments. Rehearsal labels
were supplied from the deliberately scripted answer text; they are neither human
annotation results nor model observations. No live model experiment has been run
under this protocol.

| Check | Actual result |
| --- | --- |
| Scientific protocol validator | VALID at specified status; zero errors and zero warnings. |
| Integrated suite | `make check`: 822 passed, 1 skipped; generated parser and maintained CLI/MCP example passed. |
| Actual-runtime calibration | 41 primary-plan checks and 21 diagnostic-plan checks passed, including the changed-threshold mutation; zero live requests. |
| Answer/annotation checks | 48 dedicated tests passed; whole-answer canonical coding and pending counterexamples verified. |
| Full-plan scripted rehearsals | 256 primary sequences/768 sessions and 4 diagnostic donors/28 recipients completed. Scripted transports received 1,280 and 36 requests respectively. |
| Annotation and offline reconstruction | 768 primary and 24 diagnostic pending answers passed scripted annotation import and offline analysis; original rows unchanged and resource measurements reproduced. |
| Independent acceptance review | Original scoring, tool-turn termination, missing-journal and preparation-accounting counterexamples verified as repaired. Saved diagnostic plans replay after JSON key reordering. |
| Build and distribution | `make build` passed; 2.15.0 source archive includes the current repair modules and excludes run artefacts. |
| Workflow and diff | Only manual workflow dispatch; live execution defaults off. `git diff --check` clean. |

The integrated checks cover the following properties. This list specifies the
verification scope; the table records which checks have actually completed.

* Every primary assignment preserves the case, donor, receiver, native-tool
  setting, repetition and recipient position. Diagnostic variants clone a common
  donor state into independent directories.
* The authored task contract rejects changed claim meaning, criterion, scope or
  incompatible declarations. Actual EAL evaluation distinguishes measured negative
  results, missing readings, out-of-scope observations and freshness/applicability
  boundaries. The independent reference does not read EAL conclusions.
* Generic context preserves claim statements and their `prose_verified`
  qualification. Task context contains the current decision, meaning, scope and
  supporting evidence without requiring the model to reconstruct omitted facts.
* Primary prose responses do not require JSON. An unclassifiable or contradictory
  answer remains pending annotation; empty output is observed no-answer.
  Only complete standalone canonical prose decisions receive automatic labels.
  Explanations, qualifications, volunteered JSON and unfinished tool-turn text
  remain pending independent coding.
  Secondary basis/citation/format measurements do not redefine primary task
  correctness. Blind annotation adds derived labels without altering raw answers.
* Both primary workflows retain the latest complete raw answer as a project note
  under the same size rule. Ordinary prompts include their specification and
  notes; compact EAL prompts receive the current standalone task context.
* Diagnostic state, fixture and task-fact checks detect unintended variation.
  Actual response mode, note inclusion and compatible/fresh collection are
  recorded. A failed manipulation invalidates attribution while preserving its
  answer, costs and denominator.
* Resource accounting includes initial, each subsequent and cumulative work;
  shared diagnostic donors and unique recipients count once, with separately
  recorded shared and clone preparation. Session attempt receipts distinguish
  missing accounting from confirmed zero requests. Unknown labels, interrupted requests and
  incomplete token/cost records remain distinguishable from wrong answers and
  measured zeroes.

## Implementation responsibilities

Context strategies encapsulate ordinary and EAL workflows. TaskContract checks
this experiment's authored source; its task adapter translates an actual
assessment into the declared task result. The generic model-context projection
retains argument meaning and qualifications without claiming arbitrary prose is
formally proved.

Answer annotation, independent reference scoring and aggregate reporting are
separate responsibilities. Manual annotation is a derived record joined through
a separate mapping; it is not an answer-repair request sent to the model.
Diagnostic orchestration owns donor snapshots, clone creation, factor delivery
and manipulation checks. The existing provider transport, budget ledger and
append-only attempt journal serve both investigations.

Context and response-format classes use Strategy; the task context is an Adapter
from checked assessment to application vocabulary. Transport is injected through
a small protocol. Task correspondence, prompt preparation, annotation, outcome
summaries, paired comparisons and manipulation checks have separate owners.
The packet builder keeps bounded statement and omission helpers private because
they maintain one projection invariant. Diagnostic block orchestration retains
one donor-and-clones lifecycle; its assignment and measurement policies live in
separate modules. AttemptReconciler owns request-receipt reconciliation.
PreparationTimer owns timed operation records through an injected persistence
callback; DiagnosticResources owns preparation coverage and resource contrasts.
Session helpers retain text capture, tool-message handling and unfinished-answer
classification within one response lifecycle, where they share message ordering
and side-effect invariants. Adversarial calibration retains its fixture cases
with the same actual-runtime check and pass criteria.
These boundaries permit changes without a general-purpose
framework or duplicated evaluation logic.

The production evaluator, observation repositories and collector interfaces
remain shared. No general experiment framework or alternative EAL semantics is
introduced. Scripted transports exercise integration and failure handling; their
outputs are not observations of model capability or savings.

## Empirical limits

The historical run remains separately documented in
[run-36432530106.md](results/run-36432530106.md), with its original observations
and scores unchanged. It does not establish performance under protocol 3.1.0.
Credentialed manual execution is required to observe actual answers, provider
behaviour, tokens, latency and costs for the declared plans.

The eight primary cases and two diagnostic cases are purposive synthetic tasks.
EAL source authoring and human work are unmeasured. The diagnostic contrasts have
one execution per variant and support observations of sensitivity, not equivalence
or precise effect estimates. Generalisation requires independently selected tasks
and an information-based design appropriate to that claim.
