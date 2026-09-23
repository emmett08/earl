# EAL/2 with an external finite-state checker: a bounded experiment

## Claim and decision

**On a specified finite transition model, EAL/2 can connect a recorded model, a typed question, a registered reachability calculation and an inspectable conclusion.** The registered checker supplies the calculation. EAL/2 supplies representation, binding, eligibility and argument composition. This claim concerns model-conditional reasoning within the tested fragment; it does not establish the model's correspondence with a physical controller.

The decision for an engineer is whether this combination is worth using to assess a bounded safety claim. The intended outcome is to obtain a correct answer for the represented graph, preserve a counterexample when the claim fails, and refuse evidence for another scope or an expired observation. The baseline is an EAL/2 `structured/1` argument whose author asserts that the same graph establishes safety. A direct standalone graph checker is a serious alternative. It can decide the formal question without EAL; the possible EAL contribution is integrating its output with named evidence, typed claims and other arguments.

This target emerged from three earlier measurements. The [EAL/2 regression](eal2-model-results.md) found 12/12 on six exposed tasks for two model–host conditions, but delegated conditions cost more than unaided ones and the arms had different validation obligations. The [relay pilot](eal2-relay-results.md) found 12/12 with full-tool evidence transferred to a small recipient versus 8/12 with the producer answer alone, although all twelve producer answers were already correct and the task-cluster interval included zero. The [notation and evidence diagnostic](notation-transfer-live-results.md) found raw-only EAL and equivalent JSON correct on 4/10 and 5/10 endpoints respectively; supplying raw observations plus interpreter conclusions obtained 7/10 and 8/10. Its wrong-scope controls were weak for the model recipient. These observations favour testing a computed, scope-checked result as a component of the full system. They do not establish that EAL notation itself improves correctness.

## Discovery of the root claim

The necessary parts of the bounded task and the means that supply them are separable:

| Need | EAL/2 with authored support | Standalone checker | EAL/2 with registered checker |
| --- | --- | --- | --- |
| State a reviewable proposition with a scope and horizon | Partly: prose can state it; `structured/1` does not check the graph | Partly: a query is explicit, but its place in a wider argument is application-specific | Satisfies for the typed finite-graph fragment |
| Calculate reachability and return a counterexample | Does not satisfy | Satisfies for this finite model | Satisfies through the installed method |
| Tie the result to the declared proposition and observation | Partly: authored relation and general record identity | Unknown: depends on the application wrapper | Satisfies declared start, forbidden set, horizon, subject, scope, unit and interval correspondence |
| Establish that the graph describes the device | Unknown | Unknown | Unknown; requires independent model and acquisition validation |
| Generalise to unseen engineering tasks and models | Unknown | Unknown | Unknown; this fixed corpus cannot adjudicate it |

Three materially different claims survived initial discovery. A **notation advantage** would attribute better decisions to EAL syntax; the current matched JSON diagnostic does not support it. A **general engineering improvement** would require protected, independently sampled construction and revision tasks. The selected **bounded integration claim** has a direct computation, a falsifiable reference and a concrete downstream use: an EAL argument can rely on a checked, model-conditional result and can be revised after an observation changes. It is integrative and an assurance contribution; the reachability algorithm is inherited from the external method. The strongest rival is a standalone checker plus an ordinary application wrapper, which may offer the same capability. This experiment tests the missing-computation ablation and the correspondence checks, not comparative superiority over that rival.

The [EAL/2 argument](../arguments/finite-model-checker/argument.eal) distinguishes the observed finite result, the bounded contribution, the authentication counterexample and two unestablished claims. The `structured/1` steps check declared dependency relations; their rationales remain authored warrants. The separate [audit](../scripts/check_finite_model_checker_argument.py) recomputes the saved counts and runs the argument through the actual evidence collector. A `supported` EAL label for the finite claim therefore means support under its authored warrant and audited inputs, not a proof of the warrant's prose.

## Formal question and intervention

Let $G=(V,E)$ be a supplied finite directed graph, $s\in V$ an initial state, $F\subseteq V$ nonempty forbidden states and $h\in\{0,\ldots,8\}$. The computational question is whether a directed path from $s$ to $F$ has at most $h$ edges. A path of zero edges counts when $s\in F$. The custom [registered method](../src/eal/reachability.py) performs breadth-first search and returns `reachable`, a shortest path if one exists, and a visited-state count. Its input schema limits graphs to eight vertices and 64 declared edges, rejects duplicates and out-of-range endpoints, and runs in the same bounded custom-method process used by other EAL extensions.

The [worked source](../examples/finite-reachability.eal) names the question and binds its recorded input. Its decisive fragment is:

```eal
reasoning finite_check {
  method "engineering/reachability/1";
  rationale "Search every state reachable in at most three transitions in the recorded model.";
}
claim bounded_safe {
  statement "The supplied controller transition model has no path to state three within three steps.";
  environment controller_bench;
  proposition {
    subject "controller-X"; quantity "proposition"; unit "1"; scope "controller-model-X";
    valid_from "2040-01-01T08:00:00Z"; valid_until "2040-01-01T10:00:00Z";
    query {"start":0,"forbidden":[3],"horizon":3};
    result "reachable" == false;
  }
}
argument safety_route {
  conclusion bounded_safe; reasoning finite_check; evidence graph_record; binding graph_record;
}
```

