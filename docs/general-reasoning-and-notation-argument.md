# What would establish an EAL reasoning advantage?

**Argument version 1.1; 23 September 2026.** The proposed contribution is that
EAL can help a specified model or model–interpreter system solve engineering
problems correctly, retain necessary qualifications and revise conclusions
when evidence changes. Two distinct results could support that contribution:
transfer across engineering problems, or a causal advantage of EAL notation
under otherwise equivalent conditions. Each requires its own evidence. A
notation advantage on a narrow task distribution would establish the second
result without establishing the first.

The present evidence supports a narrower conclusion: particular EAL-assisted
systems resolve the exposed synthetic cases, and some complete model sequences
correct initially wrong answers. The primary evidence-transfer contrast
demonstrates preservation of already correct answers. The completed diagnostic below
separates these outcomes; it supplies some recovery from injected wrong
proposals but does not establish the stronger requested claims.

The [executable argument](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/arguments/reasoning-advantage/argument.eal) uses the
existing EAL/2 grammar and `structured/1` method. Its empirical targets remain
unsupported until their evidence requirements are met. Executing this argument
checks recorded dependencies and predicates; it does not prove its authored
scientific warrants. Its finite diagnostic claim is checked against all retained
model trials; the independent notation and transfer criteria remain unmet.

## A worked distinction: preservation, correction and verification

Consider the existing wrong-origin RMS case. The measurements and method query
refer to an origin that differs from the claim's formal query. A positive RMS
result therefore supplies insufficient support for that claim. A recipient
must retain this qualification, even when the numerical value looks favourable.

In the original full-tool-model → small-model comparison, the producer had
already answered every task correctly. Answer-only transfer damaged four of
the twelve answers, across two task types. Evidence transfer preserved all
twelve. If the only observed producer state is “correct”, the experiment has
no observations with which to estimate correction of a producer error. Calling
preservation an improvement in recipient endpoint accuracy is appropriate;
calling it demonstrated recovery from incorrect producer reasoning is stronger
than those observations allow.

A counterexample makes the distinction explicit. A recipient that always
copies a correct label from a tool assessment can score twelve out of twelve
without deriving any conclusion from raw measurements. The original evidence
packet contains public tool results, including assessments. Private reference
labels were excluded, but an interpreter's public conclusion is itself useful
answer information. Raw observations, computed conclusions and a model's
proposed answer therefore need separate experimental conditions.

## What the existing records add

The [transition analysis](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-argument-audit/relay-transitions.json)
recomputes the transitions from the retained 324 endpoint rows, joins their
stages by cohort and stage identity, and checks that paired comparisons reuse
the same saved producer. Its denominators are twelve task/repetition blocks
and six task clusters. It distinguishes a completed incorrect answer from an
incomplete producer run. These are post-hoc descriptions of existing data.

| Sequence | Initially correct | Completed incorrect | Incomplete | Wrong → correct | Incomplete → correct | Correct → wrong/incomplete |
|---|---:|---:|---:|---:|---:|---:|
| Full tool producer → small recipient, answer | 12 | 0 | 0 | 0 | 0 | 4 |
| Same producer and recipient, evidence | 12 | 0 | 0 | 0 | 0 | 0 |
| Small producer → full tool stage → small recipient | 6 | 6 | 0 | 6 | 0 | 0 |
| Full producer → small tool stage → full recipient | 8 | 4 | 0 | 4 | 0 | 0 |

The six and four corrections occurred at the middle tool-assisted stage; the
final recipient preserved them. Their matched answer-only return baselines,
small → small and full → full, corrected none of those initially wrong answers.
This establishes that correction occurs in the archived complete systems. Tool
access, an additional stage and, in one comparison, model size change together.
The results therefore support a whole-sequence engineering capability, with
its associated cost, rather than attribution to transferred evidence or EAL
notation alone. Repeated task instances and overlapping stages supply dependent
observations; the corrections must not be added as independent replications.

