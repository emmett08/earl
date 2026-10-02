---
title: "Resource use and decision correctness in a live EAL handover pilot"
subtitle: "Six synthetic pilot tasks, 192 paired comparisons and a separate 128-session evidence-restoration follow-up"
date: "2 October 2026"
lang: en-GB
fontsize: 11pt
geometry: [a4paper, margin=25mm]
colorlinks: true
linkcolor: teal
urlcolor: teal
---

## Abstract

Engineering handovers require a new session to recover the current task, evidence and decision rules. The live pilot compares ordinary and Engineering Argument Language (EAL) workflows in six authored synthetic tasks, retaining 4,224 sessions and 192 paired trajectories. Conditional on the original AI codes, recipient agreement with authored references is 97.19–97.86% for EAL and 38.49–39.01% for ordinary. These ranges bound unresolved interpretations, rather than sampling uncertainty or assessor error. A supplemental AI review resolves six EAL interpretations and leaves 19 ambiguities overall; the primary pilot figures and frozen inference retain the original codes. Including donors and ten recipients, EAL used 33.61% fewer model tokens and 23.29% less estimated API expenditure, with 8.35% higher summed session time and more acquisitions. The joint engineering criterion passes under its stated assumptions; unresolved interpretations still block evaluation allocation.

A separate live 128-session follow-up met the primary recipient criterion of whole-verdict reference agreement **and** internal explanatory consistency in 20/40 facts-only, 30/40 EAL and 33/40 conventional evaluator answers. All 40 EAL/conventional packet pairs are identical, so their accuracy contrast cannot identify an implementation effect. Six ambiguous verdicts have contradictory explanations and remain known primary failures. Eight purposive task clusters, one execution and shared AI coding restrict these conclusions to the constructed cases. Explanation grounding and assessor error remain unmeasured.

## The question the data can answer

A handover can preserve evidence outside the model's conversation and supply a compact current assessment to the next session. The practical question is whether this reduces the resources needed to answer subsequent questions while preserving correctness. The EAL workflow in this experiment combines authored source, persisted observations, compatibility checks, evidence collection and host computation. The comparator receives the task specification file and retained answer notes.

