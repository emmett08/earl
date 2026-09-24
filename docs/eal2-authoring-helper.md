# Validated EAL/2 source authoring

`AuthoringSession` gives a source author or model adapter the installed EAL/2 description, a complete validated example and the full typed contracts for methods registered by the host. `submit` uses the same parser and semantic checks as `eal validate`. Its `validation` field preserves the service response, including source locations on semantic errors. The helper does not load a provider or open an MCP session.

```python
from eal.authoring import AuthoringSession
from eal.runtime import ReasoningService

service = ReasoningService("/path/to/workspace")
authoring = AuthoringSession(service, required_claims=("release_ready",))
reference = authoring.reference()
candidate = generate_complete_source(reference)  # Your provider or editor.
feedback = authoring.submit(candidate)
if feedback["status"] == "valid_needs_review":
    source_digest = feedback["accepted_source_digest"]
```

`required_claims` checks that named claims exist; it does not check their meanings. The helper also requires at least one claim and one argument, so an empty, statically valid program is not accepted as an authored argument. `reference()` includes the exact `language "EAL/2";` header, the language syntax and example returned by `describe()`, and `MethodRegistry.describe()` for every installed versioned method. The example must validate under the configured registry. Source may only select an installed method; it cannot supply implementation code.

For a callback that returns complete source on each turn, `revise(task, propose, max_attempts=4)` makes at most eight attempts by contract, with four as the default. On each failed attempt it supplies the exact previous source, validation diagnostics and missing required declarations or claim names. It accepts the first statically valid argument source with all required claim identifiers and retains all failed attempts. It never silently modifies source text. Exhaustion returns `status: invalid` without an accepted digest. A callback exception, malformed response or source exceeding the parser's 1 MiB limit returns `generation_error`, without copying exception details into the result. The caller can adapt a model response to the callback:

```python
def propose(request):
    # Send request to a configured model, or show it in a human editor.
    # Return one complete raw .eal document, without Markdown fences.
    return model_generate(request)

report = authoring.revise("Assess release readiness for this deployment", propose)
```

Both `submit` and `revise` return `fidelity_unverified: true`. A syntactically valid argument may omit an adverse condition, weaken a claim, select an irrelevant measurement or misrepresent a warrant. Before registering it as a reviewed artefact, compare the brief and source independently, inspect each scope and evidence acquisition, and replay the supported, contested, invalidated and missing-evidence states. Preserve the exact reviewed source bytes: formatting or revision changes the source digest and requires observations to be collected again. Compare this entire authoring and review route with an equal-capability JSON route in prospective experiments; a checked status for a correctly encoded argument alone does not establish an EAL/2 advantage.

The callback receives the full method contracts on each attempt. Count these prompt bytes and any model tokens in an authoring experiment; the helper does not estimate provider usage or human review time.
