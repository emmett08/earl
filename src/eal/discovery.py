"""Packaged language reference for models with no prior knowledge of EAL."""
from __future__ import annotations

from . import __version__


EXAMPLE = '''language "EAL/3"
environment bench {
  require site == "bench"
}
tool collector {
  version "1"
}
context environment bench, tool collector, max_age 3600 {
  evidence observation {
    kind test
    require passed == true
  }
  reasoning measured {
    method "structured/1"
    rationale "The observation supports only the stated test result in this environment."
  }
  claim checked {
    statement "The supplied test passes at the bench."
  }
  argument measurement = [evidence observation] via measured => checked
}
'''


def describe_language(*, registry=None) -> dict:
    from .methods import default_registry
    from .propositions import describe_bindings

    registry = default_registry() if registry is None else registry

    return {
        "implementation_version": __version__,
        "languages": ["EAL/3"],
        "source_syntax": "EAL/3",
        "method_registry_fingerprint": registry.fingerprint,
        "syntax": {
            'notation': 'Capitalised placeholders denote values. Fields end at newlines and may appear in any order. Square brackets are literal lists/support groups. Names are globally unique; forward references are allowed. Strings use JSON quoting; comments use // or /* */.',
            'program': 'language "EAL/3"\nDECLARATIONS',
            'context': 'context environment ENV, tool TOOL, max_age SECONDS {\nDECLARATIONS\n}',
            'environment': 'environment NAME {\nrequire CONTEXT.FIELD OP SCALAR\n}',
            'tool': 'tool NAME {\nversion "VERSION"\n}',
            'evidence': 'evidence NAME {\ntool TOOL\nkind KIND\nenvironment ENV\nmax_age SECONDS\ninput JSON\nrequire VALUE.FIELD OP SCALAR\n}',
            'assumption': 'assumption NAME {\nstatement "TEXT"\nenvironment ENV\nvalidate EVIDENCE\nvalid_from "TIME"\nvalid_until "TIME"\n}',
            'reasoning': 'reasoning NAME {\nmethod "VERSIONED_METHOD_ID"\nrationale "TEXT"\nbacking [EVIDENCE_LIST]\nrequire OUTPUT.FIELD OP SCALAR\n}',
            'claim': 'claim NAME {\nstatement "TEXT"\nenvironment ENV\nproposition {\nsubject "ENTITY"\nquantity "QUANTITY"\nunit "UNIT"\nscope "SCOPE"\nvalid_from "TIME"\nvalid_until "TIME"\nquery JSON\nresult OUTPUT.FIELD OP SCALAR\n}\n}',
            'argument': 'argument NAME = [evidence EVIDENCE_LIST, assumptions ASSUMPTION_LIST, premises CLAIM_LIST] via REASONING => CLAIM binding EVIDENCE',
            'objection': 'objection NAME = [evidence EVIDENCE_LIST, premises CLAIM_LIST] -x> TARGET_KIND TARGET_NAME',
            'pattern': 'pattern NAME(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c',
            'apply': 'apply ARGUMENT = PATTERN(PARAM=REFERENCE, ...)',
            'formal_relations': 'strict ARGUMENT reviewed "REVIEW_REFERENCE"\nrank EVIDENCE_OR_ASSUMPTION_OR_ARGUMENT INTEGER reviewed "REVIEW_REFERENCE"\ncontrary CLAIM to CLAIM reviewed "REVIEW_REFERENCE". These are ASPIC+ formalisation directives. reason validates them; compile-aspic applies their effects. Ranks are integers 0-1000; claim contraries are directed.',
            'scope_defaults': 'A context may group multiple evidence and other declarations. Each keeps its own identity, input and predicates. Nearest context wins; explicit fields override defaults. environment applies to evidence/assumption/claim, tool and max_age to evidence, valid_from/valid_until to assumptions. Proposition dates remain explicit. Contexts retain global declaration identities.',
            'optional_fields': 'Evidence input, reasoning backing, claim proposition, assumption validity dates, each support group and binding are optional. Evidence/environment require predicates; arguments/objections require nonempty support. All proposition fields are required.',
            'nested_derivations': 'Premises reference claims supported by other arguments, including pattern instances, forming an acyclic derivation graph. Premise slots do not accept argument IDs. Inline argument declarations and recursive/nested pattern applications are unsupported.',
            'abstraction': 'Patterns have closed typed parameters. Every body reference names a parameter; expansion preserves dependency identities. Forward references are allowed; invalid bindings are diagnosed.',
            'operators': ['==', '!=', '<', '<=', '>', '>='],
            'lists': 'Comma-separated identifiers retain their order. Computational methods need output predicates and typed claims need an evidence binding on each supporting argument.',
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
            "profile": "EAL/3-compiled-aspic/4",
            "cli": "compile-aspic SOURCE --context JSON --collection COLLECTION_ID --goal CLAIM [--now TIME]",
            "mcp": "eal_compile_aspic(source, context, collection_id, goal, now?)",
            "input": "Validated EAL/3 source, matching stored observation collection, declared goal claim and explicit or current assessment time",
            "meaning": "Check EAL observations and local methods, then translate available evidence, locally usable argument routes, assumptions and targeted objections into a bounded ASPIC+ theory with explicit source mapping; reviewed EAL argumentation relations supply optional strict rules, ranks and directed claim contraries; ordinary EAL reasoning is unchanged",
            "output": ["profile", "theory", "formal", "routes", "source_map", "claim_status", "authored_claim_status", "source_digest", "snapshot_digest", "collection_id"],
            "limits": "Unannotated fallible elements use rank 500 and authored routes remain defeasible; strictness, claim contrariness and ranks require checked source annotations. Objections cannot undercut strict routes or carry ranks. Accepted contrary conclusions are rejected as outside this profile. Finite acyclic argument construction and grounded minimum-rank defeat only; no inferred prose semantics, full ASPIC+ expressiveness or general EAL/ASPIC+ equivalence",
        },
        "aspic_export": {
            "cli": "export-aspic RESULT.json --output VIEW.json",
            "input": "A previously computed compiled result, or an explicit theory and matching formal solver result",
            "output": "aspic-view/2 JSON for the separate Vue/TypeScript visualisation app: arguments, direct derivations, grounded labels, defeat witnesses, typed unavailable-evidence issues and supplied source locations",
            "meaning": "Recompute the bounded formal result and require exact agreement before exporting. The separate app imports JSON locally; neither export nor viewing collects evidence or authenticates supplied provenance",
        },
        "typed_bindings": describe_bindings(registry=registry),
        "composition": "Default EAL/3 computes the least-information fixed point of authored conjunctive support, alternative derivations and objection attacks. Objections can depend on claim subarguments; targeting an objection expresses defence. Attack cycles may remain undecided. Default assessment does not construct ASPIC+ rule arguments or preference-sensitive defeat. The separate opt-in compiler constructs a bounded ASPIC+ snapshot from checked EAL declarations. Rejected acceptance does not assert falsity.",
        "statuses": {
            "valid": "Static language well-formedness only",
            "supported": "At least one usable, uncontested derivation under the declared model",
            "contested": "A usable derivation or dependency is challenged; no independent uncontested derivation",
            "unsupported": "No usable derivation; does not imply false",
            "out_of_scope": "The supplied environment does not match the declared conditions",
        },
        "workflow": ["describe", "validate", "plan", "collect_claim|collect", "reason", "packet|explain"],
        "registered_workflow": ["register", "sources|find", "assess_known", "operator_explain_if_needed"],
        "model_context": {
            "schema": "EAL/model-context/2",
            "packet_schema": "EAL/assessment-packet/2",
            "meaning": "A decision-focused projection retains bounded authored statements and explicit prose_verified qualifications for selected and premise claims, checked method outputs, assumption applicability times and bounded field-level evidence failures. Formal support does not verify authored prose. Statement truncation and other omissions mark the summary incomplete. Complete source, acquisition values and trace identities remain in host state. Numeric method results are exposed through declared output contracts, not by copying raw tool records.",
        },
        "registered_assessment": "The developer registers exact EAL source and selected claims once. Later sessions identify an entry and claim; the host plans all relevant argument routes, reuses eligible observations at their original age, collects missing evidence, evaluates the declared methods and returns a bounded packet. Model-facing registered MCP calls require a trusted launcher --known-entry allowlist and use registered context. A text-only model can receive this packet from ModelContextAdapter without tool or native reasoning calls.",
        "acquisition_plan": "eal_plan(source, claim) computes the complete potentially decisive evidence closure, including alternative arguments, transitive premises, backing, assumption validation, objections and defences. eal_collect_claim runs that plan with operator-granted tools.",
        "tool_binding": "A sibling operator-owned TOML registry chooses command or json_file, bounded execution, optional parallel_safe and command environment inheritance. Registered claims use those bindings through the host. Only operator-declared independent read-only calls may overlap.",
        "source_identity": "Collections bind exact UTF-8 source bytes and context. Registered assessment creates a new collection for a revision and can reuse matching observations at their original age. Reasoning refuses a mismatched collection.",
        "observation_import": {
            "required_envelope_fields": ["value", "observed_at", "context", "request"],
            "acquisition_request_fields": ["tool", "tool_version", "input", "context"],
            "correspondence": "File observations must match the requested acquisition. Explicit stored-observation rebinding also checks the same evidence ID, environment, kind, request, context and operator binding, preserving the original measurement time.",
            "interpretation": "Matching metadata checks correspondence; it does not authenticate a measurement. Importing again preserves original observation time.",
        },
        "time": "Timezone-aware ISO-8601; applicability intervals are [valid_from, valid_until). Evidence age is usable through max_age inclusively. New ingestion does not refresh original observation time.",
        "interpretation": "Statements and rationales are prose. Typed bindings check represented correspondence and numerical predicates, not empirical truth. Model premises, scope, sampling and causal assumptions require their own grounds. Reusing an observation does not create independent evidence.",
        "example": EXAMPLE,
    }
