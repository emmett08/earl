# Grounded reasoning over explicit argument graphs

`eal_grounded` determines which arguments can be accepted in a finite, explicitly supplied attack graph. Its argument identifiers and attack relations are inputs. EAL/0.3 also integrates a support-and-attack computation into evaluation through `solve_composed`: argument and objection nodes retain their required premises, and alternative arguments can support the same claim. Neither operation discovers arguments or attacks from prose.

## Meaning

Write an argumentation framework as `(A, R)`, where `A` is a finite set of arguments and `(b, a) ∈ R` means that `b` attacks `a`. A set `S` defends `a` exactly when every attacker of `a` is attacked by some member of `S`. Let `F(S)` contain all arguments defended by `S`. Starting from the empty set, repeatedly applying `F` reaches its least fixed point: the grounded extension. These are Dung's acceptability, characteristic-function and grounded-extension definitions [1, Definitions 6, 16 and 20].

The operation returns `accepted` for members of that extension, `rejected` for arguments attacked by accepted arguments, and `undecided` for all remaining arguments. Grounded membership concerns the supplied attack relation. It does not establish the empirical truth of a claim or the correctness of the input graph. An undecided argument can become accepted or rejected when the caller adds relevant arguments or attacks and recomputes the graph.

## Python and MCP interface

```python
from eal.dialectic import ArgumentationError, solve_grounded

result = solve_grounded(
    arguments=["measurement", "sensor_fault", "calibration"],
    attacks=[
        ["sensor_fault", "measurement"],
        ["calibration", "sensor_fault"],
    ],
)

assert result["accepted"] == ["calibration", "measurement"]
assert result["rejected"] == ["sensor_fault"]
assert result["undecided"] == []
```

The corresponding MCP tool call is:

```json
{
  "name": "eal_grounded",
  "arguments": {
    "arguments": ["measurement", "sensor_fault", "calibration"],
    "attacks": [
      ["sensor_fault", "measurement"],
      ["calibration", "sensor_fault"]
    ]
  }
}
```

In this example, the caller represents a calibration argument that defeats the particular sensor-fault argument. Whether a calibration observation supports that relation depends on the fault mechanism and on the observation. The solver checks the consequences of the supplied relation.

The result contains these fields:

| Field | Meaning |
|---|---|
| `semantics` | The literal string `grounded`. |
| `accepted`, `rejected`, `undecided` | Sorted, disjoint lists that partition the supplied argument identifiers. |
| `trace` | Successive rounds containing newly accepted arguments and newly rejected arguments. |
| `unresolved_attackers` | For each undecided argument, its attackers that have not been rejected. |

Each trace round has `round`, `accepted` and `rejected`. An accepted entry contains `argument` and a `defence` list. Every defence entry pairs an `attacker` with an earlier accepted `defender` that attacks it. Arguments accepted in the first round have no attackers and an empty defence list. A rejected entry contains `argument` and `attacked_by`, the sorted arguments from that round that attack it. Each argument appears at most once as newly accepted or newly rejected. The empty graph produces empty lists, an empty trace and an empty unresolved-attacker map.

All ordering uses Python's lexicographic string order. If several arguments defeat an attacker during its first rejection round, the defence trace selects the first in that order. The trace is therefore reproducible after reordering input lists.

## Input contract and execution bounds

`solve_grounded(arguments: list[str], attacks: list[list[str]]) -> dict` raises `ArgumentationError`, a `ValueError` subclass, for malformed graphs. Both containers must be lists. Identifiers must be unique, nonempty printable strings without surrounding whitespace and contain at most 256 characters. Internal spaces and Unicode letters are allowed. An attack must be a two-element list of declared identifiers. Duplicate directed attacks are rejected. Self-attacks and cycles are valid input.

The limits are 4,096 arguments and 65,536 attacks. The implementation builds adjacency lists and processes successive acceptance rounds without recursion. Each node and edge contributes a bounded amount of propagation and trace work; sorting gives worst-case time `O((V + E) log(V + E))`, with space `O(V + E)` including the output. It neither changes caller-owned inputs nor executes evidence tools.

## Relationship to EAL's support calculus

EAL evaluates declared evidence, conditions, assumptions, reasoning methods, premises and objections. The standalone `eal_grounded` operation evaluates explicit abstract attack relations, including cyclic ones. EAL/0.3 additionally constructs nodes and local attack relations from authored argument and objection declarations, then calls the composed solver described below. Neither solver interprets a prose rationale as a deductively valid rule. They provide no rule priorities, probabilistic acceptance or full ASPIC+ argument construction.

A host serving an LLM can submit the graph to this operation and give the model its labels and defence trace. A model without tool calling requires the host to make the MCP call through the host's structured request interface.

## EAL/0.3: required premises and alternative derivations

The composed profile gives argument and objection nodes three possible labels: `accepted`, `rejected` and `undecided`. Each node has a separately determined local-usability flag and a conjunction of required premise claims. A claim can have several alternative deriving nodes.

The following equations define the profile. `IN` denotes `accepted`; `OUT` denotes `rejected`.

| Entity | Acceptance condition | Rejection condition |
|---|---|---|
| Node | Locally usable, every required claim IN, every attacker OUT | Locally unusable, or some required claim OUT, or some attacker IN |
| Claim | At least one deriving node IN | Every deriving node OUT, including the empty set |

