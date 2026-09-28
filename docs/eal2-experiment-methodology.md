# EAL/2 experiment methodology

The investigation estimates whether retained EAL/2 arguments, compatible observations
and host reasoning reduce the work required to answer engineering questions in
fresh model sessions while preserving task correctness. The versioned
[protocol](../experiments/model_transfer/protocol.json) specifies the scientific
contract; the [run guide](../experiments/model_transfer/README.md) gives executable
commands. Protocol 4.0.0 has status **specified**. Empirical information adequacy
and a live performance benefit remain unestablished.

## Practical question and comparison

The principal question is whether EAL reduces cumulative input-plus-output tokens
by at least **20%**, including the initial session, after **ten fresh recipient
sessions**, with mean correctness no more than **five percentage points** below
ordinary prompting and **at least 90% EAL recipient correctness**. The absolute
floor prevents uniformly poor workflows from satisfying a relative comparison.
These prospective thresholds are explicit operating choices
for this investigation. They are configurable before evaluation; neither source
research nor existing EAL results establish them as universal requirements.
Estimated API cost in USD, elapsed time in seconds, evidence collection counts and
initial versus later expenditure remain separate secondary outcomes.

The ordinary comparator is a new conversation with the current task specification
and the latest complete answer retained verbatim as a project note. It receives
no supplied runbook, curated tool-result cache or previous provider conversation.
EAL adds authored source, TOML tool bindings, persistent observations and checked
host evaluation. Its compact task context can omit facts and instructions that
the host already resolves. Each workflow receives an appropriate prompt for the
same external question. The intended treatment includes their differences in
information organisation, collection and host computation.

Primary answers are ordinary prose. Independent annotation identifies the
expressed task decision, then an independent task reference scores it. Reporting
format, citations and file-writing behaviour are separate measurements. A
provider schema-enforcement facility is needed only for the explicit diagnostic
that varies that facility.

## Estimands and practical decision

Let \(H=10\), let \(Q_{wb}(H)\) denote a workflow's mean task correctness over its ten recipients in
matched block \(b\), and let
\(T_{wb}(H)=\sum_{s=0}^{H}(I_{wbs}+O_{wbs})\) denote cumulative input-plus-output
tokens for workflow \(w\). Session zero is the initial session; its correctness is reported separately from
the primary recipient outcome. The finite mixture
of selected task, donor, recipient and tool-access strata is fixed before evaluation.
The principal estimands are

\[
\Delta_Q(H)=\mathbb E[Q_{\mathrm{EAL},b}(H)-Q_{\mathrm{ordinary},b}(H)],
\qquad
R_T(H)=1-\frac{\mathbb E[T_{\mathrm{EAL},b}(H)]}
                   {\mathbb E[T_{\mathrm{ordinary},b}(H)]}.
\]

Practical support requires \(\Delta_Q(10)\geq-0.05\),
\(\mathbb E[Q_{\mathrm{EAL},b}(10)]\geq0.90\) and
\(R_T(10)\geq0.20\), assessed jointly using the declared uncertainty bounds. A point
estimate crossing a threshold alone does not establish support. A resolved
failure of any threshold identifies inadequate correctness or insufficient token
saving. Intervals spanning a threshold, incomplete accounting, unresolved answer
annotation or insufficient information produce an inconclusive decision. Cheap
incorrect responses cannot satisfy the joint criterion.

A token saving is stated both as a percentage and as the corresponding absolute
token difference. Cost and time contrasts retain their physical units; they are
not substituted for the primary endpoint after observing results. Initial cost,
each recipient's marginal cost and the cumulative trajectory show whether initial
overhead is recovered within the observed horizon. No break-even point beyond
that horizon is inferred.

## Pilot, information and evaluation

A pilot estimates paired resource variation, correctness disagreements,
within-sequence dependence, incomplete outcomes and request expenditure. At least
two pilot replications in each included case/model/tool stratum are needed to
estimate within-stratum variability. One observed pair and an absence of errors
do not establish zero variance or perfect accuracy.

The candidate pilot crosses fourteen tasks with two donor models, two recipient
models, two recipient native-tool settings, two repetitions and both workflows.
It contains **448 arm sequences and 4,928 sessions**, with at most **14,784
requests**. This count describes coverage. The USD 2 reservation cap and job
runtime can truncate it; neither completion nor adequate precision is promised
by the count.