The full transition report also retains the small tool producer's two failed
calibration episodes and subsequent recipient outcomes. A correct status after
an incomplete tool interaction does not establish that the recipient repaired
the source or independently verified the observation. The original
[model results](eal2-model-results.md) and [sequence results](eal2-relay-results.md)
remain the authoritative historical reports.

## The argument and its warrants

**Claim N — notation.** For a pinned model, specified budgets and a declared
distribution of engineering tasks, rendering the same reasoning information
in EAL improves correctness relative to a meaning-equivalent structured
representation. “Notation alone” here means the assigned surface representation:
the claims, dependency relations, observations, inference rules, tools and
scoring remain equal. Tokenisation and learned familiarity can mediate a
surface effect; this experiment cannot attribute it to a particular cognitive
mechanism.

The grounds must be paired outcomes from an intervention that changes this
representation alone. The warrant is causal: assignment to equivalent task
versions, with fresh sessions and balanced execution order, makes the observed
contrast informative about the representation intervention under consistency,
no interference and stable measurement. Semantic equivalence, equal access to
inference and independent scoring supply the necessary backing. The qualifier
restricts any conclusion to the tested models, task distribution, reference
materials and resource limits. An EAL-specific parser, extra diagnostic feedback
or a reference solution available in only one condition would undercut this
warrant. Such a comparison estimates the complete interface or tool system.

**Claim G — transfer across engineering problems.** A specified model or
model–interpreter system can formulate, solve and revise engineering arguments
on independently held-out mechanisms across the declared task families and
domains. Evidence must include successful construction and revision from
ordinary problem statements. Interpreting an already supplied EAL argument
measures a narrower ability.

The inductive warrant depends on task coverage, independent sampling or an
explicit finite target set, trusted reference solutions and protected
evaluation data. Report absolute performance, false support and domain-level
failures as well as differences from a baseline. The qualifier attaches ability
to the tested system: notation represents reasoning; a model and any connected
interpreter perform the operations. A finite suite establishes bounded transfer,
with uncertainty, rather than competence on every engineering problem.

**Claim R — correction with evidence.** With a fixed recipient and a fixed
proposed answer, adding relevant raw observations increases recovery from
incorrect proposals and preserves correct qualifications. Its grounds require
both initial-answer strata. A separate positive control supplies interpreter
conclusions. If only that control succeeds, the warranted finding concerns
use of computed answers, while the raw-evidence claim remains unresolved.

These claims are compatible with several outcomes. EAL might improve faithful
representation without improving final correctness. The interpreter might
improve performance while notation has little effect. Evidence might prevent
damage yet fail to correct errors. A system might transfer well even when EAL
and the structured comparator perform equally. The argument retains these
alternatives because each implies a different engineering recommendation.

## The runnable diagnostic

[The plan](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-notation-transfer-diagnostic.json)
and [runner](../scripts/notation_transfer_experiment.py) implement a controlled
diagnostic on five existing, well-formed synthetic tasks. The source-repair task
is excluded because a matched repair interface needs a separate design. This
suite is exposed development material, irrespective of its inherited
`held_out` field. It cannot establish Claim G.

Each argument is rendered as canonical EAL and as its source-independent JSON
semantic representation. The runner checks the canonical parse round trip and
the equality of the represented content. It removes parser bookkeeping, keeps
authored rationales and scope, and refuses patterns requiring expansion. The
same semantic reference and response schema apply to both forms. Neither
recipient receives parser feedback or tool access. The EAL grammar and
interpreter remain unchanged.

The experiment has eighteen conditions per task: the following four conditions
for each of two proposed-answer states and two representations, plus an
evidence-only condition for each representation. Two repetitions give 180
scheduled calls. A correct proposal and an intentionally incorrect proposal
are constructed before assignment. Within each task/repetition and proposal-quality
stratum, both representations and all four information views use the same
proposal; raw-only has none. The label alternatives rotate with repetition.
Recipients are not told whether a proposal is correct. Injected errors measure
resistance to controlled misinformation; they do not estimate the frequency or
composition of naturally occurring model mistakes.

