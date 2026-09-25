# Prospective real-workflow comparison

`INV-EAL-REAL-001` is a **separate, unrun study** of EAL/2 against equally equipped prose and a generic checked argument graph. The [protocol](PROTOCOL.md) defines the scientific question, comparators, reference, estimands, execution boundary and decision rules; [plan.json](plan.json) records the ordered stages and outstanding receipts. The current status is `specified_not_ready`: there are no enrolled cases, model calls, executed study tools, results or registered effect claims.

The earlier [synthetic deployment protocol](../../protocols/INV-EAL-DEPLOYMENT-001.json) and [bias follow-ups](../bias-next/README.md) remain separate. Their cases, near derivatives and results cannot become this study's unseen holdout. The paper's [limitations and proposed independent test](../../../paper/eal2-jss/manuscript.tex) motivate this study but do not count as its observations.

## Order and exit conditions

1. **Feasibility pilot:** recruit 12–20 independent real case families; independently adjudicate decision-time records; actually execute each planned read-only adapter in an isolated replay; calibrate arm parity, rubrics, cost, failure handling and variance. Keep pilot families out of confirmation.
2. **Freeze and preregister:** lock a disjoint holdout and its case genealogy, model snapshots, prompts, tool grants, budgets, analysis, practical and safety margins, sample-size simulation and stopping rule. Obtain independent reference and operational approvals. Content-address the materials before revealing outcomes.
3. **Retrospective executed-tool comparison:** cross every held-out case and named model with strong prose, Toulmin prose, EAL/2 with host-owned status, and an equal generic checker. First compare identical genuinely executed evidence captures; separately let every arm choose from the same authorised tool catalogue for the end-to-end comparison. Report these as different estimands.
4. **Prospective read-only shadow:** enrol later eligible cases and run actual authorised read-only acquisitions while normal human decisions proceed without experimental intervention. Report this later cohort separately. No arm may write, approve or deploy.

The primary comparison is the full-attempt EAL/2 workflow minus strong prose, with the same natural request, facts, acquisition permissions, underlying numerical and logical method tools, model snapshot and declared resource ceiling. The EAL/2 and JSON argument checkers are parts of their assigned workflows. Invalid authoring, wrong family selection, unavailable evidence, tool errors and inaccurate communication stay in the assigned denominator. EAL/2 versus the equal checker tests the deployed systems; a notation-only question needs isomorphic representations compiled to the same typed backend. The safety result also needs a frozen minimum decision-coverage threshold: near-total refusal cannot establish a useful safe workflow.

The existing `scripts/run_cross_model_campaign.py` accepts `json_file` observations and gives its `raw` arm EAL source. It does **not** implement this comparison. The new [version 1 runner](RUNNER-v1.md) has injected P/T/E/J policies, exact case-specific grants, executable pinned Git reads and allowlisted HTTPS JSON GETs, actual EAL/2 and generic checker calls, and a one-assignment hash-linked ledger. It distinguishes fixed evidence capture from independently selected acquisition. Local synthetic tests run a Git read; no live CI, monitoring, infrastructure or reviewed study case has been executed under this protocol. The general EAL `kind="command"` adapter remains outside this study gateway.

## Local specification check

Run from the repository root:

```sh
python benchmarks/experiments/prospective-real-workflows/validate.py
python -m unittest discover -s benchmarks/experiments/prospective-real-workflows -p 'test_*.py' -v
```

The validator exits zero for a structurally consistent **unrun** specification and lists missing prerequisites. Its `--require-ready` option always exits nonzero for the shipped `plan.json`. Actual stages require a separate, signed, versioned ready execution plan linked to this specification, independently held reviewer keys and exact signed case, grant, parity and model manifests. None exists in the repository. Ledger verification detects edits, duplicate assignments and interrupted runs; it cannot authenticate external facts or substitute for independent scoring. The stage 3 and 4 ledger receipt placeholders remain empty until execution.
