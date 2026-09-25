# Project instructions

EAL/2 is the only supported language. Backwards compatibility is never a requirement for this project. Choose the clearest coherent design for the current language; remove obsolete syntax, version-dependent semantics, aliases and compatibility adapters rather than preserving them. Do not add migration machinery solely to support an earlier EAL version.

Apply each change across the nine current documents, discovery schemas, the workflow example and runnable study plans. Earlier study artefacts were removed in the September 2026 reset and remain accessible in Git history. New frozen inputs and results must retain their original bytes, versions and failed outcomes in a versioned study directory. A source-language version, package version and observation schema version identify different contracts; declare changes to each affected contract explicitly.

Use the repository's `skills/engineer-argumentation-languages/SKILL.md` and its expert language design reference for changes to syntax, abstractions, method contracts or reasoning semantics. Separate primary-source recommendations, EAL design decisions, implemented behaviour and measured results.

Keep one versioned reasoning-method selector: `method "name/version"`. Tool `mode` describes collection variability and has a separate meaning. Built-in and installed reasoning methods follow the same typed contracts and binding checks.

Reusable argument patterns use typed parameters with closed lexical scope. Expansion must preserve evidence, claim and assumption identity and the qualifications of an ordinary argument. Retain source locations in diagnostics and canonical parse–format–parse meaning.

Do not reinterpret earlier EAL trials as EAL/2 model capability, comprehension gains or cost savings. New measurements require actual trials and retained outcomes, including failures.
