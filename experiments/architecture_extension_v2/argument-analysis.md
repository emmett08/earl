# Pre-A architecture argument: whole and parts

The practical question is whether an engineer adding successive functional or
non-functional requirements should reuse the fulfilment system's boundaries or
revise their shared contracts when a requirement exceeds them. Engineer 1's
answer in [`argument.eal`](argument.eal) is a **conditional design rule**:
inspect the current code and invariants, use suitable existing ports and one
order lifecycle, refactor dependent paths together when the boundary is too
narrow, and verify the affected qualities. SOLID principles and design
patterns are reasoning aids for that decision, not a mandate to add layers.

The pre-A evidence is the frozen `materials/base` tree identified by
`materials/freeze-base.json`. The baseline probe runs eleven named tests in
two declared subsets and inspects six Protocol definitions and their injection
into `CheckoutService`. The cognitive complexity collector measures the
baseline production package; it does not vote for a design. All source
observations have the `pre-A` environment. Engineer 3 can read this argument
after feature A, but its measurements do not thereby apply to the changed
snapshot. The agent must read the current code and retest the altered scope.

| Whole–part dependency | EAL/2 representation and local evidence | Defeater or limit |
| --- | --- | --- |
| Existing functional path: quote, reserve, capture, dispatch, order and outbox, event retry | `stage_report_pass` reports three named baseline tests; `ports_report_pass` reports exact Protocol and constructor signatures | These probes are finite. The opposite predicates share each observation and support explicit `stage_report_fail` or `ports_report_fail` if a check fails. Neither pass proves the architecture optimal. |
| Failure path and replay semantics | `rollback_report_pass` reports eight named tests for rejection, compensation, retry, idempotency and related boundaries | In-memory, sequential adapters do not test production concurrency, durability or external services. |
| Shared extension decision | `guidance_from_baseline` uses those claims and an authored `structured/1` rationale; functional and non-functional effects each require suitable checks | A material mismatch, unsuitable existing architecture or excessive indirection can reverse a local design choice. The two measured baseline failures undercut the route; other rivals remain review questions without invented observations. |
| Later AI sessions | The rationale requires reinspection of code, argument and changed requirements at each episode | A discoverable EAL file or successful MCP call cannot prove that a later agent noticed, understood or followed it. Actual prompts, tool traces and code changes are separate evidence. |
| Reduced duplication, drift and later debt | `conditional_debt_forecast` states a possible repeated-use mechanism | `followup_absent` supports an undercutter: no later maintenance episode has been observed pre-A. A passing feature test or small diff does not discharge the longitudinal prediction. |
| Cognitive complexity | `complexity_measured` reports a bounded Python AST score from pinned production source; `metric_diagnostic_only` constrains its use | The score captures selected control-flow structures. Function extraction can change totals; low scores can coexist with coupling, parallel workflows, unused code or hard future edits. Inspect per-function changes and structural/rework evidence. |

The active argument has no need to rank design heuristics numerically. ASPIC+
directives mark only the conditional implications from an exact Boolean check
to its **reported** verdict as strict. Reciprocal `contrary` directives pair
the mutually exclusive pass and fail reports for the same check. The substantive
recommendation and future-debt mechanism remain defeasible. The reviewed
references name these modelling choices; they do not certify the tests or the
English rationales. `structured/1` checks declared dependencies, not the
truth of SOLID principles or source-code interpretation.

## Rival readings and reversal observations

- **Wrong baseline architecture.** A current failure in stage behaviour or
  port signatures invalidates this baseline route. A more capable provider,
  concurrent stock updates, or a new security/performance requirement may
  call for a different contract. Inspect the changed code, then rerun relevant
  behaviour and quality probes before applying the recommendation.
- **Overengineering.** A locally narrow change may be clearer without a new
  strategy, hierarchy or shared interface. Compare the actual seam, number of
  changed responsibilities, call sites and tests. The conditional rule allows
  using an existing straightforward path and refuses abstract layers without
  a changing responsibility.
- **Hidden path or dead code.** Passing imports or feature tests cannot prove
  one lifecycle or full reachability. Review call sites, duplicate mutation
  routes, obsolete implementations and event/order transitions; add tests
  aimed at the discovered risk. Do not treat a parser or complexity score as a
  complete static analyser.
- **Metric mismatch.** The post-change score is useful only at the same
  measurement scope and implementation contract; report changed, added and
  removed functions separately. A lower score can reflect moved branching or
  split functions while future change effort rises.
- **Confounded treatment.** Different agents or model classes, asymmetric
  prompts and delivery by MCP versus raw context can affect outcomes. Preserve
  exact exposures and tool traces; compare matched arms before attributing an
  effect to the EAL argument.

The whole–part rereading leaves three deliberately separate outputs: the
bounded **pre-A baseline report**, an **actionable but defeasible design
recommendation**, and an **unmeasured longitudinal hypothesis**. Feature A and
B observations belong in the experiment's post-run records and paper, not this
frozen pre-A source.
