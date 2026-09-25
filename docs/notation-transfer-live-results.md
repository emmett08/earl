# EAL/JSON notation and evidence-transfer diagnostic

Report for the 23 September 2026 diagnostic in PR #4. The source grammar and core interpreter are unchanged. This report supplements, and does not replace, the earlier relay findings.

The completed 180-call diagnostic does **not establish an EAL notation advantage or general engineering reasoning ability**. Raw-only EAL achieved 4/10 complete correct answers, versus 5/10 for equivalent JSON. The paired difference is minus ten percentage points, arising from one JSON-only success on the sampled-negative-finding task; four pairs were jointly correct and five jointly incorrect. This is a finite description, not evidence of a population-level JSON advantage.

The new results add actual error-correction opportunities to the earlier preservation finding. With deliberately incorrect proposals, relevant raw observations yielded 2/10 correct endpoints in EAL and 5/10 in JSON, compared with 0/10 and 2/10 for answer-only. Raw observations plus interpreter conclusions yielded 7/10 and 8/10. These are recoveries from injected wrong labels under this prompt, not a natural producer-error rate or proof of independent reasoning. Supplying computed conclusions produced substantially more complete correct endpoints than supplying raw observations alone.

Raw observations did not reliably preserve correct proposals: complete correctness was 2/10 for EAL and 7/10 for JSON in that arm. Neither the circular-defence nor the wrong-origin task scored correct in either raw-only repetition for either representation. The strict JSON outcomes include malformed responses; their claim maps also give incorrect labels. Scope discrimination was also weak: with a full-information-correct proposal and irrelevant observations, neither representation produced an available-information-correct answer in ten attempts. Across all irrelevant-record arms, available-information correctness was 3/40, with 26/40 detected false-support events. None of the 28 proposals wrong under that reference was corrected; the three correct endpoints preserved proposals already correct under it. Answer-only likewise corrected none of its 28 available-reference-wrong proposals. The higher full-information agreement of answer-only arms cannot be treated as justified support when the observations are absent.

Consequently, the requested criticism is only partly mitigated: the new diagnostic adds controlled injected-error opportunities absent from the original primary evidence-transfer contrast and measures some correction. The earlier cumulative record already contained six and four corrections in complete model–tool sequences. It does not establish a robust raw-evidence correction benefit, faithful qualification preservation, a notation advantage, or transfer to new engineering problems. The original twelve-versus-eight contrast retains its original preservation-only interpretation.

## Execution and accounting

All 180 scheduled calls ran once; all ten pairs for every reported contrast are present. There were 161 responses meeting the exact output schema, eighteen malformed/schema responses and one retained output-limit failure. Every response reported the pinned model and complete usage: 1,919,842 input tokens, including 1,837,824 cached input tokens, and 29,816 output tokens. Configured-rate cost was **USD 0.0660738**; this is an estimate from recorded usage, not an invoice. No charges are unknown. The credential is absent from retained files.

Requests ran from 20:22:30 to 20:54:30 UTC on 23 September 2026, including the documented operational pause. Summed request latency was 1,481.13 seconds; median request latency was 8.02 seconds. The first thirty records remain byte-for-byte unchanged after continuation.

## Design and scoring

The frozen experiment uses GPT-4.1 nano snapshot `gpt-4.1-nano-2025-04-14`, temperature 0, a 2,048-token output limit and a common reference. Five exposed synthetic tasks span defence, registered numerical methods and negative findings. Each task has eighteen conditions and two repetitions, giving 180 scheduled calls. Repetitions are dependent; the two incorrect proposals use different wrong labels. Each response has a fresh message context, no tools and no repairs. EAL and JSON carry the same parsed meaning. Their natural input lengths differ, and the common reference uses EAL vocabulary.

