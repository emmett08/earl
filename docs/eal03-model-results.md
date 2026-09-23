# EAL/0.3 repeated model experiments — 23 September 2026

The fresh study ran 84 trials: six synthetic engineering tasks, two repetitions and seven model/interface conditions. Each delegated answer had to match the intended source and use the supplied observations through actual validation, collection and assessment. Unaided answers were scored for agreement with the expected claim-status labels. These are comparisons of complete systems, not measurements of a model’s internal reasoning ability.

## Fresh results

| Model and condition | Correct / trials | Repairs | Reported tokens | Model cost | Cost / correct task | Mean wall time |
|---|---:|---:|---:|---:|---:|---:|
| GPT-4.1 nano — unaided | 6/12 | 0 | 82,324 | $0.003887 | $0.000648 | 7.3 s |
| GPT-4.1 nano — text + EAL | 10/12 | 11 | 307,951 | $0.012101 | $0.001210 | 19.7 s |
| GPT-4.1 nano — native + EAL | 10/12 | 7 | unknown | unknown | unknown | 24.9 s |
| GPT-4.1 mini — unaided | 8/12 | 0 | 82,328 | $0.019626 | $0.002453 | 7.1 s |
| GPT-4.1 mini — text + EAL | 12/12 | 2 | 257,450 | $0.046489 | $0.003874 | 17.4 s |
| GPT-5 mini — unaided | 9/12 | 0 | 85,304 | $0.013761 | $0.001529 | 10.3 s |
| GPT-5 mini — native + EAL | 12/12 | 9 | 351,542 | $0.027878 | $0.002323 | 22.2 s |

Every scheduled trial is included, including unsuccessful interactions. A correct task requires every requested claim to match. Correct `contested` and `unsupported` outcomes count as successes where those are the known answers. Delegated scoring additionally checks source correspondence and the evidence trace; agreement with labels alone cannot earn delegated success. The unaided arm does not produce an independently checked derivation.

The model snapshots were `gpt-4.1-nano-2025-04-14`, `gpt-4.1-mini-2025-04-14` and `gpt-5-mini-2025-08-07`. GPT-4.1 configurations used temperature zero. GPT-5 mini used explicitly configured low reasoning effort and no temperature parameter. “Small”, “larger” and “reasoning-enabled” are declared experimental group descriptions; parameter counts and general model-class effectiveness were not measured.

| Task | Nano unaided | Nano text | Nano native | Mini unaided | Mini text | GPT-5 mini unaided | GPT-5 mini native |
|---|---:|---:|---:|---:|---:|---:|---:|
| defence-with-independent-subargument | 0/2 | 2/2 | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 |
| defence-cannot-ground-itself | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| registered-rms-velocity | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| registered-rms-wrong-origin | 0/2 | 2/2 | 2/2 | 0/2 | 2/2 | 1/2 | 2/2 |
| cold-room-calibration-reference-repair | 2/2 | 0/2 | 0/2 | 2/2 | 2/2 | 0/2 | 2/2 |
| sampled-negative-finding | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

The defence tasks distinguish an independently supported objection defence from a circular defence that cannot establish its own premise. The RMS tasks exercise a genuinely registered method and reject an observation whose reference origin does not match the formal query. The calibration task requires repairing an undefined assumption reference before execution. The negative-finding task binds a false formal result to an explicitly negative proposition. Observations, context and assessment time are synthetic and fixed; no physical equipment was tested.

## What the failures show

Unaided answers sometimes treated a mismatched formal query as support, misclassified composed defences, or returned the wrong kind of unresolved result. The nano text interface failed both fresh calibration repairs. Its attempts included malformed escaped source, invented syntax and requests that tried to supply their own validation result. Those were rejected; no success was inferred from the model’s assertion. The native nano run also encountered an endpoint timeout with unknown billed usage. Complete raw attempts and diagnostics remain in the archived trial files.

The simplest successful delegated workflow is `assess`, then `finish`. The host executes validation, fresh collection, reasoning and explanation as four separately recorded MCP calls, in addition to discovery. This reduces the protocol burden while keeping the engineering reasoning in the interpreter. It does not solve argument construction automatically. Larger models can use the same workflow; native tool calling is optional, and reasoning controls are enabled only for a configured compatible provider.

## Paired uncertainty

