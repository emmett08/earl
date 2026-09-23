# Negative findings as executable EAL/2 objections

**Developmental experiment, 23 September 2026.** The [retained result](../benchmarks/results/2026-09-23-negative-revisions/lifecycle.json) comes from the [reproducible runner](../scripts/experiment_negative_revisions.py), two [authored EAL/2 arguments](../arguments/negative-revision/) and the optional [registered method](../src/eal/sampled_negative.py). It contains **20 deterministic synthetic states and zero model calls**. The independently stated expected status and a small separately coded reference checker agree with EAL on all 20; the runner also checks the method and objection states. These are exposed development cases, not independent engineering tasks or evidence of a population effect.

## Which claim is worth testing?

The user's practical decision is whether EAL can materially improve responses to engineering questions when an observation later contradicts an initially plausible answer. The most promising bounded claim is: **a reviewed EAL/2 specification, a verified observation and a host-owned assessment can make an adverse finding retract a previously supported status and restore it when the finding loses eligibility, without asking a tool-free model to carry out the graph calculation in prose.** This is a hypothesis about a combined system, conditional on faithful formalisation and acquisition. The strongest rival is a general checker and host with the same binding, method and attack semantics. An equally capable checker should match final statuses on the same formalised cases; a distinctive EAL benefit would have to appear in making and maintaining the specification, trace or workflow.

Three different candidate claims have different burdens:

| Candidate | What the present experiment says | Remaining test |
| --- | --- | --- |
| A bare EAL argument improves a tool-free model's answer | The [180-call archive](eal2-evidence-failure-analysis.md) does not show that effect on five exposed task types | New roots with equivalent EAL, JSON and concise prose presentations |
| Checked EAL/2 plus registered methods and host handles adverse evidence | This implementation changes the specified finite statuses in 20/20 developmental cases | Prospective model-only versus checked-host contrast on independent briefs and sources |
| EAL adds substantial value beyond an equal checker | No such effect is measured by these cases | Equal-capability authoring, revision, tracing, time and cost comparison |

The research [literature synthesis](eal2-negative-evidence-research.md) gives a reason to test this direction: formal defeat can help with multi-step conflict, while translation into a formal representation and judging whether an absence claim has complete coverage remain serious error sources. These studies do not establish an EAL-specific advantage.

## What the 960 calls would and would not show

The earlier [specified protocol](../benchmarks/protocols/INV-EAL-MECHANISMS-001.json) proposes **24 task roots × 10 content arms × two EAL/JSON presentations × two reference lengths = 960 one-shot calls** to a pinned model. It would measure answers conditional on *already reviewed EAL/JSON specifications* and selected synthetic records. The arms vary correct/wrong proposed labels, applicable/inapplicable raw records, an eligibility memo, a method result, a full assessment and a bare invalid verdict. They could show correction, degradation, false support, copying and whether a particular prompt rendering matters on those roots. Its 192 additional EAL/standalone runs are deterministic system comparisons, not model calls.

Even 960 calls do not mean 960 independent problems: the roots are the principal case units. The design does not determine a hidden model cognitive cause from public answers. A model can copy the computed status without validating its provenance. A favourable full-assessment arm would primarily show that a checked tool and host performed work the raw-recipient arm did not. The same gain could be obtained by an equal checker. The design does not test whether a model or engineer can translate an ordinary brief into the correct formal argument, or whether a non-detection finding has adequate coverage. A null result could reflect translation, prompt burden, task choice or the absence of a benefit. No possible outcome of that factorial alone proves that EAL has a unique advantage.

The narrower [96-call staged pilot](../benchmarks/protocols/INV-EAL-NEGATIVE-REVISION-001.json) now specifies the missing discriminator. Stage A uses eight **new multi-route** roots, a valid adverse finding and its invalidated variant under two comparable text presentations: 48 model calls, plus paired EAL/equal-checker runs. Stage B starts from eight independent ordinary briefs and makes the same model draft and revise EAL or an equal-capability reusable graph through three changes: 48 more calls. It scores brief-to-formal fidelity, revisions, exact status reversals, false support, trace, effort and cost. It is a specified pilot with an early validity gate, **not an executed study or a guaranteed effect**.

