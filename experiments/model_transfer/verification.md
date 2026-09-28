# Automated model pilot verification

Recorded 2026-09-28T13:38:12.770426+00:00 for the implementation in this
commit. Live provider execution has not started.

| Check | Actual result |
| --- | --- |
| `make check` | 674 passed, 1 skipped; generated parser verified and maintained synthetic API example passed through CLI/MCP. |
| `python3 -m pytest tests/test_model_transfer.py -q` | 6 passed with scripted provider responses and the real EAL runtime. |
| `make build` | Source distribution and wheel built for 2.14.0. |
| Source archive inspection | Runner included; generated experiment run directories excluded. |
| Updated skill protocol validator | VALID, specified status, 0 errors, 0 warnings. |
| Workflow parsing | Only workflow_dispatch; live model-transfer input defaults to false. |
| `git diff --check` | Clean. |

The six case rehearsals produced expected EAL acquisition behaviour: fresh
positive/negative evidence and the expired-assumption case reused one
observation; expired positive/negative and missing-evidence cases collected
one observation. This checks runtime behaviour on synthetic measurements,
not language-model effectiveness.

The full scripted pipeline exercised all 48 sequences, native-tool masks,
reasoning-item continuation within a session, empty later conversation
history, naturally emitted notes, independent oracle labels and budget
accounting. Separate adverse tests retained incomplete paid responses and all
48 scheduled rows after a fatal provider error.

A local launch of the live entry point stopped with
`OPENAI_API_KEY is absent; no live requests were sent`.
The blocked launch recorded **zero API attempts**. The workspace has no provider
key, and the GitHub connector has no workflow-dispatch operation. A credentialed
manual workflow execution remains necessary; its records will determine actual
model performance and provider usage.
