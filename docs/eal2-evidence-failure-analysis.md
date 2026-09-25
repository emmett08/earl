# Why the supplied argument and evidence did not reliably help

**Exploratory diagnosis, 23 September 2026.** This analysis uses the [retained 180 model calls](notation-transfer-live-results.md), their exact prompts and responses, and a new [ten-case deterministic intervention](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-evidence-mechanisms/switches.json). The [reanalysis](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-evidence-mechanisms/analysis.json) is computed directly from the response archive. The cases were exposed before this analysis; neither this document nor the intervention is a fresh model evaluation. The [next investigation](eal2-mechanism-experiment.md) is specified separately.

## The claim to investigate

The most useful candidate is **conditional and architectural**: for a declared class of engineering decisions, EAL/2 can help a text-only model *as part of a system* when an independently acquired observation is matched to a typed proposition, the declared method and argument graph are executed outside the model, and the final status is taken from that checked assessment. EAL/2 supplies the inspectable representation and composition interface. Registered methods supply computations, the acquisition process supplies authentic measurements, and the host controls what is finally reported. Whether this complete system improves new decisions, and whether EAL adds value over an equally equipped standalone checker, remain empirical questions.

That claim outranks “EAL syntax makes the model reason better” as a research target because the direct EAL/JSON contrast did not favour EAL and the archived failures concern operations that have executable contracts. It is stronger and more useful than “the checker can calculate”: it identifies the missing bridge between a calculation, eligible evidence, a qualified claim and the reported answer. It is weaker than the original broad claim of general engineering improvement. The [EAL/2 argument](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/arguments/evidence-mechanisms/argument.eal) separates supported finite observations from these unmet outcome claims.

### Discovery record and alternatives

The decision is whether to build and test this combined system for bounded, source-linked engineering assessments. An engineer needs correct qualified status under the *available* evidence, an inspectable reason for refusal, revision when an observation or premise changes, and a report that does not silently reverse the assessment. These needs are linked: a correct calculation of an irrelevant record is not a justified answer.

| Need | Raw argument + text model | EAL/2 + method + checked host | Standalone checker + equivalent wrapper |
|---|---|---|---|
| Express a scoped claim and dependency/attack relations | Partly; the text is present but execution is unverified | Satisfies for the implemented fragment | Unknown; an equivalent wrapper could satisfy it |
| Compute a registered numerical, temporal or graph result | Unreliable on these exposed cases | Satisfies through the *method*, subject to its contract | Satisfies if supplied the same method |
| Reject a mismatched or stale record | Unreliable in this recipient diagnostic | Satisfies declared correspondence and freshness on the tested cases | Unknown until the wrapper implements and passes the same checks |
| Authenticate the measurement and the natural-language-to-formal translation | Unknown | Unknown; not supplied by EAL syntax, digests or the method | Unknown |
| Export the assessed status faithfully | Unreliable even with some supplied conclusions | The existing host `finish` takes statuses from the assessment | An equivalent host can do so |
| Improve new real engineering decisions at acceptable cost | Unestablished | Unestablished | Unestablished |

The notation is an **interface and assurance** contribution; the registered calculation is **inherited** from a method; acquisition and domain modelling remain external. An equal-capability checker/wrapper is the strongest rival. A reduced proposal is the checker plus a small scope/status schema, without EAL's general argument graph. The outcome comparison must count engineering errors, qualification and cost, not only final labels.

Three root candidates survive with different burdens: (C1) the combined system performs the named finite operations on exposed fixtures; (C2) it improves a new model recipient's qualified decisions over raw evidence; (C3) the EAL representation and composition add measurable value over an equal checker/wrapper. C1 is supported in its small domain by existing and new deterministic experiments. C2 and C3 are live, non-dominated outcome questions, not consequences of C1. Removing C1 removes the feasibility premise for C2. Reversing scope, binding, dependency or polarity discriminates C1 from an affirmative assertion. C3 requires an active comparator, and an observed tie would leave integration possible but defeat superiority. The discovery handoff to a warrant-level reconstruction is C2 as the primary *empirical* target, with C3 as the specific EAL contribution test; either may be narrowed or rejected.

