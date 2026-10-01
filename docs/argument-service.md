# EAL argument service

EAL/3 defines claims, evidence, reasoning methods, premises, assumptions and objections. The service connects those declarations to operator-configured collectors, computes an assessment and stores it for later models and prompt sessions. A registered claim can be assessed through one call: the host selects its complete evidence plan, reuses eligible observations, collects the remainder, evaluates the argument and returns a bounded result.

## Developer workflow

The developer writes a `.eal` file containing the claim and its supporting and opposing routes. Each `tool NAME` block declares its exact `version` and selects an interface; a sibling TOML registry supplies the executable command or observation file, input limits and credentials available to the host. A collector may authenticate, query Kubernetes, run tests and transform several results before returning a scoped JSON observation. EAL predicates state which returned fields make the evidence usable; the `reasoning` declaration names the exact versioned method that interprets it.

The host registers validated source files and their claims under stable entry IDs. A changed file creates a new source revision with its own digest. Search by claim ID, statement or label helps a developer find a candidate, but an assessment names an exact entry and claim. The registered context supplies defaults for the one-call path; trusted Python and CLI callers can supply a different context explicitly. Model-facing calls use the registered context.

```python
from eal.knowledge import EALKnowledgeBase

kb = EALKnowledgeBase(".", "tools.toml")
kb.register("arguments/payments.eal", entry_id="payments_readiness",
            context={"cluster": "prod-eu"})
result = kb.assess("payments_readiness", "pod_ready", reuse="compatible")
packet = result["packet"]
```

