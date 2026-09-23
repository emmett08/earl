# Grounded reasoning over explicit argument graphs

`eal_grounded` determines which arguments can be accepted in a finite, explicitly supplied attack graph. It gives agents a deterministic formal reasoning operation alongside EAL's authored support calculus. Argument identifiers and attack relations are inputs; the solver does not construct them from prose or from EAL declarations.

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

EAL evaluates declared evidence, conditions, assumptions, inference rationales, premises and objections. This separate operation evaluates explicit abstract attack relations, including cyclic ones. It does not automatically translate objections into attacks or interpret a rationale as a deductively valid rule. It provides no rule priorities, probabilities, attack-type distinctions or full ASPIC+ argument construction. Those require an additional, specified interpretation and its own tests.

A host serving an LLM can submit the graph to this operation and give the model its labels and defence trace. A model without tool calling requires the host to make the MCP call through the host's structured request interface.

## Verification

`python -m pytest -q tests/test_dialectic.py` checks all 531 directed graphs with zero to three arguments, including every possible self-attack. Expected results come from independent enumeration of complete extensions and selection of their least member, using Dung's characterisation [1, Theorem 25]. Additional tests cover larger seeded graphs, reinstatement, partial defence, odd cycles, input permutations, malformed inputs and a maximum-length chain. Trace checks replay each defence using only earlier rounds and check that no newly defended argument is omitted.

## Reference

1. Phan Minh Dung (1995). “On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games.” *Artificial Intelligence* 77(2), 321–357. [DOI](https://doi.org/10.1016/0004-3702(94)00041-X). [Full paper](https://cse-robotics.engr.tamu.edu/dshell/cs631/papers/dung95acceptability.pdf). Definitions checked in the primary paper, pp. 326 and 328–330.
