# EAL/2 experiment methodology

Protocol 6.0.0 uses scientific-protocol schema 1.2 and has status **specified**.
The implementation and synthetic operating characteristics are checked separately
from empirical feasibility. No live result under this protocol is claimed.

## Decision and population

The principal comparison remains EAL versus an ordinary fresh conversation with
its task specification and naturally retained project notes. The EAL treatment
includes source, compatible persisted observations, collection and host reasoning.
Both arms start each provider conversation with empty history. Initial expenditure
and all attempts count. The source is pre-authored in the automated comparison.

The default principal population is the six separately AI-authored task cases,
two donor models, two recipient models and native tools on/off, equally weighted.
The eight threshold calibration cases check the apparatus and are excluded from
the principal mean. This is a prospective change from the previous task mixture;
results from the two populations must not be pooled. Cases, models and settings
are a finite purposive population. Repetitions estimate execution variation and
do not create independent task families.

At H=10 recipient sessions let Q be mean recipient correctness and let T be the
initial-plus-recipient input and output token total. The estimands are
Delta_Q = E[Q_EAL-Q_ordinary], Q_E = E[Q_EAL], and
R_T = 1-E[T_EAL]/E[T_ordinary]. The operating boundaries remain -0.05, 0.90 and
0.20. These engineering choices are assumptions, not established utility values.

The statistical null is the union
`Delta_Q <= -0.05 OR Q_E <= 0.90 OR R_T <= 0.20`.
The alternative requires all three strict inequalities in the beneficial
direction. Success requires all three one-sided lower bounds to exceed their
boundaries. Each component uses alpha=0.05. This intersection-union decision does
not need a Bonferroni split: under the union null, success implies rejection of
at least one true component null. Endpoint independence is unnecessary for that
argument. Resource inference is approximate, so the complete implementation has
nominal rather than exact 5% false-success control.

Separate two-sided estimation intervals use Bonferroni across the three
endpoints. These intervals answer a simultaneous estimation question; the
one-sided decision bounds do not claim simultaneous 95% coverage. Failure to
establish success remains inconclusive unless an estimation interval resolves a
criterion in the adverse direction. Cheap failures cannot satisfy success.

## Correctness uncertainty

A matched trajectory, containing all ten recipient answers in both arms, is one
independent observation. No session independence is assumed. For independent
bounded X_i with range width W, the default one-sided radius is

`r = sqrt(2*s²*log(2/delta)/N) + 7*W*log(2/delta)/(3*(N-1))`.

This is Maurer and Pontil (2009), Theorem 11, which allows non-identically
distributed observations. W=2 for paired correctness differences and W=1 for
absolute correctness. The sample variance includes fixed-stratum heterogeneity;
it is conservative in that respect. Zero observed errors still produce a positive
radius. A Hoeffding method remains available as a prospectively selected
comparison, not an outcome-selected smaller interval.

Unknown outcomes are intervals. For their midpoint vector m and half-widths h,
`SD_true <= SD(m) + sqrt(sum(h_i²)/(N-1))` follows from the triangle inequality
and contraction of centring in Euclidean norm. The implementation caps the
resulting variance bound at the known range maximum. It then uses the worst-case
mean endpoints. Thus the interval contains the bound for every completion of the
latent outcomes, including dependence introduced by budget stopping. Independence
is required of the latent planned trajectories, not the missingness indicator.

The resource ratio retains the paired stratified delta method and Student
critical value. Independent reruns, finite variance and a stable positive
ordinary-token denominator are required. Zero observed within-cell resource
variance does not establish the absence of tails and produces no resource
interval. Unknown token usage also prevents a finite resource claim.

## Pilot and allocation

The default pilot has four repetitions in each of 48 task/model/tool strata:
192 matched pairs, 384 arm sequences and 4,224 sessions. These counts describe
coverage and nuisance estimation, not sufficient statistical power. USD 2 and
21,600 seconds are cumulative per-run ceilings. A partial pilot remains partial.

Four independent matched blocks run concurrently in saved-order batches. The
two arms within a block and the sessions within each arm remain serial. The
worker count is frozen in the plan; observed latency is conditional on it and
provider load. Concurrent execution reduces waiting time, not the number of
planned calls or their token expenditure. Shared reservations are atomic.

