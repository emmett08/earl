# EAL/2 deployment pilot: 800 assigned model calls

This is a prospective executable **developmental synthetic** amendment to the
historical specified `INV-EAL-DEPLOYMENT-001` version 0.1.0. Its exact original
bytes remain at `benchmarks/protocols/INV-EAL-DEPLOYMENT-001.json` on the merged
main branch; the partial execution snapshot omits that directory. The original
arithmetic excludes an optional grammar experiment. No grammar change is needed
for the base study. Its stated Stage 1 multiplication is arithmetically
inconsistent: fully crossing `8 × 3 × 2 × 2 × (2 × 3 + 1 × 2)` gives **768**,
not 384. Amendment A1 keeps 384 by allocating two of the four
format×instruction cells per root/state block. The complementary assignment
is balanced across the 24 blocks, yielding 12 blocks per cell. Format and
instruction main effects can be described in this developmental cohort;
their full within-block interaction is not identified. The exact original
full-factorial study remains unrun.

A1 stopped after eight attempted calls because a newly configured GPT-4.1 nano
provider sent an unsupported `reasoning_effort` field. Six A1 calls completed;
two returned HTTP 400 without usage. A1 is archived separately.

A2 stopped after 128 attempts because one Sol native request returned HTTP 500
without usage; 127 completed. The separately frozen C1 continuation attempted
288 more assignments, completed 284, and stopped on a failed initial linked
author turn. A2 and C1 retain five failed slots and 384 never-attempted slots;
their archives and cost accounting remain separate. Their partial outcomes are
not pooled into the fresh A3 cohort.

A3 completed a new 800-assignment draw with the same balanced incomplete
allocation, reviewed synthetic corpus and independent checker. The exact
runner, plan, freeze and review protocol were independently audited before its
first call. Its bounded policy makes one identical retry after a no-response
HTTP 500–504, retaining both requests, unknown billing reserves and elapsed
time. It stops on repeated double failures, a double-failed author turn,
integrity error or the US$45 conservative cap. At most two requests are in
flight. An assigned slot therefore can entail two actual API requests; the
actual request count and any failures belong in the terminal ledger. Its terminal
result and hashes are at
`benchmarks/results/2026-09-24-deployment-800-a3-developmental/README.md`:
800/800 slots completed through 804 actual requests, with four rescued 5xx
first requests and no final slot failures. Configured model cost was
US$1.16650454, plus US$0.14565120 conservative unknown-billing reserve.
Fixed direct exact status was 50/144, checked host owned 144/144 and native
96/96. All 320 authored recipient packets were `unavailable` because no final
source passed the executable source contract; no recipient status was accepted.

| Stage | Assigned calls | Exposure |
| --- | ---: | --- |
| Fixed source | `8 × 3 × 2 assigned format/instruction pairs × ((2 × 3) + (1 × 2)) = 384` | Eight new synthetic roots, three evidence revisions, EAL and an independent generic graph, balanced incomplete neutral/matched instruction, three delivery modes for Luna/Sol and two for nano |
| Linked author | `8 × 2 × 2 × 3 = 96` | Two formats, Luna/Sol as authors, initial positive brief then alert and independent answer, each succeeding turn sees its own previous output |
| Isolated recipient | `8 × 2 × 2 × 10 = 320` | Ten fresh model sessions per final author product; evidence states 4/3/3, recipient model classes 4/3/3 |
| **Total** | **800** | A3 has one assigned slot per row, including native tool requests; bounded 5xx retries can add actual API requests |

The current provider supports `complete_request(native_tools=True)`, with a
single Chat Completions function call and recorded tool arguments/usage. The
native mode selects the pinned artefact and claim; the host owns the returned
compact status. The direct mode leaves status to the model. The preassessed
mode gives the model a checked packet and retains host authority. A provider capability probe
established that both assigned native products accepted the specified
tool and reasoning settings before paid execution. The A2 exact function
schema returned a valid scoped request from Luna and Sol (357 input and 41
output tokens each); corrected nano text configuration returned its dated
alias with 11 input and one output token. These probes are in
`capability-probe.json` and exclude their own model calls from the 800 assigned
trial calls. Luna and Sol use reasoning effort `none`; Sol high plus native
tool returned HTTP 400 in a separate probe and is outside this treatment.
Nano has no native mode.