| Comparison | Accuracy difference | 95% task-cluster bootstrap interval |
|---|---:|---:|
| GPT-4.1 nano — text + EAL minus GPT-4.1 nano — unaided | +33.3 pp | [-33.3, +83.3] pp |
| GPT-4.1 nano — native + EAL minus GPT-4.1 nano — unaided | +33.3 pp | [-33.3, +83.3] pp |
| GPT-4.1 nano — native + EAL minus GPT-4.1 nano — text + EAL | 0.0 pp | [0.0, 0.0] pp |
| GPT-4.1 mini — text + EAL minus GPT-4.1 mini — unaided | +33.3 pp | [0.0, +66.7] pp |
| GPT-5 mini — native + EAL minus GPT-5 mini — unaided | +25.0 pp | [0.0, +58.3] pp |

There are six task clusters, not twelve independent engineering problems per condition. The runner resamples whole tasks, retaining both repetitions, for 2,000 bootstrap samples. Intervals describe variation within this finite suite; these tasks are not a random population sample. A zero-width interval when every observed outcome is identical does not establish certainty or rule out unseen failures. Shared baselines make comparisons dependent. These are descriptive comparisons, without multiple-comparison significance claims.

## Development history

Two separate eight-trial development phases used the existing `text-model-repair-and-explain` and `nested-model-observation` cases, with one repetition per condition. Phase 1 exposed requests that confused source digests with source text. Phase 2 narrowed stateful request schemas, made source proposals transactional, added `assess` and supplied deterministic next-request guidance. The evidence-trace scorer was also strengthened. Earlier results retain their original scorer and are not silently rescored or pooled with the fresh study.

| Phase | Condition | Correct / trials | Repairs | Model cost |
|---|---|---:|---:|---:|
| 1 | mini_text_legacy | 1/2 | 5 | $0.023006 |
| 1 | mini_text_stateful | 2/2 | 1 | $0.021628 |
| 1 | nano_text_legacy | 0/2 | 9 | $0.004498 |
| 1 | nano_text_stateful | 0/2 | 9 | $0.005376 |
| 2 | mini_text_legacy | 1/2 | 6 | $0.019590 |
| 2 | mini_text_stateful | 2/2 | 1 | $0.012062 |
| 2 | nano_text_legacy | 0/2 | 10 | $0.004460 |
| 2 | nano_text_stateful | 2/2 | 3 | $0.004057 |

Phase 2 is a host redesign comparison, not an isolated experiment on state memory: state retention, schemas, feedback summaries and orchestration differ together. Development success did not guarantee fresh-task repair success for nano. No source, prompt, scorer or task changes were made during the fresh study; all three experiment reports record no detected reference or EAL implementation drift.

## Cost, scheduling and reproducibility

The fresh study’s known reported token-cost subtotal is **$0.135033**; **one trial** has incomplete cost information, so the full fresh-study cost is unknown. Development cost was $0.094677 and three separate provider probes cost $0.000090. The known subtotal across these 100 experimental trials and three probes is $0.229800. Previous EAL/0.2 experiments are excluded. Development and probes do not enter fresh-study cost-per-correct-task denominators.

Rates in USD per million input / cached input / output tokens were 0.10 / 0.025 / 0.40 for GPT-4.1 nano, 0.40 / 0.10 / 1.60 for GPT-4.1 mini, and 0.25 / 0.025 / 2.00 for GPT-5 mini. These are configured token-price estimates, not invoices. Provider-reported caching and reasoning-token usage are retained. Failed attempts count. The assumed marginal MCP fixture charge is zero; host hardware, labour and taxes are excluded.

Official model and price references, checked for this run: [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini).

The runner used a seeded, rotating condition schedule and at most four concurrent trials. Seeds controlled scheduling; provider sampling seeds were not sent. Temperature zero does not guarantee replay. Cache warmth, provider load and wall-clock conditions were not fully controlled. Token/cost limits are post-response stop conditions, not provider-enforced spending caps. The frozen plans contain exact budgets, model settings and launch order.

The fresh six cases were not sent to models during host development, but they are public synthetic instances of deliberately selected task families. They do not establish breadth across engineering domains, human readability, unfamiliar model classes, long argument construction or production workloads. Mechanisms such as typed contracts, source preservation, bounded feedback and native/text parity are available across model classes; effectiveness remains empirical.

Use the [experiment plan](../benchmarks/experiments/eal03-matrix.json) and [runner documentation](model-evaluation.md) to repeat the study. Exact observations, references, code hashes, provider identities, scheduled order, trial outputs and usage are in [the archive index](../benchmarks/results/2026-09-23-eal03/index.json). Each `.json.gz` archive expands to JSON whose `files` map stores exact original UTF-8 files, including `freeze.json`, `report.json`, `trials.jsonl` and `trials/*.json`. Individual trial digests and the archive digests remain verifiable. All observations and task meanings are preserved; credentials are absent.
