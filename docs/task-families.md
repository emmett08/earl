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

The caller authenticates the user and supplies both permitted family IDs and
permitted artefact IDs. The host resolves exact bindings before invoking its
claim-specific assessment route:

```python
from eal.families import FamilyRegistry
from eal.retrieval import CandidateIndex

families = FamilyRegistry.load(artifacts, "families.toml")
candidates = CandidateIndex(families).search(
    task_text, authorised_families=caller.family_ids
)
# Present candidates for an explicit choice and obtain typed bindings.
resolved = families.resolve(
    chosen_family_id, {"site": "field"},
    authorised_families=caller.family_ids,
    authorised_artifacts=caller.artifact_ids,
)
checked = host.assess_claim(resolved["artifact_id"], resolved["claims"][0])
```

`CandidateIndex` uses bounded, deterministic lexical overlap. Equal scores
remain separate candidates. Its scores are ranking aids, not confidence or
applicability evidence. A retrieval service or RAG system may propose a family
ID, but only the exact resolver decides whether an authorised, reviewed
binding exists. The underlying artefact registry rechecks source and method
identity when the case is resolved, and normal collection still checks
observation context, acquisition request, age and EAL scope.

The current contract admits only finite string, integer and Boolean value
sets. Every parameter maps to a distinct context path that is present in the
artefact's pinned context and constrained by equality in each selected claim's
EAL environment. Cases with subject or scope differences require separately
reviewed sources whose claims express those differences. This first version
does not generalise a proof or warrant to an arbitrary new subject.
