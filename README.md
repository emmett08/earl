# Engineering Argument Language (EAL/3)

EAL/3 records engineering claims, their evidence requirements, reasoning methods, assumptions and objections in reusable source files. A Python host binds declared tools to a separate TOML configuration, collects observations, assesses claims and stores the result. Later sessions and different models can find the same source and reuse compatible observations until they expire.

The Python distribution is **`engineering-argument-language` 3.2.2** and requires Python **3.11 or later**; application code imports `eal`. The supported source language is `EAL/3`, with newline-terminated fields and typed flows. Stored tool results use `EAL/observation-record/1`; model-facing summaries use `EAL/assessment-packet/2`.

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

For a dependent claim, use `[premises measured] via authored => followup`. This builds nested derivations through claims, including pattern instances. Argument blocks can contain local declarations. Compound patterns can call nested patterns and recurse over a decreasing typed list. Modules, source imports and pure expressions support larger cases; see [scoped composition](https://github.com/emmett08/earl/blob/main/docs/eal3-composition.md). See the [language reference](https://github.com/emmett08/earl/blob/main/docs/language.md) for required fields, scope inheritance and reviewed ASPIC+ directives.

## Install for use

Create a virtual environment, then install a built or downloaded wheel:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install ./engineering_argument_language-3.2.2-py3-none-any.whl
eal --help
```

After the maintainer creates the `v3.2.2` release tag, a pinned source installation is also available:

```bash
python -m pip install \
  'engineering-argument-language @ git+https://github.com/emmett08/earl.git@v3.2.2'
```

PyPI installation becomes available when that version is published: `python -m pip install 'engineering-argument-language==3.2.2'`. See [packaging and releases](https://github.com/emmett08/earl/blob/main/docs/packaging.md) for artefact verification, supported Python imports and publication setup. Command collectors and custom reasoning methods require a POSIX host; the release workflow is configured to check distribution installation on Linux and macOS.

Original EARL software is available under the [Unlicense](https://github.com/emmett08/earl/blob/main/LICENSE), permitting commercial and non-commercial use, modification and redistribution. Dependencies and any third-party material retain their own terms; see [licence scope](https://github.com/emmett08/earl/blob/main/docs/packaging.md#licence-scope).

## Develop and check

From a source checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

The generated ANTLR parser is included. `make check-generated` verifies it against the grammar; regeneration requires Java. `make build` creates a wheel and source distribution; installing `.[release]` adds the tools used by `make check-distribution` to check both through fresh installations outside the checkout. GitHub workflows run only when manually dispatched.

## Select an MCP transport

One FastMCP 4 server exposes the same typed operations over stdio or Streamable HTTP. Stdio is the default. From a source checkout, the maintained example supplies a [server configuration](https://github.com/emmett08/earl/blob/main/examples/api-load-test/mcp.toml):

```bash
eal-mcp --config examples/api-load-test/mcp.toml --transport stdio
eal-mcp --config examples/api-load-test/mcp.toml --transport http
```

Each command launches one process with its selected transport. HTTP defaults to `http://127.0.0.1:8000/mcp`; `eal-host --url http://127.0.0.1:8000/mcp` connects to an existing HTTP service. Host configuration resolves CLI options before `EAL_MCP_*` environment variables, TOML values and defaults. HTTP validates Host and Origin headers before MCP handling. Non-loopback binds and additional non-loopback trusted hosts/origins require a bearer token supplied through a named environment variable. An endpoint exposes one operator workspace or a fixed set of registered entries. Shared local launches coordinate database initialisation and retain acquisition exclusion until owned collector processes have stopped. See [MCP and tools](https://github.com/emmett08/earl/blob/main/docs/mcp-and-tools.md) for configuration, authentication and model-host usage, and [MCP architecture](https://github.com/emmett08/earl/blob/main/docs/mcp-architecture.md) for SOLID responsibilities and execution limits.

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

The trusted TOML file binds tool names and versions to commands or JSON files. Tools may query external systems, authenticate or run tests. Command bindings can select inherited environment variables with `inherit_env`; the host keeps credentials and full outputs out of model packets. [MCP and tools](https://github.com/emmett08/earl/blob/main/docs/mcp-and-tools.md) defines the request, output, limits and execution identity.

## Reasoning and example

`method "name/version"` inside a reasoning declaration selects an installed method with its own typed input and output requirements. Built-in methods include structured, deductive, inductive, abductive, causal, counterfactual, analogical and temporal reasoning. The host checks their finite contracts, evidence predicates, premise dependencies, assumptions and targeted objections. `supported` means support under the authored scope and observations; it does not certify an omitted real-world premise. See [reasoning modes](https://github.com/emmett08/earl/blob/main/docs/reasoning-modes.md) and the [argument service design](https://github.com/emmett08/earl/blob/main/docs/argument-service.md).

The [API load-test example](https://github.com/emmett08/earl/blob/main/examples/api-load-test/README.md) uses synthetic request measurements to exercise the CLI and MCP with a custom typed method. Run `make example` for its deterministic assessment. The optional [ASPIC+ method](https://github.com/emmett08/earl/blob/main/docs/aspic-method.md) and EAL-to-ASPIC+ compiler provide a separate bounded formal argument view.

The [multi-environment example](https://github.com/emmett08/earl/blob/main/examples/multi-environment/README.md) applies one argument pattern to staging and production, preserving separate observations and reusing compatible records across sessions. The [ASPIC+ keyword example](https://github.com/emmett08/earl/blob/main/examples/aspic-keywords/README.md) exercises every reviewed argumentation directive and the implemented formal theory vocabulary, with reproducible browser snapshots and checks for all three attack types.

The [developer and model handover experiment](https://github.com/emmett08/earl/blob/main/experiments/transfer_study/README.md) supplies paired allocation, fresh-session model commands, project handover, independent answer scoring, time budgets and analysis that retains failed and missing sessions. Its synthetic fixture verifies the harness; comparative claims require independent cases and live developer and model runs. The [automated nano-model pilot](https://github.com/emmett08/earl/blob/main/experiments/model_transfer/README.md) provides a separate bounded run across reasoning and native-tool configurations.

## Documentation

| Document | Scope |
| --- | --- |
| [Argument service](https://github.com/emmett08/earl/blob/main/docs/argument-service.md) | Registered workflow, tools, reuse and model packets |
| [Language](https://github.com/emmett08/earl/blob/main/docs/language.md) | EAL/3 syntax and evidence versus observation |
| [Argument model](https://github.com/emmett08/earl/blob/main/docs/argument-model.md) | Support, objections and propagation |
| [Reasoning modes](https://github.com/emmett08/earl/blob/main/docs/reasoning-modes.md) | Built-in method contracts and extensions |
| [MCP and tools](https://github.com/emmett08/earl/blob/main/docs/mcp-and-tools.md) | Host adapters, persistence and operation schemas |
| [MCP architecture](https://github.com/emmett08/earl/blob/main/docs/mcp-architecture.md) | Shared operations, configuration, transports and acquisition coordination |
| [ASPIC+ method](https://github.com/emmett08/earl/blob/main/docs/aspic-method.md) | Optional formal method and compiler |
| [Integration contract](https://github.com/emmett08/earl/blob/main/CONTRACT.md) | Python, CLI, MCP and record interfaces |
| [Packaging and releases](https://github.com/emmett08/earl/blob/main/docs/packaging.md) | Installation, public Python imports, licensing and manual publication |
| [EAL/3 experiment methodology](https://github.com/emmett08/earl/blob/main/docs/eal3-experiment-methodology.md) | Practical thresholds, pilot-informed allocation and cumulative fresh-session evaluation |
| [Experiment workflow and inputs](https://github.com/emmett08/earl/blob/main/experiments/model_transfer/WORKFLOW.md) | One wrapper for free checks, automatic collection segments, annotation hand-off, analysis and evaluation planning |
| [Handover experiment](https://github.com/emmett08/earl/blob/main/experiments/transfer_study/README.md) | New-session developer and model comparison protocol |

Correctness of an authored question and its tool's real-world measurements remains the developer's responsibility. Collector-call reduction is tested; improvements in model accuracy, latency and cost need paired trials across model sizes and sessions.