## The concrete repair and the 20 states

The existing `temporal/1` method reports one violating value on a partial trace but returns `unsupported` because endpoints or gaps fail its complete-sampling condition. The retained ablation records `violation_count: 1`, `coverage: false`, `status: unsupported`. A witnessed counterexample to a **sampled** universal needs the observed point, not coverage of every other point. Conversely, an empty or partial search must not establish a no-violation finding.

The optional `engineering/sampled-negative/1` contract separates these tasks with a bound `mode`:

- `counterexample`: a correctly typed, in-window violating observation returns a positive finding even on a partial sampled trace. Without a witness, execution is `unsupported`.
- `non_detection`: a positive finding requires sampled endpoint and maximum-gap coverage, no reported violation, a documented detector limit below the declared maximum, and a documented sensitivity lower bound above the declared minimum. Incomplete coverage, an observed violation or inadequate detector metadata makes execution `unsupported`.

Both successful outputs use `finding == true` for the *specific mode fixed in the typed proposition*. The method never returns a false finding that an author could invert into a broad absence claim. Calibration and record metadata are **supplied assertions**, not authenticated measurements. A 0.9 lower sensitivity bound still permits misses. The conclusion is restricted to a qualified sampled search; it does not assert a continuous-time invariant or physical absence.

The [counterexample argument](../arguments/negative-revision/counterexample.eal) has two alternative positive test routes and a typed negative claim. Each route has its own objection whose premise is that negative claim. The positive test records declare matching subject, scope and bound; a separate purported defence is also checked for matching scope and sample time. These fields check correspondence, while the substantive test-to-property and defence-to-violation warrants remain authored. The [closure argument](../arguments/negative-revision/closure.eal) makes the qualified non-detection claim a required premise of a provisional decision.

| Sequence or control | Expected and observed status | What it probes |
| --- | --- | --- |
| Tests, then partial in-scope violating sample | `supported → contested`; negative claim `supported` | Witness can activate objections despite incomplete sampling |
| Same witness for another scope | `contested → supported`; negative claim `unsupported` | Typed question correspondence |
| Partial trace with no violation | Negative claim `unsupported` | Failure to find a witness is not a negative certificate |
| Independent asserted defence, then withdrawal | `contested → supported → contested` | Declared objection and defence updates, subject to the authored warrant |
| Remove the challenge to only one positive route | Parent stays `supported` | A negative claim does not silently attack a surviving route |
| Both positive tests name another bound; wrong sample in defence | Positive test claim `unsupported`; or defence does not restore it | Value and defence correspondence controls |
| Complete no-violation sampled search, then partial, wrong-scope or weak detector | Qualified claim `supported → unsupported` | Query-relative sampled coverage and detector checks |

The exact 20 rows, hashes, claim statuses, method statuses, binding statuses and objection statuses are retained in the result JSON. A small independent checker written for these two fixed graph shapes matches the explicit oracle and EAL for all rows. It is **not** an equal general-purpose graph checker or evidence of an EAL advantage. The optional method's focused unit tests exercise boundary values and fail-closed cases separately.

## Why the bare argument has disappointed

The archived model could sometimes name the relevant value yet return the wrong polarity or graph status. The argument and raw record required it to choose a source, match subject and query, perform a method, propagate objections and report a precise final status. Additional text made those tasks available but did not execute them. The earlier 180 calls show output failures, not direct access to the model's internal process. Here the registered method computes the finding, the EAL solver updates named objections, and the host can take the assessed status as the final status. Translation, source authenticity and the authored warrants remain explicit limits.

The decisive next observation would be a **paired gain on new briefs**: fewer unjustified supported answers and correct support–contest–restore transitions versus a model-only recipient, with no unacceptable increase in false abstention. If a generic checker ties EAL on statuses, the hybrid route remains useful, while an EAL-specific claim depends on lower formalisation/revision error or effort. If model-authored arguments omit attacks or mistranslate the queried bound, the formal checker will faithfully execute the wrong question; that outcome would direct work to authoring and source review rather than more syntax.

Re-run the deterministic result from the repository root without overwriting it:

```sh
python -c 'from scripts.experiment_negative_revisions import run; r=run(); print(r["passed"], r["total"])'
```