The information procedure resamples complete matched trajectories within declared
strata. It retains arm pairing and temporal dependence rather than treating
session answers or API calls as independent task replications. It evaluates
predeclared repetition allocations, each retaining all fourteen cases. Design
scenarios include a null effect, a 30% token reduction with preserved correctness,
a 30% token reduction with ten percentage points lower correctness, twice the API
expenditure and twice the elapsed time. Separate stress scenarios examine missing
answer annotations, missing usage and rare resource tails. Poor precision, poor
coverage or unattainable effects in these stress scenarios remain explicit
limitations; they do not independently determine allocation eligibility.
Its seeded simulation uses **200 replicates** and reports Monte Carlo uncertainty
separately from uncertainty in pilot estimates.

The allocation target uses **95% nominal joint confidence**, with a correctness
half-width no larger than **2.5 percentage points** and a token-reduction
half-width no larger than **10 percentage points**, achieved jointly in at least
**80% of simulated repetitions**, judged by the lower 95% Monte Carlo bound.
Allocation also requires the lower 95% Wilson bound for simulated **joint interval
coverage to reach 95%** in each design scenario. Known simulated truths determine
coverage; narrow intervals that miss them cannot qualify. These Monte Carlo
intervals apply pointwise to each candidate/scenario cell, not simultaneously
across the searched grid.

The implementation uses a conservative bounded mean inequality for independent matched sequence correctness differences and a
paired, stratified delta approximation with numerically inverted Student
critical values for the resource ratio. Bonferroni allocation divides the error
budget across relative correctness, absolute EAL correctness and token reduction.
The quality bound is distribution-free under its independence and boundedness
assumptions. Resource coverage is approximate and depends on sample
size, finite variance and denominator behaviour; joint coverage is therefore
nominal rather than an exact finite-sample guarantee. Precision assurance is a
planning result conditional on these assumptions, not achieved statistical power or measured model effectiveness.

The conservative correctness-difference bound has radius
\(\sqrt{2\log(6/(1-0.95))/N}\) for \(N\) independent matched sequences.
A 2.5-percentage-point radius therefore requires at least **15,320 pairs**.
With fourteen cases and eight donor/recipient/tool cells per case, a balanced
allocation requires **137 repetitions**, or **15,344 pairs and 337,568 sessions**.
The candidate grid retains 2, 4, 8, 16 and 32 repetitions to show the attainable
precision at smaller allocations, and includes 137 repetitions to reach the
analytic quality target. The smaller candidates cannot meet that target,
regardless of an apparently error-free pilot. This conservative information
requirement does not imply that the large candidate is affordable or timely.

The procedure exports an evaluation allocation only when empirical support,
precision, joint coverage, request-reservation and elapsed-time requirements pass in every
predeclared design scenario. Timing includes observed sequence setup and session
intervals, with a **300-second prospective workflow-overhead allowance** inside a
**7,200-second deadline**. The allowance is an assumption; its presence does not
establish that unmeasured workflow work fits it. A failed requirement produces a
report of the limiting quantity, candidate results and unresolved information.
The correctness target may admit no adequate allocation within USD 2 and the
execution deadline. Increasing counts, relaxing margins or changing the budget
requires a prospective plan choice before fresh evaluation outcomes.

All primary allocation candidates retain the same fourteen tasks and model/tool
cells. Changing task inclusion would change the estimand and requires a separately
declared investigation. Pilot and evaluation have distinct study identities and
run directories. The selected plan records the pilot inputs and information settings. Evaluation uses
new executions; pilot outcomes inform allocation and variability estimates but
are not pooled into the evaluation result. Scripted transport is labelled and
can exercise planning arithmetic, but cannot provide live variance estimates or
certify an empirically adequate allocation.

## Tasks, models and reuse

Eight existing cases remain calibration material. They exercise strict and
inclusive thresholds, fresh and expired observations, changed positive and
negative findings, missing measurements and assumption boundaries. Six additional
synthetic tasks across three further families have a recorded, separate AI
authorship process. Their evidence dependencies and decision rules broaden the
exercise beyond a single threshold comparison. This is distinct construction
within the same investigation; it is not external human authorship, independent
investigator validation or random sampling from engineering work.

