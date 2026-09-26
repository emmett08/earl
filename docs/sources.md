# Sources and retained references

The established language and reasoning references below were checked for the earlier design on 23 September 2026. Selected publisher and author records for current model-assisted research were checked on 25 September 2026; earlier development artefacts remain accessible through the pre-reset Git commit but have not been freshly reviewed as a body of evidence. The implementation and [argument model](argument-model.md) define executable EAL/2 semantics. A citation to another calculus, model or benchmark does not establish that EAL implements it or has its measured performance.

## Contents

- [Argument and reasoning models](#argument-and-reasoning-models)
- [Reasoning methods](#reasoning-methods)
- [Core language design](#core-language-design)
- [Language implementation](#language-implementation)
- [MCP integration](#mcp-integration)
- [Project-specific decisions](#project-specific-decisions)
- [Model-assisted reasoning and study design](#model-assisted-reasoning-and-study-design)
- [Model host and provider interfaces](#model-host-and-provider-interfaces)
- [Retired repository artefacts](#retired-repository-artefacts)

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

The primary language-design sources and the precise EAL adaptations are recorded in [EAL/2 design decisions](eal2-design.md#primary-recommendations-and-adaptations): Hoare on simplicity, readability and error detection; Wirth on notation and checked extension boundaries; Steele on composable language growth; Felleisen on constrained translations and eliminability; and Parr on independent implementation passes. The source recommendations do not establish expert endorsement, a formal expressiveness theorem or measured model gains for EAL/2.

## Language implementation

**Terence Parr, _Language Implementation Patterns: Create Your Own Domain-Specific and General Programming Languages_, Pragmatic Bookshelf, 2009.** ISBN 9781934356456. [Publisher](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [publisher-provided AST-pattern extract](https://media.pragprog.com/titles/tpdsl/patterns.pdf), [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf) and [typing extract](https://media.pragprog.com/titles/tpdsl/static.pdf).

The design separates parsing, typed internal representations, name resolution and evaluation. The published extract describes heterogeneous abstract syntax trees, including nodes with named fields; it informs the representation choice without dictating the domain semantics. The book predates ANTLR4, so current ANTLR4 APIs are taken from the later reference and official documentation.

**Terence Parr, _The Definitive ANTLR 4 Reference_, Pragmatic Bookshelf, 2013.** ISBN 9781934356999. [Publisher](https://pragprog.com/titles/tpantlr2/the-definitive-antlr-4-reference/).

Its documented topics include grammar design, parse-tree listeners and visitors, separating grammar from application code, symbol validation and error reporting. Those concerns guide the parser boundary. Parsing establishes syntactic structure; subsequent domain analysis and evaluation supply the language's meaning.

**ANTLR project, official ANTLR4 documentation and source.** [Documentation](https://github.com/antlr/antlr4/tree/master/doc), [parse-tree visitor API](https://www.antlr.org/api/Java/org/antlr/v4/runtime/tree/ParseTreeVisitor.html).

Generated parser code and its runtime must use compatible, explicitly selected versions. The build configuration identifies the versions used by this repository.

## MCP integration

**Model Context Protocol maintainers, architecture and protocol specification.** [Architecture](https://modelcontextprotocol.io/docs/learn/architecture), [dated tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), [2026-07-28 release announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/).

MCP connects application hosts and clients to server capabilities. A text-only model can produce a structured request for a host adapter to validate and dispatch. Protocol integration alone does not give that model native tool invocation. This implementation uses the official Python SDK 1.30.0 and selects the 2025-11-25 protocol profile; it does not claim support for the later 2026 protocol. The runtime tests exercise negotiation and tool invocation for the selected profile.

## Project-specific decisions

Evidence freshness, environment identity, assumption intervals, binding digests and the exact result vocabulary are EAL design decisions. The current grammar no longer declares deterministic versus nondeterministic tool modes. Their suitability depends on the intended engineering question. They should be assessed through executable examples and counterexamples, rather than attributed to Toulmin, ASPIC+, Dung or ANTLR.

## Model-assisted reasoning and study design

The studies below motivate testable comparisons: interpreter delegation, solver feedback, formal argumentation, completeness-sensitive negative answers, adaptive evaluation, routing and representation effects. Each result belongs to its own task, model and evaluation setting. None supplies an estimate of EAL/2's advantage over prose or meaning-equivalent JSON. Historical papers and prior versions are retained as source links; the selected publisher/author records reviewed on 25 September 2026 do not constitute full-paper replication.

### Scholarly references from retired studies

- [Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning](https://aclanthology.org/2023.findings-emnlp.248/)
- [Grammar-Constrained Decoding Makes Large Language Models Better Logical Parsers](https://aclanthology.org/2025.acl-industry.34/)
- [The Hidden Cost of Structure](https://aclanthology.org/2025.ranlp-1.124/)
- [Gao et al., PAL](https://arxiv.org/abs/2211.10435)
- [Zhou et al.](https://arxiv.org/abs/2303.11315)
- [Turpin et al.](https://arxiv.org/abs/2305.04388)
- [Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design](https://arxiv.org/abs/2310.11324v2)
- [Tyen et al.](https://arxiv.org/abs/2311.08516)
- [The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions](https://arxiv.org/abs/2404.13208)
- [When Absence Is Evidence: Evaluating Completeness-Sensitive Negative Reasoning in Large Language Models](https://arxiv.org/abs/2608.04591)
- [Equivalence Tests: A Practical Primer for t Tests, Correlations, and Meta-Analyses](https://doi.org/10.1177/1948550617697177)
- [Argumentative Large Language Models for Explainable and Contestable Claim Verification](https://doi.org/10.1609/aaai.v39i14.33637)
- [A Knowledge Compilation Map](https://doi.org/10.1613/jair.989)
- [Efficient Computation of Extensions for Dynamic Abstract Argumentation Frameworks: An Incremental Approach](https://doi.org/10.24963/ijcai.2017/8)
- [LLM-ASPIC+: A Neuro-Symbolic Framework for Defeasible Reasoning](https://doi.org/10.3233/FAIA250981)
- [Causal Inference: What If](https://miguelhernan.org/whatifbook)
- [Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)
- [RouteLLM: Learning to Route LLMs from Preference Data](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html)
- [PAL: Program-aided Language Models](https://proceedings.mlr.press/v202/gao23f.html)
- [Completeness of Queries over Incomplete Databases](https://www.vldb.org/pvldb/vol4/p749-razniewski.pdf)

## Model host and provider interfaces

These are version- and service-dependent interface pointers retained from earlier studies. Check their current contracts and the selected model snapshots before reuse; the list asserts no current availability, price or capability.

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [structured output](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting)
- [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1)
- [mini / GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [nano / GPT-4.1 nano / OpenAI GPT-4.1 nano model page / OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4.1-nano)
- [GPT-5](https://developers.openai.com/api/docs/models/gpt-5)
- [mini / GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini)
- [nano](https://developers.openai.com/api/docs/models/gpt-5-nano)
- [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [`POST /v1/embeddings` contract](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Retired repository artefacts

The repository reset removed earlier experiments, fixtures and notes from the current tree. Their prior state remains in the [pre-reset commit](https://github.com/emmett08/earl/tree/a9cdabee643118ff3ae28b3ec5c346427cca8cad). Those exposed development tasks do not establish comparative benefits for the current implementation. The subsequently removed workflow example and benchmark plans remain at [commit 0fddb9f](https://github.com/emmett08/earl/tree/0fddb9f5280711d9e10efa85b51bad2efcf89e2b).

### Other repository references

- [PR #3](https://github.com/emmett08/earl/pull/3)
