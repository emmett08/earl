# Architecture argument: whole–part review

## Question, scope and reading

The source [`architecture.eal`](architecture.eal) asks whether a fixed notification-service change uses the existing extension point while satisfying the recorded feature and byte-limit checks. Engineer 1's proposed mechanism is specific: `NotificationService` dispatches once through a `Channel` strategy selected by a registry; a channel prepares a payload; a `Gateway` performs the delivery side effect. This division gives medium preparation, dispatch and delivery separate responsibilities, with dependencies expressed through protocols. Adding a channel in the composition root extends the supported variation without a second public route. A requirement that cannot be expressed through `Channel.prepare` calls for a review of the shared contract and its callers.

The treatment argument was authored and frozen before the B implementations (SHA-256 `00b36bcd1704eeb4532c01cac357cfb7b97ab604a97cd040d44515d7969d8a53`). It sets criteria; its statements about a future report become supported only after compatible observations are collected. The later [`observed-results.eal`](observed-results.eal) adds control comparison and was never supplied to a coding agent. The measured episode is the local fixture in [`PROTOCOL.md`](PROTOCOL.md). The B treatment and control share the completed A snapshot and B brief; only the treatment receives the frozen EAL source. Their fresh agent sessions differ, so a single pair cannot identify a general causal effect of EAL exposure.

## Dependency and evidential status

| Claim and source | Grounds and inferential role | Recorded status and limit |
| --- | --- | --- |
| `extension_point`, both sources | Baseline contract check and the authored account of `Channel`, registry, `NotificationService` and `Gateway` | Supported within the fixture. The Boolean check alone does not establish the best architecture for a real provider. |
| `reported_checks_pass`, both | Conjunction of eight named B-treatment findings; the fixed `all_tests` aggregate also includes the ninth email-regression check | Supported. `strict` denotes only the formal conjunction of report fields; each observed field remains a fallible ordinary premise. |
| `architecture_within_fixture`, both | Baseline interpretation and reported checks | Supported in this snapshot. AST and call-count checks are syntactic; import coverage is not dead-code analysis. |
| `treated_dispatch_check_passed` and `treated_dispatch_check_failed`, both | Opposite predicates over the **same** treated single-dispatch observation | The passing claim is supported; the failure claim is unsupported. Their directed `contrary` relates report verdicts, not a diagnosis of a duplicate dispatcher. |
| `control_dispatch_check_passed`, `local_check_tie`, post-run | Control verdict, aggregate results, equal A snapshot and equal B brief | Both supported; both B implementations passed all nine fixed checks. This is measured parity on a finite outcome vector, not proof of general no effect. |
| `local_check_advantage`, post-run | Conditional route requiring a treated pass and a control failed check | Unsupported: the control passed. Its absence is a reported result, not suppressed contrary evidence. |
| `eal_caused_check_advantage`, post-run | Conditional advantage plus a possible prompt mechanism | Unsupported because there is no advantage premise. Unrandomised assignment and unblinded review independently object to causal attribution. |
| `future_debt_reduced`, both | Snapshot architecture and the single-path maintenance mechanism | Contested in the authored evaluator; the formal prediction route is defeated by the observed absence of longitudinal follow-up. No technical-debt reduction is measured. |

`structured/1` records authored relevance and dependency. It does not prove the English warrants. Ordinary EAL reasoning and opt-in `compile-aspic` can return different statuses because only the latter applies the reviewed strict and contrary relations. The `reviewed` references identify the asserted relation for inspection; they do not authenticate evidence or make the relation true.

## Counterexamples and unresolved rivals

A second dispatcher can pass functional tests yet introduce an independent change path. The fixed single-dispatch check addresses a narrow syntactic version of that failure. Code that imports during a probe may still contain unused functions; the source does not infer that all code is live. A real provider might require retries or security controls that no longer fit the baseline protocol, and an extra adapter may be justified rather than overengineering. Those last two judgements have no credible automatic check in this fixture and remain explicit review questions, not invented Boolean evidence.

The plain `ARCHITECTURE.md`, code and tests exposed the same extension point to both B agents; this is a rival explanation for the observed parity. Session-to-session variation could still mask either benefit or harm. Repeating paired tasks with randomised sessions and blinded review would address attribution; applying further changes and measuring duplicate sites, rework and modification effort over time would address the debt prediction. Each outcome must be interpreted within its recorded source, observation snapshot, context, assessment time and compiler profile.

## Hermeneutic disposition

The design rule, measured check conjunction, snapshot assessment, paired parity, causal account and future prediction are separate claims. Their scope narrows in that order. Reading each against the whole exposes two qualifications that must not disappear in the paper or graph: the check names do not establish global code quality, and paired parity does not measure later technical debt. The contrary single-path verdict is represented even though its failure premise is unavailable in this run; the potential need to revise the protocol remains a human review question. The source, protocol and paper should use the same meanings for *extension point*, *single path*, *module import* and *future debt*.
