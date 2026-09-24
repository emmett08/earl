# Reviewed EAL task families and candidate retrieval

`FamilyRegistry` groups exact EAL artefacts into a finite, reviewed task
family. Each tuple of typed parameters maps to a pinned artefact and selected
claims. It does not substitute strings into EAL source or change the context
at assessment time. An unseen tuple remains unresolved until an operator
adds and reviews an artefact for that tuple.

The family catalogue is a host-owned TOML file. This example assumes that
`rig_pilot` and `rig_field` already exist in an `ArtifactRegistry` catalogue,
their contexts contain the corresponding `site` value, and the selected
claims' EAL environments each require that value.

```toml
schema = "eal2-task-families/1"

[families.rig]
description = "Rig inspection by reviewed site"
terms = ["rig", "inspection"]
context_paths = { site = "site" }

[families.rig.parameters.site]
type = "string"
values = ["pilot", "field"]

[[families.rig.cases]]
bindings = { site = "pilot" }
artifact_id = "rig_pilot"
claims = ["accepted"]
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "<digest calculated after review>"

[[families.rig.cases]]
bindings = { site = "field" }
artifact_id = "rig_field"
claims = ["accepted"]
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "<digest calculated after review>"
```

After examining each source, method contract, claim, context and parameter
binding, the reviewer records the decision under the operator's normal
change control. `review_binding_digest` calculates each case's contract
checksum from the exact family ID, parameter specification, context paths,
binding, artefact source digest, method registry fingerprint, context digest
and selected claims, as well as the artefact path and configured assessment
time. The digest detects a changed contract. Reviewer identity
in the TOML is an operator attestation; a digest alone does not authenticate
the person or establish that the natural-language warrant is true. The loader
checks the asserted reviewer fields and contract digest. It cannot verify
that an independent review actually took place; the operator must retain
that record outside the catalogue.

## Trusted direct family calls

An application that has already established that the user's question concerns
one exact case can use the family route directly. The authenticated host
supplies family and claim grants and the typed bindings; model text does not
establish the case's relevance.

```python
from eal.families import FamilyRegistry
from eal.routing import TaskFamilyHost

families = FamilyRegistry.load(artifacts, "families.toml")
route = TaskFamilyHost(
    families, principal=authenticated_principal,
    authorised_families={"rig"},
    authorised_claims={"rig_field": {"accepted"}},
)
checked = route.assess("rig", {"site": "field"}, "accepted")
```

`route.explain` and `route.finish` require the same family ID, bindings, claim
and issued assessment ID. Issuance is stored under the host-assigned principal,
so an assessment ID alone cannot retrieve another caller's packet. A direct
family call assumes the application has separately established applicability.
It is not the model-facing endpoint.

## Reviewed recipient route

For a model-facing recipient, the operator additionally reviews the *exact
question* against a family case. An `eal2-task-applicability/1` catalogue binds
that question to one family ID, typed bindings and selected claim:

```toml
schema = "eal2-task-applicability/1"

[tasks.field_inspection]
question = "Does the field rig satisfy the reviewed inspection claim?"
family_id = "rig"
bindings = { site = "field" }
claim = "accepted"
reviewed_by = "engineering-review-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "<digest calculated after review>"
```

`review_applicability_digest` calculates the digest after the family case has
been reviewed; the literal placeholder above is not loadable. The operator
also retains the human review record. The digest binds the exact question,
family case and claim to the reviewed source and method registry. Changed
question bytes, artefact source or case contract fail the loader or resolver.
A paraphrase needs its own reviewed entry. There is no inferred semantic
match.

```python
from eal.applicability import TaskApplicabilityRegistry
from eal.routing import TaskFamilyHost

tasks = TaskApplicabilityRegistry.load(families, "tasks.toml")
route = TaskFamilyHost(
    families, principal=authenticated_principal,
    authorised_families={"rig"},
    authorised_claims={"rig_field": {"accepted"}},
    applicability=tasks,
    task_text=trusted_original_question,
    authorised_tasks={"field_inspection"},
)
description = route.describe_bound_task()
checked = route.assess_bound_task()
trace = route.explain_bound_task(checked["assessment_id"])
final = route.finish_bound_task(checked["assessment_id"])
```

The authenticated launcher binds `trusted_original_question` before a model
sees the task. The host selects its unique reviewed entry and checks the
question, family case and all three grants. The returned description includes
the SHA-256 digest of the exact original question bytes. No match, ambiguity,
revoked grant or changed review contract prevents an assessment. The recipient
MCP endpoint requires no task ID from a model; a trusted Python application
may also use `route.assess_task("field_inspection")` for an explicit ID.
`CandidateIndex` can rank accessible families through `route.candidates()`
using bounded lexical overlap and optional reviewed aliases. The optional
`RagCandidateIndex` ranks reviewed local snippets with BM25 or injected query
vectors through the same advisory hook; the CLI selects it with
`--rag-catalogue RAG.toml` for local BM25. Scores, aliases and snippets are suggestions,
not applicability evidence. The exact reviewed task
resolver gates assessment. Collection still checks observation context,
acquisition request, age and EAL scope. See [the recipient CLI route](model-loop.md#reviewed-recipient-route).
The [RAG index contract](eal2-rag.md) documents reviewed snippets and injected
embedding vectors; the CLI does not request vectors.

The current contract admits only finite string, integer and Boolean value
sets. Every parameter maps to a distinct context path that is present in the
artefact's pinned context and constrained by equality in each selected claim's
EAL environment. Cases with subject or scope differences require separately
reviewed sources whose claims express those differences. This first version
does not generalise a proof or warrant to an arbitrary new subject.
