# Implementation architecture

The implementation follows Terence Parr’s separation of parsing, intermediate representation, symbol analysis, static checks and high-level interpretation. Language Implementation Patterns predates ANTLR4; the design uses its architectural patterns with the ANTLR4 visitor API.

| Stage | Implementation | Result |
|---|---|---|
| Lexing/parsing | `grammar/EAL.g4`, generated lexer/parser | Complete parse tree or syntax diagnostics |
| Lowering | `parser.py`, external visitor | Typed declarations independent of generated contexts |
| Symbol and semantic analysis | `semantics.py` | Unique symbols, typed references, bounds, applicability dates, acyclic premise graph, method/evidence contract checks |
| Method computation | `modes.py` | Method-specific calculation and explicit output fields |
| Argument interpretation | `evaluator.py` | Scoped support, objections, dependencies and method traces at a supplied time |
| Dialectical calculation | `dialectic.py` | Grounded extension of an explicit finite attack graph |
| Tool execution | `runtime.py` | Bounded command or file observations |
| Persistence | `store.py` | SQLite collections, observations and reasoning results |
| Interfaces | `cli.py`, `server.py`, `host.py` | Shared operations through CLI or official MCP SDK |

There are no embedded application actions in the grammar. The pure evaluator performs no IO and takes an explicit time; fixed source, records, context and time yield the same result. A nondeterministic collector can supply different observations on repeated runs while interpretation of each fixed observation set remains deterministic.

The parser rejects lexer errors and parser recovery diagnostics before lowering. It rejects duplicate symbols and excessive source/declaration/dependency size. Predicates use a closed set of scalar comparisons rather than general-purpose code execution. JSON input has no executable expressions. The runtime’s command registry supplies executable argument vectors; a language source cannot replace the configured executable with a shell fragment.

## Extending a reasoning method

Specify the question answered, evidence schema, computation, output meaning, necessary modelling assumptions and failure conditions. Extend `modes.py` and its contract checks, the grammar’s mode enumeration where needed, then update the documentation and examples. Add a known-answer calculation and a counterexample that would produce an overstrong conclusion if the method were misinterpreted. Keep model assumptions represented as argument dependencies where they affect a conclusion.

`structured` applies an author-supplied conditional support relation. The other modes compute bounded formal, numerical or relational results; their output predicates specify the condition relevant to an argument. A proof concerning a formula, or an interval concerning a supplied sample, does not automatically establish that a prose claim accurately expresses that result.

## Extending tool collection

Use the command adapter for scripts, simulators, solvers and model-provider clients that implement the documented JSON envelope. Record model/version, sampling parameters and seed in inputs or result details when relevant. A model provider adapter must actually call that provider before its results can be described as live provider evidence. The bundled live example runs local tools; it does not call an LLM service.

Adding an adapter does not change the language’s reasoning semantics. Evidence kinds describe the role/data contract; execution modes describe how a tool produces output. Their meanings are independent.

## Regeneration and validation

`make check-generated` regenerates Python sources using the pinned, digest-checked ANTLR distribution and detects drift. `make test` exercises syntax, semantic errors, mathematical mode calculations, subargument propagation, temporal assumptions, tool execution, SQLite persistence and real stdio MCP calls. `make build` produces a source distribution and wheel. Standard use installs the generated parser and does not require Java.
