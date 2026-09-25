# Engineering Argument Language (EAL/2)

EAL/2 is a language and host for bounded engineering arguments. A source file identifies the claim, the question it addresses, its reasoning method, evidence obligations, premises and objections. The interpreter validates those declarations, collects observations through host-configured tools, evaluates the stated method and records an explanation of the resulting status. A checked status is about the declared question and collected observations; the source's relevance and the observations' real-world provenance still require review.

The Python package is **2.5.0** and requires Python **3.11 or later**. EAL/2 is the supported source language. The observation envelope is `EAL/typed-input/1`; the source, package and observation versions identify different contracts.

## Start here

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make test
```

The generated ANTLR parser is included. Regenerating it requires Java; `make check-generated` checks that the committed output matches the grammar.

## One end-to-end case

[The GitHub Actions workflow example](examples/workflow-gate/README.md) starts with an ordinary question about a specific workflow run. Its EAL/2 source declares the claim and evidence needed to answer it, while a host-configured collector fetches GitHub's run and job records. The example includes the source, tool registry, collector, context and commands to validate, collect, reason and inspect the checked result. It demonstrates a complete path for **one bounded workflow decision**, not a measured advantage over another representation or over models.

`make example` exercises the CLI and actual MCP stdio server against a digest-pinned projection of GitHub API responses. The historical-capture claim is supported at its recorded time; the live-only claim rejects the replay. A live reassessment uses the read-only HTTPS collector on a host that can reach GitHub.

The source and tool registry have different authority. A `.eal` file names evidence and its typed inputs; the example's `tools.toml` is trusted host configuration that binds the tool name to the collector command. The source cannot choose an arbitrary executable. Collection records source, context, tool version and observation identity. The host can refuse missing, malformed or mismatched observations. These checks do not establish provenance beyond the GitHub API response.

```bash
make example
```

The MCP server exposes `eal_describe`, `eal_validate`, `eal_collect`, `eal_reason` and `eal_explain`, among other operator tools. A client sends source and context to the server; the server runs configured collection and keeps the assessment status and evidence trace. The model's subsequent prose is a separate output whose accuracy must be checked against that status. The [example instructions](examples/workflow-gate/README.md) give the offline demonstration, live collection context and direct CLI/MCP commands for its specific case.

## Prospective comparison

The [new benchmark protocol](benchmarks/README.md) treats the assertion that **EAL/2 with the MCP host outperforms alternatives across small and large language model classes** as a hypothesis to test, not an established result. It specifies four arms: the actual task in plain prose (P), a Toulmin prose argument (T), a structurally equivalent JSON argument (J), and EAL/2 with its MCP host (E). The comparison must account for the checker and evidence access available to each arm. It calls for real tool calls on independently selected workflow cases, named frozen model snapshots, retained attempted results and effects within each predeclared class. The study is **specified, not run**; reviewed cases and outcome records are still needed. The single worked example checks the procedure and cannot justify a universal claim. See the protocol for the arms, randomisation, grading, costs and decision rule.

The [prospective runner](benchmarks/prospective-v1/README.md) tests the P/T/J/E execution and ledger contracts locally, but its real stages reject the current unready plan. Its `selected_acquisition` mode lets each arm select authorised calls; the separately planned `fixed_capture` diagnostic has no runner yet.

## Interfaces and boundaries

- `eal validate` checks parsing, references, types and method contracts without collecting evidence.
- `eal collect` runs the configured tools and persists their observations; `eal reason` computes method and argument statuses at an explicit or current time; `eal explain` retrieves the recorded trace.
- `eal-mcp` serves the same operations over local stdio using the MCP SDK. `eal-host` accepts one strict JSON operation for text-only clients; `eal-agent` can run a bounded model feedback loop when a provider is configured.
- The optional reviewed artifact and exact-question recipient routes bind a pinned source, context, question and claim on the host. They can keep a checked status authoritative when a recipient explanation differs.

The implementation provides finite, explicit support and attack reasoning with versioned reasoning methods. It does not infer the correct argument family from a task, authenticate GitHub beyond the configured acquisition path, prove informal warrants, or demonstrate cross-model superiority without a completed comparison.

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
| [Sources](docs/sources.md) | Primary research and retained references |

[`CONTRACT.md`](CONTRACT.md) records implementation interfaces. The [paper workspace](paper/README.md) links the Journal of Systems and Software author guide and relevant skills. Contributors should read [`AGENTS.md`](AGENTS.md) and the [argument-language skill](skills/engineer-argumentation-languages/SKILL.md).
