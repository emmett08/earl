# Primary sources

Consulted 23 September 2026. Verify current software interfaces before changing implementation versions.

- Terence Parr, Language Implementation Patterns, Pragmatic Bookshelf, 2009. Publisher overview and contents: https://pragprog.com/titles/tpdsl/language-implementation-patterns/ . Architectural source for intermediate trees, visitors, symbol tables, static checking and interpreters; it predates ANTLR4. Publisher contents: https://media.pragprog.com/titles/tpdsl/toc.pdf ; supplied typing excerpt: https://media.pragprog.com/titles/tpdsl/static.pdf . These extracts were inspected; no claim is made to have inspected an entire supplied book.
- ANTLR project: https://www.antlr.org/ and https://github.com/antlr/antlr4/tree/4.13.2/doc . Generated parse trees and target-specific integration. Pin 4.13.2 generator with 4.13.2 runtime when using that version.
- Stephen Toulmin, The Uses of Argument, updated edition, Cambridge University Press, 2003: https://doi.org/10.1017/CBO9780511840005 . Argument components; not an executable semantics specification.
- Sanjay Modgil and Henry Prakken, The ASPIC+ framework for structured argumentation: a tutorial, Argument & Computation 5(1), 2014, pp. 31–62. https://doi.org/10.1080/19462166.2013.869766 ; author manuscript https://webspace.science.uu.nl/~prakk101/pubs/ASPICtutorial.pdf . Strict/defeasible inference, attacks, defeats and requirements on instantiations.
- Phan Minh Dung, On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games, Artificial Intelligence 77(2), 1995, pp. 321–357: https://doi.org/10.1016/0004-3702(94)00041-X . Abstract argumentation and extension semantics.
- Model Context Protocol, published 2025-11-25 tools specification: https://modelcontextprotocol.io/specification/2025-11-25/server/tools ; lifecycle https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle ; official Python SDK https://github.com/modelcontextprotocol/python-sdk . Protocol operations and host integration, not a reasoning calculus.

The proposed combination of conditional assumption validation, freshness, recorded tool outputs and argument evaluation is an engineering language design choice. Do not attribute that entire design to any individual source above.