| Task family | Additional cases | Evidence and decision distinction |
| --- | --- | --- |
| `conjunctive_release` | `release-three-obligations`; `migration-cutover-obligations` | All declared obligations must hold; missing evidence remains unresolved |
| `alternative_routes` | `database-alternative-read-routes`; `dispatch-direct-or-tunnel` | A valid alternative can establish readiness while other routes fail or remain unresolved |
| `version_applicability` | `firmware-selective-applicability`; `migration-multiple-version-bindings` | Fact selection depends on declared version, scope and observation time |

The installed `experiment/task-rules/1` method evaluates three-valued composition
and scoped, dated selection of the newest applicable fact. Each acquisition is a
bundled fact snapshot with a 60-second inclusive lifetime. Measurements concern
snapshot reuse; selective collection of individual facts and general temporal
logic remain outside this experiment. Snapshot updates occur at session positions
0, 2, 4, 6, 8 and 10. Intervening odd positions retain the observation time and
outcome, so valid reuse and changed evidence are both exercised.

Fixtures specify changes at particular recipient positions, enabling measurement
of reuse, invalidation and renewed collection across ten fresh sessions. Each
new conversation has empty provider history. Project notes and compatible EAL
observations persist only within their own workflow sequence. A negative tool
finding can remain valid evidence. The task reference derives the decision from
the task specification and fixture, independently of the authored EAL argument.
Source-contract checks and deliberately invalid calibration examples prevent
argument defects from being scored as model failures.

The selected snapshots are `gpt-4.1-nano-2025-04-14` and
`gpt-5-nano-2025-08-07`, with the latter configured for low reasoning effort.
Both donor-to-recipient transitions and recipient native-tool access are crossed.
Native-tool masking tests available access; both models intrinsically support
function calls. Reasoning configuration varies with model family. Results
therefore concern those configurations and cannot identify an isolated reasoning
capability effect. EAL collection and evaluation operate in the host regardless
of recipient native-tool availability.

## Principal comparison and component diagnostics

The whole-workflow comparison receives the main information allocation. Component
diagnostics use a separate plan, budget and report. Four actual donor sessions
produce states cloned into 28 independent recipient directories. The declared
contrasts vary context projection, prior notes, response format or forced
collection while checking the required equality of donor state and current facts.

A diagnostic is expanded only when a concrete uncertainty justifies it: for
example, a quality loss concentrated after an evidence change could motivate
further stale-note contrasts. Additional diagnostic replication receives its own
information target. Diagnostic variants do not increase the primary sample size,
and their repeated use of a common donor remains explicit.

## Measurement and permissible inference

Every scheduled unit and attempted request remains in the records. Missing usage
is distinct from zero expenditure. Ambiguous or explanatory prose remains pending
independent annotation; an empty attempted response is an observed no-answer.
Incomplete decisions produce explicit bounds. Exact request receipts are
reconciled with the request journal before finite resource comparisons are made.

The statistical target is performance conditional on the selected finite tasks
and configurations. Independent executions provide information about repeated
behaviour on those tasks. They do not create new task families. Results
by individual case, task cohort, model transition and tool access remain
descriptive. Task definitions record family membership; the report does not
provide a separate family-level estimator. The same descriptive scope applies to
secondary horizons and diagnostic mechanisms. General developer productivity,
source-authoring effort, maintenance effort and performance across arbitrary
reasoning modes require further investigations.

[McKenzie (2025)](https://doi.org/10.1111/1475-5890.70003),
[*Designing and analysing powerful experiments*](https://ifs.org.uk/sites/default/files/2025-12/FISCAL~3.PDF),
informs the outcome-specific information target, treatment definition,
measurement, allocation and treatment of repeated observations. The
[Dovetail guide to experimental research design](https://dovetail.com/research/what-is-experimental-design/)
informs explicit specification of variables, comparator, assignment and
measurement. These methodological sources do not evaluate EAL or establish its
performance. The bounded-quality calculation follows
[Hoeffding (1963), Theorem 2](https://doi.org/10.1080/01621459.1963.10500830).
The resource-ratio approximation adapts the delta-method treatment in
[Deng, Knoblich and Lu (2018)](https://alexdeng.github.io/public/files/kdd2018-dm.pdf)
to independent paired repetitions within fixed strata; the Student critical value
does not make this nonlinear approximation exact. Passing calibration and
scripted pipelines establishes the exercised
implementation behaviour; empirical support requires the corresponding live data.
