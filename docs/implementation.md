# Implementation architecture

The implementation follows Terence Parr’s separation of parsing, intermediate representation, symbol analysis, static checks and high-level interpretation. Language Implementation Patterns predates ANTLR4; the design uses its architectural patterns with the ANTLR4 visitor API.

| Stage | Implementation | Result |
|---|---|---|
| Lexing/parsing | `grammar/EAL.g4`, generated lexer/parser | Complete parse tree or syntax diagnostics |
| Lowering | `parser.py`, external visitor | Typed declarations independent of generated contexts |
| Symbol and semantic analysis | `semantics.py` | Unique symbols, typed references, bounds, applicability dates, acyclic premise graph, method/evidence contract checks |
| Method computation | `methods.py`, `modes.py` | Versioned, typed contracts, bounded method execution and explicit output fields |
| Formal correspondence | `propositions.py` | Versioned input envelopes, formal query identity, quantity/unit/scope/interval checks and result predicates |
| Canonical translation | `formatter.py` | Validated IR back to source with parse–format–parse preservation |
| Argument interpretation | `evaluator.py` | Scoped support, objections, dependencies and method traces at a supplied time |
| Dialectical calculation | `dialectic.py` | Grounded labels for explicit attacks and EAL/0.3 conjunctive support with alternative derivations |
| Tool execution | `runtime.py` | Bounded command or file observations |
| Persistence | `store.py` | SQLite collections, observations and reasoning results |
| Interfaces | `cli.py`, `server.py`, `host.py` | Shared operations through CLI or official MCP SDK |
| Model interaction | `agent.py`, `providers.py`, `discovery.py` | Discovered schemas, text generation, bounded feedback/repair, retained attempts and usage |
| Task evaluation | `benchmark.py`, `experiment.py`, `benchmarks/engineering-v1`, `benchmarks/engineering-v2` | Known-answer tasks, frozen repeated provider trials and task-cluster comparisons |

There are no embedded application actions in the grammar. Interpretation takes explicit records, context and time. Built-in mathematical computations are deterministic for those inputs. Host-registered extensions declare pure input/output computations and execute within bounded workers; they are trusted application code, not a security sandbox. A resource timeout is an unusable computation. Reproducibility therefore also depends on the registered implementation and execution budget, whose identity is recorded. A nondeterministic collector can supply different observations on repeated runs without changing the declared interpretation of a fixed observation set.

The parser rejects lexer errors, parser recovery diagnostics and excessive source/token size before lowering. Semantic analysis rejects duplicate symbols and excessive declaration/dependency size. Predicates use a closed set of scalar comparisons rather than general-purpose code execution. JSON input has no executable expressions. The runtime’s command registry supplies executable argument vectors; a language source cannot replace the configured executable with a shell fragment.

## Extending a reasoning method

Specify the question answered, evidence schema, query identity, output schema and quantity/unit meaning, necessary modelling assumptions, bounds and failure conditions. Register a `MethodContract` under a versioned identifier in an immutable `MethodRegistry`. EAL/0.3 refers to it with `method "namespace/name/1";`; adding another registered procedure does not require a grammar change. See [method extensions](method-extensions.md) for the executable example and host factory configuration. Add a known-answer calculation and an adverse case that would expose an overstrong interpretation. Keep empirical model assumptions represented as argument dependencies.

The process operator chooses the registry through Python or `--methods package.module:function`. Source text only selects an already registered method identifier. Unknown versions fail validation. Contract schemas are available through discovery, and assessments retain the registry fingerprint. Changing an implementation requires a new declared implementation version; fingerprints cover the contract, limits, declared implementation version and entry-point source/code identity. They do not hash every imported dependency or external environment; reproducible host packaging remains necessary.

`structured` applies an author-supplied conditional support relation. The other modes compute bounded formal, numerical or relational results; their output predicates specify the condition relevant to an argument. A proof concerning a formula, or an interval concerning a supplied sample, does not automatically establish that a prose claim accurately expresses that result.

## Extending tool collection

Use the command adapter for scripts, simulators, solvers and model-provider clients that implement the documented JSON envelope. Record model/version, sampling parameters and seed in inputs or result details when relevant. A model provider adapter must actually call that provider before its results can be described as live provider evidence. The bundled live example runs local tools; it does not call an LLM service.

Adding an adapter does not change the language’s reasoning semantics. Evidence kinds describe the role/data contract; execution modes describe how a tool produces output. Their meanings are independent.

## Regeneration and validation

`make check-generated` regenerates Python sources using the pinned, digest-checked ANTLR distribution and detects drift. `make test` exercises syntax, semantic errors, mathematical mode calculations, subargument propagation, temporal assumptions, tool execution, SQLite persistence and real stdio MCP calls. `make build` produces a source distribution and wheel. Standard use installs the generated parser and does not require Java.