Every label initially equals `undecided`. Each round applies these rules using only the information established in earlier rounds. A determined label is permanent during that computation. Termination yields the least information state satisfying the rules. The profile is named `grounded_with_support` to distinguish this conjunction-and-alternatives interpretation from an ordinary attack graph over the authored nodes alone.

An objection whose local evidence is unusable is rejected and cannot defeat a node. An objection that requires an unsupported claim is likewise rejected. If a required claim remains undecided, the objection remains undecided unless another condition already rejects it. A positive support cycle supplies no initial acceptance. An objection depending on the very claim it attacks also remains unresolved when there is no independent support or defence. These outcomes preserve the difference between missing support and an unresolved conflict.

An attack on one argument affects that derivation. Another accepted argument can continue to support the same claim and its dependants. A claim-targeted objection is represented by attacks on all arguments for that claim. An attack on a reasoning method or assumption targets the applications that directly depend on it. An objection targeting another objection supplies a defence; a further objection can defeat that defence. Required premises propagate the resulting effects to dependent arguments without turning a local objection into an attack on every alternative derivation.

### Pure solver interface

```python
from eal.dialectic import solve_composed

result = solve_composed(
    nodes={
        "argument:first": {"usable": True, "premises": []},
        "argument:alternative": {"usable": True, "premises": []},
        "objection:calibration": {"usable": True, "premises": []},
        "argument:downstream": {"usable": True, "premises": ["measurement"]},
    },
    claims={
        "measurement": ["argument:first", "argument:alternative"],
        "consequence": ["argument:downstream"],
    },
    attacks=[["objection:calibration", "argument:first"]],
)

assert result["nodes"]["argument:first"] == "rejected"
assert result["nodes"]["argument:alternative"] == "accepted"
assert result["claims"]["consequence"] == "accepted"
```

The result contains `semantics`, `nodes`, `claims` and `trace`. The node and claim maps associate each supplied identifier with its final label. Every trace round contains newly labelled `nodes` and `claims`; an entry has `id`, `status` and structured `reasons`. Reasons identify local usability, required claims, attacking nodes or deriving nodes. Dependencies used by a trace step were determined in earlier rounds, making the explanation replayable.

The input maps use separate node and claim namespaces. Node declarations require exactly `usable` (a Boolean) and `premises` (a list of declared claim identifiers). Claim values list declared deriving nodes. All identifiers obey the standalone solver's string rules. Duplicate dependencies, duplicate attacks, dangling references and extra node fields are rejected. The generic solver allows a node to support several claims; EAL's compiler supplies each argument's declared conclusion and objection nodes that establish no claim themselves.

Limits are 4,096 nodes, 4,096 claims and 131,072 relationships in total, counting premise links, derivation links and attacks. Counter-based propagation visits each relationship a bounded number of times. Deterministic sorting gives worst-case time `O((V + C + E) log(V + C + E))`; space is `O(V + C + E)`, including the trace. Here `V`, `C` and `E` denote nodes, claims and total relationships. At most `V + C` rounds can add information. The implementation uses no recursion.

### Connection with ordinary grounded argumentation

The profile has an explicit translation to an ordinary Dung framework. Introduce a complement node for each claim. Every deriving node attacks that complement, which attacks the claim node and every node requiring the claim. An unattacked additional node attacks each locally unusable node. Retain the authored node-to-node attacks.

Under grounded labelling, the complement is rejected exactly when some deriving node is accepted; it is accepted exactly when all deriving nodes are rejected. Those are respectively the composed claim's acceptance and rejection conditions. Its attacks on requiring nodes implement the necessary-premise condition. Projecting the resulting labelling onto the authored nodes and claims therefore gives the equations above. The production implementation computes these labels directly, avoiding the extra graph nodes.

## Verification

`python -m pytest -q tests/test_dialectic.py tests/test_composed_dialectic.py` exercises both operations. The standalone tests check all 531 directed graphs with zero to three arguments, including every possible self-attack. Expected results come from independent enumeration of complete extensions and selection of their least member, using Dung's characterisation [1, Theorem 25]. Additional tests cover larger seeded graphs, reinstatement, partial defence, odd cycles, input permutations, malformed inputs and a maximum-length chain.

The composed tests compare all 1,024 combinations of usability, premise links, derivation links and attacks for two nodes and one claim against the independent Dung translation above. They also check 200 larger seeded compositions and all 512 attack-only graphs on three nodes. Specific cases cover unavailable attackers, support cycles, conjunction, alternative derivations, claim-dependent objections and defeated defences. A chain of 4,096 nodes and 4,096 claims verifies iterative execution across 8,192 rounds. Both trace suites check that each conclusion uses only earlier information and that no newly determined label is omitted.

## Reference

1. Phan Minh Dung (1995). “On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games.” *Artificial Intelligence* 77(2), 321–357. [DOI](https://doi.org/10.1016/0004-3702(94)00041-X). [Full paper](https://cse-robotics.engr.tamu.edu/dshell/cs631/papers/dung95acceptability.pdf). Definitions checked in the primary paper, pp. 326 and 328–330.
