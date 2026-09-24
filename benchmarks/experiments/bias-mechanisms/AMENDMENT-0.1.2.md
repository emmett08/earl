# Pre-call amendment 0.1.2 — current EAL/2 source closure

**Date:** 24 September 2026 UTC. **Status:** fixed before any paid call.
This amends `PROTOCOL.md` version 0.1.0 and `AMENDMENT-0.1.1.md` for the
repository main revision beginning `3b497d`. PR #9 changed the current
`src/eal` implementation after the 0.1.1 zero-call freezes were created.
Their material hashes therefore fail the current runner check. Preserve the
0.1.0 and 0.1.1 frozen schedules and their original bytes as historical
preflight records; neither was used for a provider call.

The 0.1.2 runner pins the current grammar and every Python module under
`src/eal`, alongside the case manifest, runner, analyser, base protocol and
both amendments. It records `protocol_version: "0.1.2"` in each frozen plan
and verifies that version and the full material set before a provider request.
Regenerate the pilot and full schedules under new 0.1.2 archive names. The
source parser and semantic validator must accept all 48 generated EAL/2
arguments at this revision. This check concerns static structure; no EAL host
has acquired the synthetic process records or judged a person's cognition.

The twelve author-created families, four matched classes per family, prompt
content, private gold mapping, response schema, raw primary scorer, requested
models, independent analysis route, seeded order, 72-call operational pilot,
432-call full schedule, 4,096-token output limit, USD 5 pilot cap and USD 25
cumulative cap remain as in amendment 0.1.1. This version change responds to
source-code provenance, not observed model accuracy. It supplies no model or
human outcome; all paid calls remain unrun. The archive manifest and
`RUN_STATUS.md` record exact new plan and compressed-file hashes without
placing those hashes inside this pinned amendment.