Rates use the published short-context standard input, cached-input and output
prices for the three products as inspected on 24 September 2026. The
conservative US$41.601638 reserve treats every possible input token as a
GPT-6 cache write at 1.25 times the input rate and every output at its cap;
the pilot stops at a US$45 cap. Provider usage does not currently expose
cache-write tokens through this adapter. Configured-rate model costs therefore
exclude any cache-write premium and are not reconciled invoices. Report input,
cached input and output tokens separately; total monetary cost remains
unavailable until billing and effort are reconciled.

The eight briefs concern a battery bus, database restore, robot stop, water
dosing, payment replay, rail interlock, data pipeline and solar inverter. Their
field contracts and engineering warrants differ, but all follow a controlled
positive-test → adverse-alert → independent-answer structure. The common
structure limits generalisation. Synthetic JSON is asserted acquisition, not
authenticated telemetry or proof of physical truth. The independent graph
checker is separate code and does not import EAL; the graph and EAL records
still originate in a single authored fixture generator. Each root has two
positive routes and a targeted objection. Four adverse states leave an
independent route usable, while four need the later answer. All eight share
this generator and a 15-minute synthetic acquisition pattern, so they are
dependent template variants despite different engineering fields. Reviewers
see candidate labels; their checks are independent of the author, unmasked,
and conducted by AI agents, not human judges. Expected statuses remain
synthetic reference labels only. The 24 root/state
references were reviewed independently by two AI agents, unmasked to authored
labels and pinned to manifest and checker hashes. This does not amount to a
human or physical adjudication.

Stage 2 reuses the final model-authored source as an experimental candidate.
Invalid or wrong candidates are retained. The fixed host returned
`unavailable` for all 320 A3 recipient assignments; none was replaced by a
reviewed source. Two separately sealed AI reviews agreed that all 32 final
authored sources violate the executable contract, while disagreeing on some
readable-intent criteria. They were unmasked to reference labels. The
predeclared 48-explanation sample received two independent AI reviews. They
agreed on 4/48 faithful and 44/48 unfaithful ratings; all four faithful sampled
responses were fixed direct Sol. Criterion-level disagreements remain recorded.
This exploratory unmasked AI review does not substitute for human validation.
Reviewer time and rate, acquisition cost, host compute
and provider billing must all be entered for total cost per accepted decision;
the runner reports configured-rate model cost separately. The original pilot's
token ratio at ten uses remains the registered primary estimand. Eight roots do
not support a decisive two-percentage-point false-support noninferiority claim.

Reproduce the offline material and inspect the original A2 schedule (zero paid
calls):

```sh
PYTHONPATH=src:. python benchmarks/experiments/deployment-800/generate_inputs.py
PYTHONPATH=src:. python benchmarks/experiments/deployment-800/run.py --preflight
```

A3 uses `run_a3.py`, `plan-a3.json` and its separate freeze. Two independent
AI pre-reviews, the comparator, capability probe and budget preflight were pinned
before paid execution. The author/reviewer effort template is
`effort-log.template.json`. `postcall-review-protocol-a3.json`,
`predeclared-review-slots-a3.json` and `postcall-review-rubric-a3.json` define
the exploratory 32 final authored products and 48 explanation slots selected
without using their eventual outcomes. Every selected failure is retained;
reviewers see actual recipient prompts and host packets, and are unmasked to
exposure when the packet reveals it. The credential is read from `OPENAI_API_KEY`
at execution time only. A separately frozen grammar experiment would add
calls and cannot be folded into these 800 assignments.
