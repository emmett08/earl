# Cross-model delivery: offline status

The two developmental schedules are frozen and have zero completed campaign model calls. The original attempted schedule stopped with one pending call and unknown billing when automatic approval review blocked sending private repository prompts and evidence to OpenAI. It must not be resumed automatically. `blocked-attempt.tar.gz` retains its exact freeze and ledger.

`offline-freezes.tar.gz` contains the final 180-case pilot and 135-case new-cohort schedules, including prompts, checker traces, code and fixture hashes. The new cohort has 9/9 scored EAL/independent-checker oracle agreement and 5/5 authored challenge-pair agreement. The 45 generated envelope attacks exercise the independent checker alone. These are synthetic developmental cases; external human adjudication is pending.

The API access probe succeeded for the three configured models, and one minimal nano completion reported 10 input and 1 output token. It did not execute any scheduled case. The repository tests and offline freezes are reproducible with the commands in `benchmarks/experiments/campaign-config/README.md`.

Model status accuracy, false support, explanation fidelity, campaign tokens, retries, latency and total cost per correct accepted decision cannot be reported from an unrun study. The cost denominator requires a correct, well-formed, independently adjudicated faithful decision; the numerator must include model calls, acquisition and host compute, explanation review, and initial authoring/review effort amortised over accepted decisions. The templates in `benchmarks/experiments/campaign-config/` retain unknown cost fields as unknown rather than zero.