There are two distinct scores. **Full-information agreement** compares the response with the original task answer. **Available-information correctness** compares it with the existing interpreter applied to the records actually supplied. They coincide for raw-only, answer-plus-raw and answer-plus-assessed. For answer-only and irrelevant-record arms, every requested claim is unsupported under the second reference. Appropriate caution in those arms can therefore reduce full-information agreement. Both scores require all requested claim statuses to be correct. A false-support event means at least one requested claim in an admitted response is marked supported when that reference does not support it. Malformed/provider-error content is excluded from this score; zero detected false support does not establish absence of false assertions in that content.

The primary score strictly requires the requested JSON response contract; malformed responses remain failures. Short public justifications are retained but are not a validated measure of reasoning quality. The output-format sensitivity is explicitly post-hoc: it was added after early format/schema failures appeared and changes neither the primary scorer nor any retained trial. Fence-only normalisation accepts one complete JSON code block with no surrounding prose. The separate claim-map-only readout requires a strictly parsed raw JSON object and exactly the requested claim identifiers/statuses, but ignores additional top-level fields and the basis shape. Neither mode extracts text, repairs missing labels or recovers provider-error responses. Claim-map admission measures label agreement, not successful compliance with the response contract.

The pre-outcome scoring amendment, wrapper launch events and limits of the local freeze are recorded in [execution notes](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-notation-transfer-live/execution-notes.md). [Protocol 1.0.1](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/protocols/INV-EAL-REASONING-001.json) is the exact pre-generation protocol; its execution fields remain the pre-run state. This report and the execution-status record supply the completed diagnostic status. The separate independent transfer programme remains specified. After the provider adapter stopped at a known-cost truncated response on trial 30, a documented operational continuation allowed the remaining scheduled calls. This stopping-rule change followed the observed failure; the failed response, prompts, output cap, scoring and original schedule were retained.

## Interpretation limits

This experiment measures interpretation of supplied arguments on five exposed tasks. It does not measure formulation from an ordinary engineering brief, source repair, new mechanisms or general engineering ability. The raw-only EAL/JSON comparison changes surface representation under a shared reference and response budget. Any observed difference can reflect tokenisation, input length, training familiarity and output-format compliance; these mechanisms are not individually identified.

Correct/incorrect injected proposals are defined against the full-information answer. They are controlled misinformation, not naturally sampled producer errors. On answer-only and irrelevant-record arms, their correctness can change under the available-information reference. Transition denominators must therefore be stratified separately by each reference; a “damaged” full-information answer may be a justified rejection of support with missing evidence.

A pooled score obscures the task and label mix. An always-supported response achieves 108/180 full-information agreements; an always-unsupported response achieves 100/180 available-information correct answers. These are structural baselines, not model trials. Task-level tables and matched contrasts take precedence. Five exposed tasks, with related defence and RMS pairs, cannot support a population significance claim or establish equivalence.

The original relay contrast still demonstrates preservation: the full model had already produced twelve correct answers, and the evidence recipient retained all twelve while the answer-only recipient damaged four. Its correction denominator remains zero. The new study supplies deliberately incorrect proposals and separate raw-data and computed-answer arms. It can add bounded evidence about correction without changing what the historical comparison established.

## Condition results

Every entry has ten scheduled and attempted responses. “Correct proposal” and “incorrect proposal” refer to the full-information answer. Raw, assessed and raw-only scores use identical references; answer-only and irrelevant-record references differ as described above.

| Proposal and information | EAL full | JSON full | EAL available | JSON available |
|---|---:|---:|---:|---:|
| Correct, answer only | 10/10 | 9/10 | 2/10 | 2/10 |
| Correct, raw | 2/10 | 7/10 | 2/10 | 7/10 |
| Correct, irrelevant | 6/10 | 6/10 | 0/10 | 0/10 |
| Correct, assessed | 8/10 | 8/10 | 8/10 | 8/10 |
| Incorrect, answer only | 0/10 | 2/10 | 4/10 | 4/10 |
| Incorrect, raw | 2/10 | 5/10 | 2/10 | 5/10 |
| Incorrect, irrelevant | 2/10 | 3/10 | 3/10 | 0/10 |
| Incorrect, assessed | 7/10 | 8/10 | 7/10 | 8/10 |
| No proposal, raw only | 4/10 | 5/10 | 4/10 | 5/10 |

