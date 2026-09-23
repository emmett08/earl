"""Packaged language reference for models with no prior knowledge of EAL."""
from __future__ import annotations

from . import __version__


EXAMPLE = '''language "EAL/0.1";
environment bench { require "site" == "bench"; }
tool collector { version "1"; mode deterministic; }
evidence observation {
  tool collector; kind test; environment bench; max_age 3600;
  require "passed" == true;
}
reasoning measured {
  mode structured;
  rationale "The observation supports only the stated test result in this environment.";
}
claim checked { statement "The supplied test passes at the bench."; environment bench; }
argument measurement { conclusion checked; reasoning measured; evidence observation; }
'''


def describe_language(*, registry=None) -> dict:
    from .methods import default_registry
    from .propositions import describe_bindings

    registry = default_registry() if registry is None else registry

    return {
        "implementation_version": __version__,
        "languages": ["EAL/0.1", "EAL/0.2", "EAL/0.3"],
        "method_registry_fingerprint": registry.fingerprint,
        "syntax": {
            "notation": "Capitalised placeholders denote strings, identifiers, numbers or JSON. Square brackets denote optional clauses; + denotes one or more repetitions. Clause order is fixed. Names are unique across declarations; forward references are allowed. Strings use JSON quoting. Comments use // or /* */.",
            "program": 'language "EAL/0.3"; DECLARATIONS',
            "environment": 'environment NAME { require "CONTEXT.FIELD" OP SCALAR; + }',
            "tool": 'tool NAME { version "VERSION"; mode deterministic|nondeterministic; }',
            "evidence": 'evidence NAME { tool TOOL; kind KIND; environment ENV; max_age SECONDS; [input JSON;] require "VALUE.FIELD" OP SCALAR; + }',
            "assumption": 'assumption NAME { statement "TEXT"; environment ENV; validate EVIDENCE; [valid_from "TIME";] [valid_until "TIME";] }',
            "reasoning": 'reasoning NAME { method "VERSIONED_METHOD_ID"; rationale "TEXT"; [backing EVIDENCE_LIST;] [require "OUTPUT.FIELD" OP SCALAR; ...] } — EAL/0.3. Legacy mode MODE remains supported.',
            "claim": 'claim NAME { statement "TEXT"; environment ENV; [proposition { subject "ENTITY"; quantity "QUANTITY"; unit "UNIT"; scope "MODEL_OR_EPISODE"; valid_from "TIME"; valid_until "TIME"; query JSON; result "OUTPUT.FIELD" OP SCALAR; }] }',
            "argument": 'argument NAME { conclusion CLAIM; reasoning REASONING; [evidence EVIDENCE_LIST;] [assumptions ASSUMPTION_LIST;] [premises CLAIM_LIST;] [binding EVIDENCE;] }',
            "objection": 'objection NAME { target claim|reasoning|assumption|argument|objection NAME; [evidence EVIDENCE_LIST;] [premises CLAIM_LIST;] } — argument/objection targets and premise support require EAL/0.3; at least one evidence or premise is required.',
            "operators": ["==", "!=", "<", "<=", ">", ">="],
            "lists": "One or more comma-separated identifiers. An argument requires at least one evidence, assumption or premise. A computational method requires at least one output predicate, supplied by its method-level require or its typed claim's result condition. A typed claim requires a binding for each supporting argument.",
        },
        "methods": {
            "structured": {"input": "Author-supplied evidence/premise relation", "meaning": "Checks availability and composition; does not prove prose"},
            "deductive": {"kind": "logical_case", "input": {"premises": ["FORMULA"], "conclusion": "FORMULA"}, "formula": 'An atom string, {"not":f}, {"and":[f,...]}, {"or":[f,...]} or {"implies":[f,g]}', "outputs": ["entailed", "consistent_premises", "counterexample"], "limit": "At most 12 atoms; inconsistent premises are unusable"},
            "inductive": {"kind": "sample", "input": {"successes": "INTEGER", "trials": "POSITIVE_INTEGER", "confidence": "NUMBER"}, "outputs": ["estimate", "lower", "upper", "sample_size", "confidence"], "meaning": "Wilson interval; sampling assumptions are supplied, not established"},
            "abductive": {"kind": "hypotheses", "input": {"observed": "JOINT_EVENT", "candidates": [{"name": "HYPOTHESIS", "prior": "NUMBER", "likelihood": "NUMBER"}]}, "outputs": ["posterior", "best", "best_posterior", "ties"], "meaning": "Bayesian update within supplied candidates and joint likelihoods"},
            "causal": {"kind": "experiment", "input": {"assignment": "randomised", "treatment": ["NUMBER"], "control": ["NUMBER"]}, "outputs": ["estimate", "standard_error"], "meaning": "Difference of group means with standard error; at least two values per group; design metadata is asserted"},
            "counterfactual": {"kind": "causal_model", "input": {"variables": {"VARIABLE": {"intercept": "NUMBER", "coefficients": {"PARENT": "NUMBER"}, "noise": "NUMBER"}}, "intervention": {"variable": "VARIABLE", "value": "NUMBER"}, "outcome": "VARIABLE"}, "outputs": ["factual", "counterfactual", "difference"], "meaning": "Acyclic affine structural model, supplied fixed noise; at most 32 variables"},
            "analogical": {"kind": "analogy", "input": {"relevant_features": ["FEATURE"], "source": {"FEATURE": "SCALAR"}, "target": {"FEATURE": "SCALAR"}}, "outputs": ["match_fraction"], "meaning": "Exact declared feature comparisons, not a probability or proof of transfer"},
            "temporal": {"kind": "trace", "input": {"start": "NUMBER", "end": "NUMBER", "max_gap": "NUMBER", "events": [{"time": "NUMBER", "value": "NUMBER"}], "property": {"operator": "lt|le|eq|ne|ge|gt", "value": "NUMBER"}, "semantics": "sampled"}, "outputs": ["holds"], "meaning": "Ordered, bounded finite samples with endpoint/gap coverage; no continuous-time conclusion"},
        },
        "typed_bindings": describe_bindings(registry=registry),
        "composition": "EAL/0.3 computes the least-information fixed point of explicit conjunctive support, alternative derivations and attacks. Objections can depend on claim subarguments; targeting an objection expresses defence. Attack cycles may remain undecided. Rejected acceptance does not assert falsity. Legacy EAL/0.1 and EAL/0.2 retain their original objection behaviour.",
        "statuses": {
            "valid": "Static language well-formedness only",
            "supported": "At least one usable, uncontested derivation under the declared model",
            "contested": "A usable derivation or dependency is challenged; no independent uncontested derivation",
            "unsupported": "No usable derivation; does not imply false",
            "out_of_scope": "The supplied environment does not match the declared conditions",
        },
        "workflow": ["describe", "validate", "collect", "reason", "explain"],
        "source_identity": "Collections bind exact UTF-8 source bytes. Revision or formatting requires recollection. Keep source, context and explicit assessment time tied to the intended task.",
        "time": "Timezone-aware ISO-8601; applicability intervals are [valid_from, valid_until). Evidence age is usable through max_age inclusively. New ingestion does not refresh original observation time.",
        "interpretation": "Statements and rationales are prose. Typed bindings check represented correspondence and numerical predicates, not empirical truth. Model premises, scope, sampling and causal assumptions require their own grounds. Reusing an observation does not create independent evidence.",
        "example": EXAMPLE,
    }
