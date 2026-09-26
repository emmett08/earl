# Engineering Argument Language (EAL/2)

EAL/2 is a language and host for bounded engineering arguments. A source file identifies the claim, the question it addresses, its reasoning method, evidence obligations, premises and objections. The interpreter validates those declarations, collects observations through host-configured tools, evaluates the stated method and records an explanation of the resulting status. A checked status is about the declared question and collected observations; the source's relevance and the observations' real-world provenance still require review.

The Python package is **2.8.0** and requires Python **3.11 or later**. EAL/2 is the supported source language. Its tool declaration names an interface and version; host configuration selects its execution adapter. Formal reasoning-method inputs use the independent `EAL/typed-input/1` envelope. Source, package, acquisition and typed-method identifiers describe different contracts.

## Start here

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make test
```

The generated ANTLR parser is included. Regenerating it requires Java; `make check-generated` checks that the committed output matches the grammar.

## One engineering example

[Review an API load-test result](examples/api-load-test/README.md) checks a familiar engineering question: does a particular build meet agreed latency and error-rate criteria in the supplied report? The example includes one EAL/2 source, a labelled synthetic report, a collector that computes statistics from individual request results, a trusted tool registry and a CLI/MCP walkthrough.

```bash
make example
```

The report contains 100 requests, a nearest-rank sample p95 of 180 ms and one failed request. It meets the example's limits of 200 ms and 1% at its recorded assessment time. `make example` validates, collects, reasons and explains through both the CLI and the actual MCP stdio server. It runs locally with no credentials or model provider, using a temporary database.

The source pins the report's build, run and digest. The collector preserves its original observation time; EAL checks scope and age, then the installed typed method assesses the three numerical limits. Separate passing and failing claims distinguish a measured threshold failure from unusable evidence. The [walkthrough](examples/api-load-test/README.md) explains those checks, the expected output and how to substitute a real report. The synthetic records illustrate assessment behaviour; release decisions need genuine measurements and a representative workload.

A [live API experiment](experiments/api_load_test/README.md) compares EAL/2+MCP with meaning-equivalent JSON and ordinary prose, including a conventional checked-result control. Its manually dispatched, Docker-based protocol freezes the selected measurements and scores decisions independently. An optional checked finalisation mode returns the verified decision without asking a model to restate it. The experiment measures the combined system under its specified cases; no general accuracy, cost or speed advantage over equally capable alternatives follows from the language or the synthetic example alone.

## Interfaces and boundaries

- `eal validate` checks parsing, references, types and method contracts without collecting evidence.
- `eal collect` runs the configured tools and persists their observations; `eal reason` computes method and argument statuses at an explicit or current time; `eal explain` retrieves the recorded trace.
- `eal-mcp` serves the same operations over local stdio using the MCP SDK. `eal-host` accepts one strict JSON operation for text-only clients; `eal-agent` can run a bounded model feedback loop when a provider is configured.
- The optional argument host maps reviewed prose forms to a scoped claim, decision or proposed action, collects evidence with the configured tools and tests explicit correspondence and evidence-adequacy obligations. Unreviewed wording remains unresolved unless a separately installed correspondence validator approves its interpretation. Its host-operated file-change adapter requires a checked decision before applying proposed bytes. See [executable argument host](docs/executable-argument-host.md).
- The optional reviewed artifact and exact-question recipient routes bind a pinned source, context, question and claim on the host. They can keep a checked status authoritative when a recipient explanation differs.

The implementation provides finite, explicit support and attack reasoning with versioned reasoning methods. It does not infer the correct argument family from a task, authenticate measurements beyond the configured acquisition path, prove informal warrants, or demonstrate cross-model superiority without a completed comparison.

## Documentation

| Document | Scope |
| --- | --- |
| [Design aim](docs/design-aim.md) | Intended task coverage and limits of current evidence |
| [EAL/2 design](docs/eal2-design.md) | Language decisions and alternatives |
| [Language](docs/language.md) | Grammar, declarations and typed proposition correspondence |
| [Vocabulary](docs/vocabulary.md) | Meanings of adjacent engineering terms |
| [Argument model](docs/argument-model.md) | Composed support, objections and propagation |
| [Grounded reasoning](docs/grounded-reasoning.md) | Explicit Dung graph solver |
| [Reasoning modes](docs/reasoning-modes.md) | Computational method inputs, outputs and bounds |
| [MCP and tools](docs/mcp-and-tools.md) | Tool acquisition, persistence and model hosts |
| [Executable argument host](docs/executable-argument-host.md) | Reviewed argument forms, adequacy checks and action preflight |
| [Sources](docs/sources.md) | Primary research and retained references |

[`CONTRACT.md`](CONTRACT.md) records implementation interfaces. Contributors should read [`AGENTS.md`](AGENTS.md) and the [argument-language skill](skills/engineer-argumentation-languages/SKILL.md).
