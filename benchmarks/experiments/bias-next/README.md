# Separate next experiments for bias-mechanism research

These are three independent, prospective experiments. They are deliberately
not extra arms of `bias-mechanisms`: each has its own investigation ID,
families, freeze, ledger, analysis, stopping rule and claim. No outcome has
been collected.

1. `matched-json/plan.json` isolates the rendering contrast. Every EAL/2
   packet must be mechanically lowered to a canonical JSON graph and pass a
   bidirectional semantic receipt before randomisation.
2. `equal-compute-topology/plan.json` isolates agent topology. It holds the
   EAL/2 packet fixed and gives each route exactly two fresh calls with the
   same per-call output ceiling. Natural-cost comparisons belong in a later
   operational experiment, not this estimand.
3. `human-decisions/plan.json` estimates human decision effects. It requires
   ethics approval, consent, prospective registration and independently
   authored tasks. API-only results cannot satisfy it.

The first two experiments read the provider credential only from
`OPENAI_API_TOKEN`. A freeze or validation command must never require the
secret, and neither plans nor ledgers may contain it. The human trial uses a
fixed, reviewed agent packet generated before participant randomisation; it
does not make live provider calls during a participant session.

## Readiness check

```sh
python benchmarks/experiments/bias-next/validate.py
python -m unittest benchmarks/experiments/bias-next/test_plans.py -v
```

The validator exits successfully when the three specifications are internally
consistent, but reports each experiment as `not_ready`. That is intentional:
fresh family manifests, independently signed references and representation
receipts do not yet exist, and the human study additionally lacks ethics and
registration receipts. Do not create paid calls merely because a secret is
available. Replace each `required_receipts` null with a content-addressed
receipt only after the named review has actually occurred, then freeze an
immutable schedule and add its hash to the relevant plan in a versioned
amendment.

The prior twelve synthetic families are explicitly excluded from all three
experiments. Matched JSON and equal-compute topology must also use mutually
disjoint families: otherwise inspection of the first experiment could inform
the second. Human tasks may not be paraphrases or revisions of either API
cohort.
