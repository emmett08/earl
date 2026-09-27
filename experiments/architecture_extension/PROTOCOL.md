# Architecture extension case: frozen protocol

Status: exploratory executable case. The protocol and fixed assessor are
written before launching the coding sessions. No result in this case is a
randomised estimate of the effect of EAL/2, or a longitudinal measure of
technical debt.

## Question and rival accounts

The local question is whether two independently prompted AI coding sessions,
given the same completed feature A snapshot and the same feature B brief,
produce different checked architecture and behaviour outcomes when one sees an
EAL/2 architecture argument. The broader claim that sustained use reduces
technical debt remains untested.

Under the architecture-context account, an agent exposed to the EAL/2 argument
may inspect the channel registry and preserve the single dispatch path while
adding B. Under the explicit-fixture account, both agents may do so because
`ARCHITECTURE.md`, code and tests already explain the extension point. Agent
differences, stochastic generation and unmeasured exposure to prior design
knowledge can also explain a difference. These rivals overlap in a single
case; a positive result cannot distinguish their general effects.

## Materials and intervention

The baseline is `materials/base/`. The entire A request is
`materials/prompts/a_no_eal.md`. Engineer 2 is represented by that fixed
request, not an independent recruited human. A fresh agent implements A from
baseline. Its output is copied byte for byte to two isolated B starting
directories. The B request is `materials/prompts/b_common.md`. The B control
agent receives that text and the A snapshot; the B treatment agent receives
those exact materials plus the full, validated `architecture.eal` source.
Engineer 3 is represented by the fixed B request. No agent receives the
assessor or other agent's output in its working directory. The model session
interface, task order, operator and timestamps are recorded in the result.

Conditions are assigned to different fresh agent sessions, without
randomisation or masking. Source-code access outside the isolated fixture is
discouraged in the prompt but not technically sandboxed. A single attempt per
condition is retained, including failures. There is no optional stopping or
substitution of an unsuccessful attempt.

## Fixed outcomes and analysis

`materials/assessor/probe.py` independently checks console behaviour,
unknown-channel rejection, feature A escaping, feature B body bytes, and the
160-byte boundary including multibyte UTF-8. `assess.py` runs those probes
and each candidate's local unit suite. It compares the AST of the existing
service's `send` and `register` methods with the baseline, counts `deliver`
and `prepare` calls in production modules, checks registered channel names,
and records which production modules were imported by the probes. All checks
and failures are retained in `results/observations.json`.

`reachable_code` means all production modules were imported by the fixed
probes; it does not test every function or establish the absence of dead code.
`single_dispatch_path` and `single_format_path` are syntactic checks, not a
proof that equivalent dispatch or formatting logic has no duplicate elsewhere.
Candidate tests add diagnostic information but cannot replace fixed probes.
Any assessor crash is a failed measurement, not a successful candidate.

The descriptive contrast is the treatment B outcome vector minus the control
B outcome vector for the same feature and snapshot. A numerical score, if
reported, is the count of passed predefined checks; it is not a measure of
latent technical debt. An observed B difference remains confounded with
individual session behaviour and cannot estimate an average treatment effect.
No p-value, confidence interval or token-cost estimate is warranted from this
single pair.

| Observation region | Interpretation | Next action |
| --- | --- | --- |
| Both B outcomes pass all fixed checks | EAL exposure adds no observed benefit in this case; both routes demonstrate feasibility | Repeat on independently chosen tasks and follow-up changes |
| EAL B passes and control B fails a fixed check | Local association consistent with EAL guidance, also consistent with session variation | Replicate with blocked, randomised sessions and blinded review |
| Control B passes and EAL B fails | Local association adverse to the guidance account | Inspect full attempts and treatment comprehension; replicate |
| Both B outcomes fail | Neither prompt yields checked success in this case | Diagnose tasks, apparatus and agents before testing the claim |
| Missing artefact, invalid assessor or unequal snapshots | Comparison invalid | Retain the failure and correct the apparatus in a new versioned run |

The assessor and prompts are frozen through content SHA-256 values recorded
before any B session. Deviations, if any, remain in the result and paper.
The experiment is a feasibility demonstration of task, argument, compiler,
observation and visualisation integration. It cannot establish a trend in
maintenance cost, architectural drift or future AI-session behaviour.
