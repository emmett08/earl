# ANTLR4 and Parr’s patterns

Implement selected patterns from Terence Parr’s Language Implementation Patterns as working components with explicit interfaces and tests. Choose them from the language’s needs. The book predates ANTLR4; adapt the architecture to current generated parse trees and visitors, and pin generator/runtime together. Check the publisher’s [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf) and [typing excerpt](https://media.pragprog.com/titles/tpdsl/static.pdf) when attributing individual patterns.

| Book pattern family | Application to this language | Demonstration |
|---|---|---|
| P.8; P.10–11 | Recognise source and lower it into an explicit typed intermediate form | Parsed structure and lowered meaning agree on representative and malformed inputs |
| P.13 | Put traversal/lowering logic in external visitors | Generated recognisers remain separate from language semantics |
| P.16; P.17 when modules require it | Resolve names within defined scopes | References resolve to one entity of the required kind; duplicates/ambiguities are diagnosed |
| P.20 and P.22 where expressions require them | Determine types and enforce compatible operations | Incompatible values, units or propositions are rejected before their results can support claims |
| P.25, adapted to argument dependencies | Interpret checked semantic objects | Specified operations produce reproducible results and inspectable derivations |
| P.29–31 and templates when needed | Translate a checked representation into a solver format or readable output | Translation preserves the intended proposition; formatting preserves meaning |

Record the chosen pattern, problem it solves, implementing component and behavioural check. Distinguish an architectural adaptation from an implementation of every example in the book. Include only applicable patterns: hand-written backtracking parsers, object-oriented type systems and bytecode machines require a concrete need. A generated ANTLR4 parser is not a claim that all of the book’s alternative recognisers have been separately implemented.

1. Define a grammar that recognises surface structure and preserves EOF, comments, escaped strings and locations. Keep the lexer’s keyword decisions deliberate.
2. Generate lexer, parser and visitor. Check both lexer and parser diagnostics. Abort lowering after syntax failure rather than interpreting ANTLR recovery output.
3. Use an external visitor to create a small typed AST/intermediate representation, independent of generated contexts.
4. Collect symbols before resolving uses, allowing deliberate forward references. Maintain reference categories; an evidence identifier cannot silently resolve as a claim.
5. Check cardinality, reference kinds, expression types, numeric bounds, time values and dependency structure. Fail with source-aware diagnostics before executing any tools.
6. Interpret the checked representation with explicit inputs and time. Keep side effects in adapters; keep the evaluator deterministic for fixed records even when record-producing tools are stochastic.
7. Serialise structured explanations and keep source identity in reports. Provide canonical readable output and meaning-preserving round trips when the language has textual and structured forms.

This corresponds to parsing, intermediate representation, external visitors, symbol tables, static checking and high-level interpretation. A bytecode VM is optional and usually unnecessary for a first reasoning DSL.

Retain the grammar and generated sources, generator version/digest and a regeneration script. Test regeneration drift. Distribute generated sources so users of the interpreter do not need Java. Include malformed lexer input, trailing tokens, duplicate declarations, wrong reference categories and error recovery in parser tests. Reject negative or nonfinite freshness bounds. Bound source size, AST size and dependency depth.
