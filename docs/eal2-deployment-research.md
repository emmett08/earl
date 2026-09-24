# When should an EAL/2 system be used?

**Research and decision model, 23 September 2026.** The model below is a proposed, falsifiable account of system performance. Its coefficients have not been estimated on independent tasks. The cited studies concern other languages, models and datasets; they motivate predictions rather than establish an EAL/2 effect.

## The decision and the evidence already available

An EAL file is a representation of a question, its evidence requirements and its support and attack relations. Its words do not execute a method or compel a model to use the computed result. A receiving model must still find the relevant declaration, match the observation to the formal question, perform the method, resolve objections and report the status. A tool can perform the specified finite operations, while an application host can route the question and own the reported status. Neither checks whether the original engineering brief was faithfully formalised or whether a measurement came from the physical system claimed.

The repository's [180-call notation diagnostic](eal2-evidence-failure-analysis.md) found 4/10 complete correct raw EAL answers and 5/10 meaning-equivalent JSON answers across five exposed task types and dependent repeats. Earlier [EAL/2 host trials](eal2-model-results.md) found GPT-4.1 nano at 6/12 unaided versus 10/12 with native delegation, and GPT-4.1 mini at 8/12 versus 12/12 with text delegation. Every delegated condition cost more per correct task and took longer on those six exposed synthetic task types. The [producer–recipient pilot](eal2-relay-results.md) found 12/12 for a full-model tool producer followed by nano with a tool-evidence packet, versus 8/12 with the producer's answer alone. The producer alone was already 12/12: the packet prevented damage in the recipient, and added cost. These observations support a **system design candidate**, not a population result or a demonstrated advantage for EAL syntax.

PAL [1] and Logic-LM [2] give independent reasons to separate natural-language translation from executable reasoning. LLM-ASPIC+ [3] reports larger gains from a formal argumentation solver at greater defeasible depth, but its shallowest comparison can favour chain-of-thought and its remaining errors include neural rule triggering and instantiation. Thus the most promising task class is a recurring, scoped decision with several dependent routes, adverse findings and later revisions. The formalisation should be reviewed before it is reused.

## A model that can fail

Let a route \(r\) be one of: direct model with records; model with a short EAL-use skill and raw file; EAL interpreter plus host-owned status; EAL interpreter plus host-owned status and a small model rendering the explanation; an equivalent JSON/standalone checker with the same host, observations and methods; or a stronger reasoning model. For query \(x\), record the model, graph depth, number of active attacks and alternative routes, evidence scope, revision count, source age, reference length and the availability of a reviewed formalisation. Define:

\[
q_r(x)=P(\text{correct qualified status}\mid x,r),\qquad
f_r(x)=P(\text{reference status is not supported, but reported supported}\mid x,r).
\]

For a checked route, let \(S\) mean that the source formalises the actual question, \(E\) that the observation is authentic and eligible, \(M\) that the registered method and graph compute the declared semantics, and \(H\) that the host reports that result. The chain rule gives the exact all-gates-success probability without assuming independence, conditional on the query and route throughout:

\[
p_G(x,r)=P(S\mid x,r)P(E\mid S,x,r)P(M\mid S,E,x,r)P(H\mid S,E,M,x,r).
\]

This probability **is not accuracy**: a response may happen to be correct even when a gate fails. The observable accuracy is

\[
q_r(x)=P(Y=Y^*\mid G,r,x)p_G(x,r)
    +P(Y=Y^*\mid \neg G,r,x)[1-p_G(x,r)].
\]

The gate decomposition makes proposed changes testable. A more legible grammar, constrained generation or authoring skill should chiefly change \(P(S)\); acquisition and scope checks should change \(P(E\mid S)\); method extensions and interpreter fixes should change \(P(M\mid S,E)\); a host-owned final status should change \(P(H\mid S,E,M)\). An ordinary skill may raise the chance that a model invokes the tool, but cannot guarantee the answer if it leaves the final status to free generation. A model with no tool interface can receive a compact host assessment from an external wrapper; tool ability is therefore a property of the **system route**, not an absolute property of the model. For an uncovered domain or unauthenticated source, the checked route should state its limit, rather than inflate \(q_r\) through a wrong but internally consistent formalisation.

Fit \(q_r\) and \(f_r\) from held-out briefs with a prespecified hierarchical model, using task root and author effects and route interactions with graph depth, attacks, revisions, source validity, context length and model class. Use flexible depth terms: a formal pipeline may lose on easy one-step questions through translation and tool overhead, gain when conflict resolution dominates, then lose on highly ambiguous briefs through source-authoring errors. This is a **predicted intermediate regime**, not a measured curve. Report calibration and intervals for new task roots; repeated calls on one root are dependent observations. Choose a route by the application-specific loss

\[
r^*(x)=\arg\min_r\{\lambda_e[1-q_r(x)]+\lambda_f f_r(x)+C_r(x)+\lambda_t T_r(x)\},
\]

where \(C\) is total money or labour cost and \(T\) is elapsed time in comparable units. A hard cap on false support may take precedence over this weighted loss. A router learned from these estimates must itself be tested on new roots and must use only information available before answering. RouteLLM [4] demonstrates the general value of measured cost-quality routing, not an EAL-specific routing function.

## Reuse by one author and many consumers

Suppose a first engineer and a strong model author and review an EAL source for a recurring question. Later developers and small models submit **new observations and scopes**, so the source cannot contain their final answers. Let \(F_E\) be the original drafting, checking and review cost, \(J\) the number of subsequent source revisions, \(U_E\) their mean cost, \(N\) the number of consumer decisions, and \(c_E\) the mean per-decision cost of acquisition, execution, handoff and response. Relative to a baseline with initial cost \(F_B\), revision cost \(U_B\) and per-decision cost \(c_B\), EAL breaks even in total cost when

