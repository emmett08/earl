# Execution note — 24 September 2026

Version 0.1.0 is an implemented developmental plan, not a completed model
experiment. The current EAL/2 parser and semantic validator accepted all 48
authored sources. The typed JSON graph is generated from each source and
compared with a fresh parse; it is a matched declaration rendering with
different field names and length. Five offline tests passed, including a
mocked provider run, hash-chain analysis, tamper rejection and pending-call
protection. These fixtures are exposed from Stage A.

The unauthenticated four-second endpoint preflight to
`https://api.openai.com/v1/models` returned `<urlopen error timed out>` on
24 September 2026. The executor performs this probe before reading
`OPENAI_API_KEY`; changing credentials cannot affect this particular failure.
No request was sent to the Responses API, no outcome or pending ledger was
created, no provider charge occurred and there is no ranking of models,
representations or topologies. An offline analysis of each frozen schedule
reports `unrun` and zero terminal calls.

The archived pilot and full schedules contain 128 and 768 assigned calls,
respectively. The 128 pilot request hashes match their full-schedule slots.
The configured conservative maximum reserves are US$2.0363 and US$12.3126;
these are planned upper bounds under the configured rates, not observed
charges. Do not run the full schedule until a valid terminal pilot ledger
exists. A possibly sent request must be reconciled, not retried automatically.
