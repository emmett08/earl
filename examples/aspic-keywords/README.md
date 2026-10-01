# ASPIC+ vocabulary and defeat example

This self-contained synthetic controller example exercises every ASPIC+ directive in the EAL/3 grammar and every field and option of the implemented finite ASPIC+ theory contract. The findings are stipulated fixture values. They describe no measured controller or deployment.

Two views of the same readiness question show the boundary between authored EAL routes and an explicit formal theory:

| Source | Execution | Purpose |
|---|---|---|
| [source.eal](source.eal) | The EAL compiler builds the theory from checked observations, an assumption, named arguments, a pattern application and an objection. | Inspect reviewed source directives, observation identity, source spans and the two alternative readiness routes. |
| [formal.eal](formal.eal) | A typed proposition binds the exact theory in [fixture.json](fixture.json) to an observation and `argumentation/aspic/2`. | Inspect axioms, ordinary premises, all three attack kinds, explicit negative literals and two preferred extensions. |

The two theories intentionally have different detail. The compiler represents collected evidence as ordinary premises and compiles an authored objection as an undercut. The explicit theory also represents an audit that undermines the primary ordinary premise and a tied pair of competing estimates. Neither a contrary relation nor an axiom is inferred from the wording of a claim.

## Run and import

From the repository root:

```sh
python -m pip install -e '.[dev]'
python examples/aspic-keywords/demo.py --mcp
python -m pytest -q tests/test_aspic_keywords_example.py
```

The script checks parse–format–parse equivalence and canonical formatting, collects the pinned fixture through its real host binding, compiles the authored EAL programme, evaluates the typed formal method, and asks the exporter to recompute each result. `--mcp` additionally runs a real stdio MCP client/server session for validation, collection, compilation, reasoning and explanation. Temporary databases are removed when execution completes.