The query fields must match the recorded input. The graph edges themselves are observations: a newly collected graph under the same episode can change the answer. The subject, scope, unit, time interval and method identity remain checked. Those metadata are declarations by the producer. Their equality does not authenticate the graph or establish that all physical states were recorded.

## Experimental design

The [version 1.0.1 protocol](../benchmarks/experiments/eal2-finite-model-checker.json) specified 24 generated graph pairs, each with a safe graph and an unsafe partner formed by adding an edge into a forbidden state reachable within the horizon. The pair is the design unit; 48 graphs are the fixed finite corpus. A separate reference enumerates every walk through the horizon, while the installed method uses breadth-first search. Hand-derived zero-step and direct-edge cases check the reference. The oracle is computed before the EAL outcomes. No model API, human participant or physical device was involved.

The run used the existing package 2.2.2 metadata plus the new method source recorded by SHA-256. This PR advances the package to 2.2.3 to ship that optional method. The EAL/2 source contract and `EAL/typed-input/1` observation schema are unchanged.

Each graph is assessed through two EAL/2 sources using the same typed observation: an affirmative authored `structured/1` route and the registered checker route. The graph, claim text, environment and assessment time are held fixed within each pair of routes. The computed route additionally declares a formal proposition and binding; that is part of the intervention, so the contrast estimates the combined calculation-and-binding contribution. Wrong-scope tests alter only the payload scope and recompute its digest; stale tests change only collection time. Reversing edge order checks representation invariance. A deliberately false but internally consistent safe graph is substituted for one held unsafe graph to test what record correspondence can establish.

The predeclared primary estimand is the exact finite-corpus difference in agreement with the independent oracle. There is no statistical null test or population confidence interval: these graphs are generated and paired by design. All attempted cases and per-case paths and statuses are retained in the [version 1.0.1 result](../benchmarks/results/2026-09-23-finite-model-checker-v101/result.json). The first complete run used protocol 1.0.0; a review found that its counterfeit prediction had been attached to the hypothesis it contradicts. The original protocol, runner and result are preserved [unchanged in history](history/finite-model-checker-v1/README.md). Version 1.0.1 corrected that mapping, separated the stale-record prediction as shared, added the authored wrong-scope measurement and reran into a new output path. This is a documented post-run amendment, not a preregistered confirmation.

## Observed results

| Fixed-corpus measure | Registered checker | Authored `structured/1` |
| --- | ---: | ---: |
| Agreement with independent graph oracle | 48/48 | 24/48 |
| Correct positive support on safe graphs | 24/24 | 24/24 |
| False positive support on unsafe graphs | 0/24 | 24/24 |
| Wrong-scope input refused | 48/48 | 0/48 |
| Stale record refused | 48/48 | Both routes share EAL freshness semantics; the authored route was not separately counted |

All 48 computed path outputs passed the witness check, and reversing the edge list left all 48 computed statuses unchanged. The separate host integration check collected the worked observation, returned `supported` for the safe graph, then collected an observation with an added path to the forbidden state and returned `unsupported` with counterexample `[0, 1, 2, 3]`. The old assessment remained retrievable with its original status.

The counterfeit control found the trust boundary. Replacing one unsafe graph with its safe partner, while retaining coherent subject, scope, interval and digest, made the model-conditional claim `supported`. The held graph remained unsafe. This is a constructed example of an unauthenticated producer, not a measured sensor failure. Binding detects mismatches within the declared record; independent acquisition and model validation are needed to make a device claim.

## Interpretation and next investigation

The finite result supports the selected integration claim at its stated scope. It also shows why EAL/2 alone cannot establish an authored warrant: the affirmative `structured/1` route accepts the unsafe graphs because it has no graph calculation. The checker could be called without EAL/2 and obtain the same graph answer. EAL/2 adds a place for its input, computation, qualifications, attacks and later evidence revisions to be checked together. The present trial measures the finite graph route only; it does not assess human comprehension, model construction from engineering text, live instrumentation, general task transfer, or whether the combined system saves time or money.

The next discriminating study should start with independently acquired transition models and a validated observation process. It should compare the same checker through EAL/2 and through an equivalently resourced standalone wrapper on new model families, while asking engineers or selected models to construct and revise the arguments. Freeze a task sampling frame, source-to-device reference, error categories, cost scope and paired decision thresholds before observation. A separate model adequacy test is required before treating a bounded graph result as physical safety evidence.

To reproduce the finite experiment on the current source, write to a new directory because the runner refuses to replace a retained result:

```sh
PYTHONPATH=src python scripts/experiment_finite_model_checker.py --output /tmp/eal-companion-replication.json
PYTHONPATH=src python scripts/check_finite_model_checker_argument.py
PYTHONPATH=src python -m pytest -q tests/test_reachability_companion.py
```
