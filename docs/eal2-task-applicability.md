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

The trusted application binds the *original task text* and permitted task IDs.
A model may nominate one of those IDs, but cannot supply the question. The host calls
`TaskApplicabilityRegistry.resolve(question, task_id=...,
authorised_tasks=..., authorised_families=..., authorised_artifacts=...)`
before any assessment. The model cannot supply or replace `question`. An
authorised but irrelevant family ID cannot pass this gate, and an unavailable
or ambiguous task results in refusal. The returned route contains the exact
artifact ID, claim and task review digest so an issued assessment can retain
the applicability identity. The assessment host then collects and checks the
pinned source; the final model response cannot replace its status.

This conservative gate handles repeated, reviewed questions. New wording,
even a semantically equivalent paraphrase, needs another reviewed task entry.
The index may nominate that entry for review but cannot promote the nomination
to applicability. Likewise, retrieving a document does not turn its contents
into a trusted observation; acquisition and evidence identity need their own
authenticated checks. The route makes no claim of general semantic RAG
coverage or improved performance over an equally capable JSON checker.
