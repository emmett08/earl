# Independent task reference review

Reviewer: /root/followup_scientific_review: separate AI reviewer in the same orchestration session. Review date: 2026-10-02.

Status: **passed**. The independent standard-library calculation agrees with all
88/88 authored references. It imports neither
`corpus_logic` nor `corpus_reference`, and does not execute the author's input generator.
Run from the repository root with:

```sh
python3 experiments/model_transfer/followup/review/independent_reference_review.py
```

The eight fictional instances span two logic families and four availability causes per
family. The forty scheduled case positions include **8 undetermined and 32 decisive**
answers: 20 ready and 12 not_ready. Positions 0 and all odd continuity positions remain
in the 88-reference review but are outside the recipient denominator. Manifest and
corpus content match except for their declared schema identifiers.

Each critical loss removes the decisive r0 eligibility. The all_of tasks have no false
conjunct to mask this loss; the any_of tasks have a false reserve route and an unknown
primary route. Positive restoration supplies eligible, satisfied r0; negative restoration
supplies eligible, failed r0. Both recover a decisive answer. Noncritical loss is compared
against position 8 in all_of tasks (a remaining false conjunct makes false AND unknown
false), and position 6 in any_of tasks (a remaining true route makes true OR unknown
true). Other requirement values and scope are held fixed, while timestamps are refreshed
to keep unrelated eligibility fixed. One case-level rule and unchanged admission limits
apply throughout each history.

All case invariants pass. Twelve additional reviewer fixtures, six per logic family,
exercise a retained record
with simultaneous stale/inactive/wrong-version blockers; positive and negative restores
while that record remains; a future/wrong-version record; and the inclusive age-five
boundary versus age six. These fixtures are separate machinery checks, not extra sampled
tasks or participant observations.

The author and reviewer are distinct AI agents in the same orchestration session. The
review is unblinded to authored answers, but computes its decision before comparing it;
the evaluator is independently implemented. Shared AI-family failure modes remain.
The instances are deliberate laboratory constructions, not independent human-sampled
cases. Domain wording is confounded with availability cause. Successful deterministic
checks establish bounded material/reference coherence; they establish neither general
human engineering performance nor open-domain scorer accuracy. Live prompts, state
matching, output/error retention, counts and the USD 2 stop require separate runner and
protocol review.

The JSON receipt records exact input hashes, every selected fact and eligibility blocker,
requirement and route states, all 88 decisions, invariant checks and mixed-history inputs.