`kb.register_tree("arguments", context=...)` registers a bounded directory and reports rejected files. `kb.find(query=...)` returns advisory candidates; `kb.sources()` lists the current validated entries and claim IDs. `kb.history(entry_id)` retrieves collection and assessment identities from earlier sessions. `reuse="fresh"` requests new collection for every selected evidence ID. The CLI exposes `register`, `find`, `assess-known`, `history` and `model-context`; the lower-level CLI and MCP operations remain available for explicit `plan`, `collect_claim`, `reason`, `packet` and `explain`. See [MCP operations](mcp-and-tools.md#mcp-operations).

For a model with no tools, `ModelContextAdapter(kb).prepare(question, entry_id, claim, *, context=None, now=None, reuse="compatible")` performs the same assessment and returns `EAL/model-context/2`: a checked `assessment`, a decision-focused `context`, and bounded `messages` containing that context. The application gives `messages` to the model and retains `assessment["status"]` as the host result; model prose cannot change that status. The application selects the entry and claim and must establish their correspondence to the question. A free-form question alone never authorises source selection or collection.

## Collection and argument closure

For one target claim, `EvidencePlanner` traverses every declared alternative derivation, transitive premise, reasoning backing record, assumption validation, objection and objection-to-objection defence that could affect its status. Each evidence ID appears once in source order. The plan exposes its calls before acquisition. `CollectionScheduler` overlaps only consecutive calls that the operator has marked independent and read-only; serial calls form barriers. Collection preserves each command's `evidence_id`, request, original observation time and source identity.

An EAL evidence declaration selects `tool`, `kind`, `environment`, `max_age`, optional `input` and `require` predicates over the returned `value`. The configured command receives `evidence_id`, `environment`, `tool`, `tool_version`, `input` and `context` as JSON. A successful command run produces an observation, not a conclusion. Authentication failure, timeout, malformed output, wrong identity and incomplete lookup produce an error or unusable observation; they do not establish the opposite engineering claim. `max_age` is measured in seconds from the original observation time to the assessment time. A file import must preserve its original time and matching request and context.

The operator-owned TOML binds tool versions to commands or files. The tool process uses host credentials; the EAL source cannot specify an executable or secret. A registered MCP entry uses its configured context, while the Python and CLI caller can select a different context explicitly. The collector contract excludes credentials from the returned observation; the operator configures and checks the collector's output. Execution, identity and size limits are specified in [MCP and tools](mcp-and-tools.md#tool-registry-and-observation-identity).

## Method-specific evidence and inference

`reasoning NAME { method "name/version"; rationale "..."; ... }` selects one installed method contract. Direct argument evidence, `reasoning.backing` and assumption-validation evidence supply its candidate inputs. Each computational method requires exactly one usable observation of its designated kind; multiple such observations are ambiguous unless an authored preprocessing tool has made one defined aggregate. Premise claims remain assessed graph dependencies. `evidence require` checks observation values; `reasoning require` checks computed method results. A typed `claim proposition` additionally binds its formal query and result criterion to the designated evidence ID through the argument's `binding` clause.

| Method | Designated input | Bounded computation | Additional obligation for the engineering claim |
| --- | --- | --- | --- |
| `structured/1` | No designated kind; evidence or a usable premise | Availability of authored grounds and dependencies | Adequacy of the prose rationale; no mechanical proof |
| `deductive/1` | `logical_case` | Finite propositional entailment or countermodel from consistent premises | Empirical premises and formula-to-claim correspondence |
| `inductive/1` | `sample` | Binomial estimate and Wilson interval | Sampling, independence, stopping rule and target population |
| `abductive/1` | `hypotheses` | Posterior over supplied candidates | Candidate coverage, exclusivity, priors and whole-observation likelihoods |
| `causal/1` | `experiment` | Two-arm mean contrast and standard error | Actual assignment, estimand, consistency, interference and missing outcomes |
| `counterfactual/1` | `causal_model` | Intervention in a supplied acyclic affine structural model | Model graph, equations and realised exogenous values |
| `analogical/1` | `analogy` | Correspondence of declared scalar features | Feature relevance, omitted differences and conclusion-transfer warrant |
| `temporal/1` | `trace` | Predicate over samples with endpoint and maximum-gap coverage | Any continuous-time or out-of-interval conclusion |

The optional installed `argumentation/aspic/2` method consumes `aspic_theory` and evaluates its bounded formal profile. The separate `eal_compile_aspic` operation derives a formal snapshot from checked EAL routes; neither changes the ordinary authored argument status. See [reasoning modes](reasoning-modes.md) and [ASPIC+](aspic-method.md).

A valid negative computation can support an explicitly authored negative route. An inconsistent deductive case, incomplete temporal trace, malformed method input or failed collection supplies no negative finding. Method result, result predicate, accepted argument, claim status and empirical adequacy remain separate. The ordinary solver composes premise claims, alternatives, assumptions, targeted objections and defences into `supported`, `contested`, `unsupported` or `out_of_scope`. It cannot discover an omitted premise or prove that a formalisation matches its prose claim.

## One-call assessment and reuse

`RegisteredAssessmentHost.assess(entry_id, claim, *, context=None, now=None, reuse="compatible")` reads the current registered source, selects that claim's complete plan, builds a source-bound collection, reasons at the requested or current time and returns `EAL/registered-assessment/1`. The result carries entry and claim IDs, source and context identities, collection and assessment IDs, assessed time, claim status, counts of reused and freshly collected observations, a compact `packet` and a full-explanation reference. It performs a new assessment even when every required observation can be reused; a historical status is never substituted for a current result.

Compatible reuse searches stored observations from earlier sessions by evidence ID and acquisition identity. It requires matching tool binding, command process environment, input, context, environment and evidence kind, along with original age eligibility. The host can assemble eligible observations from different collections and acquire only missing or expired evidence. Reused observations retain their original measured time and lineage while the new collection binds the current exact EAL source. A collector may depend on its `evidence_id`, so apparently identical requests under different IDs are not silently merged. A source edit produces a new revision and matching collection; it does not rewrite historical runs.

An evidence declaration's `max_age` bounds use of its original measurement time. An assumption declaration's `valid_from` and `valid_until` dates bound applicability of the assumption at assessment time. An ended assumption is out of scope; rerunning its validation tool does not extend its declared interval. Evidence whose `max_age` has elapsed is recollected, if available, and the new observation is checked against the current source and method. An unchanged eligible observation is reused without an extra tool call.

## Model-facing result

Packet declaration identifiers preserve the dot-separated names produced by modules and pattern applications, such as `staging_check.within_limit`. Each complete identifier is limited to 128 ASCII characters; every segment starts with a letter or underscore and contains only letters, digits or underscores.

`EAL/assessment-packet/2` exposes claim and premise statements and statuses, bounded method outputs, typed-binding checks, relevant assumption and objection states, evidence availability, observation identifiers and recorded observation times, with source/context/method identities. Each statement retains its explicit `prose_verified` qualification: formal support does not verify authored prose. It marks omitted material and refers to the stored explanation. It excludes raw observation values, credentials from tool records, process streams, formal input queries and arbitrary method-extension output. Authored claim statements are model-visible task data and must contain only information intended for that recipient. `ModelContextAdapter` projects that packet into decision-focused context: claim identifiers remain distinct from support statuses, method outputs and qualifications remain visible, and repeated trace digests stay in host state. Evidence entries retain bounded `predicate_failures` with field paths and issue codes; assumptions retain `time_status` and their applicability dates. Missing fields, unmet predicates and expired assumptions therefore remain distinguishable without parsing prose. The application retains the full packet and host status. An operator can retrieve the full persisted trace through `eal_explain`.

`PacketLimits.max_statement_bytes` bounds each selected or premise statement to 1024 UTF-8 bytes by default. A shortened statement carries `statement_truncated=true`; `omitted.claim_statement_bytes` counts omitted bytes and `summary_complete` becomes false. The prefix remains authored text, without a prose-verification assertion. A missing statement is `null` and contributes to `omitted.claim_statements`. If the complete packet exceeds its byte limit, the navigation fallback retains statuses and an explanation reference with `statement=null`, `prose_verified=false` and an explicit incomplete marker. Missing or shortened statements cannot establish complete claim meaning. The caller must retrieve the full explanation or report that interpretation remains unresolved.

## Acceptance properties

| Property | Observable criterion |
| --- | --- |
| Same question across sessions | An exact registered entry, claim, source revision and context can be resolved after process restart; the result identifies its collection, assessment, method registry and assessment time. |
| Complete declared reasoning | The selected plan includes every authored support, alternative, premise, objection and defence route; the result distinguishes a valid negative computation from a failed or inapplicable input. |
| Correct reuse | Reuse never refreshes original age or crosses evidence ID, acquisition, binding or context identities; an expired record triggers fresh acquisition, with any collector failure reported separately. |
| Bounded model context | Packets identify omissions and permit addressed explanation while excluding raw tool values; packet bytes, collector calls and total token use are observable. |
| Performance and conclusion quality | Compare end-to-end latency, collector calls and cost separately from method choice, correct scoped conclusions, justified unresolved outcomes and unjustified assertions on mode-stratified paired tasks with equivalent evidence access. |

Replaying a persisted assessment preserves its historical result. Recomputing from fixed source, context, observations, time and registry yields the same formal output when the installed method is deterministic. Scoped planning, concurrent independent collection, compatible reuse and compact packets provide mechanisms for reducing work; their effect on model accuracy, latency and cost is established by measured comparisons, not by the service's existence.

The prompt adapter treats current `assessed_at` results as current information and dated project notes as potentially superseded. This instruction does not guarantee model compliance. A host should retain the exact assessment alongside the generated answer. Measured negative findings belong in explicit method outputs or negative claims; placing a success condition in evidence admission only establishes whether that evidence supports the selected argument. The [model-session investigation](../experiments/model_transfer/README.md) measures the complete model response separately from host calculations.

### Model-context preservation contract

The context projection serves questions about the selected claim's current
support, checked computation and explicit qualifications. It retains bounded
claim and premise statements with their prose-verification status, claim-to-
evidence links, premise/argument relations, method outputs and bindings,
objections, evidence failures, observation times, applicability intervals and
omission indicators. It leaves opaque acquisition identifiers and repeated trace
digests in the authoritative assessment. Questions about observation provenance,
independence or source reconstruction require that full record.

The accepted input is a completed bounded packet from the same assessment;
`summary_complete=false` remains visible. Projection neither changes a support
status nor converts absent support into a negative proposition. Opposite authored
statements remain distinguishable even when their claim identifiers and formal
support are identical. Claim identifiers alone cannot substitute for the authored
proposition, and formal support cannot establish that its wording matches the
task. Registered method
outputs provide selected computed values; raw collector payloads and process
streams are never copied automatically. Packet tests verify these distinctions,
and the model-session calibration checks positive, negative, missing and expired
threshold cases. Those checks establish the tested representation behaviour;
model comprehension and engineering relevance remain empirical obligations.