| Condition | Proposed answer | Additional information | What it tests |
|---|---|---|---|
| Answer | Correct or incorrect | Argument, scope and common reference | Transfer baseline |
| Answer + raw | Same proposal | Original observation records | Effect of supplying relevant measurements |
| Answer + irrelevant | Same proposal | Same-valued records for another assembly | Relevance checking versus accepting any plausible record |
| Answer + assessed | Same proposal | Raw records plus interpreter conclusions | Benefit available from computed answer information |
| Raw only | Absent | Original observation records | Performance without a producer's answer |

The irrelevant-record condition deliberately retains measurement values while
changing their declared context. It tests scope discrimination rather than a
neutral token-length placebo. A separate length-matched neutral-text condition
would be needed to isolate a generic prompt-length effect. Natural EAL and JSON
lengths are retained; equal output caps keep response limits comparable, and truncation failures
remain recorded failed attempts. Input length is measured as part of the
practical surface intervention.

The response contains claim statuses and a short public justification. The
automatic score records agreement with the full-information reference and,
separately, correctness for the observations actually supplied. Both include
unjustified positive answers in admitted responses relative to their own
reference. Malformed/provider-error content is excluded from this positive-claim
score, so a zero count does not establish absence of false assertions there;
the justification is retained for independent assessment and is not yet a
validated reasoning-quality score. Malformed answers count as failed attempts.
Missing credentials create no attempted trials. Unknown provider usage stops
execution, retaining the attempted record. A pre-call cost allowance and the
configured two-dollar campaign threshold limit planned spending; these are
local controls, not a provider-enforced invoice cap.

Before the first model call, protocol 1.0.1 corrected a missing completion-status
field in scoring and introduced the second reference. The original bytes remain
in [the version 1 history](history/notation-transfer-v1/). The prompts, model,
schedule and budget were unchanged. Missing observations and records for another
assembly leave every requested claim unsupported in this diagnostic. Accordingly,
a recipient can correctly decline support in those arms while disagreeing with
the full-data answer. Counts called “correction”, “preservation” or “damage” must
identify their reference. Full-information disagreement alone does not show
failed reasoning or lost qualifications.

## Estimands and decisions

Let \(Y_i(n,v,a)\) indicate agreement with the complete full-information answer for task block \(i\),
notation \(n\), information view \(v\) and proposed answer \(a\). Let \(U_i\)
indicate a positive answer unjustified by that reference. Report a parallel
available-information correctness indicator using the view-specific reference.
The two references coincide in raw-only, raw and assessed arms. Primary comparisons preserve task,
model, proposed answer and resource settings; all attempted failures remain in
their denominators.

For notation, use the evidence-only comparison, which avoids anchoring on a
producer answer:

\[
\Delta_N=\mathbb E[Y_i(\mathrm{EAL},\mathrm{raw},\varnothing)
                     -Y_i(\mathrm{JSON},\mathrm{raw},\varnothing)].
\]

For correction, fix an incorrect proposal \(a^-\) and a representation:

\[
\Delta_R=\mathbb E[Y_i(n,\mathrm{answer+raw},a^-)
                     -Y_i(n,\mathrm{answer},a^-)].
\]

Define damage as \(D(n,v)=\Pr(Y_i(n,v,a^+)=0)\) for an initially correct
proposal \(a^+\). The original primary comparison observes a damage difference
of four out of twelve and has **zero correction opportunities**. Its correction
rate is undefined, not zero. Report recovery from incomplete proposals
separately. For the prospective diagnostic, compare raw evidence with irrelevant
evidence and interpreter conclusions, reporting each view's own correctness.
A higher full-information score with raw than irrelevant data is insufficient
evidence of scope discrimination: the observations and appropriate answers
change together. Examine rejection of wrong-scope records directly.

