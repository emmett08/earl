# Pre-acquisition connectivity amendment: 0.1.1 to 0.1.2

The 0.1.1 freeze is retained verbatim as
`freeze-validation-36342146781.json` and at commit
`c2db153236dbc3fd6880809389ee57fb9cc79840` in primary run
[`36342146781`](https://github.com/emmett08/earl/actions/runs/36342146781).
Its credential-free preflight verified the outer writable/read-only trial
mounts and CLI startup, but it did **not** test provider DNS or TLS. In the
live jobs, all nine first B invocations ran for the exact 1,800-second cap and
reported `failed to lookup address information` for `api.openai.com`, then
repeated HTTPS connection failures. No `turn.completed` usage was recorded.
The resource guard stopped all nine blocks with unpriced usage. Each block
retains one integrity-checkable baseline candidate and no decision probe;
the remaining 72 coding episodes and all 54 decision sessions were not
invoked. No P1/P2 outcome contrast is identified. Billed resource use is
unknown, not reported as zero. The account key was not rejected by the API:
the client never reached it.

The runner's Bubblewrap filesystem deliberately omits most host paths. On
host configurations where `/etc/resolv.conf` points into `/run`, merely
binding `/etc` leaves the resolver target absent. Revision 0.1.2 resolves
that symlink and exposes only the target resolver **file** read-only, creating
its empty path ancestors inside the sandbox. It refuses a target outside
`/etc` or `/run`; it never mounts all of host `/run`. The credential-free
preflight now resolves `api.openai.com` and completes a TLS handshake inside
both writable and read-only outer mounts, before any live job may start.
It performs no model request and sends no credential. A DNS, TLS or mount
failure stops validation rather than allowing nine capped reconnect loops.

The registered systems, assignments, source-derived P1/P2 parity, assessor,
decision oracles, model, CLI, caps, endpoints and analysis rules are unchanged.
The earlier validation and failed acquisition remain separate attempts;
the 0.1.1 baseline candidates cannot be used as a successful pilot or
backfilled into the new assignment. Revision 0.1.2 receives a new immutable
freeze before any additional live acquisition. A repository secret named
`OPENAI_API_KEY` is mapped by the workflow to the CLI process variable
`CODEX_API_KEY`; a second repository secret named `CODEX_API_KEY` is not read.
