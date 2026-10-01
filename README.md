# Engineering Argument Language (EAL/3)

EAL/3 records engineering claims, their evidence requirements, reasoning methods, assumptions and objections in reusable source files. A Python host binds declared tools to a separate TOML configuration, collects observations, assesses claims and stores the result. Later sessions and different models can find the same source and reuse compatible observations until they expire.

The package is **3.1.0** and requires Python **3.11 or later**. The supported source language is `EAL/3`, with newline-terminated fields and typed flows. Stored tool results use `EAL/observation-record/1`; model-facing summaries use `EAL/assessment-packet/2`.

## Author a bounded argument

Fields end at newlines. Context defaults remove repeated metadata; role-labelled support lists preserve reference types:

```eal
language "EAL/3"
environment lab {
  require site == "bench"
}
tool probe {
  version "1"
}
context environment lab, tool probe, max_age 60 {
  evidence reading {
    kind test
    require passed == true
  }
  claim measured {
    statement "The synthetic probe satisfies the declared acceptance condition."
  }
}
reasoning authored {
  method "structured/1"
  rationale "The accepted probe supports this bounded claim."
}
pattern measured_route(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
apply check = measured_route(c=measured, r=authored, e=reading)
rank reading 700 reviewed "synthetic-review/probe"
```

For a dependent claim, use `[premises measured] via authored => followup`. This builds nested derivations through claims, including pattern instances. Argument blocks can contain local declarations. Compound patterns can call nested patterns and recurse over a decreasing typed list. Modules, source imports and pure expressions support larger cases; see [scoped composition](docs/eal3-composition.md). See the [language reference](docs/language.md) for required fields, scope inheritance and reviewed ASPIC+ directives.

## Install and check

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

The generated ANTLR parser is included. `make check-generated` verifies it against the grammar; regeneration requires Java. GitHub workflows run only when manually dispatched.

## Assess a known claim

Register a developer-authored EAL file once, with its default context and the claims the application will use:

```bash
eal --workspace . --registry tools.toml register arguments/readiness.eal \
  --entry-id readiness --claim service_ready --context '{"cluster":"staging"}'
eal --workspace . --registry tools.toml find 'service ready'
eal --workspace . --registry tools.toml assess-known readiness --claim service_ready
eal --workspace . --registry tools.toml model-context readiness --claim service_ready \
  --question 'Is the service ready?'
```

The host reads the current registered source, plans all declared support and objection routes, reuses each compatible fresh observation from the persistent store and calls tools only for missing or expired evidence. It evaluates the declared reasoning methods again at the assessment time. The result includes the checked claim status, a bounded packet, collection and assessment IDs, and counts of reused and newly collected observations. `eal history readiness` locates prior runs; `eal explain ASSESSMENT_ID` retrieves the full stored trace for a developer.

The Python API composes the same path:

```python
from eal.knowledge import EALKnowledgeBase, ModelContextAdapter

kb = EALKnowledgeBase(".", "tools.toml")
kb.register("arguments/readiness.eal", entry_id="readiness",
            context={"cluster": "staging"}, claims=["service_ready"])
checked = ModelContextAdapter(kb).prepare(
    "Is the service ready?", "readiness", "service_ready")
messages = checked["messages"]     # Supply to any text-only or tool-capable model.
status = checked["assessment"]["status"]  # Host result, independent of model prose.
```

The application selects the exact entry and claim. A model needs no EAL parser, tool access or native reasoning mode: the host performs those steps and supplies a bounded packet. For MCP clients, the launcher selects registered entries with repeated `eal-mcp --known-entry ENTRY_ID` options. That server exposes catalogue search and one-call assessment for those entries. `eal-host --known-entry ENTRY_ID` accepts one strict JSON operation from a text-only client. The lower-level CLI and MCP source operations remain available for explicit validation, planning, collection and reasoning.

## Evidence and time

An authored `evidence` declaration names a tool, its input, context scope, acceptance predicates and `max_age`. The actual observation is the tool's JSON output, persisted separately with its original observation time and acquisition identity. `assumption.valid_from` and `valid_until` control when an assumption applies to an argument; `evidence.max_age` controls whether a stored observation is fresh. An expired assumption cannot be made applicable by running the tool again. A source edit creates a new revision; an observation can still be reused when its evidence ID, request, tool binding, environment, context and age remain compatible.

The trusted TOML file binds tool names and versions to commands or JSON files. Tools may query external systems, authenticate or run tests. Command bindings can select inherited environment variables with `inherit_env`; the host keeps credentials and full outputs out of model packets. [MCP and tools](docs/mcp-and-tools.md) defines the request, output, limits and execution identity.

## Reasoning and example

`method "name/version"` inside a reasoning declaration selects an installed method with its own typed input and output requirements. Built-in methods include structured, deductive, inductive, abductive, causal, counterfactual, analogical and temporal reasoning. The host checks their finite contracts, evidence predicates, premise dependencies, assumptions and targeted objections. `supported` means support under the authored scope and observations; it does not certify an omitted real-world premise. See [reasoning modes](docs/reasoning-modes.md) and the [argument service design](docs/argument-service.md).

The [API load-test example](examples/api-load-test/README.md) uses synthetic request measurements to exercise the CLI and MCP with a custom typed method. Run `make example` for its deterministic assessment. The optional [ASPIC+ method](docs/aspic-method.md) and EAL-to-ASPIC+ compiler provide a separate bounded formal argument view.

The [multi-environment example](examples/multi-environment/README.md) applies one argument pattern to staging and production, preserving separate observations and reusing compatible records across sessions. The [ASPIC+ keyword example](examples/aspic-keywords/README.md) exercises every reviewed argumentation directive and the implemented formal theory vocabulary, with reproducible browser snapshots and checks for all three attack types.

The [developer and model handover experiment](experiments/transfer_study/README.md) supplies paired allocation, fresh-session model commands, project handover, independent answer scoring, time budgets and analysis that retains failed and missing sessions. Its synthetic fixture verifies the harness; comparative claims require independent cases and live developer and model runs. The [automated nano-model pilot](experiments/model_transfer/README.md) provides a separate bounded run across reasoning and native-tool configurations.

## Documentation

| Document | Scope |
| --- | --- |
| [Argument service](docs/argument-service.md) | Registered workflow, tools, reuse and model packets |
| [Language](docs/language.md) | EAL/3 syntax and evidence versus observation |
| [Argument model](docs/argument-model.md) | Support, objections and propagation |
| [Reasoning modes](docs/reasoning-modes.md) | Built-in method contracts and extensions |
| [MCP and tools](docs/mcp-and-tools.md) | Host adapters, persistence and operation schemas |
| [ASPIC+ method](docs/aspic-method.md) | Optional formal method and compiler |
| [Integration contract](CONTRACT.md) | Python, CLI, MCP and record interfaces |
| [EAL/3 experiment methodology](docs/eal3-experiment-methodology.md) | Practical thresholds, pilot-informed allocation and cumulative fresh-session evaluation |
| [Experiment workflow and inputs](experiments/model_transfer/WORKFLOW.md) | One wrapper for free checks, automatic collection segments, annotation hand-off, analysis and evaluation planning |
| [Handover experiment](experiments/transfer_study/README.md) | New-session developer and model comparison protocol |

Correctness of an authored question and its tool's real-world measurements remains the developer's responsibility. Collector-call reduction is tested; improvements in model accuracy, latency and cost need paired trials across model sizes and sessions.
