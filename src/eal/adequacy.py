"""Reviewed correspondence and executable evidence obligations above EAL support.

These contracts are trusted host configuration, never a model's self-assessment.
They check a reviewed statement-to-source mapping and finite predicates; they do
not infer the meaning of arbitrary prose or authenticate physical measurements.
The pure EAL evaluator keeps its existing semantics.  A supported EAL claim alone
does not establish adequacy under this additional, explicit contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import operator
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping

from .evaluator import assess_evidence_record, canonical_digest
from .parser import parse
from .semantics import parse_time, validate


SCHEMA = "eal-adequacy/1"
RESULT_SCHEMA = "eal-adequacy-result/1"
_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ROLES = {"identity", "scope", "coverage", "sampling", "threshold", "inference", "assumption", "objection"}
_TARGETS = {"evidence", "argument", "assumption", "objection", "claim", "context"}
_OPERATORS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
              "<=": operator.le, ">": operator.gt, ">=": operator.ge}
_TABLES = {"argument": "arguments", "assumption": "assumptions",
           "objection": "objections", "claim": "claims"}


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise ValueError(f"{name} requires nonblank UTF-8 text of at most {limit} bytes")
    return value


@dataclass(frozen=True)
class EvidenceObligation:
    """One checked clause with an explicit engineering role and source.

    Evidence paths address the observation's JSON ``value``. Other paths address
    the corresponding complete EAL assessment entry, or the supplied context.
    ``about`` binds an adequacy clause to an assumption/objection's own sources;
    it does not assert that an objection's activation predicate is true.
    """
    id: str
    role: str
    target: str
    reference: str
    path: str
    operator: str
    expected: Any
    rationale: str
    about: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceObligation":
        fields = {"id", "role", "target", "reference", "path", "operator", "expected", "rationale"}
        if not isinstance(value, dict) or set(value) - fields - {"about"} or not fields <= set(value):
            raise ValueError("An adequacy obligation has missing or unknown fields")
        if not isinstance(value["id"], str) or not _ID.fullmatch(value["id"]):
            raise ValueError("Obligation id must be an EAL identifier")
        if (not isinstance(value["role"], str) or value["role"] not in _ROLES
                or not isinstance(value["target"], str) or value["target"] not in _TARGETS):
            raise ValueError("Unknown adequacy obligation role or target")
        reference = value["reference"]
        if (not isinstance(reference, str) or
                (reference != "" if value["target"] == "context" else not _ID.fullmatch(reference))):
            raise ValueError("Obligation reference must name its target; context requires an empty reference")
        if not isinstance(value["path"], str) or not _PATH.fullmatch(value["path"]):
            raise ValueError("Obligation path must contain dotted object field names")
        if not isinstance(value["operator"], str) or value["operator"] not in _OPERATORS:
            raise ValueError("Unknown adequacy comparison")
        expected = value["expected"]
        if not isinstance(expected, (str, int, float, bool, type(None))):
            raise ValueError("Obligation comparisons require a JSON scalar")
        canonical_digest(expected)
        if not isinstance(expected, (int, float)) or isinstance(expected, bool):
            if value["operator"] not in {"==", "!="}:
                raise ValueError("Ordered adequacy comparisons require numbers")
        _text(value["rationale"], "Obligation rationale")
        about = value.get("about")
        if about is not None:
            if (not isinstance(about, str) or not re.fullmatch(r"(?:assumption|objection):[A-Za-z_][A-Za-z_0-9]*", about)):
                raise ValueError("Obligation about must name assumption:<id> or objection:<id>")
            if value["role"] != about.partition(":")[0]:
                raise ValueError("Obligation role must match its assumption/objection relation")
        return cls(**value)


@dataclass(frozen=True)
class AdequacyContract:
    """A reviewed host mapping, pinned to an instantiated EAL source.

    A trusted scheme host may derive source_digest and statement after typed
    substitution into its reviewed template. Passing model-generated metadata
    here does not constitute semantic review.
    """
    source_digest: str
    claim: str
    statement: str
    environment: str
    methods: tuple[str, ...]
    correspondence: str
    obligations: tuple[EvidenceObligation, ...]
    premise_bindings: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AdequacyContract":
        fields = {"source_digest", "claim", "statement", "environment", "methods", "correspondence", "obligations"}
        if not isinstance(value, dict) or set(value) - fields - {"premise_bindings"} or not fields <= set(value):
            raise ValueError("Adequacy contract has missing or unknown fields")
        if not isinstance(value["source_digest"], str) or not _SHA.fullmatch(value["source_digest"]):
            raise ValueError("Adequacy contract requires an exact lowercase source SHA-256")
        for key in ("claim", "environment"):
            if not isinstance(value[key], str) or not _ID.fullmatch(value[key]):
                raise ValueError(f"Adequacy {key} must be an EAL identifier")
        _text(value["statement"], "Claim statement", 65536)
        methods = value["methods"]
        from .methods import is_method_identifier
        if (not isinstance(methods, list) or not 1 <= len(methods) <= 128
                or any(not is_method_identifier(item) for item in methods)
                or len(set(methods)) != len(methods)):
            raise ValueError("Adequacy methods require one to 128 distinct versioned identifiers")
        if not isinstance(value["correspondence"], str) or value["correspondence"] not in {"reviewed_source", "unresolved"}:
            raise ValueError("Correspondence must be reviewed_source or unresolved")
        raw = value["obligations"]
        if not isinstance(raw, list) or len(raw) > 256:
            raise ValueError("Adequacy requires at most 256 obligations")
        obligations = tuple(EvidenceObligation.from_dict(item) for item in raw)
        if len({item.id for item in obligations}) != len(obligations):
            raise ValueError("Adequacy obligation identifiers must be unique")
        bindings = value.get("premise_bindings", [])
        if not isinstance(bindings, list) or len(bindings) > 256:
            raise ValueError("At most 256 formal premise bindings are supported")
        identities = set()
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) != {"argument", "formula", "claim"}:
                raise ValueError("Formal premise bindings require argument, formula and claim")
            if any(not isinstance(binding[key], str) or not _ID.fullmatch(binding[key]) for key in ("argument", "claim")):
                raise ValueError("Formal premise bindings must name EAL argument and claim identifiers")
            # The deductive method separately checks formula syntax and bounds.
            identity = (binding["argument"], canonical_digest(binding["formula"]))
            if identity in identities:
                raise ValueError("A formal premise has multiple correspondence bindings")
            identities.add(identity)
        return cls(value["source_digest"], value["claim"], value["statement"], value["environment"],
                   tuple(methods), value["correspondence"], obligations, tuple(bindings))

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "methods": list(self.methods),
                "obligations": [asdict(item) for item in self.obligations],
                "premise_bindings": list(self.premise_bindings)}


class AdequacyRegistry:
    def __init__(self, contracts: Mapping[str, AdequacyContract]):
        self.contracts = dict(contracts)

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "AdequacyRegistry":
        if (not isinstance(document, dict) or set(document) != {"schema", "contracts"}
                or document["schema"] != SCHEMA or not isinstance(document["contracts"], dict)
                or not 1 <= len(document["contracts"]) <= 512):
            raise ValueError("Expected a bounded eal-adequacy/1 contract registry")
        contracts = {}
        for name, value in document["contracts"].items():
            if not isinstance(name, str) or not _ID.fullmatch(name):
                raise ValueError("Adequacy contract identifiers must be EAL identifiers")
            contracts[name] = AdequacyContract.from_dict(value)
        return cls(contracts)

    @classmethod
    def load(cls, path: str | Path) -> "AdequacyRegistry":
        with Path(path).open("rb") as stream:
            return cls.from_document(tomllib.load(stream))

    def assess(self, contract_id: str, **kwargs) -> dict[str, Any]:
        if contract_id not in self.contracts:
            raise ValueError("Unknown adequacy contract")
        return AdequacyEvaluator().assess(self.contracts[contract_id], **kwargs)


def _finding(identifier: str, status: str, reason: str, **details) -> dict[str, Any]:
    return {"id": identifier, "status": status, "reasons": [reason],
            "code": "criterion_satisfied" if status == "satisfied" else
                    "criterion_violated" if status == "violated" else "unresolved_obligation", **details}


class AdequacyEvaluator:
    """Assess host-owned EAL results against separately reviewed obligations.

    The host must retrieve assessment and collection from its own execution
    store, rather than accepting them as the language model's assertions. Their
    consistency is checked here; no digest authenticates an untrusted producer.
    Method extensions work through ordinary registered EAL result fields.
    """
    def __init__(self, *, method_registry=None):
        self.method_registry = method_registry

    def assess(self, contract: AdequacyContract, *, source: str, assessment: Mapping[str, Any],
               collection: Mapping[str, Any], context: Mapping[str, Any],
               prose: str | None = None) -> dict[str, Any]:
        if not isinstance(contract, AdequacyContract):
            raise TypeError("assess requires an AdequacyContract")
        # Direct dataclass construction receives the same checks as loaded JSON/TOML.
        contract = AdequacyContract.from_dict(contract.to_dict())
        if not all(isinstance(item, Mapping) for item in (assessment, collection, context)):
            raise ValueError("Adequacy assessment, collection and context must be mappings")
        canonical_digest(dict(context))
        result = {"schema": RESULT_SCHEMA, "status": "unresolved", "claim": contract.claim,
                  "claim_status": None, "source_digest": contract.source_digest,
                  "context_fingerprint": canonical_digest(dict(context)),
                  "assessment_id": assessment.get("assessment_id"), "assessed_at": assessment.get("assessed_at"),
                  "contract_digest": contract.digest, "obligations": [], "reasons": [],
                  "diagnostics": [],
                  "correspondence": {"status": "unresolved", "basis": contract.correspondence,
                                     "statement": contract.statement, "prose_verified": False},
                  "qualifications": ["Adequacy is relative to the reviewed contract; measurement authenticity and unrestricted prose semantics are not established."]}
        try:
            program = parse(source)
            errors = validate(program, registry=self.method_registry)
            if errors:
                raise ValueError("Source fails EAL validation: " + "; ".join(error.message for error in errors))
            if program.source_digest != contract.source_digest:
                raise ValueError("Source differs from the reviewed adequacy contract")
            claim = program.claims.get(contract.claim)
            if claim is None or claim.statement != contract.statement or claim.environment != contract.environment:
                raise ValueError("Claim statement or environment differs from the reviewed mapping")
            if (assessment.get("valid") is not True or assessment.get("source_digest") != program.source_digest
                    or collection.get("source_digest") != program.source_digest
                    or assessment.get("context_fingerprint") != result["context_fingerprint"]
                    or canonical_digest(collection.get("context")) != result["context_fingerprint"]):
                raise ValueError("Assessment/collection identity differs from source or context")
            for key in ("assessment_id", "collection_id"):
                _text(assessment.get(key), key, 256)
            _text(collection.get("collection_id"), "collection_id", 256)
            if assessment["collection_id"] != collection["collection_id"]:
                raise ValueError("Assessment names a different evidence collection")
            if not isinstance(collection.get("records"), Mapping):
                raise ValueError("Collection records must be a mapping")
            from .methods import default_registry
            registry = self.method_registry or default_registry()
            if assessment.get("method_registry_fingerprint") != registry.fingerprint:
                raise ValueError("Assessment uses a different method registry")
            instant = parse_time(assessment.get("assessed_at"))
            assessed_claim = assessment.get("claims", {}).get(contract.claim, {})
            if (assessed_claim.get("statement") != claim.statement
                    or assessed_claim.get("environment") != claim.environment
                    or assessed_claim.get("proposition") != (asdict(claim.proposition) if claim.proposition else None)):
                raise ValueError("Assessed proposition differs from the reviewed claim")
            result["claim_status"] = assessed_claim.get("status")
            if result["claim_status"] not in {"supported", "unsupported", "contested", "out_of_scope"}:
                raise ValueError("Assessment has no recognised claim status")
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            result["reasons"] = [str(exc)]
            result["diagnostics"] = [{"code": "assessment_contract_error", "message": str(exc)}]
            return result

        if contract.correspondence == "reviewed_source" and (prose is None or prose == contract.statement):
            result["correspondence"]["status"] = "satisfied"
            result["correspondence"]["proposition"] = asdict(claim.proposition) if claim.proposition else None
        else:
            result["reasons"].append("Semantic correspondence remains unresolved; only the reviewed claim statement may be delivered as checked.")
        records = collection.get("records", {})
        observations = {}

        def evidence(identifier):
            if identifier not in program.evidence:
                return None, "Evidence reference is undeclared"
            if identifier not in observations:
                declaration = program.evidence[identifier]
                matched = assessment.get("environments", {}).get(declaration.environment, {}).get("status") == "matched"
                verdict = assess_evidence_record(program, identifier, records.get(identifier), instant=instant,
                                                 context=context, environment_matched=matched)
                observations[identifier] = verdict
            verdict = observations[identifier]
            if not verdict.complete or assessment.get("evidence", {}).get(identifier) != verdict.entry:
                return None, "Observation identity, freshness, execution or field checks are incomplete: " + "; ".join(verdict.entry["reasons"])
            return records[identifier]["value"], None

        checks = []
        for obligation in contract.obligations:
            failure = self._relation_error(program, obligation)
            if failure is not None:
                checks.append(_finding(obligation.id, "unresolved", failure, role=obligation.role))
                continue
            if obligation.target == "evidence":
                value, failure = evidence(obligation.reference)
            elif obligation.target == "context":
                value = context
            else:
                value = assessment.get(_TABLES[obligation.target], {}).get(obligation.reference)
                if value is None:
                    failure = "The referenced assessment entry is missing"
                elif obligation.target == "argument" and value.get("reasoning_result", {}).get("status") != "supported":
                    failure = "The referenced computation did not produce a usable result"
            if failure is not None:
                checks.append(_finding(obligation.id, "unresolved", failure, role=obligation.role,
                                       target=obligation.target, reference=obligation.reference,
                                       code="observation_or_computation_unavailable"))
                continue
            checks.append(self._compare(obligation, value))
        result["obligations"] = checks
        by_id = {check["id"]: check for check in checks}
        mapped = {item.about for item in contract.obligations if item.about
                  and by_id[item.id]["status"] == "satisfied"}
        if not any(item.role in {"threshold", "inference"} and item.about is None for item in contract.obligations):
            result["reasons"].append("No executable threshold or inference obligation assesses the main conclusion.")
        relation_gaps = self._required_relations(program, assessment, contract.claim, mapped, evidence,
                                                set(contract.methods), contract.premise_bindings, records,
                                                [item for item in contract.obligations if item.role in {"threshold", "inference"}
                                                 and item.about is None and by_id[item.id]["status"] == "satisfied"])
        result["reasons"].extend(relation_gaps)
        if any(check["status"] == "violated" for check in checks) or result["claim_status"] == "out_of_scope":
            result["status"] = "insufficient"
        elif (result["claim_status"] == "supported" and result["correspondence"]["status"] == "satisfied"
              and checks and all(check["status"] == "satisfied" for check in checks) and not result["reasons"]):
            result["status"] = "adequate"
        if result["claim_status"] != "supported":
            result["reasons"].append(f"EAL claim status is {result['claim_status']}; adequacy cannot supply missing EAL support.")
        result["reasons"].extend(reason for check in checks if check["status"] != "satisfied" for reason in check["reasons"])
        if result["status"] == "adequate":
            result["reasons"].append("Reviewed correspondence, required evidence clauses and an accepted derivation satisfy this adequacy contract.")
        return result

    @staticmethod
    def _compare(obligation, value):
        actual = value
        for part in obligation.path.split("."):
            if not isinstance(actual, Mapping) or part not in actual:
                return _finding(obligation.id, "unresolved", f"Required field {obligation.path!r} is missing", role=obligation.role)
            actual = actual[part]
        numeric = lambda item: type(item) in (int, float)
        expected = obligation.expected
        if not (type(actual) is type(expected) or numeric(actual) and numeric(expected)) or isinstance(actual, (dict, list)):
            return _finding(obligation.id, "unresolved", f"Field {obligation.path!r} has an incompatible type", role=obligation.role,
                            code="incompatible_field_type")
        try:
            canonical_digest(actual)
            holds = _OPERATORS[obligation.operator](actual, expected)
        except (ValueError, TypeError, OverflowError):
            return _finding(obligation.id, "unresolved", "Comparison is nonfinite or incompatible", role=obligation.role)
        return _finding(obligation.id, "satisfied" if holds else "violated",
                        f"{obligation.reference or 'context'}.{obligation.path} {obligation.operator} {expected!r} "
                        f"{'holds' if holds else 'does not hold'}", role=obligation.role, actual=actual,
                        target=obligation.target, reference=obligation.reference, rationale=obligation.rationale)

    @staticmethod
    def _relation_error(program, obligation):
        if obligation.about is None:
            return None
        kind, _, name = obligation.about.partition(":")
        table = program.assumptions if kind == "assumption" else program.objections
        if name not in table:
            return "The addressed assumption or objection is undeclared"
        relation = table[name]
        evidence_ids = {relation.validation} if kind == "assumption" else set(relation.evidence)
        premise_ids = set() if kind == "assumption" else set(relation.premises)
        if not ((obligation.target == "evidence" and obligation.reference in evidence_ids)
                or (obligation.target == "claim" and obligation.reference in premise_ids)):
            return "Relation adequacy must inspect that assumption/objection's own evidence or premise claim"
        return None

    @staticmethod
    def _required_relations(program, assessment, claim_id, mapped, evidence, allowed_methods, premise_bindings, records, main_clauses):
        """Find a covered accepted derivation, preserving independent alternatives."""
        cache = {}

        def claim_gaps(name):
            if name in cache:
                return cache[name]
            candidates = []
            for argument_id, argument in program.arguments.items():
                entry = assessment.get("arguments", {}).get(argument_id, {})
                if argument.conclusion != name or entry.get("status") != "supported":
                    continue
                gaps = []
                method = program.reasoning[argument.reasoning].method
                source_ids = set(argument.evidence) | set(program.reasoning[argument.reasoning].backing)
                source_ids.update(program.assumptions[a].validation for a in argument.assumptions)
                if name == claim_id and not any(
                        (item.target == "evidence" and item.reference in source_ids)
                        or (item.target == "argument" and item.reference == argument_id
                            and item.path.startswith(("reasoning_result.details.", "reasoning_result.binding.")))
                        for item in main_clauses):
                    gaps.append(f"Argument {argument_id!r} has no satisfied main criterion on its evidence or computed result.")
                if method not in allowed_methods:
                    gaps.append(f"Accepted argument {argument_id!r} uses unreviewed method {method!r}.")
                if method == "deductive/1":
                    logical_id = next((item for item in source_ids if program.evidence[item].kind == "logical_case"), None)
                    payload = records.get(logical_id, {}).get("value", {})
                    if argument.binding == logical_id and program.claims[name].proposition is not None:
                        payload = payload.get("payload", {})
                    formal = payload.get("premises", []) if isinstance(payload, dict) else []
                    bindings = {canonical_digest(row["formula"]): row["claim"] for row in premise_bindings
                                if row["argument"] == argument_id}
                    for formula in formal:
                        bound = bindings.get(canonical_digest(formula))
                        if (bound not in argument.premises or
                                assessment.get("claims", {}).get(bound, {}).get("status") != "supported"):
                            gaps.append(f"Deductive argument {argument_id!r} has an undisclosed or unsupported formal premise: {formula!r}.")
                    if any(key not in {canonical_digest(formula) for formula in formal} for key in bindings):
                        gaps.append(f"Deductive argument {argument_id!r} has a binding to an absent formal premise.")
                for assumption in argument.assumptions:
                    if f"assumption:{assumption}" not in mapped:
                        gaps.append(f"Assumption {assumption!r} has no satisfied evidence-adequacy mapping; its use remains conditional.")
                for premise in argument.premises:
                    gaps.extend(claim_gaps(premise))
                relevant = set()
                pending = [(kind, target) for kind, target in (("claim", name), ("argument", argument_id), ("reasoning", argument.reasoning))]
                pending.extend(("assumption", item) for item in argument.assumptions)
                while pending:
                    target_kind, target = pending.pop()
                    for objection_id, objection in program.objections.items():
                        if (objection_id in relevant or objection.target_kind != target_kind or objection.target != target
                                or assessment.get("objections", {}).get(objection_id, {}).get("environment") != program.claims[name].environment):
                            continue
                        relevant.add(objection_id)
                        pending.append(("objection", objection_id))
                        if f"objection:{objection_id}" not in mapped:
                            gaps.append(f"Objection {objection_id!r} has no satisfied evidence-adequacy mapping.")
                        for identifier in objection.evidence:
                            _, failure = evidence(identifier)
                            if failure:
                                gaps.append(f"Objection {objection_id!r}: {failure}")
                candidates.append(gaps)
            if not candidates:
                answer = [f"Claim {name!r} has no accepted derivation."]
            else:
                answer = min(candidates, key=lambda gaps: (len(gaps), tuple(gaps)))
            cache[name] = answer
            return answer

        return claim_gaps(claim_id)
