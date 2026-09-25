# Reuse an assessed argument across developers

**Deterministic sensitivity exercise, 23 September 2026.** The [runner](../scripts/experiment_eal_amortisation.py) reads the 20 exposed synthetic states from the [negative-revision experiment](eal2-negative-revision-results.md). It assembles two model input packets for each state: the complete EAL/2 source, observation records and method instructions; and a short host assessment containing the claim, computed status and source/record digests. It counts their exact UTF-8 bytes. A fixed-case independent checker that agreed with the EAL statuses is assigned the *identical* short packet. [Retained rows and sensitivity calculations](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal-amortisation/offline.json) are reproducible. **No model was called; no provider tokens, prices, accuracy or latency were measured.**

The decision is whether developer A's reviewed argument can be reused by developer B and subsequent readers often enough to compensate for authoring and upkeep. A strong conditional claim is that a host can assess the current evidence on each question and give each reader a small, current result. Caching assessments across questions is a separate possible optimisation that requires invalidation on source or evidence changes. The equal-checker control shows the byte advantage belongs to reusable checked computation. EAL-specific value would require better authoring, revision, audit or interoperability than an equally capable alternative at a comparable total cost.

## Measured packets

| Packet across 20 states | UTF-8 bytes | Mean bytes per state | What is provided |
| --- | ---: | ---: | --- |
| Full EAL replay | 100,819 | 5,040.95 | Source, method instructions, current observation records, question |
| EAL host assessment | 6,380 | 319 | Computed status, claim and two digests, question |
| Fixed-case checker host assessment | 6,380 | 319 | Exactly the same status packet |

The measured difference is **94,439 bytes over these 20 packets**, or **4,721.95 bytes per packet**. Full packets repeat 48,583 source bytes in total; the remaining size comes from records and prompt framing. These are deliberately complete records, including provenance fields. A more compact raw-value prompt might use fewer bytes but could no longer independently check the same provenance. Source caching may further reduce billed input cost. A persistent context carrying the file once, or a short checked summary, is another credible comparator. The full packet is a specified workflow, not a fully cache-optimised model-only comparator.

The two host packets are bit-for-bit identical for each state. A generic checker with the same rules and validated source would offer the same consumer-side packet reduction. The present checker is a narrow reference written for these fixed graphs; this exercise cannot estimate how much an equal general-purpose checker costs to author or maintain.

## Break-even model

Let $n$ be total consumer questions across users, $r$ the number of host updates, $I_E$ extra host integration cost, $U_E$ extra cost per host update, and $h_E$ per-question host execution cost. Authoring and revising the EAL file are common to full EAL replay and EAL-host delivery, so those terms cancel in this comparison. Let $B_F$ and $B_E$ be the mean measured full and short UTF-8 packet lengths, $B_S$ the source bytes repeated in a full packet, $\rho$ a *hypothetical* input tokens per byte conversion, and $c\in[0,1]$ the effective discount on the repeated source. Express all host costs in input-token-equivalent units only after choosing a valid exchange rate for the actual model, labour and host resources. Then the hypothetical marginal saving is

\[
D_E=\rho\bigl[(B_F-B_E)-cB_S\bigr]-h_E.
\]

When $D_E>0$, the first integer consumer count that strictly repays incremental host setup and updates is

\[
n^*=\left\lfloor\frac{I_E+rU_E}{D_E}\right\rfloor+1.
\]

When $D_E\leq 0$, increased reuse cannot repay those costs under the selected assumptions. A workflow that must send both the full source and assessment on every query has a different $B_E$, so its break-even should be recalculated. Output token cost, retrieval, network, review and error consequences must also be included before a monetary or latency decision.

The runner explores **assumed** $\rho\in\{0.20,0.25,0.33\}$, source discounts $c\in\{0,0.5,0.9\}$, and per-query host overhead $h_E\in\{0,25,100\}$. To illustrate the calculation it sets $I_E=10{,}000$, $r=2$ and $U_E=1{,}000$ input-token-equivalent units. These numbers are sensitivity inputs, not observations from a model or developers. An adoption comparison against an equally informative workflow without any EAL file must additionally charge EAL authoring and validation and measure that workflow's own packet and error costs.

| Illustrative $\rho=0.25$, assumed incremental host setup + updates = 12,000 units | Source discount | Host overhead per query | Derived saving per query | First repayment query |
| --- | ---: | ---: | ---: | ---: |
| Repeated full source | 0% | 0 units | 1,180.487 units | 11 |
| Half source discount | 50% | 0 units | 876.844 units | 14 |
| Mostly discounted source | 90% | 0 units | 633.929 units | 19 |
| Mostly discounted source and host overhead | 90% | 100 units | 533.929 units | 23 |

These thresholds apply to the illustrative mix of 20 *dependent developmental states repeated evenly*. Those states use **three source digests across two problem roots**, including an unlinked revision. No single-source query count, developer population or actual traffic frequency was measured. The source-only cache discount is a sensitivity device, not a complete cache-optimised comparator: persistent conversations or a compact prompt could change both the repeated source and record costs. Counting the 20 states as independent evidence of a population effect would be an error. Provider-specific tokenisation may change $\rho$, and actual cache accounting may not be a linear discount. A provider tokenizer and usage telemetry should replace both assumptions in a live trial.

For status-only questions, the host could return the status directly without a consumer model call. This is a useful implementation option when the final answer needs no natural-language synthesis. It is available to the equal checker as well.

## What would establish an EAL-specific gain?

For an equal checker $J$ that sends the same short packet, $B_J=B_E$. Its consumer token count is equal in this exercise. EAL has a total-resource advantage only if measured differences in authoring, revisions, execution and errors favour it:

\[
(A_E-A_J)+r(M_E-M_J)+n(h_E-h_J)+C_{\mathrm{errors},E}-C_{\mathrm{errors},J}<0.
\]

The error term must be defined from consequences relevant to the actual user task. A lower token count cannot compensate for wrong status reversals merely by assertion. The next study should pair ordinary briefs across EAL and an equal-semantics graph, randomise their order between authoring developers, and give independent consuming developers the checked status over MCP. A second factor can vary whether authoring uses a grammar guide, an EAL skill, and an MCP authoring/validation tool. Pin model classes, tool rights and provider usage accounting. Record the developer's corrected source, review effort, revisions after new adverse evidence, status fidelity, false support, end-to-end latency, actual input/output tokens and resource use. Analyse by independent brief and developer; revisions within a brief are repeated observations.

Three outcomes have different meanings. A host advantage over full replay with EAL and the equal checker tied would support reusable checked assessment. An EAL advantage over the checker in correct authoring or lower revision effort would support an EAL-specific interface and maintenance claim. A model using a bare EAL prompt while ignoring its attacks would identify a reason to require host execution or a validated tool call. Source acquisition, the formalised query and observation authenticity remain potential common failure points in all three outcomes.

Recompute the deterministic record from the repository root without overwriting the retained JSON:

```sh
python3 scripts/experiment_eal_amortisation.py --verify
```
