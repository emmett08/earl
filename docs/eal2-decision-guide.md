# When to use the reviewed EAL/2 route

**Implementation cut:** package 2.5.0, 24 September 2026. The language parser,
interpreter and method registry implement a bounded argument computation. The
reviewed recipient route makes one recurring question discoverable to a model
and lets a host return a checked claim packet. It is a tool and evidence
handoff, not an increase in the model's intrinsic reasoning ability.
Authenticated live observations in the decision table are a deployment
requirement; the repository's synthetic JSON fixtures do not satisfy it.

## Decision rule

| Situation | Use | Why |
| --- | --- | --- |
| A recurring question has an independently reviewed claim, finite typed bindings, an exact approved wording, a pinned source and method registry, current authenticated evidence, and a caller grant. | Reviewed EAL/2 recipient route, with a host-owned status; use RAG only for advisory candidate discovery. | The host can reproduce the scoped status, surface defeaters and refuse a changed question or incomplete collection. |
| The task is a new paraphrase or a new tuple; no reviewer has established correspondence to a claim. | Obtain review and register a new applicability entry before using the route. | Similarity ranking cannot decide whether the formal claim answers the wording. |
| The answer is a simple lookup, extraction or formatting task with no argument, objections or repeated evidence transitions. | Direct model or a typed JSON tool, with the same evidence checks where needed. | EAL authoring and review add cost without a demonstrated benefit. |
| The task needs open-ended causal discovery, authenticated live-world truth or an unlisted engineering defeater. | Domain investigation and trusted data acquisition first. | An authored graph can omit the critical fact; a matching digest authenticates neither its producer nor its meaning. |

The route resolves the **launcher's exact UTF-8 question** against the reviewed
task catalogue. The model need not know an opaque task ID and cannot change
the task, source, context, claim, grants or assessment ID. An optional BM25
index, reviewed alias list or compatible host-supplied vector query retrieves
candidate family snippets within grants. Its suggestions do not authorise an
assessment. The server then collects the selected claim's evidence closure,
checks its typed records and returns a compact status; the model may ask for
the addressed trace and write an explanation. The host retrieves the stored
status again after that prose. A provider adapter translates this same bounded
request/result contract to plain text JSON, structured JSON or native function
calls. The Responses adapter can carry stateless reasoning items through the
function handoff; text models can use the same host without native calls.

## What the evidence currently says

Historical exposed-task comparisons in this repository found JSON ahead in
several bounded contrasts. In the 180-call notation diagnostic reported in
the README, raw-only correctness was 4/10 for EAL and 5/10 for equivalent JSON;
correction of a wrong proposal with raw observations was 2/10 and 5/10;
adding interpreter conclusions yielded 7/10 and 8/10. These small, exposed
counts do not estimate performance on new tasks. None measured this reviewed
RAG route.

The earlier 48-call artefact pilot ran on four exposed synthetic roots: raw
EAL was exact in 3/12, derived JSON in 8/12 and the checked packet in 10/12
states. Its derived JSON arm was not the independent checker now used here.
The 96/960/nominal-800 deployment designs remain unrun. These are different
cohorts and endpoints, so their fractions should not be pooled.

The new synthetic, fixture-author preflight has **14/14 EAL–JSON parity** in
checked status, while **10/14** pairs align with the corpus's original
brief-level status. In four cases both routes refuse stale or future records
that the old oracle treated as a decision. This is parity under the new
complete-collection policy, not 14/14 status accuracy or EAL superiority. Two
of the four are inactive objection/defence records: requiring all closure
records protects against missing adverse monitoring but can also reject a
decision that a less conservative status-dependent policy would make. The
policy and its availability cost need independent domain review. The candidate
RAG index has local contract tests; it has no independently measured retrieval
recall or model outcome gain. A separate local
nine-query, fixture-author retrieval diagnostic gave BM25 and the existing
lexical index the same **6/6 target recall at rank one**, **2/3 false
suggestions** on decoy or no-target queries and **1/1 abstention** on an
unrelated query. This is no observed BM25 gain and no semantic-vector test.
No live OpenAI result should be inferred from either offline preflight.

