"""Authoritative request fields shared by MCP registration and the text host."""

from types import MappingProxyType


OPERATION_FIELDS = MappingProxyType({
    "describe": (frozenset(), frozenset()),
    "format": (frozenset({"source"}), frozenset()),
    "validate": (frozenset({"source"}), frozenset()),
    "plan": (frozenset({"source", "claim"}), frozenset()),
    "collect": (frozenset({"source", "context"}), frozenset({"evidence_ids"})),
    "collect_claim": (frozenset({"source", "context", "claim"}), frozenset()),
    "reason": (frozenset({"source", "context"}), frozenset({"collection_id", "now"})),
    "compile_aspic": (frozenset({"source", "context", "collection_id", "goal"}),
                      frozenset({"now", "semantics", "query_mode", "preference"})),
    "explain": (frozenset({"assessment_id"}), frozenset({"claim"})),
    "packet": (frozenset({"assessment_id"}), frozenset({"claim"})),
    "sources": (frozenset(), frozenset({"limit", "offset"})),
    "find_claims": (frozenset(), frozenset({"query", "claim", "limit"})),
    "assess_known": (frozenset({"entry_id", "claim"}), frozenset()),
    "grounded": (frozenset({"arguments", "attacks"}), frozenset()),
})

# These operations hold the workspace acquisition lock before considering reuse.
ACQUISITION_OPERATIONS = frozenset({"eal_collect", "eal_collect_claim", "eal_assess_known"})
