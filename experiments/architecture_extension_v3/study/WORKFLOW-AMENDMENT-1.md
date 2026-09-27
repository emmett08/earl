# Workflow amendment 1: isolated attempts and a working Linux sandbox

This operational amendment follows run
[36331015150](https://github.com/emmett08/earl/actions/runs/36331015150)
at source commit `539c547aaaf492d81eca6f81ef629c0a5665876a`. Outcomes have been
observed. The amended apparatus is a further development exercise; its results
must be reported separately from that run and from the local feasibility study.
The original registration is retained byte-for-byte in
`../results/registrations/freeze-before-run-36331015150.json`.

Attempt 1 stopped because `OPENAI_API_KEY` was absent. Attempt 2 retained
provider authentication failures. Attempt 3's comparison retained six valid
rows and rejected twelve: ten invocation/dispatch mismatches and two packet
mismatches. Its reused artifact names allowed records from different attempts
to reach the same downloaded directories. A retained attempt-3 Codex trace also
reported `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` and no
edits, despite a zero CLI exit code. A green coding job therefore did not
establish feature completion.

Every artifact name and download pattern now includes the workflow attempt.
The assembler resolves episodes, assessments and prior-stage packets in that
same namespace and continues to verify invocation identities and exact hashes.
An incomplete retry cannot substitute artifacts from an earlier attempt. The
comparison log prints the named assembly errors before failing, after retention.

The runner installs distribution Bubblewrap and loads Ubuntu's packaged
`bwrap-userns-restrict` AppArmor profile following the
[OpenAI sandbox prerequisites](https://learn.chatgpt.com/docs/sandboxing).
All Codex arms retain `workspace-write` and the default Bubblewrap backend.
No global user-namespace restriction is disabled. A bounded, credential-free
shell read/write probe runs in validation and in every Codex coding runner
before model invocation. Invocation records identify the backend and probe
outcome; assembly requires a successful probe. The probe uses the pinned
0.154.0 host-selected `codex sandbox` CLI. Hosted execution verifies the package
and profile on the actual runner. The independent assessor continues to
determine whether each feature was completed.

The amendment changes workflow execution, artifact addressing, assembly tests
and this registration. It preserves the allocation, A source, briefs, EAL
argument, collectors, independent assessor, outcomes and completion-time rule.
`freeze.json` records the revised input digests and the original manifest's
SHA-256; it explicitly records that previous outcomes were observed.

Start a **new workflow dispatch** with a distinct block identifier (the revised
default is `sandbox-repair`). Retain the failed run. Use `live=false` to verify
the apparatus without model calls, then `live=true` for the separately reported
exercise. A failed-jobs-only retry can lack current-attempt inputs and is not a
supported acquisition route. A full rerun has separate artifacts but remains a
retry, not a replacement observation or an independent replication. The reused
allocation and codebase support a bounded development comparison only.