## What must improve to exceed a matched JSON baseline

1. **Review and acquisition.** Authenticate reviewers, approvals, source
   revisions, observation producers and task principals; pin source, graph,
   method, exact question, object identity and observation cut. Define which
   events invalidate an assessment. Complete-collection refusal is currently
   conservative; revise evidence obligations only after checking that an
   absent adverse monitor can never produce false support.
2. **Applicability and retrieval.** Build a labelled, held-out set with new
   exact questions, paraphrases, decoys, ambiguity and no-target queries. Rank
   reviewed family candidates with BM25/vector methods, measure recall,
   precision, leakage and abstention by family, and route a paraphrase only
   after a reviewer approves the semantic mapping. A RAG result alone never
   changes the exact-question gate.
3. **Reasoning and explanation.** Add independently reviewed claim graphs,
   objections, required evidence and human-scored explanation references for
   mechanisms where a checked argument is useful. Test restoration and
   contradiction transitions, missing/stale/replayed evidence, wrong object
   identity and source drift. Score the model's prose separately from the
   host's status. A model copying a packet is delivery fidelity, not an EAL
   reasoning improvement.
4. **Paired evaluation.** Give EAL/2 and an independently implemented JSON
   checker the same question, evidence, grant, graph semantics, tool access,
   repair allowance and context budget. Freeze examples and scoring before
   calls. Compare raw graph/source reading, checked result delivery, candidate
   retrieval, and authoring as separate arms. Randomise order and measure by
   independent task root; repeated states within a root are correlated.
5. **Success and cost.** The repository's prospective EAL-specific target is
   an upper 95% bound below **0.80** for EAL/equal-graph JSON provider-model
   tokens per correct qualified decision after source creation, two revisions and ten
   isolated same-scope recipients; an upper 95% bound below **0.02** for the
   EAL-minus-JSON false-support risk difference; and no worse than its
   prespecified absolute accuracy floor. Freeze that endpoint and report
   paired uncertainty by independent root, every refusal and failure. Count
   model tokens, retries, host collection/compute, reviewer and authoring
   time, retrieval, latency and amortisation over reuse as separate costs.
   A packet can reduce model context while increasing total system cost. The
   three-root pilot cannot estimate those bounds credibly, and it does not
   measure author or reviewer labour. No target is claimed as met.

The developmental runner in
`benchmarks/experiments/eal2-reviewed-rag/` preserves raw attempts and
reports synthetic preflight separately from model trials. Its three exposed
roots cannot establish a general improvement. A prospective held-out cohort
and independent review are needed for that inference.

## Model classes and deployment

| Model interface | Adapter route | Host contract |
| --- | --- | --- |
| Plain text, including small local or command models | Emit one strict JSON operation, receive host feedback as a user message. | Same bound task, checked assessment and finalisation. |
| Structured JSON model | Constrain a single operation envelope where the endpoint supports it; validate again in the host. | Same status and permission checks. |
| Native tool/function model | Declare the finite `answer`, `explain`, `stop` functions and return feedback by call ID. | Same operation validation and host-owned status. |
| Reasoning model with a Responses-style interface | Retain returned reasoning and function items in a stateless transcript; replay them alongside feedback. | Same tool cap, elapsed/token/cost budgets and finalisation. |
| Multimodal or embedding model | Have a trusted extractor produce reviewed typed records, or supply a compatible vector only to candidate ranking. | The extractor and correspondence need review; a vector is never evidence for a claim. |

These are adapter paths for model classes, not a claim of universal competence.
A class with no reliable JSON or tool emission can still receive a checked
packet from a trusted application, but its generated explanation may be wrong.
Where output accuracy is the goal, deploy the host's checked status and its
trace as the authoritative interface and mark generated prose as unverified.
