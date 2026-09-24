# A bounded live pilot for the EAL/2 artifact handoff

This developmental pilot makes **at most 48 single-turn model requests**: four
engineering roots, three evidence states per root and four recipient arms per
state. The roots are the analysis units. The twelve states are correlated
within their roots. The files under
`benchmarks/experiments/artifact-live-pilot/` are synthetic fixtures and must
pass their independent brief/oracle review before model calls. The run has **not
been executed against an API** in this environment.

The arms are `raw_eal` (source and complete acquired observation envelopes),
`raw_graph` (the same source parsed into a typed JSON graph and the same
envelopes), `apply_eal` (raw EAL with an explicit instruction to check bindings,
methods, objections and scope), and `checked_packet` (the host's compact
assessment given to a text recipient for an advisory explanation). The JSON
graph is generated mechanically from the EAL AST. The common EAL interpreter
assesses the host route. This is a fair recipient-representation control for
fixed semantics; it is **not** an independently implemented equal JSON checker.
The derived graph is longer than the EAL source, so its comparison measures
the complete rendering, including length and field names. It cannot isolate a
pure syntax effect or establish savings against an optimised JSON design.

Before any model request the operator-pinned `ArtifactRegistry` collects and
assesses each state, verifies its frozen oracle status, and saves its complete
collection, assessment, packet, source, method registry fingerprint and code
identity in `freeze.json`. The application owns the final status. A model's
answer and explanation are retained separately, including outputs that
contradict the checked status. Raw arms receive the observation envelope,
declared acquisition request and host collection eligibility, without an
argument conclusion or oracle status. The runner does not ask a model to choose
an artifact, change its scope or bypass the host.

## Prepare and run

Install the package and its test dependencies in an appropriate Python 3.11+
environment. Create a local provider configuration outside the repository:

```toml
[provider]
kind = "chat_completions"
model = "gpt-4.1-nano"
api_key_env = "OPENAI_API_KEY"
timeout_seconds = 60
max_tokens_field = "max_completion_tokens"

[provider.pricing]
input_usd_per_million = 0.10
cached_input_usd_per_million = 0.025
output_usd_per_million = 0.40
```

The [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4.1-nano)
lists those rates and a Chat Completions endpoint as of the protocol freeze;
check current rates and availability before running. The page marks the named
dated GPT-4.1 nano snapshot deprecated. The API key belongs only in the
`OPENAI_API_KEY` environment variable supplied by a secret manager. Do not put
it in the TOML file, command arguments, fixture tree or retained output.

With that variable supplied securely, these commands use the frozen manifest:

```bash
PYTHONPATH=src python scripts/run_artifact_live_pilot.py \
  benchmarks/experiments/artifact-live-pilot/manifest.json \
  /private/experiment-output/artifact-pilot \
  --provider /private/provider.toml --freeze-only

PYTHONPATH=src python scripts/run_artifact_live_pilot.py \
  benchmarks/experiments/artifact-live-pilot/manifest.json \
  /private/experiment-output/artifact-pilot \
  --provider /private/provider.toml --resume --max-cost-usd 0.25

PYTHONPATH=src python scripts/run_artifact_live_pilot.py \
  benchmarks/experiments/artifact-live-pilot/manifest.json \
  /private/experiment-output/artifact-pilot \
  --provider /private/provider.toml --verify
```

`--freeze-only` and `--verify` make no provider requests and do not require the
credential to be populated. `--resume` checks exact fixture, request, method
implementation and provider identities. If a request was interrupted or its
usage is unknown, it records the attempt and refuses an automatic retry because
the attempt may already have been billed. Provider errors, including a returned
model name different from the pinned identity, halt the block. When an alias
resolves to a different dated response model, a **new** frozen run can specify
that exact identity using `--response-model`; do not change it during a run.
No request is retried implicitly.

The runner limits each request to 16,000 UTF-8 prompt bytes and 256 requested
output tokens by default. At the listed rates, 5,000 input and 256 output
tokens per request would cost about **$0.029 for 48 calls** without caching.
Its byte-based preflight reserve is an estimate of input tokens, **not a hard
invoice limit**. The configured `$0.25` spending stop uses actual reported
usage after each response and leaves a reserve before the next request; an
in-flight request can exceed its estimate. Every attempt retains input,
output and cached token counts, price estimate, elapsed time, raw response,
returned model identity and parsing outcome. Missing usage halts execution.

Run the offline harness checks with:

```bash
PYTHONPATH=src python -m pytest -q tests/test_artifact_live_pilot.py

PYTHONPATH=src python scripts/run_artifact_live_pilot.py \
  benchmarks/experiments/artifact-live-pilot/manifest.json \
  --preflight-summary /tmp/artifact-preflight.json

cmp /tmp/artifact-preflight.json \
  benchmarks/results/2026-09-24-artifact-live-pilot/preflight.json
```

The retained preflight records 12 host/oracle statuses and 48 prompt-byte
counts with no model calls. In the current fixtures the total prompt bytes are
67,877 for raw EAL, 82,010 for the expanded JSON graph, 70,181 for EAL plus
application instruction and 16,698 for checked packets. These are UTF-8 bytes,
not provider tokens or charges. The brief-level oracle and interpreter agreed
for all twelve synthetic states; a second masked human review has not occurred.
One root makes a complete, scoped negative finding a necessary premise and
withdraws support when an inspection reports four rows but repeats J3 and
omits required connector position J4. The source and separate brief-level
oracle both require the specified J1–J4 identifiers.

## Interpretation

The checked packet supplies the answer, so a recipient repeating that status
does not demonstrate model reasoning. Its explanation requires separate blind
review for unsupported additions, qualification and exact adverse-evidence
handling. The host's exact statuses are fixture-consistency checks, while the
raw recipient outcomes diagnose whether syntax and explicit instructions help
the same model apply the source.

The four roots permit a feasibility report and an error taxonomy. Even four
unanimous independent paired directions give a two-sided sign-test value of
0.125. This block cannot establish a modest EAL-specific superiority, a
cross-model interaction, or the primary ten-recipient cost estimand in
`INV-EAL-DEPLOYMENT-001`. It contains no model-assisted source authoring,
two-developer transfer, native MCP selection or independent generic checker.
Those questions require the separately registered, larger investigation.
