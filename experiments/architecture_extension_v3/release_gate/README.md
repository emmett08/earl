# Refund outcome: a bounded decision gate

This is a **synthetic apparatus experiment**, separate from the v3 coding
sequences and their technical-debt outcome. It exercises the public R-D
requirement that a refund provider may apply an effect and lose the
acknowledgement. The declared operation key is
`refund:order-7:request-r`. A simulated provider record reports `applied`,
`not_applied`, `unknown`, or `unavailable`; the last value represents a
successful observation that the *status service* is unavailable. The
`tool_error` case instead makes acquisition fail before any status observation.
A separate simulated ledger reports whether inventory and the event obligation
have been reconciled. Every case and the collector are SHA-256 pinned in
[`eal-tools.toml`](eal-tools.toml).

The plain comparator in [`tool.py`](tool.py) uses the same status, age and
ledger records as [`argument.eal`](argument.eal): a current `not_applied`
permits only retry of the **same** key; a current `applied` permits completion
only after affirmative inventory and event reconciliation; unknown,
unavailable, stale, missing or incomplete evidence blocks completion. Neither
arm silently interprets absent information as `not_applied`. These are
conditional rules for the finite fixture, not proof of a live provider state.

The EAL/2 source contains an ASPIC+ undercut of a provisional
`candidate_completion` route by an explicitly unreconciled ledger. The final
`completion_safe` argument separately requires both affirmative ledger
premises. Thus a contested provisional route and a missing required premise
are distinguishable. The wrapper allows `COMPLETE` or `RETRY_SAME_KEY` only
for an accepted, supported claim; every other state fails closed. The tool's
`max_age` is 60 seconds; `stale_applied` returns a provider observation aged
120 seconds and a fresh, positive age check. A genuine collector error
produces an EAL acquisition error and an unsupported completion claim.

## Recorded result

[`results.json`](results.json) records a real MCP stdio run for all seven
fixtures and a direct plain-rule calculation. Actions agree in 7/7. One
explicit `applied_unreconciled` case constructs a provisional completion
subargument that is rejected by one ASPIC+ undercut; its final completion
route is unsupported because affirmative inventory reconciliation is absent.

| Case | Plain | EAL/MCP | Formal detail |
| --- | --- | --- | --- |
| Applied, ledger reconciled | `COMPLETE` | `COMPLETE` | Final claim accepted |
| Applied, inventory unreconciled | `BLOCK_COMPLETION` | `BLOCK_COMPLETION` | Provisional claim rejected by one undercut |
| Not applied | `RETRY_SAME_KEY` | `RETRY_SAME_KEY` | Same-key retry accepted, completion unsupported |
| Unknown | `BLOCK_COMPLETION` | `BLOCK_COMPLETION` | Explicit unknown state, completion unsupported |
| Status service unavailable | `BLOCK_COMPLETION` | `BLOCK_COMPLETION` | Explicit unavailable state |
| Applied observation stale | `BLOCK_COMPLETION` | `BLOCK_COMPLETION` | Applied premise unavailable by freshness rule |
| Collector acquisition error | `BLOCK_COMPLETION` | `BLOCK_COMPLETION` | Six provider/freshness evidence acquisitions error |

The direct plain calculation took approximately 0.2–0.4 ms per case and the
separately started EAL/MCP server approximately 1.4–1.5 s per case in the
recorded local run. This is a **harness comparison**, not a priced AI token
or production throughput result. A persistent server, batching, cache and
on-demand detail retrieval could change the overhead; they have not been
measured here. The formal layer supplies inspectable premises, undercut and
fail-closed status, while the strong plain comparator makes identical safe
decisions. The seven-case tie establishes no coding, financial or
technical-debt improvement.

## Reproduce

From the repository root with the project virtual environment:

```bash
../.venv/bin/python experiments/architecture_extension_v3/release_gate/run.py
../.venv/bin/python -m unittest discover -s experiments/architecture_extension_v3/release_gate -p 'test_*.py' -v
```

`run.py` calls `eal_validate`, `eal_collect`, `eal_reason` and
`eal_compile_aspic` through a real MCP stdio client. The four tests cover
the decision table, distinct tool error, timestamps, pinned source files,
MCP output, explicit defeat and failure handling. The source and registry
digests in `results.json` bind the recorded run. No case consults the hidden
v3 coding assessor or exposes its tests to an agent. A live release gate would
need authenticated provider status, independently trustworthy inventory and
event records, atomic state transitions, currentness policy and tested
authorisation; this fixture asserts none of those capabilities.
