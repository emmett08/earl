"""Finite abstract argumentation with Dung's least-fixed-point grounded semantics.

Argument identifiers and attacks are supplied explicitly by the caller. This
module does not infer attacks from natural language or interpret EAL declarations.
"""
from __future__ import annotations

MAX_ARGUMENTS = 4096
MAX_ATTACKS = 65536
MAX_IDENTIFIER_LENGTH = 256


class ArgumentationError(ValueError):
    """An abstract argumentation graph violates the input contract."""


def _identifier(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise ArgumentationError(f"{location} must be a string")
    if not value or value != value.strip() or not value.isprintable():
        raise ArgumentationError(
            f"{location} must be nonempty and printable without surrounding whitespace"
        )
    if len(value) > MAX_IDENTIFIER_LENGTH:
        raise ArgumentationError(
            f"{location} exceeds {MAX_IDENTIFIER_LENGTH} characters"
        )
    return value


def solve_grounded(arguments: list[str], attacks: list[list[str]]) -> dict:
    """Return the grounded labelling and deterministic, replayable defence trace.

    ``[source, target]`` means source attacks target. The accepted arguments form
    the least fixed point of the defence function F, starting with the empty set.
    Rejected arguments are attacked by an accepted argument; the rest remain
    undecided. These are graph-relative argument statuses, not truth values.

    Input lists must contain distinct identifiers and distinct directed edges.
    Cycles and self-attacks are valid. All result identifiers use Python's sorted
    string order, independent of input order. No caller-owned value is modified.
    Propagation visits each node and edge a bounded number of times. Deterministic
    sorting gives O((V + E) log(V + E)) worst-case time; space is O(V + E), including
    the trace. No recursion, network, clock or tool execution is used.
    """
    if not isinstance(arguments, list):
        raise ArgumentationError("arguments must be a list")
    if not isinstance(attacks, list):
        raise ArgumentationError("attacks must be a list")
    if len(arguments) > MAX_ARGUMENTS:
        raise ArgumentationError(f"arguments exceeds the limit of {MAX_ARGUMENTS}")
    if len(attacks) > MAX_ATTACKS:
        raise ArgumentationError(f"attacks exceeds the limit of {MAX_ATTACKS}")

    nodes: set[str] = set()
    for index, value in enumerate(arguments):
        argument = _identifier(value, f"arguments[{index}]")
        if argument in nodes:
            raise ArgumentationError(f"duplicate argument: {argument!r}")
        nodes.add(argument)

    edges: set[tuple[str, str]] = set()
    for index, edge in enumerate(attacks):
        if not isinstance(edge, list) or len(edge) != 2:
            raise ArgumentationError(f"attacks[{index}] must be a two-element list")
        source = _identifier(edge[0], f"attacks[{index}][0]")
        target = _identifier(edge[1], f"attacks[{index}][1]")
        if source not in nodes or target not in nodes:
            raise ArgumentationError(f"attack contains an undeclared argument: {edge!r}")
        pair = (source, target)
        if pair in edges:
            raise ArgumentationError(f"duplicate attack: {edge!r}")
        edges.add(pair)

    ordered = sorted(nodes)
    incoming: dict[str, list[str]] = {node: [] for node in ordered}
    outgoing: dict[str, list[str]] = {node: [] for node in ordered}
    for source, target in sorted(edges):
        incoming[target].append(source)
        outgoing[source].append(target)

    # An argument is defended once all its attackers have been rejected. The
    # remaining count is reduced once per rejected attacker, never per defender.
    remaining = {node: len(incoming[node]) for node in ordered}
    accepted: set[str] = set()
    rejected: set[str] = set()
    rejected_by: dict[str, str] = {}
    wave = [node for node in ordered if remaining[node] == 0]
    trace: list[dict] = []
    round_number = 0

    while wave:
        round_number += 1
        # Certificates only refer to defenders accepted in an earlier round.
        accepted_trace = [
            {
                "argument": node,
                "defence": [
                    {"attacker": attacker, "defender": rejected_by[attacker]}
                    for attacker in incoming[node]
                ],
            }
            for node in wave
        ]
        accepted.update(wave)
        defeated: dict[str, list[str]] = {}
        for defender in wave:
            for target in outgoing[defender]:
                if target not in rejected:
                    defeated.setdefault(target, []).append(defender)
        rejected.update(defeated)
        for target, defenders in defeated.items():
            rejected_by[target] = defenders[0]

        trace.append(
            {
                "round": round_number,
                "accepted": accepted_trace,
                "rejected": [
                    {"argument": target, "attacked_by": defeated[target]}
                    for target in sorted(defeated)
                ],
            }
        )
        next_wave: set[str] = set()
        for target in defeated:
            for dependent in outgoing[target]:
                remaining[dependent] -= 1
                if (
                    remaining[dependent] == 0
                    and dependent not in accepted
                    and dependent not in rejected
                ):
                    next_wave.add(dependent)
        wave = sorted(next_wave)

    undecided = sorted(nodes - accepted - rejected)
    return {
        "semantics": "grounded",
        "accepted": sorted(accepted),
        "rejected": sorted(rejected),
        "undecided": undecided,
        "trace": trace,
        "unresolved_attackers": {
            node: [attacker for attacker in incoming[node] if attacker not in rejected]
            for node in undecided
        },
    }
