# Sources and design decisions

Primary sources checked on 23 September 2026. These references explain the concepts used in EAL and the alternatives considered. The executable semantics are defined by the implementation and [argument model](argument-model.md); citing a formal framework does not establish that EAL implements that framework.

## Argument and reasoning models

**Stephen E. Toulmin, _The Uses of Argument_, updated edition, Cambridge University Press, 2003; first published 1958.** [Publisher and DOI](https://doi.org/10.1017/CBO9780511840005).

Toulmin supplies the conceptual distinction between a claim, its grounds, the inference connecting them, support for that inference, qualification and possible rebuttal. EAL expresses these functions through engineering terms and explicit dependencies. The publisher record was checked; this project does not reproduce the book or claim that its complete text was inspected during implementation.

**Sanjay Modgil and Henry Prakken, “The ASPIC+ framework for structured argumentation: a tutorial”, _Argument & Computation_ 5(1), 31–62, 2014.** [DOI](https://doi.org/10.1080/19462166.2013.869766), [author-hosted full text](https://webspace.science.uu.nl/~prakk101/pubs/ASPICtutorial.pdf).

Sections 3.2–3.4 define structured arguments, attacks and defeat. Section 4 explains choices required to instantiate the framework. EAL takes inspiration from explicit premises and targeted objections. Full ASPIC+ additionally requires a logical language, strict and defeasible rule sets, argument construction, a contrariness relation, argument preferences and specified acceptance semantics. The present implementation makes no full-ASPIC+ claim.

**Sanjay Modgil and Henry Prakken, “A general account of argumentation with preferences”, _Artificial Intelligence_ 195, 361–397, 2013.** [DOI](https://doi.org/10.1016/j.artint.2012.10.008), [author-hosted corrected text](https://webspace.science.uu.nl/~prakk101/pubs/AIJfinalErratum.pdf).

This gives the more detailed formal account behind the structured-reasoning extension discussed in the argument model. Its consistency and closure results have assumptions; the presence of argument-shaped data alone does not establish those properties. The corrected author-hosted version was inspected.

**Phan Minh Dung, “On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games”, _Artificial Intelligence_ 77(2), 321–357, 1995.** [DOI](https://doi.org/10.1016/0004-3702(94)00041-X), [original paper hosted by Texas A&M](https://cse-robotics.engr.tamu.edu/dshell/cs631/papers/dung95acceptability.pdf).

Dung provides the grounded semantics implemented by the separate `eal_grounded` operation. That operation evaluates explicit argument-and-attack graphs, including cyclic graphs. Its input contract and verification are documented in [grounded reasoning](grounded-reasoning.md).

## Reasoning methods

**Edwin B. Wilson, “Probable Inference, the Law of Succession, and Statistical Inference”, _Journal of the American Statistical Association_ 22(158), 209–212, 1927.** [DOI](https://doi.org/10.1080/01621459.1927.10502953), [original article scan hosted by McGill](https://jhanley.biostat.mcgill.ca/c607/ch08/wilson_jasa_1927.pdf).

The inductive calculation uses the Wilson score interval for a Bernoulli success probability. The [NIST Dataplot reference](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/agcoulci.htm) supplies the formula and a numerical example. Its confidence level refers to a sampling procedure under the stated model; it is not a posterior probability that an engineering claim is true.

**David Poole, “Probabilistic Horn abduction and Bayesian networks”, _Artificial Intelligence_ 64(1), 81–129, 1993.** [DOI](https://doi.org/10.1016/0004-3702(93)90061-F), [author-hosted paper](https://www.cs.ubc.ca/~poole/papers/pha-bn.pdf).

Poole connects hypotheses, probabilistic evidence and abductive explanation in a formal language. EAL's bounded Bayesian hypothesis-ranking calculation is a smaller operation: it conditions declared priors on supplied likelihoods. It does not implement probabilistic Horn abduction or discover an exhaustive hypothesis set.

**Judea Pearl, “Causal inference in statistics: An overview”, _Statistics Surveys_ 3, 96–146, 2009.** [DOI](https://doi.org/10.1214/09-SS057), [author-hosted full text](https://ftp.cs.ucla.edu/pub/stat_ser/r350-reprint.pdf).

Sections 3.2.1 and 3.4 distinguish interventions and counterfactual evaluation within structural causal models. These support the distinction between an observed association, an intervention contrast and a counterfactual conditional on a causal model. The bounded EAL methods do not discover causal structure or establish that a supplied model represents the physical system.

**Dedre Gentner, “Structure-mapping: A theoretical framework for analogy”, _Cognitive Science_ 7(2), 155–170, 1983.** [DOI](https://doi.org/10.1207/s15516709cog0702_3), [author-hosted full text](https://groups.psych.northwestern.edu/gentner/papers/Gentner83.2b.pdf).

Gentner treats analogy in terms of correspondences between represented domains, with an emphasis on relations. EAL's initial feature-comparison method checks declared correspondences and reports mismatches. It does not implement Gentner's full relational structure-mapping theory or establish the truth of an unmeasured target property.

**Andreas Bauer, Martin Leucker and Christian Schallhart, “Runtime Verification for LTL and TLTL”, _ACM Transactions on Software Engineering and Methodology_ 20(4), article 14, 2011.** [DOI](https://doi.org/10.1145/2000799.2000800), [author institution's publication page](https://www.isp.uni-luebeck.de/research/publications/runtime-verification-ltl-and-tltl).

The paper explains why partial observations require care when evaluating temporal properties. EAL implements bounded trace checks with an explicit scope; it does not implement the paper's general LTL/TLTL monitor construction. A result over recorded samples establishes only the declared sampled-trace property.

## Core language design

The primary language-design sources and the precise EAL adaptations are recorded in [EAL/2 design decisions](eal2-design.md#expert-recommendations-and-eal-adaptations): Hoare on simplicity, readability and error detection; Wirth on notation and checked extension boundaries; Steele on composable language growth; Felleisen on constrained translations and eliminability; and Parr on independent implementation passes. The source recommendations do not establish expert endorsement, a formal expressiveness theorem or measured model gains for EAL/2.

## Language implementation

**Terence Parr, _Language Implementation Patterns: Create Your Own Domain-Specific and General Programming Languages_, Pragmatic Bookshelf, 2009.** ISBN 9781934356456. [Publisher](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [publisher-provided AST-pattern extract](https://media.pragprog.com/titles/tpdsl/patterns.pdf).

The design separates parsing, typed internal representations, name resolution and evaluation. The published extract describes heterogeneous abstract syntax trees, including nodes with named fields; it informs the representation choice without dictating the domain semantics. The book predates ANTLR4, so current ANTLR4 APIs are taken from the later reference and official documentation.

**Terence Parr, _The Definitive ANTLR 4 Reference_, Pragmatic Bookshelf, 2013.** ISBN 9781934356999. [Publisher](https://pragprog.com/titles/tpantlr2/the-definitive-antlr-4-reference/).

Its documented topics include grammar design, parse-tree listeners and visitors, separating grammar from application code, symbol validation and error reporting. Those concerns guide the parser boundary. Parsing establishes syntactic structure; subsequent domain analysis and evaluation supply the language's meaning.

**ANTLR project, official ANTLR4 documentation and source.** [Documentation](https://github.com/antlr/antlr4/tree/master/doc), [parse-tree visitor API](https://www.antlr.org/api/Java/org/antlr/v4/runtime/tree/ParseTreeVisitor.html).

Generated parser code and its runtime must use compatible, explicitly selected versions. The build configuration identifies the versions used by this repository.

## MCP integration

**Model Context Protocol maintainers, architecture and protocol specification.** [Architecture](https://modelcontextprotocol.io/docs/learn/architecture), [dated tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), [2026-07-28 release announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/).

MCP connects application hosts and clients to server capabilities. A text-only model can produce a structured request for a host adapter to validate and dispatch. Protocol integration alone does not give that model native tool invocation. This implementation uses the official Python SDK 1.30.0 and selects the 2025-11-25 protocol profile; it does not claim support for the later 2026 protocol. The runtime tests exercise negotiation and tool invocation for the selected profile.

## Project-specific decisions

Evidence freshness, environment identity, assumption intervals, deterministic versus nondeterministic tool declarations, and the exact result vocabulary are EAL design decisions. Their suitability depends on the intended engineering question. They should be assessed through executable examples and counterexamples, rather than attributed to Toulmin, ASPIC+, Dung or ANTLR.
