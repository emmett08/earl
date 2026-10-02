# Supplemental answer-measurement review

This post-collection amendment concerns the communicated current whole-task decision. It is separate from the completed pilot's original FINISH coding, which remains the primary historical analysis. Neither original answers nor provider identities are edited. The source rows have SHA-256 `927d14d61ad67dceb1bf72e3e5c8dda0e73e6c29407dec660f9490fdf02460ef`.

## Selection and masking

The review includes all 25 originally ambiguous answers and one randomly selected resolved recipient answer in each of 144 arm, recipient-model, tool, task and reference strata. Selection uses seed 20261002. The resulting 169-item packet contains opaque identifiers and complete answer text. Reviewers received no original codes, reference decisions, arm or model labels, private mapping or other experiment records. Answer text can itself reveal contextual information; masking does not establish that treatment was unrecognisable.

Two fresh AI reviewers independently interpreted every complete answer under the supplied semantic rubric and froze their codes and exact supporting quotations. They agreed on all 169 initial codes: both retained the original 25 ambiguities and flagged one previously resolved answer. Agreement measures consistency under that rubric; it does not establish correctness or an assessor error rate.

## Semantic adjudication

A third fresh AI adjudicator received only the 26 flagged complete answers and opaque identifiers, with a clarified semantic instruction. The instruction distinguishes a formal failed criterion from practical withholding of readiness when evidence is missing. A parenthetical or the full explanation may disambiguate the heading without an explicit correction phrase. Literal occurrence of both labels is insufficient to establish conflict. Competing formal current classifications, or a tentative answer without a definite current verdict, can remain ambiguous.

This clarification was developed after collection and after inspection of the initial reviews. It is a supplementary measurement amendment, not a preregistered validation. The adjudicator froze 7 undetermined codes and 19 ambiguous codes before reference agreement was calculated. One undetermined code restored the original resolved answer. Six original ambiguities became undetermined: five agree with their references and one disagrees. The unfavourable amendment is retained.

All quotations are verified as exact source spans; source hashes, unique identifiers, full answers and private mapping are checked before joins. The six changed rows append an annotation-history record in a separately derived file. All 4,224 original answers and API identities remain byte-equivalent at the field level. A separate scorer recomputes references from the original cases. Resource accounting remains unchanged.

## Results and limits

Nineteen whole-dataset ambiguities remain: 12 ordinary (including 2 donors) and 7 EAL recipients. Recipient counts are ordinary 739 matches, 1,171 mismatches and 10 unresolved; EAL 1,871 matches, 42 mismatches and 7 unresolved. The corresponding missing-code bounds are 38.49–39.01% and 97.45–97.81%. The recomputed report remains `pending_annotation`; its practical conclusion remains `pilot_only`.

These are AI interpretations from the same orchestration environment. There is no independent human validation, factual-grounding review or representative random sample of all resolved answers. The deliberately stratified sample cannot estimate a population assessor-error rate. The refined rubric can also change the interpretation of answers outside the sample. The remaining masked packet is prepared for subsequent review; no favourable code is substituted for unresolved evidence.

## Reproduction

From the repository root, with the completed archive extracted and this review directory available:

```bash
python3 scripts/review_pilot_measurement.py REVIEW_DIRECTORY \
  --rows FINISH_DIRECTORY/annotated-rows.json \
  --cases FINISH_DIRECTORY/cases.json \
  --output NEW_DIRECTORY/supplemental-review.json \
  --derived-rows NEW_DIRECTORY/supplemental-annotated-rows.json
python3 -m experiments.model_transfer.analyse FINISH_DIRECTORY \
  --rows NEW_DIRECTORY/supplemental-annotated-rows.json \
  --output NEW_DIRECTORY/supplemental-analysis.json
```

The derived-row destination must be new. `paper/analysis/check_supplemental_measurement.py` independently checks the retained amendment against the immutable paper snapshot. The review JSON files bind the packets and decisions by exact hashes.