## What the model responses actually show

All figures below describe GPT-4.1 nano `gpt-4.1-nano-2025-04-14` at temperature zero, five exposed task types, two dependent repeats, one response and no tools, with a common reference of roughly 49,000 characters. Each arm has ten attempted answers. The main scorer requires exact requested statuses and the JSON output contract. Two repetitions of a task do not provide ten independent problem types. An always-`supported` map happens to get 6/10 of the raw-only tasks right, so the 4/10 EAL and 5/10 JSON scores cannot be sold as improvement over a trivial task prior.

| Input to recipient | EAL complete correct | Equivalent JSON complete correct | What it can establish |
|---|---:|---:|---|
| Raw records, no proposal | 4/10 | 5/10 | No observed notation advantage in this finite contrast |
| Incorrect proposal only | 0/10 | 2/10 | Baseline for injected wrong labels |
| Incorrect proposal + relevant raw records | 2/10 | 5/10 | Some corrections, many residual errors |
| Incorrect proposal + records + interpreter conclusions | 7/10 | 8/10 | A computed assessment helps more than raw records here; it is answer information |
| Correct proposal only | 10/10 | 9/10 | Preservation of supplied labels, not grounding in records |
| Correct proposal + relevant raw records | 2/10 | 7/10 | Raw material can damage already correct statuses |

For a paired intervention, the net correctness change is the fraction wrong→correct minus the fraction correct→wrong. Looking only at a pooled success rate obscures both. In the EAL answer-only arm the model copied all 20 proposed label maps, including ten deliberately wrong maps; with raw records it stopped copying most wrong proposals but did not reliably compute the right statuses. Adding the information changed behaviour without making the required decision operation reliable.

There are two reference questions. **Full-information agreement** asks whether a final label matches the original task's complete record. **Available-information support** asks whether the *records actually supplied in that arm* license it. An answer-only arm can agree with the full answer while having no evidential basis. In the irrelevant-record arms, 3/40 attempts were available-information correct and 26/40 admitted responses contained false support under that reference. A true but unrelated reading is not support for this assembly.

| Archived behaviour | Required operation | Why “more evidence” is insufficient |
|---|---|---|
| `trial-00020` reads origin `0.1`, calculates RMS ≈0.3536 about zero and returns `supported` | Require query origin `0` to equal the input origin before using the number | Correct arithmetic on the wrong query is not a result for this proposition |
| `trial-00050` notices the defence premise is the very claim under attack, then returns `supported` | Evaluate the grounded dependency/attack cycle | Merely enumerating edges does not license a self-grounding defence |
| A sampled trace contains a value above the bound, yet raw EAL misses both negative-finding repetitions | Compute `holds == false` and map that to support for the *violation* claim | The polarity of a method result and the polarity of the claim differ |
| `trial-00147` calls records for another assembly a match | Check provenance/context equality before considering measurement values | Plausible values are not interchangeable observations |
| `trial-00023` reads the interpreter's `unsupported` conclusion but reports `contested` | Preserve the exact assessed status at the output boundary | Even a supplied answer can be reinterpreted or copied incorrectly |

These are observed outputs and task contracts, not a window into model internals. Incorrect calculation, attention to salient values, incomplete semantic understanding, instruction conflict and distributional priors can produce overlapping outputs. The long common reference and token placement are plausible contributors but were not independently manipulated. Eighteen strict-schema failures and one output-limit failure further mix task reasoning with response-contract compliance; the exploratory claim-map-only scoring does not rescue a raw EAL advantage (4/10 versus 6/10 JSON).

## A causal account to test, not an asserted psychology

Supplying source text adds *information*. It does not install a parser, binding check, numerical method, grounded argument solver or trustworthy output gate in a text-only recipient. The model must first select the right facts, then check admissibility, perform the declared method, compose attacks and premises, map the result to the precise proposition, and emit the status. An attractive reading can bias an early step even while another step has the right number. Failures at any one stage can make more raw context reduce accuracy. The original relay's 12/12 evidence versus 8/12 answer-only comparison had **zero initially wrong producers** and measures prevention of degradation, not repair of wrong answers.

