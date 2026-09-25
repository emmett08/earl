# Claim and evidence review

Review scope: the manuscript and its three figures. Source snapshot: `8220e838a8d42922edc0496ff50927c672a1f87d`; historical experiment: `3490076dd78404caa1326d9aae704f964910c4c8`. This is a bounded author-review record, not independent publication assurance.

The root claim is that EAL/2 implements inspectable evidence binding and defeasible assessment, and that the historical pilot exposes useful system and interface behaviour on its recorded cases. The claim does not require a universal notation advantage. A simpler checker, a better status schema or clearer instructions could account for much of the observed difference; the pilot does not isolate those alternatives.

| Manuscript claim | Grounds and reproducible locator | Inference and limit |
| --- | --- | --- |
| Typed correspondence checks subject, quantity, scope, interval, units and query | `docs/language.md`, `docs/argument-model.md`, `tests/test_typed_propositions.py`, `tests/test_binding_contract_review.py` | Checks operate on the represented fields. They do not establish truthful metadata or verify prose. |
| Versioned methods implement bounded computations | `docs/reasoning-modes.md`, `tests/test_modes.py`, `tests/test_reasoning_contract_review.py`, `tests/test_method_extensions.py` | A schema-conformant input still requires justified engineering assumptions. |
| Composed acceptance rules settle information monotonically | `docs/grounded-reasoning.md`, `docs/argument-model.md`, `tests/test_composed_dialectic.py` | Termination argument applies to finite label propagation after local checks. No new theorem about external collector termination is claimed. |
| Exhaustive finite comparisons and 846 tests pass | `tests/test_dialectic.py`, `tests/test_composed_dialectic.py`, `review/validation.txt` | The finite oracle comparisons and integration suite check implemented cases; they are not universal formal verification. |
| Worked API report is supported at inclusive thresholds | `examples/api-load-test/`, `tests/test_load_test_example.py` | Synthetic finite report, not an estimate of production service reliability. The listing is an exact excerpt of the tested source. |
| Archive identity matches the supplied experiment | `data/provenance.json`, exact digest comparison with GitHub artefact metadata | Content identity establishes integrity of the supplied bytes, not independence of study design. |
| 1,200 assigned; 628 complete, 131 failed, 441 unattempted | `analysis/reproduce.py`, `results/reproduction.json`, `data/historical-manifest.json` | Preserve every assigned attempt. Unattempted assignments yield zero successes but do not reveal hypothetical model answers. |
| Per-condition correctness and paired differences | `results/summary.json`, generated TeX tables, Figure 3 | Finite descriptive contrast, with case pairing and completion exposure; no population effect or equivalence conclusion. |
| Full GPT-4.1 JSON errors concern failed-check enumeration | `results/error-components.json`; assertions in `analysis/check_paper.py` | Status, scope, selection and metrics were correct. The composite score difference is narrower than a status-accuracy difference. |
| Mini GPT-4.1 EAL errors include seven statuses and one scope | `results/error-components.json`, trial answers and outcomes | Accurate host checks can coexist with incorrect final communication. Causation by a particular prompt feature remains untested. |
| 141 host comparison flags are true | Curated trial `host_checks`; generated error-components report | Flags are replayed as archived, not reconstructed by rerunning the old host. Full receipts remain in the original archive. |
| Frozen-rate cost totals USD 3.97892431 over 2,342 calls | Decimal recomputation in `analysis/reproduce.py`, retained token counts and manifest rates | Recorded accounting, not current prices or cost at equal successful completion. |

Argument review retained the main counterevidence: JSON/full status equivalence on these cases, mini's incorrect status communication, missing GPT-5.4 exposure, purposive dependent families, supplied rather than authored EAL, unequal checker access and exact-set rubric sensitivity. These conditions appear next to the relevant results as well as in the threats section.

All empirical figures and numerical tables are derived from the preserved historical scorer. Figures 1 and 2 are explicitly constructed explanatory figures. No synthetic observation is presented as a pilot measurement. No new experimental result is attributed to package 2.5.0.
