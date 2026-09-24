# Synthetic EAL/2 bias-mechanism study harness

`cases.json` describes twelve author-created engineering episodes. `run.py`
expands each into a process-supported candidate, a stronger technical rival, a
missing-link case, and an insufficient-record case (48 total). Each API input
contains a statically checked EAL/2 engineering decision argument, a separate
candidate mechanism argument with stable process-record IDs, and the synthetic
process record. An authored EAL argument does not make its evidence true. The
runner performs static parse and semantic validation against the repository's
current `src/eal` and grammar before freezing; it does not acquire those
process records through the EAL host or verify an actual person's cognition.

The default matrix is 48 cases × 3 models × (one direct call + two independent
analyst calls) = 432 calls. Independent calls see identical facts and no other
analyst's answer. They run serially in a seeded shuffled schedule. The
deterministic combination publishes an agreed disposition or `UNDECIDED`.
Both topologies receive the same citation gate based on the *author-labelled
synthetic* role records. Compare raw and gated false attribution, supported
recall, decisive coverage, wrong corrections, citations, latency and cost
together. A zero gated false-attribution count on these constructed negatives
can follow from the gate by construction; it is not validation on human cases.

## Offline checks and an uncharged reachability check

```sh
python -m unittest discover -s benchmarks/experiments/bias-mechanisms -p 'test_*.py' -v
python benchmarks/experiments/bias-mechanisms/run.py preflight
```

Preflight sends an unauthenticated GET to `/v1/models` through the configured
HTTPS path and expects HTTP 401. It never sends the key or creates a model
response. A timeout or blocked endpoint stops the paid runner before billing.

## Freeze, execute and analyse

The exact zero-call pilot and full freezes from this revision are archived in
`benchmarks/results/2026-09-24-bias-agent-zero-call/`. To execute those
reviewed schedules, decompress their `.json.gz` members to `pilot.json` and
`full.json` in a protected working directory. Regenerate instead only after
a versioned amendment; the runner rejects an archive whose source hashes no
longer match.

```sh
python benchmarks/experiments/bias-mechanisms/run.py freeze pilot.json --families 2 --max-usd 5
python benchmarks/experiments/bias-mechanisms/run.py execute pilot.json pilot.jsonl
python benchmarks/experiments/bias-mechanisms/analyse.py pilot.json pilot.jsonl pilot-report.json

python benchmarks/experiments/bias-mechanisms/run.py freeze full.json --max-usd 25
python benchmarks/experiments/bias-mechanisms/run.py execute full.json full.jsonl --prior-ledger pilot.jsonl
python benchmarks/experiments/bias-mechanisms/analyse.py full.json full.jsonl full-report.json --prior-ledger pilot.jsonl
```

Set `OPENAI_API_KEY` in the process environment through a secret manager, not
in a command line, source file or log. The full schedule contains identical
request IDs and payload hashes for the pilot subset; `--prior-ledger` validates
and imports those attempts, so it attempts the remaining 360 calls. A pilot
failure, an incomplete response, an unresolved write-ahead `pending` event, a
returned-model change or a budget breach stops execution. There is no automatic
retry. An interrupted call requires independent provider/billing reconciliation
before a new, documented run can proceed. The ledger retains redacted raw
provider responses, usage, model identity, UTC time, latency and a hash chain.
Do not edit frozen plans or ledgers; a changed plan fails deterministic
regeneration. The optional `--families` and `--models` subset is exploratory
unless its information target was fixed in the protocol beforehand.

The configured input/output rates were checked on 24 September 2026 against
the [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano),
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) and
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol) model
pages. Nano uses a dated snapshot; Luna and Sol are aliases whose returned
`response.model` must be recorded and constant within a run. The spending
reservation charges every input byte as though it were a token and reserves
the maximum output tokens. Reported token cost uses the configured uncached
rate and is an estimate: cached, regional, fast, write and account billing
terms require a separate invoice check. The $5 and $25 caps apply to this
plan's estimated/reserved calls, not to account-wide spending.

The output rationale allows blinded reviewers to code categorical accusations
made under a weak status. The script cannot make that semantic judgement.
Human-case confirmation requires contemporaneous records, an independent gold
adjudication and a held-out protocol; these author-created cases assess rule
application and model behaviour under stipulated facts only.
