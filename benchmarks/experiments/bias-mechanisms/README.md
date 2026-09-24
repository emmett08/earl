# Synthetic EAL/2 bias-mechanism study harness

`cases.json` describes twelve author-created engineering episodes. Read
`AMENDMENT-0.1.1.md` and `AMENDMENT-0.1.2.md` with the original `PROTOCOL.md`
before using this runner.
Amendment 0.1.1 was fixed before the first paid call. It removes public class
labels, aligns the EAL candidate-objection scaffold and makes raw agent accuracy
the primary outcome. Amendment 0.1.2 followed the first invalid pilot response;
it permits independent assignments to continue after terminal invalid outcomes.
This Stage A run is developmental. `run.py`
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
deterministic combination publishes an agreed disposition or `UNDECIDED`
and retains only citations supplied by both analysts. The primary score uses
this raw output. The secondary gate uses *private author-labelled synthetic*
role records; it is an oracle-assisted diagnostic and is not deployable as
written. Compare raw and gated false attribution, supported recall, decisive
coverage, analyst-level wrong corrections, citations, latency and cost
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

The superseded amendment 0.1.1 pilot and full freezes are archived as
`pilot-freeze-0.1.1.json.gz` and `full-freeze-0.1.1.json.gz` under
`benchmarks/results/2026-09-24-bias-agent-zero-call/`. They retain the original
stop-on-invalid policy and must not be executed by the current runner.
The original `pilot-freeze.json.gz` and `full-freeze.json.gz` remain historical
zero-call inputs with known class leakage; current `load_freeze` rejects them.
The executed 0.1.2 continuation freezes and historical execution commands are
retained with their results under `benchmarks/results/2026-09-24-bias-agent-stage-a/`.

```sh
cat benchmarks/results/2026-09-24-bias-agent-stage-a/COMMANDS.txt
```

The archived commands document the completed run; do not execute its calls
again. To create a future amended plan, first version and review its changed source,
then run `run.py freeze` with **new output filenames**. A freeze command never
overwrites an existing path; do not run it against decompressed archive files.

Set `OPENAI_API_KEY` in the process environment through a secret manager, not
in a command line, source file or log. The full schedule contains identical
request IDs and payload hashes for the pilot subset; `--prior-ledger` validates
and imports those attempts, so it attempts the remaining 360 calls. A terminal
invalid answer, refusal or provider failure remains in the assigned denominator
without retry and does not block independent calls. An unresolved write-ahead
`pending` event or a prospective budget breach still stops execution. An
interrupted call requires independent provider/billing reconciliation before a
new, documented run can proceed. The ledger retains redacted raw
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