The five-task diagnostic reports counts and paired task-level differences.
Its repetitions are not additional independent tasks; incorrect proposals also
rotate between different wrong labels, so these are not identical-prompt
replications. It supplies no
population significance claim, and selection among its eighteen conditions
creates no confirmatory result. Before a fresh confirmatory study, freeze a
five-percentage-point minimum useful gain, the model-specific primary contrast,
the task sampling frame and a calibrated information target. For a causal
advantage of at least that size, use
\(H_{0N}:\Delta_N\leq0.05\) against
\(H_{1N}:\Delta_N>0.05\), and analogously for \(\Delta_R\).
A lower confidence bound above zero alone establishes a weaker claim.
The proposed practical threshold means one additional correct solution per
twenty tasks at equal resource limits. It is an explicit design choice; its
deployment value needs assessment before the confirmatory protocol is frozen.

| Observed pattern, after design checks | Permitted conclusion |
|---|---|
| Relevant raw data improve full-information recovery; view-specific scoring also demonstrates rejection of missing or irrelevant support | Bounded recovery and scope discrimination in the tested conditions; each result retains its own denominator |
| Raw data reduce damage, with no adequate correction evidence | Preservation benefit; correction unresolved |
| Only interpreter conclusions improve outcomes | Benefit from computed answer information; raw-evidence reasoning unresolved |
| EAL exceeds matched JSON in raw-only trials | Surface-representation effect on these tasks; mechanism and broader transfer unresolved |
| EAL with tools exceeds JSON without those tools | Complete-system difference; notation effect unidentified |
| Both representations transfer well and their difference lies within a prespecified equivalence interval | Bounded system capability with practical equivalence of representations |
| Intervals remain wide, or manipulation/scoring checks fail | Inconclusive, or affected inference suspended; preserve all records |

These result patterns can coexist; report each relevant estimand rather than
selecting a favourable row as a single verdict. A nonsignificant contrast does
not establish equivalence. Evidence quality and protocol deviations take
precedence over any nominal threshold.

## The transfer study needed for Claim G

Build a new task frame crossing electronics/control, mechanical/thermal,
distributed software and reliability/manufacturing with six activities:
diagnosis, quantitative prediction, constrained design, interpretation of tests,
causal/counterfactual analysis and revision after new evidence. Task authors
should supply independently checked solutions, admissible alternative
solutions and genuinely underdetermined cases. Include counterexamples to
unwarranted extrapolation, shared-evidence double counting, unit mismatches,
confounding, stale observations and changes of operating conditions.

Split by underlying mechanism and problem template before prompt development.
Changing equipment names or numerical constants supplies new instances of an
exposed template. It does not supply independent task-family transfer. Reserve
mechanisms and independently authored tasks for final evaluation; do not
release their answers into prompts or feedback. Task construction after a
model's training date reduces one exposure risk without proving absence of
training contamination or subsequent provider adaptation.

Use four matched core conditions: structured representation alone, EAL alone,
structured representation with the common interpreter/solvers, and EAL with
the same interpreter/solvers. Give both tool conditions the same operation
schemas, diagnostics, repair allowance, observation access and budgets through
a common structured interface. This separates representation from execution.
An unstructured-prose baseline can additionally estimate the value of explicit
argument structure, provided it receives the same problem facts. If an author
has already supplied the decisive derivation to one arm, the comparison ceases
to measure formulation of engineering reasoning.

Score correct conclusions, valid numerical or formal derivations, essential
qualifications and appropriate revision using representation-blind references.
Score source validity and tool completion separately. A system that always
declines to answer must fail on the resolvable cases; a system that always
asserts support must fail on the adverse cases. Measure total calls, failed
attempts, tokens, latency and cost per correctly resolved task. Reviewers must
not infer reasoning quality from eloquence or agreement with another model.

The [investigation protocol](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/protocols/INV-EAL-REASONING-001.json)
records this as **specified**, with task construction, measurement validation,
precision planning still outstanding. The live diagnostic has authorised access;
its execution and findings are reported separately. A generic minimum number
of API calls would not resolve those requirements. Independent templates are
the sampling units; repetitions estimate within-task variability. Use the
diagnostic to validate the apparatus, then simulate interval coverage and power
over plausible task heterogeneity before fixing the confirmatory sample size.
Declare multiplicity across model-specific primary claims and any sequential
stopping rule before looking at those outcomes.

