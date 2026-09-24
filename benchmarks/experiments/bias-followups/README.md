# Matched representation and equal-allocation model cohort

This developmental cohort compares a checked EAL/2 source with a mechanically
derived typed JSON declaration graph, and two independent general critics
with independent mechanism/rival critics. Every topology receives two calls
with the same model and per-call output ceiling. Both answers are retained;
agreement-only synthesis intersects cited record IDs. Actual input and
reasoning usage can differ and must be reported. The 12 case families are
reused from Stage A, so this cohort cannot serve as independent confirmation.

From the repository root:

```sh
python -m unittest discover -s benchmarks/experiments/bias-followups -p 'test_*.py' -v
python benchmarks/experiments/bias-followups/followup.py preflight
python benchmarks/experiments/bias-followups/followup.py freeze /protected/pilot.json --families 2 --models luna sol --max-usd 5
python benchmarks/experiments/bias-followups/followup.py execute /protected/pilot.json /protected/pilot.jsonl
python benchmarks/experiments/bias-followups/followup.py analyse /protected/pilot.json /protected/pilot.jsonl /protected/pilot-report.json
python benchmarks/experiments/bias-followups/followup.py freeze /protected/full.json --families 12 --models luna sol --max-usd 20
python benchmarks/experiments/bias-followups/followup.py execute /protected/full.json /protected/full.jsonl --prior-freeze /protected/pilot.json --prior-ledger /protected/pilot.jsonl
python benchmarks/experiments/bias-followups/followup.py analyse /protected/full.json /protected/full.jsonl /protected/full-report.json --prior-freeze /protected/pilot.json --prior-ledger /protected/pilot.jsonl
```

Use the archived frozen inputs when possible; regeneration changes the
creation timestamp and exact file digest. The 128-call pilot is a subset of
the 768-call full schedule, so a completed valid pilot contributes its calls
to the full denominator. Preflight makes an unauthenticated request before
the key is read. Keep `OPENAI_API_KEY` in a protected process environment,
never in commands, the repository or a response archive. The runner writes a
hash-chained, redacted ledger before each attempt, stops on invalid output or
provider failure, and never retries a possibly sent request automatically.

The analyser reports no contrasts until every assigned call has a valid
terminal record. The raw author-labelled reference remains developmental.
See `PROTOCOL.md` for the estimands, limits and independent confirmation
requirements. A timed-out preflight means **zero model calls**, irrespective
of which API key is supplied.
