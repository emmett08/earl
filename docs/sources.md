# Sources for the current language and runtime

These primary sources inform the language, inference methods and host interfaces. The implementation and [argument model](argument-model.md) define executable EAL/3 semantics. A citation to another calculus or package does not establish that EAL implements it or has its measured performance.

## Contents

- [Argument and reasoning models](#argument-and-reasoning-models)
- [Reasoning methods](#reasoning-methods)
- [Core language design](#core-language-design)
- [Language implementation](#language-implementation)
- [MCP integration](#mcp-integration)
- [Project-specific decisions](#project-specific-decisions)
- [External argumentation and enthymeme models](#external-argumentation-and-enthymeme-models)
- [Model host interface](#model-host-interface)

## Argument and reasoning models

**Stephen E. Toulmin, _The Uses of Argument_, updated edition, Cambridge University Press, 2003; first published 1958.** [Publisher and DOI](https://doi.org/10.1017/CBO9780511840005).

Toulmin supplies the conceptual distinction between a claim, its grounds, the inference connecting them, support for that inference, qualification and possible rebuttal. EAL expresses these functions through engineering terms and explicit dependencies. The publisher record was checked; this project does not reproduce the book or claim that its complete text was inspected during implementation.

**Sanjay Modgil and Henry Prakken, “The ASPIC+ framework for structured argumentation: a tutorial”, _Argument & Computation_ 5(1), 31–62, 2014.** [DOI](https://doi.org/10.1080/19462166.2013.869766), [author-hosted full text](https://webspace.science.uu.nl/~prakk101/pubs/ASPICtutorial.pdf).

Sections 3.2–3.4 define structured arguments, attacks and defeat. Section 4 explains choices required to instantiate the framework. EAL's core takes inspiration from explicit premises and targeted objections. The optional [bounded method](aspic-method.md) now chooses a finite atom language, strict/defeasible rules, an explicit contrariness relation, one global ordinal argument ordering and grounded acceptance. These choices instantiate a fragment; the implementation makes no full-ASPIC+ claim.

**Sanjay Modgil and Henry Prakken, “A general account of argumentation with preferences”, _Artificial Intelligence_ 195, 361–397, 2013.** [DOI](https://doi.org/10.1016/j.artint.2012.10.008), [author-hosted corrected text](https://webspace.science.uu.nl/~prakk101/pubs/AIJfinalErratum.pdf).

This gives a formal account of preferences and defeat. Its consistency and closure results have assumptions; the presence of argument-shaped data alone does not establish those properties. EAL's authored objections do not implement this preference calculus.

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

Gentner treats analogy in terms of correspondences between represented domains, with an emphasis on relations. EAL's bounded feature-comparison method checks declared correspondences and reports mismatches. It does not implement Gentner's full relational structure-mapping theory or establish the truth of an unmeasured target property.

**Andreas Bauer, Martin Leucker and Christian Schallhart, “Runtime Verification for LTL and TLTL”, _ACM Transactions on Software Engineering and Methodology_ 20(4), article 14, 2011.** [DOI](https://doi.org/10.1145/2000799.2000800), [author institution's publication page](https://www.isp.uni-luebeck.de/research/publications/runtime-verification-ltl-and-tltl).

The paper explains why partial observations require care when evaluating temporal properties. EAL implements bounded trace checks with an explicit scope; it does not implement the paper's general LTL/TLTL monitor construction. A result over recorded samples establishes only the declared sampled-trace property.

## Core language design

The primary language-design sources and the precise EAL adaptations are recorded in [EAL/3 design decisions](eal3-design.md#primary-recommendations-and-adaptations): Hoare on simplicity, readability and error detection; Wirth on notation and checked extension boundaries; Steele on composable language growth; Felleisen on constrained translations and eliminability; and Parr on independent implementation passes. The source recommendations do not establish expert endorsement, a formal expressiveness theorem or measured model gains for EAL/3.

## Language implementation

**Terence Parr, _Language Implementation Patterns: Create Your Own Domain-Specific and General Programming Languages_, Pragmatic Bookshelf, 2009.** ISBN 9781934356456. [Publisher](https://pragprog.com/titles/tpdsl/language-implementation-patterns/), [publisher-provided AST-pattern extract](https://media.pragprog.com/titles/tpdsl/patterns.pdf), [contents](https://media.pragprog.com/titles/tpdsl/toc.pdf) and [typing extract](https://media.pragprog.com/titles/tpdsl/static.pdf).

The design separates parsing, typed internal representations, name resolution and evaluation. The published extract describes heterogeneous abstract syntax trees, including nodes with named fields; it informs the representation choice without dictating the domain semantics. The book predates ANTLR4, so current ANTLR4 APIs are taken from the later reference and official documentation.

**Terence Parr, _The Definitive ANTLR 4 Reference_, Pragmatic Bookshelf, 2013.** ISBN 9781934356999. [Publisher](https://pragprog.com/titles/tpantlr2/the-definitive-antlr-4-reference/).

Its documented topics include grammar design, parse-tree listeners and visitors, separating grammar from application code, symbol validation and error reporting. Those concerns guide the parser boundary. Parsing establishes syntactic structure; subsequent domain analysis and evaluation supply the language's meaning.

**ANTLR project, official ANTLR4 documentation and source.** [Documentation](https://github.com/antlr/antlr4/tree/master/doc), [parse-tree visitor API](https://www.antlr.org/api/Java/org/antlr/v4/runtime/tree/ParseTreeVisitor.html).

Generated parser code and its runtime must use compatible, explicitly selected versions. The build configuration identifies the versions used by this repository.

## MCP integration

**Model Context Protocol maintainers, architecture and protocol specification.** [Architecture](https://modelcontextprotocol.io/docs/learn/architecture), [dated tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

MCP connects application hosts and clients to server capabilities. A text-only model can produce a structured request for a host adapter to validate and dispatch. Protocol integration supplies that interaction boundary; native model tool invocation remains a capability of the model's application.

**PrefectHQ, FastMCP 4 documentation and source.** [Server transports](https://gofastmcp.com/deployment/running-server), [HTTP deployment](https://gofastmcp.com/deployment/http), [middleware](https://gofastmcp.com/servers/middleware), [SDK v1 porting guide](https://gofastmcp.com/getting-started/upgrading/from-mcp-sdk-v1), [release source](https://github.com/PrefectHQ/fastmcp/tree/v4.0.10).

FastMCP supplies typed operation registration, stdio and Streamable HTTP runners, middleware and authentication hooks. EAL selects FastMCP `4.0.10` for one adapter over both transports. Its strict validation, exposure allowlist, immutable settings and acquisition coordination are EAL implementation choices; see [MCP architecture](mcp-architecture.md).

**Model Context Protocol maintainers, Python SDK 2.** [SDK source](https://github.com/modelcontextprotocol/python-sdk/tree/v2.2.0), [v2 protocol and API changes](https://github.com/modelcontextprotocol/python-sdk/blob/v2.2.0/docs/whats-new.md).

EAL pins SDK `2.2.0`, which underlies FastMCP 4. SDK 2 supports the `2026-07-28` discovery profile and earlier handshake profiles. EAL's protocol tests exercise `2025-11-25` and `2026-07-28` tool discovery and invocation; application contract tests compare stdio and HTTP operation behaviour. Support for a protocol profile establishes the transport boundary, while observations and claim results retain their EAL identities and scope.

## Project-specific decisions

Evidence freshness, environment identity, assumption intervals, binding digests, tool declarations and result vocabulary are EAL design decisions. Their suitability depends on the intended engineering question and should be tested through executable examples and counterexamples rather than attributed to Toulmin, ASPIC+, Dung or ANTLR.

## External argumentation and enthymeme models

**Jean-Guy Mailly, [`pygarg` 1.0.2](https://pypi.org/project/pygarg/) and [source repository](https://github.com/jgmailly/pygarg).** This PySAT-backed package solves extension and acceptability queries for supplied abstract Dung argument-and-attack graphs under several semantics. It is a useful candidate if EAL needs preferred, stable, semi-stable or other abstract extension queries. It does not construct arguments, evidence obligations or attacks from EAL source, and it does not directly implement EAL's claim dependencies, alternative derivations and explanatory trace. The existing grounded solver covers the present graph contract; adopting `pygarg` would require an explicit adapter and differential tests for a specified new query.

**Daphne Odekerken and PyArg contributors, [PyArg documentation](https://daphneodekerken.github.io/PyArg/aspic_examples.html) and [source repository](https://github.com/DaphneOdekerken/PyArg).** The `python-argumentation` package exposes ASPIC+ theory construction, arguments, attacks and extensions. It is an external implementation to compare with the locally specified [finite method](aspic-method.md), not a dependency installed by this repository. A differential comparison needs a translation that equates premise classes, contraries, preferences, rule names, resource limits and grounded semantics. Either solver's result still needs reviewed bindings to the intended engineering claim and observations.

**Victor David and Anthony Hunter, “A Logic-based Framework for Decoding Enthymemes in Argument Maps Involving Implicitness in Premises and Claims”, _IJCAI 2025_, 4445–4453.** [Official paper and DOI](https://www.ijcai.org/proceedings/2025/495), [PDF](https://www.ijcai.org/proceedings/2025/0495.pdf). The work models missing premises or claims through implicit default rules and uses MaxSAT to select decodings that respect an argument map's support and attack relations. Its optimisation criterion and background theory address an enthymeme-decoding problem; they do not prove correspondence between arbitrary prose and an EAL claim. A candidate decoding needs independent applicability review before it can enter the checked argument procedure.

**Xuyao Feng and Anthony Hunter, “Making Implicit Premises Explicit in Logical Understanding of Enthymemes”, 2026, arXiv:2603.06114v3.** [Versioned record](https://arxiv.org/abs/2603.06114v3), [full text](https://arxiv.org/html/2603.06114v3). Sections 3–6 describe LLM-generated intermediate premises, a neural AMR parser and logical translation, and SAT-based reasoning with explicit semantic relaxation. The ARCT and ANLI experiments compare two fixed candidate premises; the discussion explicitly leaves unrestricted generation to further work. This motivates evaluating proposal and formal checking separately. It does not establish whole-document omission detection, exact preservation of prose meaning or empirical support for generated premises. EAL's [reconstruction guidance](argument-reconstruction.md) is a design adaptation, not an implementation of that pipeline.

**Yufeng Du and colleagues, “Context Length Alone Hurts LLM Performance Despite Perfect Retrieval”, 2025, arXiv:2510.05381v1.** [Versioned paper](https://arxiv.org/abs/2510.05381v1). The authors report degradation with increasing input length in experiments on five models and maths, question-answering and coding tasks, including conditions with successful retrieval. This supports comparing context strategies rather than treating nominal window size as evidence of effective reasoning. These tasks do not measure EAL enthymeme reconstruction, and the findings do not establish the performance of an untested model or deployment.

**`formal-argumentation` 0.3.0, [PyPI distribution and documented interfaces](https://pypi.org/project/formal-argumentation/), [source repository](https://github.com/ctoth/argumentation).** The package documents Dung and ASPIC+ operations, with optional solver and grounding dependencies. It is a possible external provider to evaluate after fixing exact task semantics, input limits, licensing, dependency and version contracts. It is not installed by EAL; package documentation alone does not establish substitutability with `solve_composed`.

## Model host interface

The [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) underlies the FastMCP stdio and HTTP protocol paths used by EAL. The strict JSON host can launch a local stdio subprocess or connect to an existing HTTP endpoint. The Python `ModelContextAdapter` produces bounded messages for an application-selected model without requiring native tool calling. Model capabilities, costs and availability belong to that application's selected deployment; they are not properties of EAL/3 source or argument semantics.

### Model reasoning and tool use: applicability review, 28 September 2026

The sources below inform component boundaries and evaluation requirements.
They do not establish that EAL implements the latest solution for every task.
Publication recency alone is insufficient reason to replace a calculation whose
stated mathematical contract remains appropriate. The Wilson interval, for
example, retains the sampling assumptions and reference case documented above.

**Patil et al., “The Berkeley Function Calling Leaderboard (BFCL): From Tool Use
to Agentic Evaluation of Large Language Models”, ICML 2025.**
[Proceedings and abstract](https://proceedings.mlr.press/v267/patil25a.html).
The benchmark distinguishes serial/parallel calls, abstention and stateful
multi-step behaviour; its reported findings identify persistent memory and
long-horizon reasoning difficulties. EAL adaptation: evaluate correct tool
selection, valid arguments, observation use and final scoped conclusions
separately. Successful MCP round trips test transport and execution, not model
selection competence.

**Choi et al., “ToolMATH: A Diagnostic Benchmark for Long-Horizon Tool Use under
Systematic Tool-Catalog Constraints”, arXiv:2602.21265v2, 18 May 2026.**
[Versioned abstract](https://arxiv.org/abs/2602.21265v2).
This preprint varies tool availability and distractors and measures behaviour
across dependent call chains. EAL adaptation: use task-scoped discovery and
registered one-call assessment where the application already knows the claim;
test missing capabilities, misleading alternatives and misuse of earlier
outputs. The present tests verify declared dependency traversal and evidence
reuse. They do not measure a model's robustness to those catalogue variations.

**Anthropic, “Writing effective tools for AI agents”, 11 September 2025.**
[Engineering guidance](https://www.anthropic.com/engineering/writing-tools-for-agents).
The authors recommend distinct tool purposes, useful bounded responses and
held-out evaluations recording errors, calls, tokens and runtime. EAL implements
claim-scoped planning, combined assessment and bounded packets with omission
markers and explanation references. Their effect on accuracy and total cost
requires comparative trials. This is provider engineering guidance, rather than
a theorem that shorter context improves every model.

**OpenAI, “Reasoning best practices”, live documentation inspected
28 September 2026.**
[Official guidance](https://developers.openai.com/api/docs/guides/reasoning-best-practices).
The guide recommends direct objectives and says explicit step-by-step prompts
are unnecessary for its reasoning models. It also describes preservation of
reasoning items around tool calls for applicable Responses API models. These are
model/API-specific requirements for the calling application. EAL's current host
dispatches one checked JSON request and its context adapter prepares messages;
neither owns a provider conversation loop. A native-tool adapter must preserve
the chosen provider's call IDs, required continuation items and tool results,
handle failed or incomplete calls and account for reasoning-token costs.
Applying one prompt or conversation format to every model needs evidence.

**Wang and Brorsson, “Rethinking Scale: Deployment Trade-offs of Small Language
Models under Agent Paradigms”, arXiv:2604.19299v1, 21 April 2026.**
[Versioned abstract](https://arxiv.org/abs/2604.19299v1).
The authors report a better performance/cost balance for single agents with
tools than their tested multi-agent alternatives. This preprint supports
including a single-agent condition; it does not establish a universal ranking
of agent designs or model sizes. EAL does not require multiple agents to assess
a registered argument.

**Shemla et al., “Internalizing Tool Knowledge in Small Language Models via
QLoRA Fine-Tuning”, arXiv:2605.17774v2, 26 May 2026.**
[Versioned abstract](https://arxiv.org/abs/2605.17774v2).
The authors report benefits from adapting small models to a fixed tool catalogue,
alongside forgetting on general benchmarks. The reported planning and judge
scores do not establish end-to-end EAL correctness. Fine-tuning is an application
option after measuring a stable task distribution; it is not required for the
interpreter or a general substitute for discovering current tool contracts.

For each selected model, evaluate both native-tool and host-prepared context
routes where supported. Pin model/version, reasoning effort, prompts, available
tools and budgets. Measure incorrect selection, invalid requests, retries,
unsupported conclusions, justified unresolved results, latency and total cost.
Retain failed trials. The application supplies the provider interaction; EAL
supplies the formal computation. Published model results and deterministic
interpreter tests establish different properties.