The [synthetic precision sensitivity](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/protocols/reasoning-precision-sensitivity.json)
uses 10,000 simulated datasets per scenario. With a true ten-percentage-point
gain and 480 independent templates, a one-sided 97.5% lower bound exceeds five
percentage points in approximately 72% of simulated datasets when 20% of pairs
are discordant, and 31% when 60% are discordant. At 960 templates these figures
are approximately 95% and 52%. Repetitions are perfectly dependent within a
template in this calculation and count once. These are planning sensitivities,
not EAL results. They show why the information target depends on paired outcome
variability. Correlation between templates, scoring error and provider drift
still require calibration before confirmation.

## Reproduction and current status

Run the existing-record analysis and freeze the new diagnostic:

```bash
python scripts/analyse_relay_transitions.py \
  --output benchmarks/results/2026-09-23-argument-audit/relay-transitions.json
python scripts/notation_transfer_experiment.py \
  benchmarks/experiments/eal2-notation-transfer-diagnostic.json \
  --output /tmp/eal-notation-diagnostic
python scripts/check_reasoning_argument.py
```

After configuring the provider named in the plan, adding `--execute` runs the
live diagnostic and preserves every attempted response. An identical freeze
can resume completed records; uncertain attempts are never silently retried.
Changed source, protocol, prompts or provider configuration require a separate
output directory and a recorded protocol amendment. Freezing and local checks
make no generation requests.

The [completed live report](notation-transfer-live-results.md) retains all 180
attempts, including eighteen schema failures and one output-limit failure.
The original runner stopped at trial 30; a separately documented continuation
reconciled its known usage and ran the remaining schedule without retrying or
changing any prompt. Estimated configured-rate cost was USD 0.0660738, with no
unknown charges. The pre-generation protocol remains frozen; execution status
and the operational deviation are recorded alongside the results.

Raw-only EAL achieved 4/10 complete correct answers versus 5/10 for equivalent
JSON. With incorrect injected proposals, raw observations produced 2/10 and
5/10 correct answers respectively, while observations plus interpreter
conclusions produced 7/10 and 8/10. The exploratory claim-map-only readout
changes raw-only JSON to 6/10 and leaves EAL at 4/10. These results add bounded
correction observations beyond the earlier preservation finding. They do not
establish a robust raw-evidence benefit, an EAL notation advantage or general
engineering transfer. In particular, the circular-defence and wrong-origin
cases failed in both raw-only repetitions for both representations, and
irrelevant-record controls exposed weak scope discrimination. All condition,
reference, failure and task counts appear in the report.

The executable argument now supports the finite measured diagnostic claim.
Its stronger notation, raw-correction and engineering-transfer claims remain
unsupported under their stated criteria. This is a limit of the evidence,
not a claim that every possible EAL-assisted system must fail.

## Methodological sources and their use

The local [engineer-argumentation-languages skill](../skills/engineer-argumentation-languages/SKILL.md)
requires controlled surface comparisons, explicit method contracts, independent
task coverage and separation of authored warrants from executable checks. This
document applies those requirements without proposing a language change.

Sclar, Choi, Tsvetkov and Suhr (ICLR 2024),
[Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design](https://arxiv.org/abs/2310.11324v2),
report sensitivity to meaning-preserving prompt formatting. Their result
motivates predefined representation variants and model-specific reporting; it
does not establish an EAL effect.

Dwork, Feldman, Hardt, Pitassi, Reingold and Roth (2015),
[Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html),
explain why repeated adaptive reuse can overfit an evaluation set. This supports
the distinction between the current exposed diagnostic and future protected
evaluation. Their specialised reusable-holdout algorithm is not implemented here.

The potential-outcome estimands and identification assumptions follow the
framework of Hernán and Robins, [Causal Inference: What If](https://miguelhernan.org/whatifbook).
The trial factors, thresholds and EAL-specific scoring are proposals made here,
not findings attributed to those authors.
