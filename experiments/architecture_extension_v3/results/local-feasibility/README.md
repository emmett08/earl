# Completed local coding feasibility exercise

This is the separate exploratory exercise selected in [`selection.json`](selection.json)
before the first B agent. Six independently copied A baselines were assigned
P0, P1 and P2 once per family. A new local collaboration agent received only
the current `FEATURE.md`, `AGENTS.md` and worktree logistics at B, C and D;
P1/P2 also had their assigned, freshly assessed packet in the worktree.
The host made real EARL MCP `tools/list`, assess and finish calls for every
P2 source cut. The exact MCP wire is retained in the archive. No hidden
assessor result was returned to an agent.

| Family | Arm | B independent pass | C independent pass | D independent pass | D findings |
| --- | --- | ---: | ---: | ---: | --- |
| R | P0 | 15/15 | 19/19 | 21/23 | Checkout rollback after lost refund acknowledgement; unknown refund outcome |
| R | P1 | 15/15 | 19/19 | 21/23 | Same two cases |
| R | P2 | 15/15 | 19/19 | 22/23 | Unknown refund outcome |
| W | P0 | 13/13 | 16/16 | 18/18 | None on the finite probes |
| W | P1 | 13/13 | 16/16 | 18/18 | None on the finite probes |
| W | P2 | 13/13 | 16/16 | 18/18 | None on the finite probes |

Every failure is retained. In R-D the P2 candidate passed one case that both
comparators failed, yet **all three failed a critical unknown-refund case**.
Thus the prespecified substantial local criterion fails its safety condition.
The local runner could not enforce or attest the 30-minute episode cap,
provider tokens, billed costs, exact backend revision, or comparable coding
elapsed time, so its 25% time comparison and economic break-even are
unavailable. There was no condition-masked architecture review or measured
maintenance-demand ledger. This is six assignment units in one codebase, not
18 independent replications or an estimate of monetary technical debt.

The pinned Python Cognitive Complexity instrument was run on each sealed
snapshot. Production-function totals at D were R: P0 180, P1 186, P2 188;
W: P0 146, P1 150, P2 151. They describe control flow under this instrument;
none is a debt-cost measurement or an unambiguous quality ranking. Across the
six P1 source assessments, the host recorded 1.709 s assessment wall,
11,259 packet bytes and 43,184 direct-tool exchange bytes. P2 recorded
8.496 s, 14,505 packet bytes and 65,100 MCP exchange bytes. This is host
overhead; it excludes coding agent compute and P0 preparation time. It does
not show a net cost saving.

The [summary](summary.json) holds every due finding, source digest, packet
and host metric. The [339-file manifest](archive-manifest.json) binds the
retained [candidate/source and tool archive](episodes.tar.gz), SHA-256
`dd59b904ed0722d2b1be333fd90b67cd13dc756bc55d53634ce04fbb12f00b31`.
The archive contains all 18 sealed code snapshots, source/exposure manifests,
agent-visible brief/context files, assessment findings, P1 direct collector
traces and P2 exact MCP wire, excluding runtime SQLite credentials and cache
files. Run:

```bash
python experiments/architecture_extension_v3/results/local-feasibility/replay.py
```

That check verifies every archive byte against the manifest and reruns all
18 due independent assessments on extracted candidates. It does not recreate
the agents' internal reasoning or provider billing. The root workspace gave
agents access to other files in principle despite the instructions to use
only their assigned worktree; there was no OS or network concealment. The
separate credentialed [workflow study](../../study/PROTOCOL.md) remains
unrun. After the first local B agents began, two CI-only changes normalized
three generated parser file endings and updated five whole-result golden
digests for typed evidence status. The 117 frozen study inputs and their
composite digest remained unchanged and still verify; these later CI fixes
do not turn this exploratory local exercise into a controlled trial.
