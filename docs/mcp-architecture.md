# MCP composition and execution

EAL composes one FastMCP 4 server from an SDK-independent `ReasoningService`, a shared operation catalogue and validated `ServerSettings`. The launcher selects stdio or Streamable HTTP after constructing the service. A shared operation contract defines names and permitted fields, and the catalogue binds typed handlers for the selected exposure. FastMCP derives their schemas; the strict JSON host checks its flat request against the shared fields and then the discovered schema. The source language remains `EAL/3`, and stored observations remain `EAL/observation-record/1`.

## Responsibilities and patterns

| Component | Responsibility | Design consequence |
| --- | --- | --- |
| `ReasoningService` | Validate, acquire, evaluate and persist scoped EAL results | Application facade; assessment code remains independent of the MCP framework |
| Operation contract and catalogue | Define names and fields, and bind typed handlers for the selected exposure | Shared contract; the host discovers the adapter's derived schemas |
| FastMCP adapter | Register operations, validate arguments and apply admission limits | Adapter and middleware; protocol behaviour remains outside application calculations |
| `ServerSettings` | Resolve and validate service, exposure and transport settings | Immutable configuration; malformed settings fail before serving |
| Application factory | Construct the service, catalogue, adapter and authentication verifier | Composition root; dependencies are supplied explicitly |
| Transport launcher | Start the selected framework runner | Small transport strategy; handlers require no transport branch |
| Workspace acquisition coordinator | Serialise acquisition and registered reuse/collection decisions | Shared local lease; inherited descriptors preserve exclusion through collector cleanup |
| Command supervisor | Own collector process-group termination and reaping | Process lifecycle remains independent of the requesting server's lifetime |
| Store initialisation coordinator | Serialise private identity, WAL, schema and index setup | Concurrent startup establishes one database before serving requests |

Single responsibility follows the listed boundaries. Open/closed extension is provided through operation handlers and existing method/tool registries. The service receives host-selected registries without importing FastMCP, which preserves dependency inversion at the application boundary. Operator and registered exposure provide separate, task-appropriate interfaces.

Substitution between transports means equivalent tool names, input schemas, exposure restrictions and application results for the same service configuration and request. Stdio and HTTP retain their respective connection and authentication behaviour. Contract checks apply before a typed handler can coerce a caller's values. FastMCP middleware supplies this cross-operation check through a supported hook.

## Trusted configuration and access

TOML service settings choose the workspace, registry, database, methods, limits and registered entry IDs. Server settings choose transport, exposure and admission concurrency. HTTP settings choose host, port, path, a token environment-variable name and additional trusted Host/Origin lists. CLI overrides environment; environment overrides file values; file values override defaults. Selected lists replace their lower-precedence values. The host configuration selects executable dependencies and credentials. EAL source supplies the represented question and declared reasoning inputs.

Registered exposure requires a non-empty entry allowlist and uses those entries' stored context. Operator exposure permits source-level operations and result retrieval for the configured workspace. A bearer credential authenticates access to that fixed endpoint; it supplies no separate caller-specific workspace or claim allowlist. An operator can deploy separate endpoints for separately authorised caller groups. Non-loopback HTTP binds and additional non-loopback Host/Origin trust entries require a token, including proxy deployments whose listener binds to loopback. Network deployment requires an HTTPS boundary outside the plain HTTP launcher. Stdio relies on the permissions of its launching process.

The HTTP runner explicitly enables strict Host/Origin protection. FastMCP accepts its loopback host defaults, the configured host, the actual bound address and configured host additions. It accepts same-origin requests and loopback origins on loopback requests, plus configured origin additions. Untrusted headers are rejected before MCP handling. Host/Origin trust lists contain up to 128 unique literal entries each; their validation rejects wildcards. Browser CORS response headers remain a separate deployment setting.

The HTTP client constructs `BearerAuth` explicitly, keeping credentials opaque instead of interpreting token spellings as authentication modes. Host sanitisation preserves fixed envelope fields and the content-block fields declared by the pinned MCP SDK, together with public envelope metadata and recognised content discriminators. Application object keys and string values are remote data and are sanitised recursively, including JSON encoded within content text. Extra wrapper fields receive the same treatment. Strictly undecodable JSON-looking text is replaced in full; object-key collisions caused by redaction return an error instead of overwriting a value. Structured and text representations use the same application-data sanitiser.

## Execution and verification scope

Admission defaults to one tool call per server process. Acquisition coordination additionally covers the workspace across participating processes, including a stdio process and an HTTP process sharing the local database. The registered reuse check runs within the acquisition boundary, so another assessment can reuse a completed observation before deciding to collect it again. Within an acquisition, the existing bounded scheduler may overlap collectors whose operator bindings declare `parallel_safe = true`.

On POSIX, acquisition ownership uses a close-only `flock` descriptor. Each command supervisor inherits that descriptor, so termination of the MCP process closes only its own copy. A separate ownership pipe signals server loss or cancellation. The supervisor stops the collector's owned process group and retains the lease until its members have exited. Linux subreaper support lets the supervisor reap orphaned descendants. Normal collector completion also triggers cleanup of residual group members before serial admission resumes. Configured commands must keep descendants in that group; detached work in another group and remotely started work require separate ownership mechanisms. This local process contract assumes a running host and kernel.

The supervisor receives the exact selected argument vector and effective environment through a bounded 4 MiB configuration pipe. A separate bounded status pipe reports the actual collector return code and whether the supervisor's deadline expired. Working directory, request stdin, output streams, output bounds and environment-based observation identity retain the command adapter's existing contracts. Command execution requires POSIX and uses the host's permissions; operating-system isolation belongs to deployment.

Store construction takes a private sibling initialisation lock before opening SQLite or establishing the binding key. The lock serialises WAL setup, schema creation and observation-index backfill across participating threads and processes. The retained lock file avoids splitting contenders across replacement inodes. SQLite connections commit or roll back their transaction and close before returning.

The acquisition lease and SQLite deployment assume one local filesystem. A multi-host service needs a coordinator and storage design for that deployment. Sessionless MCP requests do not make application acquisition or persistence distributed. Increasing admission concurrency provides no quantitative latency, throughput or model-cost guarantee.

Verification covers real stdio and loopback HTTP invocation, operation discovery, strict validation, configured exposure, bearer acceptance/rejection, collection and reasoning, and stored-observation reuse. Clients exercise the `2025-11-25` handshake and `2026-07-28` discovery profiles. Regression checks exercise Host/Origin rejection before collection, literal bearer handling, response-schema preservation, host deadlines, client cancellation, abrupt server termination, collector descendants and concurrent store initialisation. These checks establish the tested interface and coordination behaviour; provider-model performance and production deployment require their own measurements.

## Deployment alternatives

One framework owns both direct transports, keeping operation registration and validation in one adapter. Separate stdio and HTTP launches can share a local workspace when both access routes are required. A FastMCP stdio proxy to a central HTTP service can instead keep acquisition in one process; it adds a connection hop and depends on the HTTP service. EAL's launcher selects one direct transport, while FastMCP's proxy facility supports the latter arrangement.

Maintaining separate SDK and FastMCP servers would require duplicate registration and protocol adaptation. The shared catalogue would reduce that duplication, but one FastMCP adapter already supports the requested transports. A distributed coordinator becomes appropriate when the deployment spans hosts; the local acquisition lock defines the current bounded contract.

See [MCP and tools](mcp-and-tools.md) for executable configuration, and [primary sources](sources.md#mcp-integration) for framework and protocol documentation.
