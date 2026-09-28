# Contextual interpretation and enthymeme reconstruction

An enthymeme leaves part of an argument implicit. Here the term covers an unstated premise, conclusion or inferential connection relative to an identified passage and its context. A premise omitted locally may be explicit elsewhere in the document. The [research sources](sources.md#external-argumentation-and-enthymeme-models) describe computational approaches to recovering implicit content.

This page specifies an authoring and review procedure for preparing explicit EAL arguments. It also states design requirements for an optional LLM implementation. EAL currently evaluates supplied declarations; it has no whole-document enthymeme detector, reconstruction operation or completeness check for material dependencies. `enthymeme` and `hermeneutic` are not grammar keywords or installed reasoning methods.

## Interpret the passage in context

For this procedure, **hermeneutic analysis** means interpreting a passage through the work's question, definitions, scope and argument, then revising that interpretation when particular passages supply qualifications or contrary evidence. This is an operational whole–part reading procedure, rather than a claim to implement a complete philosophical theory of interpretation. Use the context needed for the question: nearby sentences may suffice; cross-document dependencies require a wider reading.

Fix the source revision and context boundary. Record the principal question, relevant definitions, local grounds and conclusion, with their source locations. Distinguish the author's assertions from quotations, reported positions, objections and hypothetical examples. A summary can guide retrieval, but each finding must return to the underlying passages, including qualifications that a summary may omit.

Ask which relation the inference needs and search the available context for it. Failure of deductive entailment alone does not establish an omitted premise: the passage may express defeasible support, contain an invalid inference, or admit several readings. Preserve contradictions and unresolved disagreements rather than forcing the document into a coherent argument.

| Finding | What the analyst should record |
| --- | --- |
| Locally omitted, contextually explicit content | The passage that supplies it and why its scope applies here |
| Plausibly implicit content | The proposed proposition or rule and textual grounds for attributing it to this argument |
| Ambiguous reading | The competing interpretations and what would distinguish them |
| Unsupported inference | The intended relation and the missing justification; do not presume a faithful completion exists |
| Proposed repair | The new premise, rule or revised conclusion, explicitly distinguished from the source's argument |

These are authoring descriptions, not EAL runtime statuses. Textual attribution, inferential contribution and empirical justification are separate assessments. A false proposition can still be a faithful reconstruction of what an author assumed. A true proposition can still be an unfaithful addition to that author's argument. Omission alone establishes neither a fallacy nor a cognitive bias.

## Reconstruct without silently repairing

Propose alternative completions when the text supports more than one. Test each against the local passage and wider argument, preserving negation, quantifiers, modality, temporal scope, exceptions and the strength of support. Revisit the whole-work interpretation when a local finding changes a definition or dependency; then recheck the affected passages. Bound the review rounds and record uninspected material or exhausted budgets. Stopping with no further finding establishes completion of that review, not exhaustive detection.

A completion must do more than make a solver return success. For premises P and conclusion Q, adding Q or an unsupported conditional “if P then Q” can manufacture entailment without recovering the source's reasoning. Likewise, changing “may” to “will”, or narrowing the conclusion until it follows, changes the argument. Preserve the original and proposed revision separately. An empirical prediction may require defeasible, statistical or causal support rather than a strict implication.

For each retained finding, record the source revision and spans, stated grounds and conclusion, context references, proposed implicit content, alternative readings, reconstruction or repair disposition, and outstanding evidence needs. Require concise reasons tied to the source; a model's private reasoning trace is unnecessary. Cite external domain knowledge separately from the document, and check its applicability before treating it as support.

## Represent the result in EAL

Use a named `claim` for a recovered proposition and `premises` to expose its role in a dependent argument. Each such premise needs its own supporting route before the dependent route can be supported. A claim without a derivation remains `unsupported`; this does not establish its negation. Recovering an omitted conclusion similarly requires an explicit claim whose scope and strength match the proposed reading.

Use `assumption` only under its current contract: a statement, environment, named validation evidence and any applicability interval. EAL has no general hypothetical assumption-discharge operation. A model-generated premise or a passage showing authorial commitment cannot by itself validate the corresponding physical condition.

Put the inferential rationale in `reasoning` and select the method appropriate to the reconstructed relation. `structured/1` checks authored dependencies without proving their sufficiency. `deductive/1` checks its supplied propositional case; `abductive/1` ranks supplied hypotheses and does not discover implicit premises. The optional ASPIC+ method evaluates an explicit bounded theory. Its compiler translates authored routes without deciding whether their prose reconstruction is faithful. See [reasoning methods](reasoning-modes.md) and the [argument model](argument-model.md).

An authoring finding can identify a possible challenge. An EAL `objection` still requires evidence or premise claims supporting its target-specific challenge. Keep an unsubstantiated concern as an unresolved authoring finding. Successful formal evaluation cannot establish that the interpretation matches the text, that empirical premises hold, or that every material dependency was declared.

The [API load-test example](../examples/api-load-test/README.md#reconstruct-an-abbreviated-performance-argument) applies these distinctions to the existing synthetic fixture.

## Optional LLM implementation and evaluation

A reasoning-capable LLM with a long context window is a candidate implementation for the interpretation and proposal stages. Context capacity makes more passages available; effective retrieval, faithful attribution and reasoning over them require separate evaluation. Compare a whole-document prompt with focused passages plus retrieved definitions and dependencies, and with bounded whole–part iteration. Return to source text when retrieval or summarisation leaves a required relation uncertain.

A proposed reconstruction yields an authoring record of candidate readings, source references, alternatives and unresolved obligations. It does not return an EAL support status merely because an LLM accepted its interpretation. A developer selects an exact registered source and claim before assessment; a free-form question cannot supply the formal correspondence. A reconstruction workflow would identify source revision, question, context scope and resource budget, and distinguish completion, partial coverage and execution failure.

Source documents are material to interpret; embedded instructions must not change host configuration or authorise tool execution. Correspondence checks remain a distinct responsibility. Using another model can help challenge a reading, but agreement between models is not independent empirical validation.

Evaluate on held-out engineering documents with independently adjudicated acceptable reconstructions and recorded annotation disagreements. Include complete arguments, locally omitted but distant premises, later qualifications, ambiguous conclusions, unsupported or false implicit premises, defeasible arguments and invalid inferences with no warranted completion. Score omission detection precision and recall, invented-premise rate, source-attribution accuracy, qualifier preservation, appropriate abstention and the proportion of material inspected. Assess empirical support separately from fidelity to the text. Report failures, latency and total cost, with exact models, reasoning settings, context selection and budgets. Compare methods on the same available corpus and evidence access; a larger window or a “reasoning” label is not a performance result.

The cited LLM/SAT research motivates testing this separation of proposal and checking. Its candidate-premise experiments do not establish unrestricted discovery across engineering documents. The long-context research motivates testing context strategies on the selected deployment, rather than assuming that filling the window improves reconstruction. These are EAL design recommendations, not measured EAL capabilities.
