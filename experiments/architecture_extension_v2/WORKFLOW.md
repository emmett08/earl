# Running the architecture extension workflow

The [GitHub workflow](../../.github/workflows/architecture-extension-v2.yml) runs its deterministic replay on pull requests without model credentials. The replay checks the EAL/2 language, fixture tests, the retained A and paired B source chain, assessor and complexity results, ASPIC+ export schema, and an actual EAL MCP JSON-RPC exchange. It does not create fresh feature implementations.

After the workflow file is on the default branch, a maintainer can use **Actions → Architecture extension EAL/2 experiment → Run workflow** with `live: true` and a `model_blocks` JSON array. These live runs are an operational replication of the experiment, separate from the ordered local pair reported in the paper. They require repository Actions secrets corresponding to the classes in each block: `OPENAI_API_KEY` for `codex_action` and `ANTHROPIC_API_KEY` for `claude_code`. The replay never requires either secret.

Each block specifies the Engineer 2 class, model and effort for feature A, then one Engineer 3 class, model and effort for **both** B arms. This permits different A/B classes and models while keeping treatment and control matched within each B pair. The class names execute pinned runners: `codex_action` uses `openai/codex-action@86365089eb2b84e0a8fb0717b304f8bdcb13b20e` with the `codex_version` input; `claude_code` uses `anthropics/claude-code-action/base-action@756cc22e19660d20e8cc9496b4f242475a7f7790`, which installs Claude Code `2.1.283`. Supply a provider-valid model ID for each selected class; access to a model depends on the configured account. The following values illustrate the matrix structure and are not completed runs:

```json
[
  {
    "id": "same-codex",
    "a_class": "codex_action", "b_class": "codex_action",
    "a_model": "gpt-5.4", "b_model": "gpt-5.4",
    "a_effort": "high", "b_effort": "high"
  },
  {
    "id": "same-claude",
    "a_class": "claude_code", "b_class": "claude_code",
    "a_model": "claude-sonnet-5", "b_model": "claude-sonnet-5",
    "a_effort": "high", "b_effort": "high"
  },
  {
    "id": "cross-stage",
    "a_class": "codex_action", "b_class": "claude_code",
    "a_model": "gpt-5.4", "b_model": "claude-sonnet-5",
    "a_effort": "high", "b_effort": "high"
  }
]
```

The direct prompt to each agent is exactly the corresponding requirement brief. The host prepares the isolated source tree, invokes the EAL MCP server for Engineer 2 and records the raw exchange. The two Engineer 3 jobs receive the same A source; the treatment tree alone includes the EAL MCP packet. A short identical host instruction makes that packet discoverable if present. The control host also runs and records the MCP preflight, but does not hand its packet to the control agent. The Claude base action receives that same host instruction through its documented appended system prompt file because it does not automatically read `AGENTS.md`. Claude runs in restricted mode with file tools confined to the trial directory and no command tool; the host runs the tests and assessor afterwards. Its tool set therefore differs from Codex Action, while it is identical across its own B pair. A cross-class contrast changes runner and tool affordances together and cannot be interpreted as a pure model effect. Analyse the classes in separate sensitivity pairs.

The workflow retains source manifests, requirement assessments, complexity observations, MCP transcripts, Codex final output or Claude execution JSON, and a checked pair summary. For Claude pairs the summary checks successful execution records and matching reported initial models. The B arms may start concurrently; this workflow does not reproduce the primary local trial's randomised arm order. The checked pair report records requested runner/model settings; inspect the retained agent logs before making claims about a resolved model or completed implementation. A fresh live run is not claimed until the manual dispatch actually completes.

The Claude base action is intended for trusted `workflow_dispatch` inputs: its own documentation says it does not enforce the trust checks of the higher level action. Avoid dispatching unreviewed repository revisions with model credentials. The feature source trees and prompts are versioned here for review.
