# Optional ASPIC+ method

`argumentation/aspic/1` is a bounded, host-installed ASPIC+ instantiation. It constructs arguments from an explicit finite theory, derives undermining, rebutting and undercutting defeats, and computes the grounded extension of that defeat graph. It uses the existing EAL/2 grammar and `EAL/typed-input/1` envelope; installing it does not change default methods or the authored EAL objection calculus. The [ASPIC+ tutorial](sources.md#argument-and-reasoning-models) supplies the framework's argument, attack and defeat definitions; the restrictions and ranking below are this implementation's choices.

## Run the synthetic engineering case

From the repository root after `pip install -e '.[dev]'`:

```sh
python examples/api-load-test/aspic_demo.py
```

This optional companion to the [API load-test case](../examples/api-load-test/README.md) has one primary latency finding, a synthetic diagnostic showing a gap in its trace and an independent synthetic probe of the same run. A strict rule takes the diagnostic to `~applicable_pass` and undercuts the defeasible primary route to `run_passes`. A separate defeasible probe route remains accepted. The script runs collection, reasoning, explanation through a real MCP subprocess and a reviewed adequacy check. It prints `formal_status: accepted`, `defeat_kinds: ["undercut"]`, `claim_status: supported`, `adequacy: adequate` and `mcp_claim_status: supported`. These are fixture-relative results, not measurements of a deployed service. Remove the independent probe premise and rule, then review and update both the EAL query and collector fixture: the primary route is defeated and the goal becomes `rejected`.

The exact theory appears in [aspic-source.eal](../examples/api-load-test/aspic-source.eal) as the typed proposition's `query`, and in the pinned [synthetic fixture](../examples/api-load-test/aspic-fixture.json) as the observation's `payload.theory`. An altered premise, rule, contrary, rank or goal fails the EAL query binding before the method runs. The observation also binds subject, unit `1`, run scope, validity interval, tool request, environment and age. The host installs the method with `--methods eal.aspic:aspic_registry`; `eal_describe` advertises its schemas and implementation identity. For CLI use:

```sh
eal --workspace . --registry examples/api-load-test/aspic-tools.toml \
  --methods eal.aspic:aspic_registry validate examples/api-load-test/aspic-source.eal
```

The [demo script](../examples/api-load-test/aspic_demo.py) supplies the remaining collection, reason, explain and MCP calls without leaving a database behind.

## Formal contract

The designated evidence kind is `aspic_theory`. Its value is an `EAL/typed-input/1` envelope with `method: "argumentation/aspic/1"`, `quantity: "proposition"`, `unit: "1"`, and `payload: {"theory": ...}`. The complete `theory` is the one required formal query field. A typed claim can use `result "grounded_accepted" == true`; an untyped claim needs an explicit `reasoning require` but lacks the exact theory-to-proposition binding used in the reviewed example.

| Theory member | Meaning |
|---|---|
| `premises` | Distinct `atom` values, each `kind: "axiom"` or `kind: "ordinary"`. An ordinary premise requires integer `rank` 0–1000; axioms have no rank and cannot be undermined. |
| `rules` | Unique `id`, 1–8 `antecedents` and `consequent`. A `strict` rule has no rank; a `defeasible` rule requires a unique applicability atom `name` and rank 0–1000. Rules only build arguments when their antecedents have arguments. |
| `contraries` | Explicit directed `{"attacker": atom, "target": atom}` pairs. Negation spelling such as `~ready` has no implicit meaning: include the relevant pair. Two pairs express reciprocal contrariness. |
| `goal` | Atom queried under grounded semantics; it does not have to be derivable. |

Premise and rule ranks share one global ordinal scale. An argument's strength is the minimum rank of its ordinary premises and defeasible rules, or 1001 if it uses only axioms and strict rules. A conclusion attacks an ordinary premise with a declared contrary (undermining), a defeasible subargument's conclusion (rebutting), or its applicability name (undercutting). An underminer or rebutter defeats the whole target argument exactly when its strength is at least that of the **attacked subargument**. An undercutter always defeats. Strict conclusions and axioms cannot be directly attacked, though a strict superargument can be defeated through one of its fallible subarguments.

The solver constructs every available combination of antecedent arguments within the stated bounds; identical conclusions can have independent derivations. It labels the resulting defeat graph with the least grounded fixed point. `grounded_status` is `accepted` when any argument concluding `goal` is in, `rejected` when goal arguments exist and all are out, `undecided` when some remain undecided without an accepted route, and `unconstructed` when no goal argument exists. `grounded_accepted` and `grounded_rejected` are separate Boolean query fields. A successful computation with `grounded_accepted: false` is **not** proof of the contrary of the goal. The output also contains argument IDs, conclusions, subargument IDs, strength and labels, defeat witnesses with their attack kinds, edge count and a SHA-256 of the formal theory.

This version admits 1–64 premises, 0–64 rules, 0–128 contrary pairs and at most 128 distinct atoms. A constructed theory is limited to 128 arguments and 4096 defeat witnesses; the method worker has a five-second execution budget, 256 KiB input and 1 MiB output. Duplicate premises or rule names, cyclic atom dependencies and contradictory axiom/strict-only closure make the method unsupported. These are profile restrictions, not conclusions about the physical system. Other ASPIC+ choices, including assumption premises, priorities as partial orders, last-link comparison and preferred or stable extensions, require separate versioned contracts. This method does not parse arbitrary natural-language rules or prove that an authored strict rule is deductively valid in an external logic.

The regression suite checks hand-worked undermining, rebutting, undercutting, preferences, cycles, alternatives, binding and MCP behaviour. An optional differential check uses PyArg 2.0.2 on a shared grounded undercutting fragment: `pip install -e '.[dev,aspic-reference]' && python -m pytest tests/test_aspic_pyarg.py`. It checks the overlapping cases, not equivalence over every admissible theory or ordering.

## Evidence and adequacy

EAL assesses observation identity, selected collector, environment, age and typed input correspondence before consuming the formal theory. The solver then settles only what follows within that supplied theory. A supported EAL claim remains conditional on the theory's relevance and on the trustworthiness of the observations.

The argument host's `eal-adequacy/1` contract admits `argumentation/aspic/1` and requires one `premise_bindings` entry for **each** formal axiom or ordinary premise. Each entry maps `{"argument": "formal_run", "formula": "latency_ok", "claim": "latency_ok"}` to a supported named EAL premise claim of that argument. It also requires a typed bound theory and a main inference or threshold obligation on the method result. An absent, unlisted or unsupported claim makes adequacy unresolved. The demo supplies all four mappings and an obligation that checks `reasoning_result.details.grounded_accepted == true`.

Those checks do not infer that an EAL claim's English statement actually means its formal atom. The mapping and the strict/defeasible classification, contrary pairs, rank choices and intended scope must be reviewed. A reviewer can map an atom to the wrong supported claim; its presence and status alone cannot establish semantic correspondence. The example marks that review assumption through `correspondence: "reviewed_source"`. Its `adequate` result is relative to that declared, synthetic contract. The API load-test experiment has a frozen argument and does not include this optional method; any comparison with another ASPIC+ solver needs a separately specified, paired task and equal evidence access.