Actions collects for at most 6,000 seconds within each 120-minute job. Checkpoints,
per-session terminal records and the append-only API journal support resumption
of the same run with the same code, paths and runtime. Completed or interrupted
sessions are retained without replaying requests. Unknown usage keeps its reserved
cost and incomplete session timing blocks deadline-feasibility claims. Segment
time and expenditure remain cumulative; a hard-killed segment consumes its full
time lease. The workflow never automatically launches another paid segment.

Correctness coding applies to the whole answer. Only standalone canonical prose
decisions are automatically coded; all JSON explanations require independent
annotation, including in provider-enforced JSON conditions. Formatting validity
does not establish substantive correctness.

The pilot supplies complete paired trajectories, correctness disagreements,
within-stratum variation, serial dependence, reservations, charges and elapsed
time. At least four complete repetitions per stratum are the default empirical
planning minimum; this is a floor, not evidence of accurate variance estimation.
The planner retains incomplete units and blocks empirical export when annotation,
resource, timing, provenance or replication requirements fail.

Resampling alone is supplemented by positive mean-one resource shocks. If X is
an empirical draw and independent M has E[M]=1, then
`Var(XM)=Var(X)+E[X²]Var(M)`. The chosen lognormal M restores the difference
between empirical variance and unbiased sample variance. Declared shocks also
represent unobserved resource variation. This is an explicit generating model,
not an estimate of unseen tails. Required sensitivity includes a sixteen-fold
variance inflation and larger unobserved variation. Pilot uncertainty cannot be
removed by increasing the number of simulation draws.

Quality scenarios can independently set ordinary correctness and the paired
correctness effect. One shared perturbation per arm trajectory permits perfect
serial dependence. Scenarios include useful benefit, no saving, harm, each of the
three decision boundaries, higher expenditure, slower execution, rare tails,
missing annotations and missing usage. Changes to nuisance scenarios must be
prospective and justified before evaluation.

The allocation grid retains the declared population and changes repetitions.
Selection requires correctness half-width <=0.025, token-reduction half-width
<=0.10, joint precision assurance >=0.80, and joint decision power >=0.80 in the
scenarios explicitly designated beneficial. All scenarios check false success.
Plausible missing-annotation and tail scenarios require information and coverage;
a missing-usage scenario instead requires safe inconclusive behaviour, because
unknown costs cannot become a complete resource estimate.

Screening uses 200 simulations per cell. A prospective calibration tolerance of
0.01 is separate from the scientific margins: validation requires the Monte Carlo
lower coverage bound >=0.94 and upper false-success bound <=0.06. Nominal targets
remain 95% and 5%; these tolerances qualify the numerical diagnostic of the
approximate resource procedure and do not create an exact guarantee.

A screened candidate must pass fresh-seed validation with 10,000 simulations per
scenario. Monte Carlo confidence is adjusted across all candidate/scenario and
four acceptance-criterion checks. Candidates that fail validation are retained in
the report. Only a live, completely measured pilot can produce an evaluation
plan. Synthetic runs can never do so. Evaluation uses a new study/run identity
and never pools allocation-pilot outcomes.

Concurrent feasibility uses complete paired trajectories in batches of the frozen
worker count. A batch takes the maximum pair duration. Its admission uses the
sum of charges plus one maximum request reservation per worker, a conservative
upper bound on simultaneous reserved expenditure. If a batch cannot fit, that
batch and later batches retain unknown-outcome bounds. This approximation does
not predict provider rate limits or extra contention: slower-execution sensitivity
remains necessary, and no evaluation worker override is permitted.

The former 15,320-pair Hoeffding requirement is reported as a reference calculation.
The empirical Bernstein requirement depends on observed variance; its zero-variance
calculation is a best-case bound, not an allocation recommendation. Budget and
runtime can still make every candidate infeasible. The software reports that
outcome explicitly and does not relax quality requirements or increase spending.

## Mechanism diagnostics

Diagnostics are separate from the ordinary-workflow comparison. They clone donor
state, randomise variant order, preserve every attempt and verify delivered
manipulations. The reasoner factor supplies the same rules, scope, times and raw
facts in three conditions: facts alone, an EAL-derived decision, and a decision
from a conventional evaluator. The conventional evaluator calls neither EAL nor
the independent reference scorer. Only the optional decision field varies in the
model-facing packet. Identical correct decisions produce identical packets, so
this comparison does not presume an intrinsic model-accuracy advantage for EAL.
It detects evaluator disagreements and distinguishes host-computation expenditure.

