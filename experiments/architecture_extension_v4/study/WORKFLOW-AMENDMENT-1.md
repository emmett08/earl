# Pre-acquisition infrastructure amendment: 0.1.0 to 0.1.1

**Recorded before any v4 live agent call.** The original frozen input inventory
is retained verbatim as `freeze-validation-36341669596.json` and at GitHub
commit `f1c32d6125c161c9c6928565f88f43bb8d3db8af` (run
[`36341669596`](https://github.com/emmett08/earl/actions/runs/36341669596)).
The validation job passed source, assessor, packet and nine-episode/six-probe
synthetic smoke checks and mounted both writable and read-only trial views.
It stopped on the *nested* Codex sandbox preflight: `bwrap: No permissions to
create new namespace, likely because kernel does not allow non-privileged user
namespaces.` The nine live jobs were skipped. No v4 agent result, treatment
contrast or provider usage was observed in that run.

The 0.1.1 runner invokes the pinned Codex CLI **inside** the already checked
outer Bubblewrap mount with `codex exec --sandbox danger-full-access`. This
prevents Codex from trying to create a second namespace. It does not remove
the enclosing `bwrap` boundary: the agent sees its own `/trial`, an ephemeral
`/home/agent`, a temporary `/tmp`, read-only utilities, and network access for
the provider API. The decision case has a read-only `/trial` bind; a separate
credential-free probe verifies that a write fails. The preflight also checks
that the pinned CLI starts inside each view without a model request. If any
outer mount or CLI check fails, the run stops before live acquisition. The
documentation for this configuration is [Codex agent approvals and security](
https://developers.openai.com/codex/agent-approvals-security), section
“Run Codex in Dev Containers”: when the enclosing environment is the intended
security boundary, the CLI can use `--sandbox danger-full-access` to avoid a
second sandbox layer. GitHub Actions does not provide an invoice or guaranteed
provider budget ceiling; the registered conditional list-rate stop is intact.

The finite systems, source anchors, corrected refund assessor, hidden controls,
P0/P1/P2 renderers, parity assertions, assignment seed/permutations, sequence,
decision-case oracles, time cap, model, effort, CLI version, conditional price
guard, endpoints and analysis rules are **unchanged**. The only pre-outcome
change is the runner's sandbox layering and its associated credential-free
preflight/test/workflow documentation. This revision is frozen separately and
must pass CI validation before any assigned coding or decision session.
Neither version can be retroactively described as a prior public
preregistration; the apparatus is registered prospectively with respect to
v4 model outcomes after the earlier v3 pilot and the failed 0.1.0 validation.