\[
F_E+J U_E+N c_E<F_B+J U_B+N c_B,
\qquad N>\frac{F_E-F_B+J(U_E-U_B)}{c_B-c_E}\quad(c_B>c_E).
\]

For repeated direct prompting, \(F_B\) may be small; an equal JSON checker has its own substantial \(F_B\). If \(c_B\leq c_E\), no positive \(N\) can recover a positive EAL setup disadvantage through per-decision savings. Measure author labour, review, failed attempts, model input **and output** tokens, provider cache reads/writes, local compute and tool round trips. Repeat the inequality for elapsed time; cheaper need not mean quicker. OpenAI's latency guidance [5] says halving ordinary input text may yield only about 1–5% lower request latency, whereas reducing output tokens or the number of serial calls can matter much more. Stable long prompt prefixes can already be cached [6]; a reusable EAL file must outperform a baseline that uses this facility. A short host status may avoid sending the source to each consumer, but source creation and versioned revalidation remain in \(F_E\) and \(U_E\). The analogy to offline knowledge compilation [7] motivates this accounting; EAL/2 currently does not establish the query-complexity guarantees studied there.

For an **EAL-specific** test, let the baseline instead be meaning-equivalent JSON plus identical checker, acquisition and host semantics. Both should compute the same verdict from equally correct formal inputs. An EAL advantage then requires fewer omitted relations, lower author/reviewer effort, safer revisions, clearer traces or lower real resource use. Count these at the author and consumer boundaries. A cheaper generic checker that ties or wins on all these outcomes defeats the comparative claim even if either checked system beats a model working alone.

## Which change should be tested first?

| Change | Predicted mechanism and discriminating measurement | Observation that would weaken it |
| --- | --- | --- |
| First-class negative finding, scoped search coverage or source-binding syntax | Reduce omitted objections and false absence claims when authors translate new briefs; compare source fidelity, revision errors and false support with equal semantic JSON | Syntax validates while authors omit the adverse relation or misstate the scope equally often |
| EAL-use skill in a trusted application instruction | Increase correct routing and tool calls for covered questions; count invocation and final status preservation by model class | Model still skips the tool or reverses a checked status; cost rises without quality gain |
| MCP interpreter with host-owned status | Execute matched methods and objections, then return the exact result even for a text-only consumer; compare under changed evidence and attack depth | Source/acquisition errors dominate, or equal checker obtains the same quality at lower cost |
| Strong author, reviewed source, many small-model consumers | Amortise one correct specification across fresh scoped observations, with compact status transfer; estimate the break-even \(N\) and query-level accuracy | The producer's answer alone suffices, the source becomes stale, or consumer errors and maintenance exceed savings |
| Grammar-guided EAL drafting | Raise parsability and perhaps semantic fidelity in small models, measured separately | Valid source expresses the wrong brief, or constraints reduce generation quality |

Grammar-constrained logical parsing improved syntax and semantic accuracy in Raspanti and colleagues' selected tasks [8], including smaller models. Another multi-model study found constrained generation could damage instruction-tuned generation despite good format compliance [9]. A grammar change must therefore pass a **brief-to-semantics** test, not just a parser test. A skill locates an operation and an MCP server exposes it; the host can require its execution and control the status. The source file itself remains task data. Research on instruction hierarchy [10] cautions against treating text found in a file as if it were trusted application instructions.

The next experiment should freeze new ordinary engineering briefs and independently checked source/observation oracles. Cross reviewed versus model-authored formalisation with raw EAL, skill, EAL host, equal JSON host and a competent reasoning-model baseline. Give each author at least three new evidence/scope revisions and each reviewed source many different consumer questions. Balance supported, contested, unsupported and out-of-scope outcomes; include genuine counterexamples, complete and partial null searches, wrong-scope records and an independent supporting route. Analyse false support, correct reversals, formalisation errors, output fidelity, developer time, tokens, money and wall time by task root and author. The existing [96-call pilot](../benchmarks/protocols/INV-EAL-NEGATIVE-REVISION-001.json) can check feasibility; a substantial superiority claim needs more independent briefs and measured reuse. Prespecify the practically significant quality and cost margins before seeing new responses.

## Primary sources

1. Gao et al., “[PAL: Program-aided Language Models](https://proceedings.mlr.press/v202/gao23f.html)”, ICML 2023.
2. Pan et al., “[Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning](https://aclanthology.org/2023.findings-emnlp.248/)”, Findings EMNLP 2023.
3. Fang et al., “[LLM-ASPIC+: A Neuro-Symbolic Framework for Defeasible Reasoning](https://doi.org/10.3233/FAIA250981)”, ECAI 2025 proceedings, online 2026.
4. Ong et al., “[RouteLLM: Learning to Route LLMs with Preference Data](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html)”, ICLR 2025.
5. OpenAI, “[Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)”, developer documentation, accessed 23 September 2026.
6. OpenAI, “[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)”, developer documentation, accessed 23 September 2026.
7. Darwiche and Marquis, “[A Knowledge Compilation Map](https://doi.org/10.1613/jair.989)”, *Journal of Artificial Intelligence Research* 17, 2002.
8. Raspanti et al., “[Grammar-Constrained Decoding Makes Large Language Models Better Logical Parsers](https://aclanthology.org/2025.acl-industry.34/)”, ACL 2025.
9. Schall and de Melo, “[The Hidden Cost of Structure](https://aclanthology.org/2025.ranlp-1.124/)”, RANLP 2025.
10. Wallace et al., “[The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions](https://arxiv.org/abs/2404.13208)”, 2024.