False support below is relative to the available-information reference and counts admitted primary responses only. Malformed and provider-error attempts remain in the denominator and are also shown.

| Proposal and information | EAL false support | JSON false support | EAL failed contract/provider | JSON failed contract/provider |
|---|---:|---:|---:|---:|
| correct_answer | 8/10 | 7/10 | 0/10 | 1/10 |
| correct_answer_raw | 4/10 | 2/10 | 2/10 | 1/10 |
| correct_answer_irrelevant | 7/10 | 8/10 | 1/10 | 2/10 |
| correct_answer_assessed | 0/10 | 0/10 | 2/10 | 2/10 |
| incorrect_answer | 2/10 | 5/10 | 0/10 | 0/10 |
| incorrect_answer_raw | 4/10 | 4/10 | 0/10 | 1/10 |
| incorrect_answer_irrelevant | 3/10 | 8/10 | 2/10 | 1/10 |
| incorrect_answer_assessed | 0/10 | 1/10 | 1/10 | 0/10 |
| raw_only | 4/10 | 2/10 | 0/10 | 3/10 |

## Raw-only task results

| Exposed task | EAL correct | JSON correct | EAL false support | JSON false support |
|---|---:|---:|---:|---:|
| defence-cannot-ground-itself | 0/2 | 0/2 | 2/2 | 1/2 |
| defence-with-independent-subargument | 2/2 | 2/2 | 0/2 | 0/2 |
| registered-rms-velocity | 2/2 | 2/2 | 0/2 | 0/2 |
| registered-rms-wrong-origin | 0/2 | 0/2 | 2/2 | 1/2 |
| sampled-negative-finding | 0/2 | 1/2 | 0/2 | 0/2 |

## Exploratory output-format sensitivity

All eighteen schema failures contained an admissible claim map under the exploratory readout. Fence removal recovered none. Across all conditions, admitting claim maps raises full-information agreement from 94/180 to 109/180 and available-information correctness from 71/180 to 81/180, but also raises detected available-information false support from 69/180 to 77/180. These pooled figures are accounting summaries, not treatment effects. The raw-only contrast remains unfavourable to EAL: 4/10 versus 6/10 under claim-map-only reading. Relaxing output compliance therefore does not reveal a hidden EAL advantage.

| Readout | EAL raw only | JSON raw only | EAL incorrect + raw | JSON incorrect + raw |
|---|---:|---:|---:|---:|
| strict | 4/10 | 5/10 | 2/10 | 5/10 |
| fence_only | 4/10 | 5/10 | 2/10 | 5/10 |
| claim_map_only | 4/10 | 6/10 | 2/10 | 6/10 |

## Reproduce the recorded analysis

The [retained bundle](https://github.com/emmett08/earl/tree/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-notation-transfer-live) includes the exact freeze, all 180 raw trials in `trials.tar.gz`, a per-record hash manifest, the original stop and continuation records, the full analysis and five CSV tables. The analysis reads the archive directly; no model calls or extraction are needed.

```bash
python scripts/analyse_notation_transfer.py \
  benchmarks/results/2026-09-23-notation-transfer-live \
  --output /tmp/notation-analysis.json
python scripts/analyse_notation_format_sensitivity.py \
  benchmarks/results/2026-09-23-notation-transfer-live > /tmp/notation-format-sensitivity.json
python scripts/check_reasoning_argument.py
```

For a new live cohort, use a new output directory and an authorised `OPENAI_API_KEY` environment variable with the documented runner. The retained cohort is analysed as recorded; failed attempts are never silently retried.
