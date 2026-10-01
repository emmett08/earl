# Optional ASPIC+ method

`argumentation/aspic/2` is a bounded, host-installed ASPIC+ instantiation. It constructs arguments from an explicit finite theory, derives undermining, rebutting and undercutting defeats, and computes grounded, preferred or stable extensions with a separate credulous or sceptical conclusion query. The separate, opt-in `EAL/3-compiled-aspic/5` operation translates authored EAL routes at a checked observation snapshot. EAL/3 admits reviewed `strict`, `rank`, `contrary` and `prefer` relations with targets resolved through its own declaration namespace. The default authored evaluator validates these directives without applying their inference effects. The [ASPIC+ tutorial](sources.md#argument-and-reasoning-models) supplies the framework's argument, attack and defeat definitions; the restrictions and ranking below are this implementation's choices.

The Python package is 3.2.1. The compiled profile is `/5`, while the installed ASPIC method is `argumentation/aspic/2` with implementation `eal-aspic-finite-5`. Stored observations retain acquisition identities and original measurement times; returned records contain output digests and byte counts without raw process streams.

## Run the synthetic engineering case

From the repository root after `pip install -e '.[dev]'`:

```sh
python examples/api-load-test/aspic_demo.py
```

This optional companion to the [API load-test case](../examples/api-load-test/README.md) has one primary latency finding, a synthetic diagnostic showing a gap in its trace and an independent synthetic probe of the same run. A strict rule takes the diagnostic to `~applicable_pass` and undercuts the defeasible primary route to `run_passes`. A separate defeasible probe route remains accepted. The script runs collection, reasoning and explanation through a real MCP subprocess. It prints `formal_status: accepted`, `defeat_kinds: ["undercut"]`, `claim_status: supported` and `mcp_claim_status: supported`. These are fixture-relative results, not measurements of a deployed service. Remove the independent probe premise and rule, then review and update both the EAL query and collector fixture: the primary route is defeated and the goal becomes `rejected`.

The exact theory appears in [aspic-source.eal](../examples/api-load-test/aspic-source.eal) as the typed proposition's `query`, and in the pinned [synthetic fixture](../examples/api-load-test/aspic-fixture.json) as the observation's `payload.theory`. An altered premise, rule, contrary, rank or goal fails the EAL query binding before the method runs. The observation also binds subject, unit `1`, run scope, validity interval, tool request, environment and age. The host installs the method with `--methods eal.aspic:aspic_registry`; `eal_describe` advertises its schemas and implementation identity. For CLI use:

```sh
eal --workspace . --registry examples/api-load-test/aspic-tools.toml \
  --methods eal.aspic:aspic_registry validate examples/api-load-test/aspic-source.eal
```

The [demo script](../examples/api-load-test/aspic_demo.py) supplies the remaining collection, reason, explain and MCP calls without leaving a database behind.

## Compile authored EAL routes

The [compiled companion source](../examples/api-load-test/aspic-compiled.eal) contains ordinary EAL evidence, claims, arguments and an objection. An engineer need not duplicate a JSON theory in a typed proposition to try the compiled profile. `compile-aspic` uses a previously collected, source- and context-matched observation set; it performs EAL validation and local method/evidence checks, constructs a finite theory, runs the bounded ASPIC method and returns both the formal result and a source map. The ordinary `reason` result remains a separate assessment of the authored EAL graph. Compilation neither collects observations nor persists a new assessment.

```sh
eal --workspace . --registry examples/api-load-test/aspic-tools.toml \
  collect examples/api-load-test/aspic-compiled.eal \
  --context '{"service":"orders-api","build_id":"demo-build-42","dataset":"synthetic"}'
# Copy collection_id from the collection result.
eal --workspace . --registry examples/api-load-test/aspic-tools.toml \
  compile-aspic examples/api-load-test/aspic-compiled.eal \
  --context '{"service":"orders-api","build_id":"demo-build-42","dataset":"synthetic"}' \
  --collection COLLECTION_ID --goal run_passes --now 2026-09-25T10:00:30Z
```

The MCP equivalent is `eal_compile_aspic` with `source`, `context`, `collection_id`, `goal` and optional `now`, `semantics`, `query_mode`, `preference`. The response includes `profile`, the generated `theory`, `formal` solver result, EAL `routes`, `source_map`, `claim_status`, `authored_claim_status`, `source_digest` and `snapshot_digest`. `source_map` links each generated premise, rule and contrary to its EAL declaration and source span. Available evidence includes its recorded observation identity; every present record, including an unusable one, has a digest. An absent or stale observation supplies no formal premise. The snapshot digest binds the collected record digests, checked EAL assessment, emitted theory, backend contract and solver module. The `routes` field reports the grounded formal label of each authored argument rule; `authored_claim_status` is the independent ordinary EAL result. A difference between the two statuses requires inspection of the mapped routes and their contracts. `CompiledTheory` checks its complete captured theory, assessment and source-map identities before solving and returns detached exported dictionaries; mutating its nested state invalidates the snapshot instead of acquiring the original provenance.

### Export a graph for the visualisation app

Save the complete `compile-aspic` JSON result, then export the versioned graph:

```sh
eal --workspace . export-aspic compiled-result.json --output compiled-arguments.json
```

Alternatively, the synthetic demonstration writes an export with `python examples/api-load-test/aspic_compiled_demo.py --export-view /tmp/compiled-arguments.json`. Open the JSON locally in the [Vue and TypeScript visualisation app](https://github.com/emmett08/aspic_visualisation). Its single graph shows derivation edges and defeat witnesses together; selections expose the attacked subargument, authored claim, inference rationale, declaration span, observation identity and review references. Unavailable evidence retains its reasons and supplies no premise. The app imports JSON locally and performs no collection or solver execution.

The Python exporter owns the [`aspic-view/3` contract](aspic-view.schema.json). It recomputes the supplied theory through the same isolated, resource-bounded `ASPIC_CONTRACT` used by the compiler and requires exact equality with the supplied formal result, including constructed arguments, ranks, labels and every defeat witness. An explicit-theory JSON object containing `theory` and `formal` can use the same exporter. Incorrect labels, omitted defeats and results from an incompatible implementation fail closed. Evidence evaluation supplies typed `availability_issues`: `predicate_not_met` identifies a comparable observation that fails a declaration's condition; `missing_observation`, `stale_observation`, `tool_error`, `invalid_observation` and `out_of_scope` identify distinct limitations. Several issues may apply to one record. An older compiled result without these typed issues is marked `unclassified_legacy` on export; its diagnostic text is never used to guess a category. These issue categories are supplied source metadata, not browser-verified facts.

Source maps receive structural and theory-correspondence checks; they remain supplied metadata. The export explicitly records `validation: {"formal_result": "recomputed", "provenance": "supplied"}`. This does not authenticate authored prose, observation identities or review references. A browser importing an arbitrary JSON file cannot independently authenticate even the exporter's validation assertion. `theory_digest`, optional source and snapshot digests, and optional `evaluated_at` identify the supplied assessment; they do not turn UI interactions into new assessments. Authored EAL status and formal status remain separately named. The command accepts at most 4 MiB of JSON and confines input and output paths to `--workspace`.

| EAL/3 input at the checked snapshot | Compiled ASPIC+ representation |
|---|---|
| Available evidence | Distinct ordinary premise with its recorded identity in `source_map` |
| Locally usable argument | Defeasible rule from its evidence, backing, assumption and claim dependencies to its conclusion; an explicit reviewed `strict` directive changes that route to a strict rule |
| Applicable assumption | Defeasible rule from its validation observation to an assumption atom |
| Eligible objection | Defeasible objection rule whose conclusion undercuts the targeted argument, assumption or objection rule; a claim or reasoning target expands to matching routes |
| Reviewed `rank` and directed `contrary` | Integer rank on a fallible premise or rule, and a directed formal attack relation between two claims; source map retains the review reference and directive span |
| Authored relation with no antecedent | Marked structural axiom used solely to satisfy the finite rule profile; it is not a measurement |

Unannotated ordinary premises and defeasible rules have rank 500. The compiler infers no strict inference, logical contradiction, preference, negation or validity of prose. Directed undercuts come only from EAL objection targets. A negative diagnostic needs its own declared evidence whose `require` predicate admits that finding, as `gap_found == true` does in the example; a failed or absent observation does not become a contrary. Compilation rejects an invalid EAL programme, an unknown goal, a source already using `argumentation/aspic/2`, an objection that would undercut a strict route, or a theory outside the finite solver profile; the host operation also rejects a source/collection/context mismatch. The authored EAL evaluator stays the default. Promoting this profile would require a concrete inference case EAL cannot express, differential review of disputed outcomes, and measured latency and memory cost on representative engineering tasks; the synthetic fixture does not establish those conditions.

### Argumentation directives in EAL/3

The `strict`, `rank` and `contrary` directives are declarations in the same EAL/3 language as claims, evidence and arguments. Place them among those declarations. Names resolve after pattern applications expand, so a generated route can be named. For example, with two claims `run_passes` and `run_fails` in the same environment and authored routes `probe_route` and `failure_route`:

```eal
strict report_arg reviewed "review/report-implication";
rank probe_record 700 reviewed "review/probe-observation";
rank probe_route 800 reviewed "review/probe-inference";
rank failure_route 400 reviewed "review/diagnostic-limit";
contrary run_fails to run_passes reviewed "review/incompatible-outcomes";
contrary run_passes to run_fails reviewed "review/incompatible-outcomes";
```

EAL's unique names determine each target kind. `strict` requires an argument, including a named `apply` result. `rank` accepts evidence, assumptions and arguments and requires an integer 0–1000; it is an ordinal defeat preference, not a probability. Strict arguments cannot have ranks. Objection ranks are rejected because compiled objections only undercut applicability, which ignores preference. `contrary` requires two claims in one environment. One direction expresses a one-way attack; both directions make the claim pair contradictory, so the solver compares attacker and attacked subargument strengths. The solver uses the minimum rank of each argument's fallible elements, and undercuts defeat regardless of rank. The `reviewed` string is a required human supplied review reference, **not** proof that a claim follows deductively, that two English sentences are logical contraries, or that evidence is authentic. The validator reports unknown, ambiguous and wrong-kind names at the relation's source span, and rejects duplicate relations and self-contraries. If an objection addresses an argument, claim or reasoning declaration whose expansion includes a strict route, compilation rejects the mapping because a strict rule has no undercuttable name. A strict route can still lose through a defeated fallible subargument. Default `reason` validates these directives without applying their inference effects and may disagree with the compiled profile; both statuses remain separately reported.

### Coverage boundary

The compiler lowers named patterns and applications, scopes evidence to the checked collection, uses EAL's local method and proposition checks as gates, expands alternative and nested claim routes into formal subarguments, and translates assumption validation and objections against claims, reasoning, arguments, assumptions or other objections. It preserves directed attack cycles for grounded evaluation and exposes original declarations, spans, review references and observation identities in the source map. The compiler lowers scoped modules/imports, block arguments, compound patterns and finite list recursion into typed EAL records, then preserves their generated names and source origins. Its ordinary EAL premise graph remains acyclic. Explicit formal theories may have cyclic atom dependencies under the finite construction policy below. This does not prove prose equivalence, directive soundness or the physical justification of a reviewed scope transfer. Conditional transfer metadata remains inspectable, including `transport_justification_verified: false`.

## Formal contract

The designated evidence kind is `aspic_theory`. Its value is an `EAL/typed-input/1` envelope with `method: "argumentation/aspic/2"`, `quantity: "proposition"`, `unit: "1"`, and `payload: {"theory": ...}`. The complete `theory` is the one required formal query field. A typed claim can use `result "grounded_accepted" == true`; an untyped claim needs an explicit `reasoning require` but lacks the exact theory-to-proposition binding used in the reviewed example.

| Theory member | Meaning |
|---|---|
| `premises` | Distinct `atom` values, each `kind: "axiom"` or `kind: "ordinary"`. An ordinary premise requires integer `rank` 0–1000; axioms have no rank and cannot be undermined. |
| `rules` | Unique `id`, One or more `antecedents` within the host budget and `consequent`. A `strict` rule has no rank; a `defeasible` rule requires a unique applicability atom `name` and rank 0–1000. Rules only build arguments when their antecedents have arguments. |
| `contraries` | Explicit directed `{"attacker": atom, "target": atom}` pairs. Negation spelling such as `~ready` has no implicit meaning: include the relevant pair. A single direction is a contrary; reciprocal pairs express a contradiction for preference comparison. |
| `goal` | Atom queried under the selected extension semantics; it does not have to be derivable. |

Premise and rule ranks share one global ordinal scale. An argument's strength is the minimum rank of its ordinary premises and defeasible rules, or 1001 if it uses only axioms and strict rules. A conclusion attacks an ordinary premise with a declared contrary (undermining), a defeasible subargument's conclusion (rebutting), or its applicability name (undercutting). A one-way contrary and an undercut defeat regardless of rank. With reciprocal contraries, an underminer or rebutter defeats the whole target argument when its strength is at least that of the **attacked subargument**. Strict conclusions and axioms cannot be directly attacked, though a strict superargument can be defeated through one of its fallible subarguments.

Acyclic theories construct every supported antecedent combination in topological order. Cyclic theories construct finite premise-founded arguments without repeating a conclusion along any branch. An unfounded cycle builds no arguments. This explicit finite profile omits repeated-conclusion cyclic derivations; it is not unrestricted infinite ASPIC+ enumeration. Distinct named rules and shared evidence retain their identities.

Optional theory fields are:

```json
{
  "options": {"semantics": "preferred", "query_mode": "sceptical", "preference": "last_link_partial"},
  "priorities": [{"kind": "rule", "higher": "d2", "lower": "d1"}]
}
```

Defaults are `grounded`, `sceptical` and `minimum_rank`. `last_link_rank` compares the minimum numerical rank of last defeasible rules; when both last-rule sets are empty it compares ordinary premises. `last_link_partial` uses a reviewed, acyclic strict partial order and strict elitist set lifting over those same sets. Empty sets are strongest; tied or incomparable sets do not suppress reciprocal-contrary attacks. Priorities compare premises with premises or defeasible rules with rules. Directed contraries and undercuts remain preference-independent. `strength` always records the minimum numerical fallible rank for inspection, even when another preference policy is selected; it is not then the active comparison algorithm. These specified policies do not claim every ASPIC+ rationality condition.

Grounded graph labels and `grounded_status` remain available. `extensions` contains all selected extensions found by exact bounded enumeration: the single grounded extension, maximal admissible preferred extensions, or stable extensions that attack every outside argument. `query_status` is conclusion-level: credulous acceptance requires some extension containing a goal argument; sceptical acceptance requires every extension containing some goal argument, possibly different derivations. `query_rejected` requires every goal argument to be attacked in every extension; otherwise a constructed unaccepted goal is undecided. A goal with no argument is `unconstructed`. An empty stable family is `no_extension`, never vacuous sceptical acceptance. Use typed Boolean outputs `query_accepted` or `query_rejected` for a selected-semantic proposition; `grounded_accepted` and `grounded_rejected` remain explicitly grounded queries.

Default host budgets are 64 premises/rules, eight antecedents, 128 atoms/contraries/arguments and 4,096 defeat witnesses. `ExecutionLimits` and `[limits]` TOML allow operator configuration. `formal_construction` bounds argument-combination work; `extension_search` bounds enumeration and maximality comparisons. Exhaustion or extension timeout returns `incomplete` with empty details, never a partial accepted result. The method worker separately has a five-second deadline, 256 KiB input and 1 MiB output. Duplicate identities, cyclic priorities, contradictory strict/axiom closure and any accepted contrary pair invalidate a computation. These are profile constraints, not physical conclusions; the solver does not parse prose, implement arbitrary first-order reasoning or prove an authored strict rule's external deductive validity.

CLI compilation accepts `--semantics`, `--query-mode` and `--preference`; the MCP operation accepts the corresponding fields. Source `prefer A over B reviewed "REF"` selects partial last-link preference by default and forbids a conflicting numerical preference override. Both targets must be fallible references of the same formal domain. The compiler emits only priorities whose elements are present at the checked observation snapshot, and retains every source directive in review metadata.

`aspic-view/3` contains selected semantics, query mode/status, preference policy, extensions and captured execution limits, plus the complete reviewed `formal_directives` list, grounded graph, typed evidence-availability causes, generated source names, source-file origins and conditional transfer metadata. The exporter recomputes the formal result under its captured budgets before emitting it. The browser checks supplied extension admissibility/stability and query consistency against the graph; it does not authenticate source provenance or independently prove preferred-family completeness.

The regression suite checks hand-worked undermining, rebutting, undercutting, preferences, cycles, alternatives, binding and MCP behaviour. Optional differential tests use PyArg 2.0.2: `pip install -e '.[dev,aspic-reference]' && python -m pytest tests/test_aspic_pyarg.py`. They compare constructed arguments, defeat edges and grounded labels across a finite equal-rank fragment covering each attack kind, alternatives, strict downstream rules and shared diamond derivations, plus a one-way contrary with unequal ranks. The oracle follows direct subarguments rather than guessing immediate children from the transitive closure. PyArg coalesces separately named rules with identical antecedents and consequent, while this method retains their identities; its set-based preference options also differ from this method's minimum-rank ordering. PyArg is therefore an independent reference for the tested overlap, not a drop-in implementation of this versioned EAL contract or evidence boundary.

## Evidence and scope

EAL assesses observation identity, selected collector, environment, age and typed input correspondence before consuming the formal theory. The solver then settles only what follows within that supplied theory. A supported EAL claim remains conditional on the theory's relevance and on the trustworthiness of the observations.

The solver does not infer that an EAL claim's English statement actually means its formal atom. The strict/defeasible classification, contrary pairs, rank choices and intended scope must be examined for the intended question. An accepted formal atom describes the declared theory under the supplied observations; it cannot establish physical provenance or the validity of an omitted empirical premise.
