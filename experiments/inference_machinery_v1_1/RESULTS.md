# Corrected finite inference pilot: run 36354664940

**Status:** completed descriptive pilot, 27 September 2026. The source is
commit `cfd4167a874b70c75e9a7d68b02ab688182a7714`; the pilot freeze digest
in `result.json` is `d71a9242adafd07316a3817bc55b6f95bc7b38b720de4c2fe0fa57c2e22be519`.
Validation, offline EAL assessment and the two live `gpt-5.4-nano` Responses
sessions succeeded. The provider returned snapshot `gpt-5.4-nano-2026-03-17`
for both arms. The original GitHub Actions artefact is
[`inference-v1-1-live-36354664940-1`](https://github.com/emmett08/earl/actions/runs/36354664940/artifacts/10943034756)
with ZIP SHA-256
`e8e8fbed3b196e99c588f3fb2a1bd5dfb671c8fbca09222a628a8eeaf7ba4894`.
An unchanged copy is retained in `results/run-36354664940.zip`.

## Observed conclusions

| Measure | Result |
|---|---:|
| EAL/2 engine against the independently specified project-authored oracle | 12/12 |
| Raw evidence, one fresh nano session | 11/12 |
| Same evidence plus computed EAL/2 result, one fresh nano session | 12/12 |
| Assisted minus raw, exact cases | +1/12 |

Both agent outputs were complete JSON with exactly one answer per registered
case. The checked prompt prefix confirmed identical raw observations, including
`ok=true` and age for every present observation; the assisted arm additionally
received the actual evaluator status and trace. The only agent disagreement
was **C04**: a current claim-level blocker attacks both constructed support
routes. The oracle and EAL/2 returned `contested`; the raw session returned
`unsupported`; the assisted session returned `contested`. C01–C03 and
C05–C12 matched the oracle in both arms. Thus the local benefit occurred in
the distinction between defeated support and absent support.

| Session | Input tokens | Output tokens, including reasoning | Agent wall seconds | Conditional high Standard-rate USD scenario |
|---|---:|---:|---:|---:|
| Raw | 1,107 | 638 (498 reasoning) | 4.609 | 0.001182 |
| EAL-assisted | 2,845 | 181 (40 reasoning) | 1.474 | 0.001031 |
| Both | 3,952 | 819 | 6.083 summed call time | 0.002213 |

The scenario uses the posted `gpt-5.4-nano` rates and deliberately dearer
input/cache-write and regional allowances. It is not a provider invoice or a
guaranteed spending bound. Call times are measured separately and are not
end-to-end workflow duration. The aided prompt is longer but the observed
output and call time were smaller in these two calls; this is not a reliable
latency or cost effect estimate.

## Inferential limit and next step

The engine correctly executed the authored finite argument cases. In one pair
of model sessions its computed result corrected one raw response. This is a
local existence observation on synthetic, project-authored cases; the twelve
answers within each session are dependent. It neither estimates population
accuracy nor proves that EAL/2 beats another accurate checked-result tool.
The oracle was constructed separately from the runtime but has not had blind
external adjudication. A substantive test needs independently sourced cases,
validated domain facts and more independent session pairs after a pilot shows
that the endpoint can discriminate.

The earlier [v1.0 run 36354451977](https://github.com/emmett08/earl/actions/runs/36354451977)
is **invalid as an agent contrast**: the raw prompt omitted the `ok=true` fact
that EAL evaluated. Its 12/12 versus 3/12 agent scores must not be pooled with
or substituted for the corrected run. The original ZIP is retained in
`../inference_machinery_v1/results/run-36354451977.zip` with SHA-256
`4b68a786a35213b72c797577576c85b8ce5a0c06c58a404cb6fbbd9f04a6391c`.
