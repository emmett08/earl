# Reviewed recipient model loop

`run_reviewed_recipient` joins a configured model provider to the dedicated
recipient MCP endpoint for one recurring, exactly reviewed question. The
trusted launcher passes the original question both to the server as a file and
to the application as text. Before collection or model generation, the
application discovers the endpoint's limited tools, asks `eal_bound_task()`
for the sole authorised reviewed route, and compares the server's question
SHA-256 with its own exact UTF-8 bytes. A changed or uncovered question stops.

The host then calls `eal_assess_bound_task()` with no model arguments. It
feeds the model the original question, reviewed route, advisory candidates and
the compact checked claim packet. The model can return one strictly checked
JSON operation:

```json
{"operation":"answer","text":"The observation supports the scoped claim."}
```

Alternatively, `{"operation":"explain"}` obtains the addressed argument and
evidence trace; the next turn receives that trace and can answer. An explicit
`{"operation":"stop","reason":"The declared scope does not answer this question"}`
leaves the interaction incomplete. A final `eal_finish_bound_task` call
retrieves and compares the host-owned packet after model output. The report
separates `checked_answer` from `recipient_output_unverified`; consumers must
use the former for claim status. Even when the provider fails, a successfully
finalised assessment remains available with `status: incomplete`.

The same request and result checks apply to a plain-text provider, a provider
configured for structured JSON, and a provider configured for native function
calls. For native calls, `interaction_mode="native"` requires explicit
`native_tools` capability; the application returns the addressed explanation
using the provider's function call ID. A command provider or any other
configured adapter can use text mode. These are interfaces, not claims that
every model can reliably author a faithful explanation.

```python
import asyncio
import os
import sys
from pathlib import Path

from mcp import StdioServerParameters
from eal.providers import load_provider
from eal.recipient import RecipientBudget, run_reviewed_recipient

root = Path("/trusted/earl-workspace")
question_file = root / "question.txt"  # Exact reviewed bytes, no added newline.
server = StdioServerParameters(
    command=sys.executable,
    args=["-m", "eal.server", "--workspace", str(root),
          "--registry", str(root / "tools.toml"),
          "--artifacts", str(root / "artifacts.toml"),
          "--families", str(root / "families.toml"),
          "--tasks", str(root / "tasks.toml"),
          "--recipient-task-file", str(question_file),
          "--recipient-only", "--recipient-principal", "caller_a",
          "--recipient-family-grant", "rig",
          "--recipient-task-grant", "field_inspection",
          "--recipient-grant", "rig_field:accepted"],
    env=dict(os.environ),
)
provider = load_provider(root / "provider.toml")
report = asyncio.run(run_reviewed_recipient(
    question_file.read_text(encoding="utf-8"), provider, server,
    budget=RecipientBudget(max_model_turns=3, max_tool_calls=5),
))
print(report["status"], report["checked_answer"])
```

The application accepts only a dedicated reviewed recipient server. An
operator endpoint or older artefact-only endpoint is refused before any
assessment. The launcher must authenticate the principal and derive grants
outside model text; arbitrary CLI flags are not an authentication scheme.
Stored reviewer names and digests detect contract changes but do not
authenticate human review or the physical observation source. The loop is
bounded by model turns, repairs, tool calls, total tokens, prompt and response
bytes, elapsed time and optional configured model cost. A missing token count
prevents another model turn; missing pricing prevents a stated cost budget.
Token and cost thresholds are checked after provider usage is returned, so
one in-flight request can exceed them; they are stopping thresholds rather
than a provider billing guarantee. Set an external call/spend reservation for
paid studies. The response report states these budget semantics explicitly.
The report retains failed attempts, tool calls, protocol identity, model usage,
candidate suggestions and checked packet for a paired experiment.

The candidate operation provides suggestions only. Even if an alias or
retrieval catalogue improves recall, it cannot promote a new paraphrase into
an assessed case. Its failure is recorded and does not block an otherwise
reviewed exact task. The applicability catalogue still requires an exact
reviewed question and bindings. The model cannot supply source, claim,
context or assessment ID. A source written through `AuthoringSession` requires
an independent correspondence review before registration. Compare this route
against an equally capable JSON checker on held-out task fidelity, correct
correction after evidence changes, abstention, latency and complete cost,
including authoring and review. Equal checked graphs should have equal
statuses; the implementation alone establishes no EAL/2 accuracy advantage.
