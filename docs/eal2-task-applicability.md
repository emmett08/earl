# Reviewed task applicability and candidate retrieval

The candidate index suggests families. It does not decide whether a family
answers a user's question. Its lexical score is not evidence, a case binding,
or permission to assess a claim. An operator may add synonyms through an
`eal2-retrieval-aliases/1` manifest; each alias entry names a family, up to
32 terms, a reviewer and time, and a `review_contract_sha256` produced by
`alias_review_digest`. The checksum binds the aliases to the family's current
description, terms and reviewed case contracts. Reviewer authentication is a
deployment responsibility.

The applicability gate uses a separate `eal2-task-applicability/1` manifest.
Each `tasks.<id>` entry records an exact question, family ID, complete typed
bindings, one reviewed claim, reviewer and time, and a
`review_contract_sha256` produced by `review_applicability_digest`. This
checksum binds the exact question and claim to the reviewed family case and
pinned EAL source. The catalogue refuses duplicate exact questions, including
duplicates that would route to different cases. A changed question, case or
source requires review again.

The trusted application binds the *original task text* and grants. The host
calls `TaskApplicabilityRegistry.resolve_bound(question,
authorised_tasks=..., authorised_families=...,
authorised_artifacts=...)` before any assessment. It selects the unique exact
question in the reviewed catalogue, then checks the task, family and artefact
grants and source contract. An absent, ambiguous or revoked entry refuses
assessment before collection. The model supplies neither the question nor an
opaque task ID, family, binding or claim. `eal_bound_task()` discovers the
checked route and SHA-256 of the original question bytes without collecting
evidence; `eal_assess_bound_task()` evaluates it. Finish and explanation need
only the issued assessment ID and recheck the same route, principal and packet.
Durable issuance records the packet, task and review digests;
the final model response cannot replace its status.

Trusted Python applications can still call `resolve(question, task_id=...)`
and `TaskFamilyHost.assess_task(task_id)` when they already hold an exact task
ID. Those methods perform the same applicability check; the recipient MCP
surface exposes only the bound route. Candidate ranking remains advisory.

This conservative gate handles repeated, reviewed questions. New wording,
even a semantically equivalent paraphrase, needs another reviewed task entry.
The index may nominate that entry for review but cannot promote the nomination
to applicability. Likewise, retrieving a document does not turn its contents
into a trusted observation; acquisition and evidence identity need their own
authenticated checks. The route makes no claim of general semantic RAG
coverage or improved performance over an equally capable JSON checker.