The five artefacts from [collection run 36985062352](https://github.com/emmett08/earl/actions/runs/36985062352) record preparation, apparatus checks, collection and annotation export. The subsequent [finish run 36997861629](https://github.com/emmett08/earl/actions/runs/36997861629) restores that export and adds answer coding, outcome analysis and allocation planning. Both describe the same 192 paired trajectories. Finish performs offline processing and makes no fresh collection calls.

Tokens, API usage, elapsed time and acquisition counts are observed. Task facts and reference decisions are constructed inputs. Decision correctness is derived by comparing an AI-coded communicated conclusion with the corresponding authored reference. Explanation correctness and total adoption expenditure remain separate measurement questions. The primary pilot results below retain the original finish codes. Later sections report the supplemental interpretation and a separate live evidence-restoration follow-up.

## From six artefacts to one annotated pilot

The archive manifest contains the artefact identities, creation times, byte counts and SHA-256 digests. Each downloaded archive was checked against its published digest. Table 1 identifies each artefact's role and evidential status. Collection, export and finish contain cumulative copies of the same live observations. Across the original export and finish, 15,187 of 15,189 shared files are byte-identical; only pipeline status and the restore receipt change. Five derived files add labels, annotated rows, outcome analysis and allocation inputs/results. Counting each snapshot as a separate experiment would duplicate the observations.

| Artefact | Role in this analysis | Evidential status |
|:--|:--|:--|
| Prepared | Frozen plan and preparation state | Design input |
| Preflight | Calibration and scripted rehearsal | Instrument checks using synthetic responses |
| Segment 1 | Complete retained live collection | Earlier cumulative copy of the live observations |
| Export | Raw rows, journal, resource report and annotation mapping | Canonical collection snapshot |
| Annotations | Masked answer text and blank coding fields | Original assessor hand-off |
| Finish | Imported AI codes, annotated rows, outcome analysis and allocation report | Derived processing of the original pilot |

Table: Roles and evidential status of the six retained artefacts.

The journal contains 10,884 events: one request-start event and one request-finish event for each of 5,442 API attempts. All attempt identifiers are distinct and each belongs to one session. A start and finish pair describes one attempt. The masked bundle contains 4,224 answers with matching identifiers. Raw answers and resource records remain unchanged throughout the analysis.

Calibration checks whether the apparatus computes the expected result on authored examples. Scripted rehearsal checks whether collection, export and processing work with fixed synthetic responses. Neither supplies a live model-accuracy observation. Their records remain separate from the live comparison.

All 83 calibration checks passed: 66 task-time outcomes, seven source mutations and ten boundary conditions. A separate implementation reproduced the 66 authored task-time reference decisions. These checks establish consistency with the stated fixture rules within the tested cases.

## What was compared

The design crosses six task cases, two donor models, two recipient models and two levels of recipient native-tool availability. Four repetitions in each of the 48 configurations produce 192 paired blocks. Each block contains an ordinary and an EAL sequence, with one initial donor followed by ten fresh recipient sessions. Thus each arm contains 192 sequences and 2,112 sessions; the full run contains 384 sequences and 4,224 sessions.

The plain model is `gpt-4.1-nano-2025-04-14`; the reasoning model is `gpt-5-nano-2025-08-07` at low reasoning effort. Both arms start each provider conversation with empty history. Persisted project material supplies the handover. The donor has native probe access in every condition. The tool-availability factor applies to the recipient sessions.

The donor is the initial session at position zero. It assesses a prepared project and leaves retained project state for ten subsequent recipients. The host creates the specification and EAL source before that initial session; the term donor describes the session's handover role. Later ordinary recipients also replace the retained latest-answer note, so continuity includes successive answers. Donor and recipient model assignments can differ. Quality outcomes cover recipients, while cumulative resources include the initial session.

The task corpus exercises release obligations, migration cutover, alternative database read routes, alternative dispatch routes, selectively applicable firmware conditions and migration version bindings. The facts, time progression, changes and decision rules are synthetic. The model calls and their resource usage are live. Case provenance records separately delegated AI construction within the same development session; this supplies a convenience corpus rather than an independently sampled engineering population.

After the task rules were drafted, timeline scheduling was adapted to the host acquisition contract. Six acquisition opportunities occupy even session positions, each separated from the previous acquisition by an unchanged intervening snapshot. This construction deliberately permits the measured reuse pattern.

All donor snapshots have a ready reference result. Across the 3,840 recipients in both arms, the constructed references comprise 1,536 ready, 1,024 not-ready and 1,280 undetermined outcomes. These class frequencies describe the task design; they are not frequencies of model decisions.

An EAL recipient receives a host-computed current assessment even when recipient native tools are disabled (Table 2). An ordinary recipient receives the task specification, a retained answer note and the configured probe access. Consequently, the intervention changes information delivery and host computation together. Its effect can be interpreted as a comparison of the two implemented workflows. A claim about language notation alone would require an additional comparison.

| Recipient condition | Host task assessment supplied | Specification file and latest answer note supplied | Native probing permitted |
|:--|:--|:--|:--|
| Ordinary, tools disabled | No | Yes | No |
| Ordinary, tools enabled | No | Yes | Yes |
| EAL, tools disabled | Yes | No | No |
| EAL, tools enabled | Yes | No | Yes |

Table: Model-visible information and permitted native probing in recipient conditions.

The compact EAL message supplies the host's decision, requirement states and applicability, rather than the complete raw snapshot. A permitted native probe can retrieve that snapshot; use depends on the model's calls. Both workflows save answer notes on disk, but only ordinary presents those notes and the specification file to the model in this run. The comparison therefore also changes which retained material the model sees.

For pair $i$, arm $a$ and recipient position $h$, define cumulative token use as

$$
T_{ia}(h)=\sum_{s=0}^{h}\bigl(I_{ias}+O_{ias}\bigr),
$$

where session zero is the initial donor, $I$ is provider-reported input tokens and $O$ is provider-reported output tokens. The principal observed reduction at ten recipients is

$$
\widehat R_T=1-\frac{\sum_{i=1}^{192}T_{i,\mathrm{EAL}}(10)}{\sum_{i=1}^{192}T_{i,\mathrm{ordinary}}(10)}.
$$

All configurations have equal replication. This ratio of totals therefore estimates the declared equally weighted ratio of mean cumulative token use. It differs from averaging 192 individual percentage reductions, which would give small and large ordinary trajectories the same ratio weight.

A paired trajectory is the comparison unit. Its eleven serial sessions share a task and retained state. The 4,224 session count measures coverage; it does not provide 4,224 independent comparisons. The repeated executions estimate variation within the fixed task and model settings. They do not add new task families.

## Coding the communicated decision

The original finish artefact contains 4,224 imported coding entries: 4,199 resolved communicated decisions and 25 ambiguous interpretations. The resolved categories are ready, not-ready and undetermined. An explicit undetermined conclusion is a coded decision; ambiguity denotes an unresolved interpretation of the text. There are no no-answer entries. Of the 25 ambiguities, 12 belong to ordinary and 13 to EAL; two ordinary ambiguities occur in donors and the other 23 occur in recipients.

The assessor coded the conclusion communicated by each answer before reference scoring. The record identifies AI-assisted rule scans for every answer and full semantic review of 392 flagged answers. The remaining 3,832 received rule scans. Frozen scripts and adjudications reproduce the imported label file byte-for-byte. Every masked identifier joins uniquely to a retained session, every answer hash matches, and every supporting quote is an exact substring of its answer. These checks establish record identity and reproducibility; they leave interpretation error unmeasured.

Assignment, model, task and reference metadata were masked in the coding hand-off. The declared assessor provenance also records prior project context and possible disclosure through answer wording. The exact serving model identifier is unavailable. There is no independent human validation or measured assessor-error rate. Rechecking with shared rules and context supplies an error control, rather than an independent inter-rater reliability estimate.

After the codes were frozen, scoring compared each communicated decision with the authored reference. Ambiguous codes retain unknown correctness. The pilot quality outcome measures decision agreement. Basis agreement, explanation correctness, grounding and internal consistency remain unassessed in the retained pilot answers. The deterministic EAL host assessment agrees with the reference in all 2,112 EAL sessions; the model's communicated conclusion still requires separate scoring.

{{FIG_MEASUREMENT}}

## Recipient decisions and their errors

The primary quality endpoint retains the original finish codes, covers ten recipients per trajectory and excludes donors. Ordinary has 739 known reference matches, 1,171 known mismatches and ten ambiguous recipient decisions; EAL has 1,866 known matches, 41 known mismatches and 13 ambiguities. Both denominators remain 1,920, retaining every planned recipient. Coding decisions are conditional measurements: an erroneous resolved AI code is outside the ambiguity calculation.

For trajectory $i$ and arm $a$, let $c_{ia}$ count known matching recipient decisions and $m_{ia}$ count unresolved ones. Define

$$
Q_{ia}^{-}=\frac{c_{ia}}{10},\qquad
Q_{ia}^{+}=\frac{c_{ia}+m_{ia}}{10}.
$$

Averaging these limits over all 192 trajectories gives recipient correctness bounds of 38.49–39.01% for ordinary and 97.19–97.86% for EAL. The paired difference is bounded by the means of $Q_{i,\mathrm{EAL}}^{-}-Q_{i,\mathrm{ordinary}}^{+}$ and $Q_{i,\mathrm{EAL}}^{+}-Q_{i,\mathrm{ordinary}}^{-}$: 58.18–59.38 percentage points. These finite-record envelopes allow unresolved decisions to be either correct or incorrect. They express ambiguity rather than repeated-execution uncertainty.

The reference-versus-communicated comparison distinguishes types of error. Each arm has 768 ready, 512 not-ready and 640 undetermined recipient references. Ordinary communicates ready in 291 not-ready and 362 undetermined reference cases; EAL does so in two and six cases respectively. Thus the observed affirmative readiness errors are 653 for ordinary and eight for EAL among 1,152 not-ready or undetermined reference cases per arm. These are disagreements with the authored decision criterion; the experiment records no deployment failures.

{{FIG_RECIPIENT_DECISIONS}}

Among 1,920 matched recipient positions, both arms match in 731, only EAL matches in 1,125, only ordinary matches in three, and both mismatch in 38; 23 positions remain unknown. Every whole trajectory has a positive conservative recipient-match difference. This is a finite paired description across the selected configurations, with the AI-coding qualification retained.

{{FIG_RECIPIENT_MATCH_BOUNDS}}

The task comparison in Table 3 retains the same 320-recipient denominator in each arm and task. EAL decision agreement is higher across all six authored cases, with variation within each workflow. These are descriptive contrasts within the chosen fixtures.

| Authored task | Ordinary match bounds (%) | EAL match bounds (%) |
|:--|--:|--:|
| Alternative database read routes | 44.38–45.94 | 98.44–99.38 |
| Direct or tunnel dispatch | 43.44–43.75 | 95.62–95.94 |
| Selective firmware applicability | 38.75–39.69 | 96.25–97.19 |
| Migration cutover obligations | 33.75–33.75 | 99.69–99.69 |
| Migration version bindings | 34.06–34.06 | 98.75–99.06 |
| Release obligations | 36.56–36.88 | 94.38–95.94 |

Table: Recipient decision-match ambiguity bounds by task in the original finish coding snapshot. Each task contributes 320 recipients per arm from 32 paired trajectories. Bounds retain every recipient and condition on the AI codes.

All 41 known EAL recipient errors occur when native tools are enabled: 33 with the plain recipient and eight with the reasoning recipient. Disabled-tool EAL conditions have no known errors but retain one plain-model and five reasoning-model ambiguities. The computed host assessment is supplied in both conditions. The contrast identifies a configuration pattern; its cause and the correctness of the accompanying explanations remain unmeasured.

## Token use across paired trajectories

At the ten-recipient horizon, ordinary sequences used 2,982,385 input and output tokens, while EAL sequences used 1,980,029. The difference is 1,002,356 tokens, giving the 33.61% reduction. The primary endpoint includes the initial donor and ten recipients in both arms. Donor tokens fell by 47.46%; tokens in the ten recipients fell by 31.49%. The whole-sequence reduction therefore combines a larger donor reduction with a smaller recipient reduction.

Input tokens fell from 2,468,145 to 1,533,871, a reduction of 37.85%. Output tokens fell from 514,240 to 446,158, a reduction of 13.24%. Input accounts for 93.21% of the total token difference. The observed result is therefore primarily a reduction in material sent to the models. The reduction in reported output tokens is smaller; that measure includes reasoning and tool-call output as well as answer text.

Reasoning tokens are a reported subset of output tokens and are counted once in the primary endpoint. Cached input tokens are a reported subset of input tokens. Adding either subset again would inflate totals. The composition figure separates these categories only where their relationship is explicit.

{{FIG_TOKEN_DISTRIBUTION}}

EAL used fewer total tokens in 190 of the 192 paired trajectories. The other two used more. Individual paired reductions ranged from a 5.38% increase to a 56.35% reduction, with a median reduction of 35.74%. This observed spread describes the matched cases; the median and the ratio-of-totals endpoint answer different aggregation questions.

{{FIG_TOKEN_SUBGROUPS}}

Case-level reductions ranged from 29.50% for migration version bindings to 37.56% for alternative database read routes. Across trajectories that include the donor, configurations assigned plain recipients showed a 29.24% reduction and those assigned reasoning recipients a 38.50% reduction, pooling over the remaining factors. Configurations with recipient native tools enabled showed a 30.37% reduction, compared with 39.21% when those tools were disabled. These descriptive marginal comparisons retain the workflow's unequal evidence-delivery paths, so their differences cannot be attributed solely to model reasoning or tool capability. Same-model and cross-model handovers had similar aggregate reductions, 33.73% and 33.49% respectively, within this selected corpus.

{{FIG_CUMULATIVE_TOKENS}}

The cumulative relative saving was already 47.46% at the donor session and declined to 33.61% after ten recipients. Absolute token saving accumulated while relative saving narrowed. This pattern gives no evidence of a growing percentage benefit with each additional handover, and the observed horizon supplies no extrapolation beyond ten recipients.

{{FIG_TOKEN_COMPOSITION}}

The composition plot isolates recipient sessions, so its model and tool labels identify the sessions that contribute the displayed tokens. The configuration estimates that include donors pool donor work from both models, and all donors have native tools. Figure {{NUMBER_TOKEN_SUBGROUPS}} compares recipient-only and donor-inclusive summaries.

Independent reconstruction reproduces the report's approximate stratified paired delta-method interval of 32.33% to 34.89% for the primary donor-plus-ten-recipient token reduction. It uses a Student correction and a nominal 98.33% component interval, from a Bonferroni split intended to provide 95% simultaneous two-sided estimation across three endpoints. This interval is conditional on independent reruns, adequate within-configuration variance estimation and a stable positive ordinary-token denominator. Four repetitions per configuration provide limited information about rare provider or output tails. The exact observed totals need none of those sampling assumptions; extrapolation to repeated executions does.

## Resource savings depend on which resource is counted

The frozen plan prices input tokens at USD 0.10 per million for the plain model and USD 0.05 per million for the reasoning model; output is USD 0.40 per million for both. Reconstructing each attempt's input and output charge at these rates gives USD 0.4015426 for ordinary and USD 0.3080341 for EAL. The combined estimate is USD 0.7095767, within the run's USD 2 ceiling. These amounts reproduce the recorded cost calculation. They are estimates at declared rates rather than a reconciled provider invoice; the calculation applies full input rates to cached input.

The lower reasoning-model input rate is the published tariff for GPT-5 nano, whereas the plain model is GPT-4.1 nano. Reasoning capability does not define a universal price tier. The [official GPT-5 nano](https://developers.openai.com/api/docs/models/gpt-5-nano) and [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano) pages verify those rates; they disclose no internal cost basis sufficient to explain the 50% difference. Hidden reasoning tokens are billed within output usage, as specified in the [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning). At one million inputs and 100,000 billed outputs the respective costs are USD 0.09 and USD 0.14. An additional 400,000 reasoning tokens raises the reasoning request to USD 0.25. The study's estimates depend on both the tariff and actual usage.

The API estimate in Table 4 fell by 23.29%, which is smaller than the token reduction because output and input have different rates, and the two model families have different input rates. A token count does not carry a common monetary value across these categories.

| Resource, including initial donor and ten recipients | Ordinary | EAL | EAL relative to ordinary |
|:--|--:|--:|--:|
| Input plus output tokens | 2,982,385 | 1,980,029 | 33.61% lower |
| Estimated API expenditure, USD | 0.4015426 | 0.3080341 | 23.29% lower |
| API attempts | 2,758 | 2,684 | 2.68% fewer |
| Summed session elapsed time, seconds | 5,166.34 | 5,597.71 | 8.35% higher |
| Native probe calls | 646 | 572 | 11.46% fewer |
| Host acquisitions | 0 | 1,152 | Added by the EAL workflow |
| Native calls plus host acquisitions | 646 | 1,724 | 166.87% higher |

Table: Whole-run resource totals, including each donor and ten recipients.

{{FIG_RESOURCE_RATIOS}}

The acquisition counts expose an operational consequence hidden by the token endpoint. EAL made fewer native probe calls, but its host made 1,152 additional acquisitions. Total recorded acquisitions were therefore 2.67 times the ordinary total. The two acquisition types have different execution paths, so their count sum is an activity measure rather than a calibrated cost measure. This run supports a claim about lower model-token demand alongside higher recorded acquisition activity.

The lower aggregate native-call and API-attempt counts arise from the donor phase. Across the recipients, ordinary recorded 466 native calls and 2,386 API attempts, while EAL recorded 486 and 2,406. EAL recipients therefore made 4.29% more native calls and 0.84% more API attempts, despite using fewer tokens. A donor/recipient comparison preserves this change of direction. Each acquisition here obtains one complete authored fixture snapshot; it does not measure the cost of collecting individual real-world facts.

{{FIG_PHASE_CONTRASTS}}

## Time and reuse: where the work moved

Summed session elapsed time rose from 5,166.34 to 5,597.71 seconds. Adding separately recorded sequence setup gives 5,166.74 and 5,607.64 seconds respectively, an 8.53% increase. The EAL arm recorded 875.15 seconds of context preparation compared with 0.0053 seconds for ordinary. Context time is included in session elapsed time and must not be added again.

These sums describe accumulated session durations. Four workers overlapped paired blocks, and the two arms inside a block ran serially. The recorded shuffled schedule put ordinary first in 101 pairs and EAL first in 91. The live collection segment lasted 3,521.13 seconds, including its broader segment work. Neither an arm's summed session time nor the full workflow duration is the wall-clock completion time of an independently deployed arm. Model/provider variation, concurrency and shared load qualify latency comparisons.

Client-observed API-attempt durations summed to 5,158.84 seconds for ordinary and 4,715.71 seconds for EAL, an 8.59% reduction. The timing boundary includes transport, response processing and accounting; it does not isolate provider computation. Context preparation finishes before the synchronous request loop begins. Subtracting these two non-overlapping measured components from session time leaves 7.49 seconds for ordinary and 6.85 seconds for EAL. This remaining time is calculated, rather than separately instrumented overhead. The additional context preparation exceeds the API-time saving and produces the higher session-duration total.

{{FIG_TIME_PARTITION}}

EAL had higher summed time in 138 of the 192 whole-sequence comparisons; the median paired excess was 2.96 seconds across the donor and ten recipients, or 3.01 seconds when sequence setup is included. The median setup-inclusive excess was 2.34 seconds in ordinary-first pairs and 3.31 seconds in EAL-first pairs. The direction persists in both order groups, while shared-provider interference remains unmeasured.

{{FIG_LATENCY}}

The two empirical distributions describe token and time variation separately. The paired scatter shows their joint result: 136 trajectories used fewer tokens with higher summed setup-inclusive time, 54 used fewer tokens with lower summed time, and two increased both quantities. None used more tokens with lower summed time. The two token-increase cases both used a reasoning donor and a plain recipient with native tools; this shared setting is a description of two observations, rather than an isolated mechanism.

{{FIG_PAIRED_TRADEOFF}}

EAL recorded 960 host reuses and 1,152 host acquisitions across 2,112 sessions. The donor acquired a current observation in each of the 192 EAL sequences. The ten recipients contributed 960 acquisitions and 960 reuses, yielding a 50% recipient reuse fraction. This fraction follows the authored evidence changes and eligibility conditions in the fixture.

{{FIG_ACQUISITIONS}}

Reuse can reduce repeated host acquisition while a fresh computed assessment is prepared for the model. Its benefit depends on the evidence-validity rules and change schedule. The fixture deliberately keeps facts and scope unchanged at intervening odd positions, permitting reuse at the inclusive 60-second validity boundary. The next even position expires that snapshot and triggers reacquisition. This schedule supplies the changes; the experiment does not measure an autonomous ability to discover real-world changes. A separate cadence comparison is needed to establish how the resource balance changes under different evidence-update rates.

## The joint engineering decision

The primary inference retains the original finish codes. The frozen plan defines recipient correctness $Q_a$ over repeated executions of the selected configurations, the paired difference $\Delta_Q=E[Q_{\mathrm{EAL}}-Q_{\mathrm{ordinary}}]$, and cumulative token reduction $R_T$. Its joint criterion requires $\Delta_Q>-0.05$, $E[Q_{\mathrm{EAL}}]>0.90$ and $R_T>0.20$. The null is

$$
H_0:\quad \Delta_Q\leq-0.05\ \text{or}\ E[Q_{\mathrm{EAL}}]\leq0.90\ \text{or}\ R_T\leq0.20,
$$

and the alternative requires all three strict inequalities. These are prospective engineering choices in the frozen design; developer utility at these boundaries remains unvalidated.

The analysis distinguishes simultaneous estimation from the decision test. Its two-sided intervals use a Bonferroni split across the three endpoints, giving nominal 98.33% component intervals for an intended 95% family. The quality-difference interval is 41.50–76.05 percentage points, EAL absolute correctness is 88.71–100%, and token reduction is 32.33–34.89%. The last uses an approximate stratified delta method, so the intended family coverage also inherits that approximation.

The separate intersection-union decision requires all three one-sided component tests to pass at the 5% significance level. Its lower bounds are 46.47 percentage points for the quality difference, 91.22% for EAL correctness and 32.74% for token reduction. All exceed their respective boundaries: $-5$ percentage points, 90% and 20%. These lower bounds are component decision bounds, rather than a simultaneous confidence family. The wider two-sided EAL interval crossing 90% is consistent with the one-sided decision passing: the two procedures answer different inferential questions.

Quality uncertainty uses empirical Bernstein bounds on independent whole trajectories. The theorem permits different distributions across the fixed configurations; serial dependence among recipients remains inside each trajectory. The calculation uses a conservative variance envelope over possible completions of the ambiguous decisions. It therefore preserves unresolved outcomes without assuming that missingness is independent of correctness. Independence between trajectories and valid resolved coding remain assumptions. Shared provider conditions could make trajectories dependent; common assessor rules could introduce systematic coding error.

A distribution-free Hoeffding sensitivity calculation gives an EAL one-sided lower bound of 88.35%, which does not pass the 90% criterion. The frozen empirical Bernstein procedure uses the smaller observed variance and passes. This comparison exposes the consequence of the uncertainty method; the primary decision retains the method specified before these coded outcomes were analysed. Neither bound estimates assessor error or extends the six authored tasks into an independently sampled task population.

The pilot result is consequently conditional support for the joint workflow criterion. It remains labelled `pilot_only`. A prospective evaluation would test the joint criterion with new outcomes and independently validated codes.

{{FIG_FROZEN_ENDPOINT_BOUNDS}}

## Competing explanations and the next comparison

The joint pattern of lower token demand and higher reference agreement is consistent with smaller model-facing context and computation transferred to the host. EAL supplies a current computed conclusion, requirement states and applicability, while the ordinary workflow asks the model to use its specification, latest answer note and available tools. This interpretation accounts for lower input-token demand and the additional host preparation and acquisition activity. The bundled comparison does not identify which component produced each difference.

A conventional evaluator supplying the same decision, requirement states, applicability and packet format provides an implementation control. The separate follow-up below compares equal current raw facts with and without a computed decision, and verifies identical EAL and conventional evaluator packets. Its new tasks and narrow execution do not retrospectively decompose the original workflow contrast. Holding other packet contents fixed while adding or removing the latest answer note remains a further comparison.

An EAL recipient without native tools still receives the current host assessment. An ordinary recipient without tools may depend on its retained note. The observed advantage in that condition can arise from the supplied assessment as well as model reasoning. Equal current facts in the follow-up hold that source of information disparity fixed within its matched comparisons.

Total adoption expenditure requires observed authoring, correction, maintenance, host and reviewer effort in both arms. The source is pre-authored here, and the cost ledger is absent. Unmeasured work has no defensible monetary value of zero. The estimated API difference of USD 0.0935085 therefore places a narrow limit on any total-cost inference from this run. The monetary cost of those activities could exceed that API difference even where the token reduction persists.

External validity requires independently supplied engineering tasks, evidence sources whose update cadence, acquisition latency and failure modes match the intended setting, and human-authored or independently reviewed rules. The workflows' change rates and handover practices must also match that setting. More repetitions of the existing six tasks refine within-task execution estimates. Additional task families are needed to support claims about a broader engineering population. Model versions, tool configuration and provider conditions should remain recorded so that a later evaluation has a defined intervention.

## Why the reference can remain undetermined

The 1,280 reference-undetermined recipient outcomes are completed three-valued assessments of the available task evidence. They arise from 20 authored task/time positions repeated in 32 trajectories per workflow across two workflows. These repetitions expand the same constructed states; their frequency describes the selected corpus. Every EAL reference-undetermined assessment has an available snapshot and a completed host evaluation. The uncertainty concerns the readiness criterion.

Figure {{NUMBER_REFERENCE_UNDETERMINED_PROFILES}} partitions those positions by the rejection reasons for decision-relevant evidence. Missing observations contribute 256 references; stale-only support contributes 128; profiles involving invalidation contribute 384; profiles involving version or configuration mismatch contribute 512. The finer profiles retain combinations with staleness, including rejected older fallback records. These are descriptions of constructed evidence patterns, rather than isolated causal-effect estimates.

{{FIG_REFERENCE_UNDETERMINED_PROFILES}}

For example, the release case's rollback observation exceeds its three-minute freshness limit. The cutover case contains no replication-lag observation. Dispatch TLS evidence has been invalidated while its alternative tunnel fails capacity. Firmware safety evidence for `fw1` cannot establish the current `fw2` condition. A mismatch establishes inapplicability; the current condition remains unknown. Missing JSON fields, unknown current-version identifiers and expiry of the outer snapshot do not explain the retained 1,280 outcomes.

Resolution requires an observation eligible under the task rules. Stale support calls for a repeated measurement; absent support requires instrumentation and acquisition; invalidated support requires justified replacement; a changed version requires applicable testing or a validated transfer rule. The pilot collector reads frozen fixture snapshots, so a repeated probe retrieves the same supplied facts. A new acquisition timestamp cannot refresh an old underlying test result. Freshness and applicability rules can be revised through validation against the engineering objective; a more permissive rule changes that objective unless its continued adequacy is established.

An unknown requirement affects readiness only when it can change the whole-task result. A false mandatory conjunct establishes `not_ready` despite another unknown requirement. A true alternative route establishes `ready` despite uncertainty elsewhere. The follow-up therefore tests decision-critical gaps and noncritical gaps separately.

## Controlled evidence loss and restoration

The separate follow-up was conducted as a bounded feasibility investigation with a fresh identity and new task material. Eight fictional task instances cross two logic families with missing, stale, invalidated and version-mismatched evidence. A separate AI author constructed the material and another AI reviewer recomputed all 88 timeline references directly from raw facts. The 40 scheduled recipient positions comprise 20 ready, 12 not-ready and eight undetermined references. This agreement checks implementation consistency with the authored rules. The material remains purposively selected and lacks independent human authorship or field validation. The cause of unavailable evidence is tied to the task domain, so effects of that cause cannot be separated from task-domain wording.

Each task contributed one initial donor and five recipient evidence conditions. Its actual donor state was cloned for every condition and context variant, creating 120 recipient sessions from eight donors. Only the raw snapshot changed between evidence conditions; rules and admission criteria remained fixed. Within each of the 40 task-condition comparisons, recipients received identical raw facts, scope, time and rules. The three contexts supplied either those facts alone, those facts plus an EAL-computed verdict, or those facts plus a conventional evaluator's verdict. The EAL and conventional model-visible packets were identical in all 40 comparisons. Any difference between their answers therefore describes variation under identical audited packets, rather than an EAL implementation effect on answer accuracy.

| Evidence condition | Conjunctive reference | Alternative-route reference | Diagnostic purpose |
|:--|:--|:--|:--|
| Complete eligible evidence | Ready | Ready | Establish the intact criterion |
| Critical gap | Undetermined | Undetermined | Preserve warranted uncertainty |
| Positive replacement evidence | Ready | Ready | Resolve the gap with satisfaction |
| Negative replacement evidence | Not ready | Not ready | Resolve the gap with failure |
| Noncritical gap | Not ready | Ready | Preserve a decisive result despite local uncertainty |

Table: Constructed reference patterns for the follow-up. Each pattern occurs in four task instances per logic family. These are authored reference states; observed model-answer outcomes are reported below.

One fixed plain model, `gpt-4.1-nano-2025-04-14`, and disabled native tools kept the diagnostic narrow. Randomised context order and cloned state controlled exposure to the other recipient answers. All 128 sessions were collected in one execution, with one response at each of the 120 recipient cells. Observations are grouped within eight task instances and two logic families; the 120 recipients are not independent task replications. The follow-up retains the designated canonical JSON decision field and full answer text. For the 120 recipients, the primary substantive endpoint requires whole-answer verdict agreement with the authored reference **and** internal explanatory consistency. Canonical-field agreement and format validity remain separate diagnostics. Contradictory, absent or unresolved explanations cannot establish substantive success. Factual grounding and the correctness of every explanatory assertion remain unassessed by answer-only consistency coding.

The earlier 128-session scripted rehearsal used fixed answers and synthetic provider usage to check software paths. The separate [live collection run 37023431850](https://github.com/emmett08/earl/actions/runs/37023431850), at revision `054c27354e1d3ed15d9c1c20f4b2110169b84a4e`, retained 128 actual API attempts and all scheduled sessions under run identity `adc97f7b-113d-4404-811d-16c5857e9d20`. A retrospective AI collection audit passed 1,027 checks with no failures, including source and answer identities, donor-state cloning, equal-fact delivery, packet equality and independent reference arithmetic. These checks establish retained-record and apparatus consistency; participant accuracy requires separate whole-answer coding.

The follow-up recorded 152,581 input tokens and 12,879 output tokens, or 165,460 in total. Configured-rate API expenditure was USD 0.0204097, with no unpriced attempts, below the shared USD 2 ceiling and the conservative USD 1.048576 reservation envelope. The estimate charges all input at USD 0.10 per million and output at USD 0.40 per million, retaining 1,152 cached input tokens without applying a discount. Task construction, host work and coding effort remain outside that estimate, which is not a reconciled invoice. Native tools were absent from every request. One execution of these eight fixed cases supplies finite collection and resource observations; it supplies no principal-study power or representative task effect.

| Follow-up resource group | Sessions | Input tokens | Output tokens | Configured API estimate, USD |
|:--|--:|--:|--:|--:|
| Common donors | 8 | 2,632 | 607 | 0.0005060 |
| Facts-only recipients | 40 | 49,863 | 4,314 | 0.0067119 |
| EAL recipients | 40 | 50,043 | 4,036 | 0.0066187 |
| Conventional evaluator recipients | 40 | 50,043 | 3,922 | 0.0065731 |

Table: Disjoint resource groups in the separate live follow-up. Common donors are counted once. Full current facts are retained in every recipient context, unlike the compact EAL delivery in the original pilot. Equal EAL and conventional input-token totals agree with the audited packet identity; output and cost differences describe this execution under those identical packets. These estimates omit cached-input discounts and total adoption effort.

Assessor qualification occurred after live collection and before participant-answer coding. Three initial exercise versions failed material eligibility review because of nonunique reference interpretations; their materials and attempted answers remain retained and ungraded. The fourth version was independently reviewed in draft before freezing and administration; each of its 24 exercises has a uniquely determined decision/consistency reference pair, with no unresolved keys. The version 2 coding supplement and acceptance threshold remained unchanged. Both actual coders and the fresh disagreement adjudicator each obtained 24/24 decision labels, 24/24 consistency labels and 48/48 exact, semantically relevant supporting quotations. The 144 checked quotations across the three assessors establish passage identity and rubric application on those exercises. Assessor error remains unmeasured, and the shared AI procedure supplies no independent human validation.

Two qualified AI coders independently interpreted all 128 full answers under opaque identifiers, with assignment and reference metadata withheld. Answer wording could still disclose its context. Initial agreement covered both axes in 126/128 answers and 252/256 individual labels. Two answers received a fresh masked adjudication. The final recipient codes retain six ambiguous whole-answer verdicts: three in facts-only and three in EAL. All six also have contradictory explanations, so each is a known failure of the conjunctive primary endpoint even while verdict agreement remains unresolved. The finished pipeline records `processing_complete` and complete execution, while its analysis retains `pending_annotation` for six verdicts, with no unresolved primary conjunctions. Planning is `not_applicable_to_diagnostics`, with no principal-study allocation or available evaluation.

A separate derived-record audit passed 926 mechanical checks with no failures. It verifies preservation of raw answers, requests, usage, timings and matched packets, along with supplied-code arithmetic and the 120-cell figure projection. Its scope is record identity and deterministic derivation; it supplies no independent semantic recoding.

The primary endpoint is met by 20/40 facts-only recipients, 30/40 EAL recipients and 33/40 conventional evaluator recipients: 50%, 75% and 82.5%, respectively. New tasks, full-fact delivery and the added consistency criterion give this follow-up a different endpoint from the pilot's decision-match bounds. Figure {{NUMBER_FOLLOWUP_PRIMARY_CELLS}} retains all 120 cells in their matched task and evidence conditions. Across the three contexts, successes total 23/24 with complete eligible evidence, 1/24 with a critical gap, 22/24 with positive replacement, 16/24 with negative replacement and 21/24 with a noncritical gap. Maintaining the warranted undetermined result after critical evidence loss was therefore rarely successful in this execution. Both replacement conditions have higher primary success counts than critical gaps. The noncritical controls retain the distinction between a local gap and a whole-task result. These are descriptive outcomes within eight task clusters, conditional on the AI interpretations and authored references.

{{FIG_FOLLOWUP_PRIMARY_CELLS}}

Canonical JSON fields agree with the references in 20/40 facts-only, 31/40 EAL and 33/40 conventional answers. Known whole-verdict matches number 20/40, 30/40 and 33/40, with three, three and zero verdicts unresolved. Internal consistency is coded in 37/40, 37/40 and 40/40 answers, respectively; the other six are contradictory. Known whole-verdict matches and primary successes have equal counts in this execution, although their definitions differ and all primary states are determined. Figure {{NUMBER_FOLLOWUP_ENDPOINT_SEPARATION}} keeps these overlapping measurements distinct. Field agreement alone supplies no assessment of the full communicated verdict or explanation. The EAL and conventional contrast is variation under identical audited packets; the three-success difference cannot identify an EAL implementation effect.

{{FIG_FOLLOWUP_ENDPOINT_SEPARATION}}

The host supplied the correct authored verdict in every EAL and conventional packet, yet ten EAL and seven conventional recipient answers fail the substantive endpoint. Apparatus correctness therefore coexists with communicated-answer failures in these cases. Qualification and masked adjudication concern these new answers and do not retrospectively validate the original pilot's codes. Shared AI provenance, one response per cell, purposive tasks and confounding of evidence cause with task wording limit transfer beyond this diagnostic. Factual grounding and real acquisition-service effectiveness remain separate questions.

The design follows [NIST's blocking guidance](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm) by holding nuisance conditions fixed within comparisons and randomising remaining execution order. [Imai, Tingley and Yamamoto's mechanism-design analysis](https://imai.fas.harvard.edu/research/Design.html) motivates the distinction between a whole-workflow effect and a separately manipulated component. An improvement after evidence replacement establishes response to that supplied evidence within the task; it does not measure the success of a real acquisition service. An unsuccessful real acquisition retains an undetermined reference.

## Supplemental answer-measurement review

The supplemental review preserves the completed pilot's original codes and primary calculations. It includes all 25 original ambiguities and one randomly selected resolved recipient from each workflow/model/tool/task/reference stratum, giving 144 resolved answers and 169 answers in total. Opaque identifiers and full answer text are supplied to two fresh AI reviewer contexts, with original codes and references withheld. The reviewers share model-family and rubric risks; their agreement shows reproducible interpretations in this selected packet under that procedure. It supplies no independent human accuracy standard or population assessor-error rate.

Both first reviewers retain the original 25 ambiguities and flag one additional answer because of its parenthetical heading. A third masked semantic adjudication reviews all 26 flagged answers and distinguishes practical withholding of readiness from a formal negative criterion result. Parentheses and an explicit explanation can clarify the former without announcing a correction. This adjudication resolves six original ambiguities as `undetermined` and restores the additional flagged answer's original `undetermined` reading. Five of the six amended codes match their references; one is a mismatch. The remaining 19 answers stay ambiguous. Every supporting quotation is checked against the unmodified answer before the coding is joined to references.

The derived supplemental rows therefore give EAL 1,871 matching recipients, 42 mismatches and seven unresolved recipients: 97.45–97.81% agreement. Ordinary retains 739 matches, 1,171 mismatches and ten unresolved recipients: 38.49–39.01%. The full dataset retains 19 ambiguities, including two ordinary donors. These finite-record envelopes use the supplemental interpretation and condition on all retained resolved AI codes. The primary figures and frozen inference retain the finish snapshot's coding; supplemental rows and recomputed reports remain separately identified. Shared AI-assessor errors and the representativeness of the resolved-answer sample remain unmeasured.

The refinement exposes a measurement requirement: the rubric must distinguish a criterion-failed decision from a statement that the action should be withheld because the criterion is unknown. Modal wording such as 'may be considered ready' can remain ambiguous even without explicit contradictory categories. Prospective coding uses the whole answer, preserves a declared canonical field separately, and records internal contradictions instead of treating every lexical collision as a conflicting conclusion.

## Allocation and the remaining validation work

The original finish report records successful execution and complete resource accounting. It records `pending_annotation` with 25 ambiguous communicated decisions and a `pilot_only` practical result. The separately recomputed supplemental analysis also records `pending_annotation`, now with 19 ambiguities, and retains `pilot_only`. The report's `measurement_status: complete` field refers to resource accounting, rather than complete answer adjudication. Processing success, bounded quality estimates and unresolved interpretation therefore describe different properties of the same retained pilot.

All 48 configurations have four fully collected paired repetitions. In the original finish coding snapshot, only 173 of the 192 pairs have every recipient decision resolved in both arms. Of the 48 configurations, 33 retain 4 fully scored repetitions, 11 retain 3 and 4 retain 2. The planner requires at least four complete repetitions per configuration and complete recipient annotation. The original report's input gates block all five candidate allocations, with 4, 8, 16, 32 or 64 repetitions, before simulation. `no_supported_allocation` therefore establishes refusal to allocate with these inputs; it supplies no measured power, budget infeasibility or precision failure for the untested candidates.

The supplemental AI review leaves a need for independently validated adjudication of the 19 retained ambiguities and independent coding of a stratified sample of resolved answers. The sample should cover both workflows, model/tool conditions, tasks and decision categories. Record disagreement, exact supporting passages and every revised code before recomputing the outcomes. A conclusion with unresolved internal conflicts can remain ambiguous. A prospective allocation method that explicitly retains bounded outcomes offers an alternative to requiring complete labels, provided its assumptions and calibration are frozen and checked before new evaluation data.

Using the original finish codes, normalising the recorded whole-sequence API estimate by reference-matching recipients gives USD 0.536–0.543 per thousand matching ordinary decisions and USD 0.164–0.165 for EAL. These finite-snapshot ratios include donor API usage and allow unresolved recipients to be correct or incorrect. They condition on the AI codes and exclude host computation, task authoring, maintenance and assessment work. They describe one resource per measured decision outcome, while the joint endpoint retains the separate token and quality criteria.

Any evaluation needs a fresh study identity and newly collected outcomes. Freeze its task eligibility, information supplied to each arm, models, worker count, coding protocol and success rule before inspecting those outcomes. Equal-information comparisons can distinguish the supplied host decision from EAL implementation; a full activity ledger can assess adoption expenditure. A latency-sensitive deployment requires an arm wall-clock or deadline endpoint, while a collector-limited deployment requires acquisition cost and rate-limit measurements.

## Reproducibility and conclusion

The accompanying package retains all six source archives, their digests, the frozen plan, task definitions, coding protocol, scripts and adjudications, annotation mapping, raw and derived records, resource and outcome calculations, editable article source and reviewed vector figures. Independent reconstruction verifies the collection-to-finish lineage, all answer joins and quotes, ambiguity preservation, 5,442 unique API attempts and the frozen endpoint calculations. Whole trajectories remain the units for repeated-execution uncertainty in the original pilot. No answer text or model response is repaired during scoring. The package separately retains the reference-profile analysis, supplemental review and amended rows, plus the follow-up task material, protocol, earlier scripted rehearsal, actual collection, calibration qualification, masked coding, adjudications and derived endpoint/resource summaries. Follow-up observations remain grouped within eight tasks.

This fixed pilot combines 33.61% fewer cumulative model tokens with substantially higher AI-coded agreement of recipient decisions with authored references. With the original finish codes, the conservative recipient-match difference is 58.18 percentage points and the joint one-sided engineering criterion passes under the specified stochastic and coding assumptions. The original figures and frozen tests retain that coding snapshot, with 25 ambiguous answers overall. The supplemental interpretation resolves six EAL codes and leaves 19 answers ambiguous; it does not independently validate assessor accuracy or support an evaluation allocation. Higher summed session time and total acquisition activity remain part of the resource result. The strongest defensible conclusion concerns the implemented workflows, selected tasks and conditional decision measurements; independent coding validation and a prospective broader evaluation remain necessary for stronger claims.

The separate live follow-up adds 128 actual sessions at a configured API estimate of USD 0.0204097. Correct whole verdicts with internally consistent explanations occur in 20/40 facts-only, 30/40 EAL and 33/40 conventional recipient answers; only 1/24 critical-gap answers meets that criterion across contexts. All six ambiguous verdicts retain contradictory explanations and known primary failures. Equal facts and identical EAL/conventional packets separate this diagnostic from the original bundled workflow comparison. They show that correct host verdicts do not ensure correct, consistent communicated conclusions in these constructed cases. One execution of eight purposive tasks supplies a bounded account of these responses, with assessor error and explanation grounding still unmeasured.

## Sources

The original collection is [EAL Actions run 36985062352](https://github.com/emmett08/earl/actions/runs/36985062352), attempt 1, at [revision c0974bc6bb6a](https://github.com/emmett08/earl/commit/c0974bc6bb6a2df30d1423b6248bfc51b4d2a9d7), live run identity `45488cb5-624e-4267-b12c-97fe503ff4d1`. [Finish run 36997861629](https://github.com/emmett08/earl/actions/runs/36997861629), attempt 1, processes the same live run at [revision cea2b59e686d](https://github.com/emmett08/earl/commit/cea2b59e686d57e0c071924f184b497919ec91a7). The archive manifest retains both full revisions and six immutable artefact digests.

The design and processing definitions are the repository's [EAL/3 experiment methodology](https://github.com/emmett08/earl/blob/c0974bc6bb6a2df30d1423b6248bfc51b4d2a9d7/docs/eal3-experiment-methodology.md), [model-transfer workflow](https://github.com/emmett08/earl/blob/c0974bc6bb6a2df30d1423b6248bfc51b4d2a9d7/experiments/model_transfer/WORKFLOW.md), and pinned resource and statistical implementation retained with the analysis. The historical methodology is the design contract. The post-collection [AI coding record](https://github.com/emmett08/earl/blob/cea2b59e686d57e0c071924f184b497919ec91a7/annotations/pilot-36985062352-AI-CODING.md) describes the measurement amendment and its limitations; its scripts, frozen adjudications and hashes are retained in the package.

The additional package records are `reference-unknown-causes.json`, `supplemental-review.json` and `supplemental-analysis.json`. The separate live follow-up retains `protocol.json`, `plan.json`, independent review/rehearsal records, collection run 37023431850, `calibration-qualification.json`, codes and adjudications, `endpoint-summary.json`, `resource-summary.json` and sanitized figure-production inputs. Its collection revision and live identity are stated above. These records remain separate from the original pilot observations and inference. Calibration material was revised after follow-up collection and before participant coding under the unchanged version 2 supplement and threshold; its qualification receipt binds the accepted fourth-version exercise and assessor responses.

The successful [offline finish run 37038229027](https://github.com/emmett08/earl/actions/runs/37038229027) processes those same 128 observations at [measurement revision 777ab4c2f5b0](https://github.com/emmett08/earl/commit/777ab4c2f5b0ed2165d662992db0413d82dde14a). Its imported labels and annotated rows match the audited local records, and its archive preserves the original raw collection without further API attempts. The associated source and reproducibility changes are tracked in [pull request 59](https://github.com/emmett08/earl/pull/59).

Alex Deng, Ulf Knoblich and Jiannan Lu (2018), [Applying the Delta method in metric analytics: A practical guide with novel ideas](https://arxiv.org/abs/1803.06336), provides the methodological context for approximate ratio uncertainty. The run's exact estimator and configuration assumptions are stated above.

Andreas Maurer and Massimiliano Pontil (2009), [Empirical Bernstein Bounds and Sample Variance Penalization](https://arxiv.org/abs/0907.3740), is the declared source of the protocol's bounded quality-uncertainty method. Theorem 11 permits independent bounded variables with differing distributions. Its application here uses whole trajectories and a conservative variance envelope for the unresolved decisions; validity of the resolved AI codes remains a separate assumption.
