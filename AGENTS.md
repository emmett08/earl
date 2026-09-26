# Project instructions

EAL/2 is the only supported language. Backwards compatibility is never a requirement for this project. Choose the clearest coherent design for the current language; remove obsolete syntax, version-dependent semantics, aliases and compatibility adapters rather than preserving them. Do not add migration machinery solely to support an earlier EAL version.

Apply each change across affected current documentation, discovery schemas and the single API load-test example. Earlier examples and benchmark plans remain accessible in Git history. Keep the maintained example self-contained and clearly distinguish synthetic data from measurements. The single experiment in `experiments/api_load_test/` extends that task: JSON and prose use direct collection, never MCP or EAL evaluation. Preserve its frozen assignment ledger, independent reference and Docker execution path. A source-language version, package version and observation schema version identify different contracts; declare changes to each affected contract explicitly.

Use the repository's `skills/engineer-argumentation-languages/SKILL.md` and its expert language design reference for changes to syntax, abstractions, method contracts or reasoning semantics. Separate primary-source recommendations, EAL design decisions, implemented behaviour and measured results.

Keep one versioned reasoning-method selector: `method "name/version"`. A tool declaration names an interface version; its operational characteristics belong to the trusted host binding and the recorded acquisition, not an EAL `mode` clause. Built-in and installed reasoning methods follow the same typed contracts and binding checks.

Reusable argument patterns use typed parameters with closed lexical scope. Expansion must preserve evidence, claim and assumption identity and the qualifications of an ordinary argument. Retain source locations in diagnostics and canonical parse–format–parse meaning.

Do not reinterpret earlier EAL trials as EAL/2 model capability, comprehension gains or cost savings. New measurements require actual trials and retained outcomes, including failures.
