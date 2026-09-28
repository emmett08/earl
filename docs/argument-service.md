# EAL argument service

EAL/2 describes a bounded engineering argument. A host reads its declarations,
collects evidence through operator-configured tools, evaluates an exact
reasoning-method contract, and stores an assessment that any model or later
prompt session can inspect. The source language, package and stored observation
record have distinct versions: `EAL/2`, Python package `2.14.0`, and
`EAL/observation-record/1`. The compact model projection is
`EAL/assessment-packet/1`.

## Components and ownership

| Component | Responsibility | Boundary |
| --- | --- | --- |
| Parser and semantic validator | Expand typed patterns; check names, kinds, method contracts, graph references and source locations | Pure EAL/2 source; no tools run |
| `EvidencePlanner` | Traverse the requested claim's alternatives, premises, backing, assumption validations, objections and defences | Immutable plan in source order |
| `ToolRegistry` and acquisition adapters | Resolve a declared tool/version to operator TOML; run a bounded command or import a JSON observation | EAL cannot install a command, choose a path or supply credentials |
| `CollectionScheduler` | Overlap only consecutive calls marked independent and read-only by the operator | Serial barriers, bounded workers, ordered records |
| `RunStore` and `ObservationRebinder` | Persist individual observations, collections, assessments, reuse identities and invalidation events | Explicit rebinding creates new source-bound records; original times survive |
| Method registry and evaluator | Apply an exact installed method to checked evidence and compose support/attack routes | Finite method contracts; no implicit collection |
| `AssessmentPacketBuilder` | Project an assessed claim into bounded model-facing fields | Full result remains available by assessment ID |

The registry selects command and file adapter strategies. The planner, scheduler,
rebinder, evaluator and packet builder each have one decision to make and are
composed by `ReasoningService`. The store is the repository for immutable run
records. Both CLI and MCP use the same service; model-facing collection applies
an explicit operator access policy before acquisition. New reasoning methods
are installed through typed registry contracts without changing the collection
or graph traversal components.

## Declared collection

An EAL source names `tool NAME { version "..."; }` and evidence with `tool`,
`kind`, `environment`, `max_age`, optional `input` and predicates over the
returned `value`. The sibling TOML binds that name and version to `command`
with an argv or `json_file` with a workspace path. The operator owns execution
limits, file pins and credentials. A command receives JSON containing
`evidence_id`, `environment`, `tool`, `tool_version`, `input` and `context` on
stdin. It can authenticate, query a Kubernetes resource, run tests or transform
several upstream results before returning a bounded observation. The adapter
must expose the target, source revision/time and completeness constraints
needed to interpret the result. Credentials remain outside EAL and the returned
observation.

`model_access = "reviewed"` is the default TOML policy. The general MCP
collection operations need `model_access = "general"` for every configured
tool in the selected plan. Reviewed artefact and recipient routes use their
separate source and principal grants. `parallel_safe = true` is an operator
assertion that calls are independent and read-only; other calls execute
serially. These operational choices are absent from EAL source and contribute
to the binding identity.

Collection checks the entire selected plan before starting tools: context JSON
at most 16 KiB, at most 128 evidence IDs, each request at most 1 MiB and at
most 16 MiB of aggregate configured output allowance. Each adapter has its own
timeout and output limit. A command failure, authentication error, incomplete
read, malformed response or identity mismatch becomes an error observation;
it cannot establish the contrary claim. Stored records retain original
observation time, ingestion time, source/context/request and binding identities,
output digests and byte counts. Raw process streams are excluded. The SQLite
store and its keyed binding identity are private host files.

## Planning and assessment

`eal_plan(source, claim)` finds every declared route capable of changing the
claim's status. `eal_collect_claim` collects that plan once per evidence ID;
`eal_collect` accepts an explicit subset. The assessment takes exact source,
context, a collection ID and an explicit or current time. It rejects a stored
collection from another source or context. The evaluator rechecks evidence
identity, current operator binding, environment, original age and value
predicates, then runs the declared versioned method and evaluates the argument
graph. Optional `eal_compile_aspic` uses the same checked observation cut but
reports a separate formal profile.

The method registry specifies each input kind, schema, formal query, result
schema and resource bound. A computational method consumes exactly one usable
observation of its designated kind from direct evidence, backing and
assumption-validation evidence. A valid negative result can support an
explicitly authored negative route; a failed collection or invalid input
cannot. Typed propositions additionally require the argument's `binding` to
correspond to the formal subject, quantity, unit, scope, interval, query and
result criterion. Premise claims and objections remain graph dependencies.
The authored rationale and any real-world modelling obligation remain visible
as such; a calculation alone does not establish prose or physical adequacy.

## Persistence and reuse

The SQLite store persists immutable individual observations, collections and
assessments. `collection_id` and `assessment_id` let different models and
sessions share the same checked computation. Reasoning over a frozen collection
does not rerun its tools. A revised source needs a new collection. The operator
can explicitly rebind a named earlier collection when each successful
observation has the same evidence ID, request, input, context, environment,
evidence kind, current TOML binding and, for commands, effective process
environment identity. The rebinder records origin and derived IDs, preserves
the original time, and makes no new physical measurement. Freshness and the
revised predicates are checked at the next assessment. A changed inherited
credential, endpoint or kubeconfig refuses command rebinding.

An operator can record a source event or reconnect gap with `eal invalidate`.
Origin-level invalidation excludes that observation lineage; scoped binding
or request invalidation excludes older and in-flight measurements from future
reuse. A fresh authoritative read makes a new observation cut. Historical
assessments remain available with their original identities and time. An
external watch or event source is responsible for invoking the invalidation
hook; reconnect gaps require a broad invalidation before reuse resumes.

## Model-facing result

`eal_packet(assessment_id, claim?)` returns a bounded result with claim and
premise states, relevant method outputs, typed-binding decisions, live
objections, assumptions, evidence availability codes, observation IDs and
original times where recorded. It includes source/context/method identities
and a reference for `eal_explain`; it excludes raw observation values,
credentials, arbitrary extension fields and process output. Omitted detail is
marked explicitly. A model can request the full stored explanation when the
packet is insufficient. The text agent's stateful assessment collects the
requested claim's closure and feeds the compact packet back to the model.

Formal statuses are reproducible for fixed source, context, collection,
assessment time and method registry. Faster collection and smaller prompts
follow from bounded concurrency, scoped work and projection; gains in model
accuracy, token use or total latency require trials with retained outcomes.
