# Human decision study: EAL/2 critique, reliance and fluency

**Version:** 0.1.0, 24 September 2026. **Readiness:** specified administrative
tooling; no participants, approvals, independently adjudicated study cases or
human outcomes. `trial.py` is an allocation and packet-integrity tool. Its
offline tests use invented records and are not a pilot with people.

## Question and target

Among practising engineers assessing bounded engineering decisions, does an
EAL/2-based critique change final decision accuracy after exposure to AI
advice, compared with conventional AI advice under the same available
evidence? A separate wording intervention asks whether more fluent wording
changes acceptance of incorrect advice when its proposition and recommendation
are held fixed. A changed answer is an observable reliance outcome. It does
not by itself establish the person's cognitive mechanism.

Each participant first reads a case's question, evidence and options and
records a decision, confidence, reasons and time. The administrator then
releases the assigned assistance packet and records a second decision,
confidence, reasons and time. Six between-participant assistance arms are
conventional AI advice, a content-matched prose challenge, EAL/2 structure
without agent critique, EAL/2 with agent critique, an evidence-only summary
and no assistance. Wording (`fluent` or `plain`) is allocated independently in
every arm, giving twelve allocation cells. The no-assistance wording cells are
identical by design and act as a randomisation check. Each participant sees
the same case set in a randomised order but remains in one assistance/wording
cell to limit carryover between intervention styles. Participant IDs are
pseudonyms; a separate restricted recruitment system holds their identities.

## Cases and causal contrasts

New cases must be disjoint from the exposed 12 synthetic model-benchmark
families. Include valid decisions with tempting but answered objections,
defective decisions, missing evidence, ambiguous scope, technical rivals and
rationally asymmetric costs. Conventional advice must be correct in some
cases and incorrect in others. Obtain two independent ex-ante reference
reviews and a third adjudication before freezing the manifest. Independently
check source facts, option correctness, advice content, EAL argument
faithfulness, assistance length, and whether fluent/plain versions preserve
the same propositions, evidence and recommendation. A programmatic check of
the recommendation ID is necessary but cannot establish semantic equivalence.
Do not score cases with unresolved reference disagreement as binary correct.

The primary intention-to-treat contrast is the participant-average final
correct-decision difference between assigned EAL/2 agent critique and conventional
AI advice, averaging over the predeclared case distribution. Report it
separately when conventional advice is correct and incorrect, alongside
pre-to-post wrong-to-right and right-to-wrong transitions. The fluency
contrast is the difference in acceptance of incorrect conventional advice
between fluent and plain wording, with meaning and recommendation held
fixed. The EAL/2 structure versus content-matched prose challenge contrast
tests format under independently checked matching; EAL/2 agent critique
versus EAL/2 structure estimates the incremental agent package. Evidence-only
and no-assistance arms distinguish the effect of added evidence and repeated
consideration from the combined AI intervention. The structure contrast is
still sensitive to length, familiarity and authoring quality; the separate
matched-representation API experiment tests a different model endpoint.

Serious rival accounts are different verification costs, rational trust in a
known source, case difficulty, domain expertise, changed material facts,
time pressure, and demand effects. Record expertise and familiarity before
allocation; make source access and time allowance equivalent across cells.
Collect which supplied records participants consulted and whether they sought
disconfirming evidence through a separate approved instrument. The current
packet tool captures answer, confidence, reason and elapsed time only. It
cannot adjudicate cue uptake or certify a human cognitive bias mechanism.

## Assignment, masking and analysis

Freeze the reviewed manifest, seed, participant count and twelve-cell
allocation before enrolling anyone. `trial.py` balances cell counts to
within one, shuffles case order per participant, emits a pre packet without
assistance or reference, and releases the post packet only against a valid
response bound to the pre packet digest. The participant necessarily sees
the assigned content; reference assessors and analysts can receive records
with condition codes masked until accuracy coding is locked. Packet hashes
identify administered content but do not prove that a participant read it.

Treat participant as the assignment and analysis unit; cases are repeated
within participant and shared across participants. A confirmatory analysis
should fit a preregistered participant- and case-aware model or use a
randomisation analysis with participant-level resampling, report uncertainty
for the primary accuracy and wrong-advice contrasts, and control the
predeclared family of tests. Analyse all assigned participants under a
specified missing-outcome rule; report attrition and compliance separately.
Do not interpret a nonsignificant difference as equivalence. The included
`score` command validates packet-bound pairs and produces descriptive counts
only, including final agreement with wrong advice and switches to it. It issues
no significance test, effect certification or model ranking.

Run a small feasibility exercise to estimate case difficulty, time,
attrition and between-participant variation. Then simulate information for
a practically important accuracy gain and maximum tolerable
right-to-wrong increase, accounting for participant and case clustering.
Freeze the sample size, stopping rule, exclusions, primary contrast and
minimum usable evidence coverage before a confirmatory trial. The twelve
participant minimum in the allocation code merely ensures every cell can
appear; it is not an adequate scientific sample.

## Safeguards and status

Obtain applicable ethics review, consent, recruitment and compensation
arrangements before exposing any participant. Avoid confidential employer
material unless permission and de-identification are documented. Keep the
case reference and treatment assignment restricted, store response files
outside Git, set a retention period and separation of participant identity
from pseudonymous records, and publish only consent-compatible aggregates.
The administrator should record assignment delivery, withdrawals, failed
packets, deviations and whether participants could consult external tools.
Pause if case reference validity, intervention equivalence, privacy or
participant welfare fails. Approval of a manifest's `review` field is an
input assertion; the script cannot verify reviewer independence or ethics
approval.

No human study result may be inferred from the synthetic unit tests, API
responses or the allocation schedule. A participant-level gain in decision
accuracy would support the bounded assistance contrast; the fluency
mechanism additionally requires a successful meaning-preserving wording
manipulation and evidence that advice acceptance changed in its predicted
direction. A trial without that manipulation identifies the intervention
package, not fluency bias.
