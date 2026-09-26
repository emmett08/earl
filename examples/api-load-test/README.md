# Review an API load-test result

**Engineering question:** Does this build's load-test report meet the agreed latency and error-rate criteria?

An engineer is reviewing `orders-api` build `demo-build-42`. The example checks one report for a workload labelled with 10 concurrent clients. Its acceptance criteria are at least 100 recorded requests, sample 95th-percentile latency no greater than 200 ms, and at most 1% failed requests. These are illustrative requirements chosen for this example.

The bundled [report](report.json) contains **synthetic teaching data**. The checked claim concerns these supplied records. A real release decision needs genuine measurements, a complete report and a workload representative of the intended use; this example supplies no evidence about production performance.

## Run it

From the repository root, with Python 3.11 or later:

```sh
python3 -m pip install -e '.[dev]'
make example
```

This validates the [EAL source](source.eal), collects the report, assesses the claim and retrieves its explanation through both the CLI and the actual MCP stdio server. It needs no credentials, model provider or network connection after installation. Assessment records are written to a temporary database and removed when the demonstration ends.

The expected output contains:

```json
{
  "dataset": "synthetic",
  "assessed_at": "2026-09-25T10:00:00Z",
  "metrics": {
    "request_count": 100,
    "p95_ms": 180,
    "failed_requests": 1,
    "error_rate_percent": 1.0
  },
  "cli_claim_status": "supported",
  "mcp_claim_status": "supported",
  "cli_failed_claim_status": "unsupported",
  "mcp_failed_claim_status": "unsupported"
}
```

## Follow the argument

The source names the service, build, run, client count and report digest. Its evidence declaration checks that the collector returned a usable request count within a 24-hour evidence age limit. The host installs `engineering/api-load-criteria/1`, a versioned typed method that checks the three inclusive numerical limits. The `passes` result supports `performance_criteria_met`; the `fails` result supports the separate `performance_criteria_failed` claim. A failed threshold is a usable negative measurement. An expired or unavailable report supports neither claim.

The host's [tool registry](tools.toml) binds `load_test_report/1` to [collect_results.py](collect_results.py). The EAL tool declaration has only its name and version; source does not declare whether collection is deterministic. The collector reads the selected report, checks its SHA-256 digest and identity, then computes the statistics. The EAL source supplies expected identity and thresholds; the trusted host selects the executable and report file. Collection records carry a store-local keyed `tool_binding_digest` of that selected configuration. The registry pins the collector script's bytes and rejects changes at collection or later assessment. It does not pin Python or all imported dependencies.

For n recorded requests, the nearest-rank p95 is the sorted latency at one-based position ceil(0.95 × n). In this report, position 95 is 180 ms. All requests contribute to latency, including errors. Any non-2xx HTTP status counts as a failed request; status code 0 represents a transport failure or timeout, whose elapsed time must also be recorded. One failed request out of 100 gives 1%, which meets the inclusive limit. This is a sample statistic with no population confidence bound.

The collector returns the report's original `observed_at`. Reading the file again does not make its measurements newer. The demonstration deliberately assesses the report at its stated time, `2026-09-25T10:00:00Z`; a current-time assessment beyond the 24-hour limit returns `unsupported`.

## Inspect each operation

The following commands retain records in the default `.eal/runs.sqlite3` database:

```sh
eal --workspace . --registry examples/api-load-test/tools.toml \
  --methods eal.api_load_methods:registry validate examples/api-load-test/source.eal

eal --workspace . --registry examples/api-load-test/tools.toml \
  --methods eal.api_load_methods:registry collect examples/api-load-test/source.eal \
  --context '{"service":"orders-api","build_id":"demo-build-42","dataset":"synthetic"}'
```

Copy the returned `collection_id` into the next command:

```sh
eal --workspace . --registry examples/api-load-test/tools.toml \
  --methods eal.api_load_methods:registry reason examples/api-load-test/source.eal \
  --context '{"service":"orders-api","build_id":"demo-build-42","dataset":"synthetic"}' \
  --collection COLLECTION_ID --now 2026-09-25T10:00:00Z

eal --workspace . --registry examples/api-load-test/tools.toml \
  --methods eal.api_load_methods:registry explain ASSESSMENT_ID \
  --claim performance_criteria_met
```

Replace `ASSESSMENT_ID` with the assessment's identifier. Inspect both `claims.performance_criteria_met.status` and `claims.performance_criteria_failed.status`. The second claim distinguishes an observed criterion failure from missing or stale evidence. The source statement and rationale remain authored assertions; the method checks only the declared finite measurements.