Import either of these files with **Import snapshot** in the [ASPIC+ visualisation application](https://github.com/emmett08/aspic_visualisation):

| Browser import | Expected graph |
|---|---|
| [output/compiled-view.json](output/compiled-view.json) | 15 arguments, 6 defeat witnesses, all four reviewed directive kinds; `reportable` accepted under preferred, sceptical, partial last-link settings. |
| [output/formal-view.json](output/formal-view.json) | 15 arguments, 10 defeat witnesses: undermining, rebutting and undercutting; `ready` accepted; two preferred extensions. |

The checked-in imports are review snapshots. Running the script regenerates them and [output/summary.json](output/summary.json); observation identities and the compiled snapshot digest may change with a new collection. Large raw compiler and method results are also generated in `output/` and remain untracked. Use `--output /tmp/aspic-keywords-review` to inspect a fresh execution without rewriting the checked-in snapshots.

To enter the explicit theory in the application's text editor, use the atoms, ranks, rules, contraries, options and priorities in `fixture.json`. Preserve the applicability names: the primary rule's name is `use_primary`, so its editor spelling is `primary_ready [use_primary]: criterion_defined, primary_ok => ready @ 700`. The undercutter concludes `~use_primary` and needs the declared contrary pair targeting `use_primary`.

## EAL keyword coverage

ASPIC+ does not prescribe EAL keywords. In the current EAL/3 grammar its dedicated declarations are the following four directives; `reviewed`, `to` and `over` are parts of their syntax.

| Keyword or syntax | Occurrence and effect |
|---|---|
| `strict NAME reviewed "REFERENCE"` | `definition_route` projects the fixture's criterion field; `reporting_route` lifts an accepted readiness subargument to `reportable`. These routes have no defeasible applicability name. |
| `rank NAME NUMBER reviewed "REFERENCE"` | Evidence, arguments and the `calibration` assumption all carry reviewed integer ranks. Ranks remain visible when partial last-link priorities determine defeat. |
| `contrary A to B reviewed "REFERENCE"` | `ready` and `not_ready` have reciprocal directions; `caution` attacks `not_ready` in one direction. |
| `prefer A over B reviewed "REFERENCE"` | Rule priorities order probe above fault above primary; a premise priority orders the probe observation above the primary observation. |
| `evidence`, `assumptions`, `premises`, `via`, `=>` | `primary_route` combines all three support categories; `reporting_route` supplies a strict superargument with a fallible subargument. |
| `objection ... -x> argument` | `primary_trace_gap` undercuts only `primary_route`, leaving the independently supported probe route available. |
| `method "argumentation/aspic/2"`, `proposition`, `query`, `result`, `binding` | `formal.eal` binds the exact input theory, subject, scope, unit and validity interval; its claim tests `query_accepted == true`. |
| `pattern`, `apply` | `probe_route` is an expanded named application; its generated rule retains the authored origin. |

Every `reviewed` reference is a labelled synthetic review reference. A reference's presence cannot establish the deductive validity of its authored rule or the truth of its fixture values.

## Formal method vocabulary

The following names are typed JSON fields or enum values, rather than additional EAL grammar keywords. Attack kinds are derived from the theory's arguments and explicit contraries.

| Field or value | Demonstration |
|---|---|
| `premises`, `atom`, `kind: "axiom"` | `criterion_defined` is a stipulated axiom with strength 1001 and no premise rank. It cannot be undermined. |
| `kind: "ordinary"`, `rank` | Primary, probe, audit, trace gap, fault and the two estimates are fallible ordinary premises. |
| `rules`, `id`, `antecedents`, `consequent`, `kind: "strict"` | Audit and gap rules are strict; the strict reporting rule builds one argument for each readiness derivation. |
| `kind: "defeasible"`, `name` | Primary, probe and fault inferences have explicit applicability names and ranks. |
| `contraries`, `attacker`, `target` | One-way relations support the audit underminer and gap undercutter. Reciprocal relations express contradictions between readiness conclusions and between the tied estimates. |
| `~primary_ok`, `~ready`, `~use_primary` | Negative spelling has meaning only through the specified contrary pairs. Removing the audit contrary leaves the primary ordinary premise undefeated. |
| `undermine` | `~primary_ok` attacks the primary premise. The two tied ordinary estimate premises also undermine one another. |
| `rebut` | `ready` and `~ready` attack defeasible conclusions. The probe rule outranks the fault rule in the partial order. |
| `undercut` | `~use_primary` attacks the primary rule's applicability, irrespective of its rank. |
| `goal` | The baseline queries `ready`; option variants also query `estimate_normal` and a goal with no constructed argument. |
| `options`, `semantics` | The script executes `grounded`, `preferred` and `stable`. |
| `query_mode` | Both `credulous` and `sceptical` are executed; the tied estimate distinguishes their results. |
| `preference` | Every supported selector is executed: `minimum_rank`, `last_link_rank`, `last_link_partial`. |
| `priorities`, `kind: "rule"`, `kind: "premise"`, `higher`, `lower` | Explicit partial priorities compare both defeasible rules and ordinary premises. A separate regression orders the tied estimate premises. |

The method exposes these three preference selectors. It uses strict elitist set lifting for `last_link_partial`; independent weakest-link, democratic and other ASPIC+ preference selectors are outside this contract.

## Hand-assessed results

In the explicit theory, the accepted audit undermines `primary_ok`, and the trace gap independently undercuts the primary readiness inference. Both attacks also defeat the strict reporting superargument built on that primary route. The independently supported probe readiness argument is accepted and defeats the lower-priority fault argument. Its reporting superargument is accepted. The resulting grounded labels are nine `in`, four `out` and two `undecided`.

The two undecided arguments conclude `estimate_normal` and `estimate_abnormal`. Each preferred or stable extension contains exactly one of this pair and the same nine grounded `in` arguments. Every extension contains the probe readiness argument, so `ready` remains sceptically accepted even though the estimates remain contested.

| Query and variation | Expected result |
|---|---|
| `ready`, any of the 18 semantics/query-mode/preference combinations | `accepted` |
| `estimate_normal`, grounded, either query mode | `undecided` |
| `estimate_normal`, preferred or stable, credulous | `accepted` |
| `estimate_normal`, preferred or stable, sceptical | `undecided` |
| Readiness with the probe, audit and gap removed; minimum rank | `rejected`: the primary argument's minimum rank is 400, below the fault argument's 600. |
| The same isolated reciprocal conflict; numerical last link | `accepted`: the primary rule's 700 exceeds the fault rule's 600. |
| The same isolated conflict; partial last link, fault preferred to primary | `rejected` |
| The same isolated conflict; partial last link, incomparable rules | `undecided` |
| A queried goal with no supporting premise or rule | `unconstructed` |
| The estimates changed to a directed three-cycle, stable semantics | `no_extension`; an empty extension family supplies no vacuous acceptance. |
| Compiler snapshot with the probe observation omitted | `reportable` is `rejected`; the export records `missing_observation`. |
| Compiler snapshot after calibration expires while observations remain fresh | The primary route is unconstructed; the probe and `reportable` remain accepted. |

The regression tests also reject a collection used with a different context and an export whose formal labels were edited after solving. Default authored EAL reasoning and compiled ASPIC+ reasoning remain separate results: in particular, authored EAL reasoning can support both readiness claims because the reviewed formal contraries and preferences apply only during ASPIC+ compilation.

This is coverage of the implemented bounded contract. It verifies the supplied finite argument theory and executable bindings; it establishes no physical controller behaviour, first-order ASPIC+ completeness, authentication of review references, or independent proof of preferred-family completeness by a JSON-importing browser. The exporter recomputes the formal result and marks provenance as supplied.
