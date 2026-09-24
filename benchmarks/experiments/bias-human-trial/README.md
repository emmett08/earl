# Human decision trial administration

`trial.py` freezes a twelve-cell participant allocation, serves the same
case's evidence before assistance, and releases assigned assistance only
after a valid pre-decision response. It validates paired records and reports
descriptive results. **No people have been recruited or tested.** Read
`PROTOCOL.md` and obtain the specified independent case review, approval and
consent before using it with participants.

The private manifest has schema `eal2-human-decision-manifest/1` and at least
four new, independently reviewed case families. Each case has the following
shape (repeat with unique `id` and `family`; supply real checked content):

```json
{
  "id": "case_001", "family": "family_001", "domain": "engineering domain",
  "question": "Bounded decision question",
  "evidence": [{"id": "E1", "text": "Record and scope"}, {"id": "E2", "text": "Second record"}],
  "options": [{"id": "a", "text": "Option a"}, {"id": "b", "text": "Option b"}],
  "reference": {"correct_option_id": "a", "rationale": "Ex-ante reasons"},
  "review": {"initial_reviewers": ["R1", "R2"], "adjudicator": "R3", "approved": true},
  "assistance": {
    "conventional_ai": {
      "fluent": {"text": "Checked wording", "recommendation_id": "a"},
      "plain": {"text": "Equivalent plainer wording", "recommendation_id": "a"}},
    "prose_challenge": {
      "fluent": {"text": "Matched prose challenge", "recommendation_id": "a"},
      "plain": {"text": "Equivalent plainer challenge", "recommendation_id": "a"}},
    "eal_structure": {
      "fluent": {"text": "Checked EAL/2 argument", "recommendation_id": "a"},
      "plain": {"text": "Same argument with plainer frame", "recommendation_id": "a"}},
    "eal_agent": {
      "fluent": {"text": "Checked EAL/2 and agent critique", "recommendation_id": "a"},
      "plain": {"text": "Equivalent plainer agent critique", "recommendation_id": "a"}},
    "evidence_only": {
      "fluent": {"text": "Checked record summary", "recommendation_id": null},
      "plain": {"text": "Equivalent record summary", "recommendation_id": null}},
    "no_assistance": {
      "fluent": {"text": "", "recommendation_id": null},
      "plain": {"text": "", "recommendation_id": null}}
  }
}
```

The top-level object is `{"schema": "eal2-human-decision-manifest/1", "cases": [...]}`.
Some conventional advice must be correct and some incorrect. Reviewer IDs and
`approved: true` are assertions supplied by the study team; the script does
not verify review quality or approval. An external record must establish
that fluent and plain packets preserve factual content and recommendation.

Use paths outside the repository for allocation, packets and responses:

```sh
python -m unittest discover -s benchmarks/experiments/bias-human-trial -p 'test_*.py' -v
python benchmarks/experiments/bias-human-trial/trial.py freeze /protected/cases.json /protected/allocation.json --participants 120 --seed 240925
python benchmarks/experiments/bias-human-trial/trial.py pre-packet /protected/cases.json /protected/allocation.json P00001 case_001 /protected/pre-packet.json
python benchmarks/experiments/bias-human-trial/trial.py post-packet /protected/cases.json /protected/allocation.json /protected/pre-response.json /protected/post-packet.json
python benchmarks/experiments/bias-human-trial/trial.py score /protected/cases.json /protected/allocation.json /protected/paired-responses.jsonl /protected/descriptive-report.json
```

The administrator collects a pre response with `phase`, `freeze_sha256`,
`participant_id`, `case_id`, `packet_sha256`, a selected `answer_id`, integer
`confidence` from 0 to 100, a nonempty `reason` and `elapsed_seconds` before
calling `post-packet`. The post response has the same fields bound to the
post packet. `paired-responses.jsonl` contains one `{"pre": {...}, "post": {...}}`
per participant and case. Keep the allocation and raw responses restricted;
the generated report includes pseudonymous IDs and should not be committed.
The displayed 120 participants are a command example, not a justified sample
size. A feasibility study and precision calculation must fix that number
before a confirmatory trial.
