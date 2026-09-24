# Artifact recipient pilot: independent live replication

**Execution:** 24 September 2026 against PR #7 head `89288dfd723d36eee06948367386fca6fcdd0d6d`, using the unchanged four-root, three-state, four-arm manifest. This is a second one-shot run of the existing 48-request developmental pilot. It does not execute the separately specified 96-, 800- or 960-call investigations.

The OpenAI models endpoint authenticated before the experiment. The source files needed by the runner were fetched from the pinned Git tree and all 76 reconstructed files matched their Git blob SHA-1 hashes. The brief-level oracle and EAL/2 interpreter agreed on all 12 synthetic states; ten runner tests passed. The generated preflight summary matched the PR's retained preflight **byte for byte**, including all 48 frozen prompts. Current published GPT-4.1 nano token rates matched the provider configuration: US$0.10 per million input, US$0.025 per million cached input and US$0.40 per million output tokens. The model identity was pinned before the run to `gpt-4.1-nano-2025-04-14`, the identity returned in the first live pilot.

The new freeze digest is `aff3ffbf296130c8c292bdc8bc4ac39181ec2226fccc7c96513401b2c35e94e5`. All **48/48** one-shot requests completed with that returned model identity and complete usage. The source-bound offline verification passed with zero unknown usage attempts. The configured-rate estimate for this replication is **US$0.0066409**; it is not an invoice. No identity-discovery attempt occurred in this run.

## Recipient results

The primary exact score requires a JSON object with exactly `claims` and `explanation`, exactly the requested claim in `claims`, and the fixture-correct status. Named-claim extraction tolerates extra keys and is diagnostic only. Four adverse states per arm have an unsupported or contested reference status; false support counts an explicit `supported` answer on one of these states.

| Arm | Exact correct / 12 | Valid format / 12 | Named correct / 12 | False support, strict / 4 | False support, named / 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw EAL | 6 | 8 | 8 | 2 | 3 |
| Derived JSON graph | 8 | 12 | 8 | 3 | 3 |
| EAL with application instruction | 5 | 6 | 7 | 1 | 2 |
| Checked host packet | 10 | 12 | 10 | 0 | 0 |

| Arm | Input tokens | Cached input | Output tokens | Estimated US$ | Median call wall time, s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw EAL | 17,855 | 0 | 653 | 0.0020467 | 6.610 |
| Derived JSON graph | 20,813 | 5,760 | 577 | 0.0018801 | 6.578 |
| EAL with application instruction | 18,287 | 0 | 706 | 0.0021111 | 6.932 |
| Checked host packet | 3,754 | 0 | 569 | 0.0006030 | 6.409 |

Against raw EAL on the same 12 states, the JSON graph gained three exact answers and lost one; the explicit EAL instruction gained one and lost two; the checked packet gained four and lost none. Exact scores by root in raw/JSON/instruction/packet order were AH-73 direction **3/2/3/3**, calibration assumption **2/2/0/3**, bounded negative inspection **0/2/0/1**, and vent model **1/2/2/3**. Twelve states are correlated within four selected roots, so these paired counts do not support a population claim.

The first live block recorded raw/JSON/instruction/packet exact scores of **3/8/5/10**. The replication recorded **6/8/5/10**. JSON's two-answer exact advantage over raw EAL in this run is smaller than its five-answer advantage in the first run. It also returned false support on **3/4** adverse states under strict scoring, compared with **2/4** for raw EAL. The graph is mechanically derived from EAL, has a longer prompt, and received cached tokens while raw EAL did not. This design cannot attribute the exact-score difference to training familiarity with JSON or infer a representation-specific cost saving.

The packet supplies the authoritative status, so its score measures recipient delivery fidelity. It still contradicted the host on two supported bounded-inspection states. The host assessment must remain the application result; recipient prose and status fields are fallible. The unchanged synthetic roots, missing masked source review, and absence of an independently implemented equal JSON checker continue to limit the study.

## Retained evidence

The complete new freeze and trial ledger are in `benchmarks/results/2026-09-24-artifact-live-replication/live-run.tar.gz` (SHA-256 `692bca96bd1601ae2a559d5c983555ce69c87c444714694e22deff7408ebafba`, 51,720 bytes). `analysis.json` retains every per-case classification, usage figure, paired comparison and source-head identity. The two uncompressed JSON files were checked for the credential marker and key fragment; neither contains them. The archive uses the members `pilot-output-replication/freeze.json` and `pilot-output-replication/trials.json`.

The runner's `--verify` succeeds against the original execution paths and checks current source identity; the frozen trace records absolute paths, so a different checkout should audit the archived ledger with the portable `_audit` function in `scripts/analyse_artifact_live_pilot.py`. That audit checks frozen digests, case/attempt links, parsed answers, usage and recomputed costs without provider calls. The first pilot's archive and analysis remain untouched. The 96-, 800- and 960-call protocols still require new adjudicated roots, independently matched checking paths, and runnable schedules before a prospective execution can begin.
