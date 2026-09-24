# Route a reviewed task family to a checked claim

The application authenticates the caller and constructs `TaskFamilyHost` with
that caller's family and claim grants. Recipient text cannot supply a new
principal or grant. The route is an in-process application API; a remote MCP
deployment must make the same binding at its authenticated endpoint.

```python
from eal.families import FamilyRegistry
from eal.routing import TaskFamilyHost

families = FamilyRegistry.load(artifacts, "families.toml")
host = TaskFamilyHost(
    families,
    principal=authenticated_caller.id,
    authorised_families=authenticated_caller.family_ids,
    authorised_claims=authenticated_caller.artifact_claims,
)

candidates = host.candidates(task_text)
# The application obtains an explicit family, typed bindings and selected
# claim from trusted task metadata or an appropriately checked user choice.
packet = host.assess("rig", {"site": "pilot"}, "accepted")
recipient_input = {"task": task_text, "checked_assessment": packet}
# Optional recipient prose is kept separate from the host-owned status.
checked = host.finish("rig", {"site": "pilot"}, "accepted", packet["assessment_id"])
trace = host.explain("rig", {"site": "pilot"}, "accepted", packet["assessment_id"])
```

`candidates` returns lexical family suggestions without a binding or verdict.
`assess` resolves an exact reviewed tuple, confirms both artefact and claim
grants, and calls `ArtifactRegistry.assess_claim`. No source, context, claim
scope or assessment time is created by retrieval. Unreviewed combinations
remain unresolved. `finish` rechecks the saved host assessment; it does not
take a recipient's proposed status. `explain` retrieves that claim's direct
trace only. Both operations require an assessment issued by this host
instance. An application that must retrieve results after a restart needs a
durable principal-bound issuance record or a fresh assessment.

The family catalogue's reviewer field and checksum pin the reviewed contract
but do not authenticate the reviewer. Operators must maintain their actual
review and source provenance separately. The claim packet reports
`consistency_checked_not_authenticated` for evidence integrity.