This account is consistent with research on unfaithful explanations ([Turpin et al.](https://arxiv.org/abs/2305.04388)), difficulty locating reasoning mistakes even when correction is possible ([Tyen et al.](https://arxiv.org/abs/2311.08516)), and systems that let an interpreter execute generated steps ([Gao et al., PAL](https://arxiv.org/abs/2211.10435)). Those studies motivate interventions; they do not explain these EAL trials by themselves. Context-faithful prompting can improve some contextual tasks ([Zhou et al.](https://arxiv.org/abs/2303.11315)), so the correct conclusion is not that prompting can never work.

| Live rival | Intervention and distinguishing observation |
|---|---|
| Eligibility/binding is the bottleneck | Hold values fixed while changing only origin, assembly, freshness or source identity; raw responses fail to flip while a verified binding result and checked host do flip |
| Method or graph execution is the bottleneck | Hold eligibility fixed, change only one edge, defence dependency or violating sample; an independently checked method result improves over raw and mere field extraction |
| Proposal anchoring drives the result | Cross correct, wrong and absent proposals against the *same* records; correction and damage change sharply with proposal status after eligibility is controlled |
| Representation or context load dominates | Match information, length and location while varying compact/full reference and EAL/JSON/plain wording; effects follow length/position or surface form across task families |
| Final answer copying is the remaining bottleneck | A verified verdict is visible but free responses still reverse it; host-owned finish eliminates those reversals without altering earlier acquisition/method errors |
| Source or translation is wrong | A counterfeit but internally coherent observation or mistranslated formal proposition passes internal checks; independently validated acquisition/translation detects it |

The new [switch experiment](../scripts/experiment_evidence_switches.py) held original exposed fixture values fixed where possible and changed one decisive feature in each pair: a circular versus independent defence, origin `0.1` versus `0`, a violating versus non-violating sample, a matching versus other assembly, and fresh versus stale observations. The interpreter matched ten independently specified statuses in ten cases and flipped each pair as predicted. This establishes that the installed operations can express these particular distinctions. It is not a ten-call LLM improvement, independent confirmation, physical authentication or proof that EAL is better than a checker with the same rules. The previous [finite-graph companion study](eal2-companion-investigation.md) likewise found 48/48 computed graph statuses against a separate bounded oracle versus 24/48 affirmative authored statuses, while a counterfeit graph exposed the source-truth boundary.

## Engineering route and next decision

For the next bounded system, an operator should obtain and validate observations independently, have a model draft or revise the EAL question and argument where appropriate, execute the registered method and binding checks in the host, and let the host return the exact assessed statuses with evidence IDs, failed predicates and source/version identity. Existing `eal-agent` has a stateful `assess` and a `finish` operation that takes statuses from the latest server assessment; the present prompt-only diagnostic did not use it. A free prose explanation may accompany the result but must not silently change the status. Each boundary needs a test: source authenticity and formal translation upstream; eligibility and computation in the interpreter; faithful reporting downstream.

The next live study must compare raw EAL, equivalent JSON/plain material, targeted intermediate feedback, full verified assessment with free response, host-owned final status, and an equally equipped checker/wrapper on **new** problem instances. Include correct and deliberately wrong proposals, wrong-scope values, authentic and counterfeit sources, plus strict and label-only scoring. Freeze independent reference answers, cluster by newly authored task, and report correction, damage, false support, abstention, cost and contract failures separately. If only host execution helps, the result supports an external-work allocation account; if EAL and the standalone wrapper tie, the EAL-specific comparative claim remains unestablished. If neither helps on new cases, revisit the translation and source-validation bridge before adding more syntax.

Reproduce the new analyses from the repository root (the switch runner refuses to overwrite the retained result):

```sh
python scripts/analyse_evidence_mechanisms.py --output /tmp/eal-mechanism-reanalysis.json
python scripts/check_evidence_mechanisms_argument.py
python -c 'from scripts.experiment_evidence_switches import run; print(run()["passed"])'
```

The last command re-executes the ten fixed synthetic cases in a temporary workspace; it prints `10`. No provider is contacted. The new live protocol has not run: no provider credential is available in this working environment. Its results must be reported separately from these post-outcome and deterministic observations.