The EAL-versus-facts contrast tests the effect of supplying a computed conclusion.
It includes the additional computation and decision information; it is not a
claim that notation alone changes reasoning. An EAL-versus-conventional advantage
requires analysis of implementation, validity and resources before attributing
it to a language or inference mechanism. Shared or inconclusive results remain
explicit possibilities.

Existing projection, notes and response-format factors remain available.
Compatible reuse versus forced collection is additionally crossed with stable,
periodic and frequent evidence changes in a separate cadence diagnostic plan.
Within each cadence, the paired facts and state are equal; comparisons across
cadences describe the declared task regimes. Public evidence revision events
invalidate earlier observations through the existing context-aware reuse contract.
Both workflows receive the revision notification. Revision detection itself is
supplied by the fixture and is not measured as an inferred capability.

Each correctness contrast is summarised at the independent donor-block level,
with simultaneous empirical Bernstein bounds across reported contrasts. Failed
manipulations and unknown labels contribute adverse bounds. These sparse pilots
will commonly be unresolved. Additional replication must be selected for the
specific contrast and donor population; diagnostic answers never increase the
principal sample size.

## Task variation and external evaluation

The task-manifest CLI validates independently supplied task rules, scope, eleven
snapshots, evidence revisions, authored answer keys and provenance. It rejects
changed facts without an invalidation event, incorrect answer keys, duplicate
identities and calibration-name collisions. The entire manifest is embedded in
the saved plan; a declared digest is checked. Author and reviewer identities are
recorded attestations, not independently authenticated credentials.

The included example contains six internal synthetic task patterns crossed with
three cadences. It exercises alternative routes, conjunctions, version selection,
conflicting dated evidence, invalidated facts and missing evidence. Its provenance
explicitly records internal construction and automated reference checking. It does
not supply independent human authorship or a representative engineering sample.
Independent authors must supply a new manifest for those stronger claims. The
CLI creates a separately identified pilot and does not silently change the default
principal population.

## Adoption expenditure

API tokens remain the primary resource endpoint. An optional run-bound cost ledger
adds observed authoring, correction, maintenance and host activities in each arm.
It records measured seconds, declared USD/hour rates, session positions and
measurement references. Coverage declarations distinguish complete measured zero
work from missing observations. Unknown rates or incomplete coverage prevent a
total-cost claim. Every ledger edit produces a new version, and event IDs are unique.

Cumulative adoption expenditure includes initial activities once and later events
at their recorded positions, plus reconciled API charges. Reports retain each cost
category, the first observed cost crossing and the separate correctness decision.
A cost crossing alone cannot establish quality-preserving adoption. No crossing
beyond the observed horizon is extrapolated. Values depend on the declared rates;
the experiment does not invent a monetary value for unmeasured human work.

## Evidence and methodological sources

`validation/design-validation.json` records actual synthetic operating-characteristic
calculations using production statistics. `verification.md` records commands and
checks. Neither is an empirical model comparison.

* Maurer and Pontil (2009), Theorem 11, https://arxiv.org/abs/0907.3740:
  independent non-identical bounded observations and variance-sensitive uncertainty.
* FDA (2022), Multiple Endpoints in Clinical Trials, section III.C.1,
  https://www.fda.gov/media/162416/download: the statistical distinction between
  conjunctive success and disjunctive endpoint selection; no clinical claim is made.
* Deng, Knoblich and Lu (2018), https://alexdeng.github.io/public/files/kdd2018-dm.pdf:
  approximate ratio uncertainty with paired covariance.
* Imai, Tingley and Yamamoto (2013), https://imai.fas.harvard.edu/research/files/Design.pdf:
  treatment randomisation alone does not identify a causal mechanism.
* McKenzie (2025), https://doi.org/10.1111/1475-5890.70003:
  design, measurement, dependence and analysis can change information for a fixed budget.

Screening rejects a candidate only when its Monte Carlo interval lies wholly on
the inadequate side of a required threshold. An uncertain screen advances to
fresh validation; it is not treated as an adequate design. The final gates use
the adverse interval endpoints at confidence adjusted across all candidates,
scenarios and four selection criteria. This avoids asking 200 screening draws to
certify a near-5% boundary rate. The default validation uses 10,000 new draws per
scenario; a candidate is exported only after those stricter checks pass.
