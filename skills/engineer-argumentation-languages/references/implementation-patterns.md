# ANTLR4 and Parr’s patterns

Use the architectural ideas of Terence Parr’s Language Implementation Patterns rather than copying its older tool syntax. The book predates ANTLR4. Verify current target documentation and pin generator/runtime together.

1. Define a grammar that recognises surface structure and preserves EOF, comments, escaped strings and locations. Keep the lexer’s keyword decisions deliberate.
2. Generate lexer, parser and visitor. Check both lexer and parser diagnostics. Abort lowering after syntax failure rather than interpreting ANTLR recovery output.
3. Use an external visitor to create a small typed AST/intermediate representation, independent of generated contexts.
4. Collect symbols before resolving uses, allowing deliberate forward references. Maintain reference categories; an evidence identifier cannot silently resolve as a claim.
5. Check cardinality, reference kinds, expression types, numeric bounds, time values and dependency structure. Fail with source-aware diagnostics before executing any tools.
6. Interpret the checked representation with explicit inputs and time. Keep side effects in adapters; keep the evaluator deterministic for fixed records even when record-producing tools are stochastic.
7. Serialise structured explanations and keep source identity in reports.

This corresponds to parsing, intermediate representation, external visitors, symbol tables, static checking and high-level interpretation. A bytecode VM is optional and usually unnecessary for a first reasoning DSL.

Retain the grammar and generated sources, generator version/digest and a regeneration script. Test regeneration drift. Distribute generated sources so users of the interpreter do not need Java. Include malformed lexer input, trailing tokens, duplicate declarations, wrong reference categories and error recovery in parser tests. Reject negative or nonfinite freshness bounds. Bound source size, AST size and dependency depth.
