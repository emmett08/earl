"""Packaged language reference for models with no prior knowledge of EAL."""
from __future__ import annotations

from . import __version__


EXAMPLE = '''language "EAL/2";
environment bench { require "site" == "bench"; }
tool collector { version "1"; }
evidence observation {
  tool collector; kind test; environment bench; max_age 3600;
  require "passed" == true;
}
reasoning measured {
  method "structured/1";
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
        "languages": ["EAL/2"],
        "method_registry_fingerprint": registry.fingerprint,
        "syntax": {
            "notation": "Capitalised placeholders denote strings, identifiers, numbers or JSON. Square brackets denote optional clauses; + denotes one or more repetitions. Clause order is fixed. Names are unique across declarations; forward references are allowed. Strings use JSON quoting. Comments use // or /* */.",
            "program": 'language "EAL/2"; DECLARATIONS',
            "environment": 'environment NAME { require "CONTEXT.FIELD" OP SCALAR; + }',
            "tool": 'tool NAME { version "VERSION"; }',
            "evidence": 'evidence NAME { tool TOOL; kind KIND; environment ENV; max_age SECONDS; [input JSON;] require "VALUE.FIELD" OP SCALAR; + }',
            "assumption": 'assumption NAME { statement "TEXT"; environment ENV; validate EVIDENCE; [valid_from "TIME";] [valid_until "TIME";] }',
            "reasoning": 'reasoning NAME { method "VERSIONED_METHOD_ID"; rationale "TEXT"; [backing EVIDENCE_LIST;] [require "OUTPUT.FIELD" OP SCALAR; ...] }',
            "claim": 'claim NAME { statement "TEXT"; environment ENV; [proposition { subject "ENTITY"; quantity "QUANTITY"; unit "UNIT"; scope "MODEL_OR_EPISODE"; valid_from "TIME"; valid_until "TIME"; query JSON; result "OUTPUT.FIELD" OP SCALAR; }] }',
            "argument": 'argument NAME { conclusion CLAIM; reasoning REASONING; [evidence EVIDENCE_LIST;] [assumptions ASSUMPTION_LIST;] [premises CLAIM_LIST;] [binding EVIDENCE;] }',
            "objection": 'objection NAME { target claim|reasoning|assumption|argument|objection NAME; [evidence EVIDENCE_LIST;] [premises CLAIM_LIST;] } — at least one evidence or premise is required.',
            "pattern": 'pattern NAME(PARAM: claim|reasoning|evidence|assumption, ...) { conclusion PARAM; reasoning PARAM; [evidence PARAM_LIST;] [assumptions PARAM_LIST;] [premises PARAM_LIST;] [binding PARAM;] }',
            "apply": 'apply NAME = PATTERN(PARAM=DECLARATION, ...);',
            "formal_relations": 'strict ARGUMENT reviewed "REVIEW_REFERENCE"; | rank EVIDENCE_OR_ASSUMPTION_OR_ARGUMENT INTEGER reviewed "REVIEW_REFERENCE"; | contrary CLAIM to CLAIM reviewed "REVIEW_REFERENCE"; — optional EAL declarations for compile-aspic only. Global name resolution after pattern expansion determines each reference kind; ranks are integers 0–1000 and contraries are directed.',
            "abstraction": "Patterns bind typed declaration references. Every body reference is a parameter; there is no implicit capture, recursion or executable import. Applications expand into named arguments and preserve original evidence identities. Forward references are allowed; invalid or ambiguous bindings are diagnosed.",
            "operators": ["==", "!=", "<", "<=", ">", ">="],
            "lists": "One or more comma-separated identifiers. An argument requires at least one evidence, assumption or premise. A computational method requires at least one output predicate, supplied by its method-level require or its typed claim's result condition. A typed claim requires a binding for each supporting argument.",
        },
        "methods": {
            "structured/1": {"input": "Author-supplied evidence/premise relation", "meaning": "Checks availability and composition; does not prove prose"},
            "deductive/1": {"kind": "logical_case", "input": {"premises": ["FORMULA"], "conclusion": "FORMULA"}, "formula": 'An atom string, {"not":f}, {"and":[f,...]}, {"or":[f,...]} or {"implies":[f,g]}', "outputs": ["entailed", "consistent_premises", "counterexample"], "limit": "At most 12 atoms; inconsistent premises are unusable"},
            "inductive/1": {"kind": "sample", "input": {"successes": "INTEGER", "trials": "POSITIVE_INTEGER", "confidence": "NUMBER"}, "outputs": ["estimate", "lower", "upper", "sample_size", "confidence"], "meaning": "Wilson interval; sampling assumptions are supplied, not established"},
            "abductive/1": {"kind": "hypotheses", "input": {"observed": "JOINT_EVENT", "candidates": [{"name": "HYPOTHESIS", "prior": "NUMBER", "likelihood": "NUMBER"}]}, "outputs": ["posterior", "best", "best_posterior", "ties"], "meaning": "Bayesian update within supplied candidates and joint likelihoods"},
            "causal/1": {"kind": "experiment", "input": {"assignment": "randomised", "treatment": ["NUMBER"], "control": ["NUMBER"]}, "outputs": ["estimate", "standard_error"], "meaning": "Difference of group means with standard error; at least two values per group; design metadata is asserted"},
            "counterfactual/1": {"kind": "causal_model", "input": {"variables": {"VARIABLE": {"intercept": "NUMBER", "coefficients": {"PARENT": "NUMBER"}, "noise": "NUMBER"}}, "intervention": {"variable": "VARIABLE", "value": "NUMBER"}, "outcome": "VARIABLE"}, "outputs": ["factual", "counterfactual", "difference"], "meaning": "Acyclic affine structural model, supplied fixed noise; at most 32 variables"},
            "analogical/1": {"kind": "analogy", "input": {"relevant_features": ["FEATURE"], "source": {"FEATURE": "SCALAR"}, "target": {"FEATURE": "SCALAR"}}, "outputs": ["match_fraction"], "meaning": "Exact declared feature comparisons, not a probability or proof of transfer"},
            "temporal/1": {"kind": "trace", "input": {"start": "NUMBER", "end": "NUMBER", "max_gap": "NUMBER", "events": [{"time": "NUMBER", "value": "NUMBER"}], "property": {"operator": "lt|le|eq|ne|ge|gt", "value": "NUMBER"}, "semantics": "sampled"}, "outputs": ["holds"], "meaning": "Ordered, bounded finite samples with endpoint/gap coverage; no continuous-time conclusion"},
        },
        "optional_compilation": {
            "profile": "EAL/2-compiled-aspic/4",
            "cli": "compile-aspic SOURCE --context JSON --collection COLLECTION_ID --goal CLAIM [--now TIME]",
            "mcp": "eal_compile_aspic(source, context, collection_id, goal, now?)",
            "input": "Validated EAL/2 source, matching stored observation collection, declared goal claim and explicit or current assessment time",
            "meaning": "Check EAL observations and local methods, then translate available evidence, locally usable argument routes, assumptions and targeted objections into a bounded ASPIC+ theory with explicit source mapping; reviewed EAL formal relations supply optional strict rules, ranks and directed claim contraries; ordinary EAL reasoning is unchanged",
            "output": ["profile", "theory", "formal", "routes", "source_map", "claim_status", "authored_claim_status", "source_digest", "snapshot_digest", "collection_id"],
            "limits": "Unannotated fallible elements use rank 500 and authored routes remain defeasible; strictness, claim contrariness and ranks require checked source annotations. Objections cannot undercut strict routes or carry ranks. Accepted contrary conclusions are rejected as outside this profile. Finite acyclic argument construction and grounded minimum-rank defeat only; no inferred prose semantics, full ASPIC+ expressiveness or general EAL/ASPIC+ equivalence",
        },
        "aspic_export": {
            "cli": "export-aspic RESULT.json --output VIEW.json",
            "input": "A previously computed compiled result, or an explicit theory and matching formal solver result",
            "output": "aspic-view/1 JSON for the separate Vue/TypeScript visualisation app: arguments, direct derivations, grounded labels, defeat witnesses, unavailable evidence and supplied source locations",
            "meaning": "Recompute the bounded formal result and require exact agreement before exporting. The separate app imports JSON locally; neither export nor viewing collects evidence or authenticates supplied provenance",
        },
        "typed_bindings": describe_bindings(registry=registry),
        "composition": "Default EAL/2 computes the least-information fixed point of authored conjunctive support, alternative derivations and objection attacks. Objections can depend on claim subarguments; targeting an objection expresses defence. Attack cycles may remain undecided. Default assessment does not construct ASPIC+ rule arguments or preference-sensitive defeat. The separate opt-in compiler constructs a bounded ASPIC+ snapshot from checked EAL declarations. Rejected acceptance does not assert falsity.",
        "statuses": {
            "valid": "Static language well-formedness only",
            "supported": "At least one usable, uncontested derivation under the declared model",
            "contested": "A usable derivation or dependency is challenged; no independent uncontested derivation",
            "unsupported": "No usable derivation; does not imply false",
            "out_of_scope": "The supplied environment does not match the declared conditions",
        },
        "workflow": ["describe", "validate", "collect", "reason", "explain"],
        "source_identity": "Collections bind exact UTF-8 source bytes. Revision or formatting requires recollection. Keep source, context and explicit assessment time tied to the intended task.",
        "observation_import": {
            "required_envelope_fields": ["value", "observed_at", "context", "request"],
            "acquisition_request_fields": ["tool", "tool_version", "input", "context"],
            "correspondence": "File observations must match the requested acquisition. Source and local evidence identifiers are assigned separately by collection; an observation can be reused only when its acquisition still matches.",
            "interpretation": "Matching metadata checks correspondence; it does not authenticate a measurement. Importing again preserves original observation time.",
        },
        "time": "Timezone-aware ISO-8601; applicability intervals are [valid_from, valid_until). Evidence age is usable through max_age inclusively. New ingestion does not refresh original observation time.",
        "interpretation": "Statements and rationales are prose. Typed bindings check represented correspondence and numerical predicates, not empirical truth. Model premises, scope, sampling and causal assumptions require their own grounds. Reusing an observation does not create independent evidence.",
        "example": EXAMPLE,
    }