To use MCP directly, launch `eal-mcp --workspace . --registry examples/api-load-test/tools.toml`. Supply the source text and the same context to `eal_validate` and `eal_collect`, then the returned collection ID and the recorded assessment time to `eal_reason`. Call `eal_explain` with its assessment ID and claim. [run.py](run.py) is a complete Python MCP client for this sequence.

## Reuse a reviewed argument for later prose

The optional argument host uses a second, bounded view of this **same synthetic fixture**. Its [reviewed scheme](argument-schemes.toml) pins [EAL source bytes](argument-host.eal), three initial wordings and one later wording. [Tool configuration](argument-tools.toml) selects a pinned [collector](recompute_synthetic.py) that checks the fixture's digest and identity, then computes the sample statistics again. The host installs the same versioned API criteria method and the source has separate passing and failing claims. That computation is current; the original fixture's measurement time remains `2026-09-25T10:00:00Z`. It does not represent a new load test.

From the repository root after installing the package, run:

```sh
python examples/api-load-test/argument_host_demo.py
```

The [demonstration](argument_host_demo.py) obtains `supported` and `adequate` for the first wording. A later question and a reviewed paraphrase each resolve to the same claim and method but trigger new tool collections and assessments. An unreviewed question about production reliability stays `unresolved` and runs no evidence tools. The output checks three different collection IDs through `fresh_collection_for_later_wording: true`; it does not recycle the first status. The temporary database is removed at the end.

Changing the EAL source invalidates the scheme's pinned SHA-256 until an operator reviews and updates the TOML contract. The form match establishes applicability only for these reviewed phrasings and synthetic context, including the separately reviewed p95/error paraphrase. Negated, compound, stronger and production questions remain unresolved before collection. The three adequacy obligations check sample count, sample p95 and observed sample error percentage; neither they nor the finite criteria method establish population reliability, representative workload or production readiness.

## Try your own report

Keep the report schema and include every attempted request, including timeouts. Set the actual service, immutable build identity, run ID, client count and observation time; use `"dataset": "measured"` for genuine measurements. The host can select a different report with `--report PATH` in the collector's configured argument vector.

Review the claim and thresholds for that workload. Update the EAL input, environment and assessment context to match, and pin the selected bytes using `sha256sum PATH`. Then collect a new observation and assess at the intended decision time. A digest detects changed bytes; the collector cannot authenticate measurements, discover omitted requests or determine whether the workload is representative.

The teaching collector requires at least one valid recorded request; it rejects an empty fixture before method evaluation. The experimental collector can retain an otherwise complete empty run, for which the shared method reports a failed sample-size criterion and leaves latency and error-rate criteria unknown. The regression tests exercise limits that this example must respect: exactly 1% passes; 2% fails; excessive p95 latency and too few requests support the negative claim; stale evidence and mismatched build identities support neither claim.

## Resolve conflicting findings with the optional ASPIC+ method

The same API task has an additional [synthetic formal variant](aspic-source.eal). The [fixture](aspic-fixture.json) stipulates a primary latency finding, a trace gap that undercuts its inference, and an independent probe of that same run. Strict and defeasible rules, explicit contrariness and global ordinal ranks appear in the formal theory; the source binds its **complete** theory as a typed query for `demo-load-001`. EAL collects scoped observations through the [pinned fixture collector](aspic_fixture_collector.py) and requires supported EAL claims for the theory's premises. The ASPIC+ method constructs and resolves the formal conflict. The [method reference](../../docs/aspic-method.md) defines its exact semantics and limits.

```sh
python examples/api-load-test/aspic_demo.py
```

The script expects `formal_status: "accepted"` and `defeat_kinds: ["undercut"]`: the primary route is defeated, while the independent probe route remains accepted. It also reports `claim_status: "supported"`, `adequacy: "adequate"` under the stated reviewed mappings, and `mcp_claim_status: "supported"` from a real stdio exchange. All findings are stipulated synthetic records. The original [report](report.json) is unchanged and does not contain the additional trace or probe observations. A real use needs an identified, trustworthy collector for each finding and review of the rule and premise meanings.

## Live model comparison

The single [API experiment](../../experiments/api_load_test/README.md) extends this same task with actual HTTP traffic and six nano/mini/full model snapshots. It compares EAL/2+MCP, equivalent JSON prompt text and three developer prompts in Docker. The synthetic report here remains a reproducible teaching fixture and is not used as experimental measurement data.
The optional ASPIC+ variant is outside that frozen experiment. A formal solver comparison would need a separate paired protocol with equal observations and checker authority.
