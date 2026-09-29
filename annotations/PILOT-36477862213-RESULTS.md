# Retained principal pilot: AI-coded results

Collection run `36477862213` retained 384 sequences and 4,224 sessions. Export
run `36487342999`, artefact `10998924773`, supplied the masked answers.
The user authorised the AI assessment described in [AI-CODING.md](AI-CODING.md).
Raw rows remain byte-for-byte unchanged. These are live model observations on
selected synthetic task cases, with derived AI labels, not human-validated outcomes.

All 4,224 answers have a code and an exact supporting excerpt: 2,345 `ready`,
850 `not_ready`, 998 `undetermined`, and 31 `ambiguous`. Import preserves the 31
ambiguous decisions as unscored outcomes. The labels file SHA-256 is
`e0fdfa6aa0b1f37b72334d55a4bfec06c281198ce08483efb0c455b6a7bf43c4`.

| Recipient outcome over ten recipients | EAL | Ordinary workflow |
|---|---:|---:|
| Planned and observed answers | 1,920 | 1,920 |
| Correct task decisions | 1,876 | 746 |
| Incorrect task decisions | 17 | 1,173 |
| Unresolved decisions | 27 | 1 |
| Correctness bounds, all planned recipients | 97.7083–99.1146% | 38.8542–38.9063% |

The other three ambiguous answers are initial-session answers. The correctness
bounds allocate unresolved outcomes adversely/favourably; they are not confidence
intervals and do not include assessor error. Basis, citations and JSON-format
diagnostics remain unassessed where the prose answers did not supply those fields.

Cumulative input-plus-output token use, including initial sessions, was 1,943,638
for EAL and 2,992,739 for the ordinary workflow, a 35.0549% reduction. Known model
API expenditure was USD 0.29840445 and USD 0.39637595 respectively, totalling
USD 0.69478040 over 5,453 attempts with complete recorded accounting. This is
collection API expenditure, excluding platform/host usage and assessment effort.

The existing practical-decision procedure returns `pilot_only`, even though its
conditional point and interval criteria are met. It does not promote a pilot to
an independent confirmatory evaluation. The allocation planner returns
`no_supported_allocation`: complete recipient annotation is required, and the
minimum number of complete repetitions per stratum is one against a requirement
of four. The 31 ambiguous answers remain unresolved instead of being forced into
a convenient category. No paid evaluation is started and no supported evaluation
plan is generated.

These results support a descriptive comparison of the retained tasks, models,
tools and ten-recipient horizon under the recorded AI coding. They do not establish
human productivity gains, general model capability or accuracy in a broader task
population. Correlated AI coding error remains unmeasured. Human review of the
ambiguous answers can preserve ambiguity when it is inherent in the response;
removing that blocker may require a prospectively specified measurement procedure
or additional complete pilot repetitions, not retrospective answer repair.

Reproduce with the full export unpacked into a new run directory:

```bash
python -m experiments.model_transfer.annotations import /path/to/run \
  /path/to/run/annotation-bundle annotations/pilot-36477862213-ai-labels.json \
  --output /path/to/run/annotated-rows.json
python -m experiments.model_transfer.analyse /path/to/run \
  --rows /path/to/run/annotated-rows.json --output /path/to/run/analysis-ai.json
python -m experiments.model_transfer.plan_information /path/to/run \
  --rows /path/to/run/annotated-rows.json --output /path/to/run/information-ai.json \
  --evaluation-plan /path/to/run/evaluation-plan-ai.json
```

The **EAL experiment → finish** workflow performs these stages in order and retains
the labels, derived rows, analysis, allocation result and original collection in
one downloadable artefact. A successful processing job and a supported scientific
decision are separate statuses.
