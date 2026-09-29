# AI assessment of the retained principal pilot

The user authorised AI labelling on 28 September 2026 after collection and masked
export. This is a post-collection measurement amendment for the existing pilot,
not a prospectively registered human assessment. Collection remains protocol
6.0.0; the offline processing package is 2.18.1. No collected answer, assignment,
request receipt, plan, or collection budget is changed. Do not resume collection
under the changed implementation digest.

Source collection: run `36477862213`. Masked export: run `36487342999`, full
artefact `10998924773`. The assessment contains 4,224 exported answers. The
annotator is OpenAI ChatGPT/Codex; its exact serving model identifier is not
exposed. No additional provider requests were purchased for coding.

The coding input is only `annotation-bundle/items.json`. Assignment mappings,
reference decisions and outcome reports are excluded during coding. Answer text
can itself disclose a workflow. Prior project context is available to the AI,
so this is masking of record metadata, not a claim of complete assessor blinding
or statistical independence from the evaluated models.

## Coding procedure

Use the exported rubric: code the decision explicitly communicated, rather than
its correctness. `ready`, `not_ready`, and `undetermined` are separate categories.
Do not replace a mistaken conclusion with a decision calculated from task facts.
Component-route statements, past assessments, general rules, negated categories
and hypothetical future outcomes are distinguished from the current overall
conclusion. A stated correction followed by an explicit final assessment can
resolve an earlier statement. Competing current conclusions without such a
resolution receive `ambiguous`. Qualified wording such as "not fully ready" can
communicate `undetermined` when the answer explicitly withholds a current verdict.
The literal code `not_ready` is not equated with `undetermined`.

`scripts/code_pilot_annotations.py` applies AI-authored rules to straightforward
statements and flags unresolved wording. The AI inspected all 214 flagged
answers in full and made answer-specific adjudications. A separate comparison
against the first stated category found seven further cases, including three
incorrect rule candidates; those seven are recorded as adjudications too.
An adverse check inspected the undetermined clauses of 86 otherwise definitive
candidates and found one further conflicting current conclusion, also recorded.
Additional checks examined negative clauses in affirmative candidates and
negative-category clauses in undetermined candidates. These checks improve this
coding pass; they are not an independently measured accuracy estimate.

The labels retain every original item ID and answer, an exact supporting excerpt
(the complete answer where context is necessary), a coding note and assessor
provenance. The script and adjudication-file hashes are recorded alongside the
masked source-file hash. Reproduction uses no reference data:

```bash
python scripts/code_pilot_annotations.py /path/to/annotation-bundle/items.json \
  annotations/pilot-36477862213-ai-adjudications.json /tmp/reproduced-labels.json
```

## Interpretation and continuation

This is AI-assisted rule coding with AI semantic adjudication. It is not 4,224
independent model calls and is not human validation. Errors can be shared across
answers and with the evaluated model family. Task correctness is scored separately
by the existing reference implementation after labels are frozen. Unknown scores
and their bounds remain in the analysis. Processing completion does not imply a
supported allocation or a completed confirmatory investigation.

Use **EAL experiment → finish**, selecting the branch containing these changes,
source artefact `10998924773`, and labels path
`annotations/pilot-36477862213-ai-labels.json`. The wrapper imports labels,
recomputes analysis and runs the allocation planner without model calls. A new
paid evaluation remains a separate decision. Independent human validation and an
assessor-error sensitivity analysis would strengthen any substantive conclusion.

Methodological basis: Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and
Chatbot Arena*, NeurIPS 2023, https://arxiv.org/abs/2306.05685, documents judge
biases. Its results do not validate this coding method or establish its error rate.
