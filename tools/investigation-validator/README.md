# Pinned scientific investigation validator

These files are a repository-local snapshot of the
`design-scientific-investigations` validator supporting protocol schemas
1.0, 1.1 and 1.2. `provenance.json` identifies its source, retrieval date and
SHA-256 digest of each unmodified upstream file. The regression suite checks
those digests. Updating the validator is an explicit reviewed source change.

Run `make scientific` from the repository root. It runs the validator self-test
and validates both maintained investigation protocols. `make check` includes
this gate, and the manual GitHub workflow runs `make check` before experiments.
No installed personal skill or external mutable validator path is required.

A valid specified protocol establishes structural and semantic consistency with
the declared schema. It does not establish empirical results or statistical
adequacy of an unexecuted investigation.
