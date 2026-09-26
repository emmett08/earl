"""Persistent, host-executed argument schemes for plain-text requests.

A scheme pins an EAL programme, typed subject bindings and its adequacy
obligations. The built-in recogniser handles reviewed surface forms; installed
recognisers can propose richer argument structures. A proposal alone never
establishes that a formal claim represents unrestricted natural language.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import string
import sys
import tomllib
from typing import Any, Collection, Protocol

from antlr4 import InputStream

from .artifacts import _claim_closure, _require_complete_collection
from .evaluator import canonical_digest, evaluate
from .generated.EALLexer import EALLexer
from .parser import MAX_SOURCE_BYTES, parse
from .runtime import ReasoningService, bounded_path, strict_json
from .store import utc_now


SCHEMA = "eal2-argument-schemes/1"
_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_KINDS = {"claim", "decision", "action"}


class ArgumentRecogniser(Protocol):
    """Trusted host plug-in proposing argument roles and typed bindings."""

    def recognise(self, prose: str, context: dict, schemes: dict) -> list[dict]: ...


class CorrespondenceValidator(Protocol):
    """Independent host component checking an unrestricted interpretation.

    Returning satisfied is a deployment-supplied semantic judgement, not a
    consequence of the span or type checks implemented by this module.
    """

    def validate(self, prose: str, scheme_id: str, bindings: dict,
                 context: dict, candidate: dict) -> dict: ...


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise ValueError(f"{name} must be nonempty UTF-8 text of at most {limit} bytes")
    return value


def _object(value: Any, name: str, limit: int = 65536) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    encoded = _json(value)
    if len(encoded.encode("utf-8")) > limit:
        raise ValueError(f"{name} exceeds its byte limit")
    return strict_json(encoded)


def _get(context: dict, path: str) -> Any:
    value: Any = context
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _set(context: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    target = context
    for part in parts[:-1]:
        if part in target and not isinstance(target[part], dict):
            raise ValueError(f"Context path {path!r} conflicts with an existing scalar")
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _merge(old: dict, new: dict) -> dict:
    result = deepcopy(old)
    for key, value in new.items():
        result[key] = _merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


@dataclass(frozen=True)
class SchemeParameter:
    kind: str
    context_path: str
    source_literal: str
    values: tuple[Any, ...] | None = None

    def check(self, value: Any, *, captured: bool = False) -> Any:
        if captured:
            if self.kind == "integer" and re.fullmatch(r"-?(?:0|[1-9][0-9]{0,17})", value):
                value = int(value)
            elif self.kind == "boolean" and value.casefold() in {"true", "false"}:
                value = value.casefold() == "true"
        expected_type = {"string": str, "integer": int, "boolean": bool}[self.kind]
        if type(value) is not expected_type:
            raise ValueError(f"Binding must have type {self.kind}")
        if isinstance(value, str) and (not value or len(value.encode("utf-8")) > 256):
            raise ValueError("String binding must contain one to 256 UTF-8 bytes")
        if self.values is not None and not any(type(value) is type(item) and value == item for item in self.values):
            raise ValueError("Binding is outside the scheme's declared domain")
        return value


@dataclass(frozen=True)
class ArgumentScheme:
    source: str
    source_sha256: str
    method_registry_fingerprint: str
    claim: str
    kind: str
    description: str
    forms: tuple[str, ...]
    followups: tuple[str, ...]
    parameters: dict[str, SchemeParameter]
    context: dict
    adequacy: dict | None


def _form_pattern(form: str, parameters: dict[str, SchemeParameter]) -> re.Pattern:
    """Compile bounded literal/slot forms, without operator-supplied regex."""
    parts = []
    seen: set[str] = set()
    for literal, name, spec, conversion in string.Formatter().parse(form.strip().rstrip("?.!")):
        parts.append("".join(r"\s+" if piece.isspace() else re.escape(piece)
                             for piece in re.split(r"(\s+)", literal)))
        if name is None:
            continue
        if name not in parameters or spec or conversion:
            raise ValueError("Surface forms may contain only declared {parameter} slots")
        if name in seen:
            parts.append(f"(?P={name})")
        else:
            # Each slot is one lexical entity; multiword values use explicit
            # trusted context or an installed recogniser, not greedy guessing.
            parts.append(f"(?P<{name}>[A-Za-z0-9_+-][A-Za-z0-9_.:/@+-]{{0,255}})")
            seen.add(name)
    return re.compile("".join(parts) + r"[?.!]*", re.IGNORECASE | re.ASCII)


def _substitute(source: str, replacements: dict[str, Any]) -> str:
    """Replace complete string tokens, never splice input into EAL syntax."""
    edits = []
    lexer = EALLexer(InputStream(source))
    for token in lexer.getAllTokens():
        if token.type == EALLexer.STRING:
            literal = json.loads(token.text)
            if literal in replacements:
                edits.append((token.start, token.stop + 1, _json(replacements[literal])))
    for start, end, value in reversed(edits):
        source = source[:start] + value + source[end:]
    return source


def _replace_values(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace_values(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_values(item, replacements) for key, item in value.items()}
    return value


class ArgumentHost:
    """Bind one authenticated principal/session to executable argument schemes."""

    def __init__(self, service: ReasoningService, schemes: dict[str, ArgumentScheme], *,
                 principal: str, session_id: str, authorised_schemes: Collection[str] | None = None,
                 recogniser: ArgumentRecogniser | None = None,
                 correspondence_validator: CorrespondenceValidator | None = None):
        self.service = service
        self.principal = _text(principal, "principal", 128)
        self.session_id = _text(session_id, "session_id", 128)
        self._key = canonical_digest({"principal": principal, "session_id": session_id})
        if authorised_schemes is not None and (not isinstance(authorised_schemes, (list, tuple, set, frozenset))
                                              or len(authorised_schemes) > 128):
            raise ValueError("Scheme grants must be a bounded collection of identifiers")
        grants = set(schemes) if authorised_schemes is None else set(authorised_schemes)
        if any(not isinstance(key, str) for key in grants) or not grants <= schemes.keys():
            raise ValueError("Scheme grant contains unknown schemes")
        self.schemes = {key: deepcopy(value) for key, value in schemes.items() if key in grants}
        self.recogniser = recogniser
        self.correspondence_validator = correspondence_validator
        from dataclasses import asdict
        self.fingerprint = canonical_digest(strict_json(_json({key: asdict(value) for key, value in self.schemes.items()})))
        self._patterns = {key: [(form, _form_pattern(form, scheme.parameters), False) for form in scheme.forms]
                          + [(form, _form_pattern(form, scheme.parameters), True) for form in scheme.followups]
                          for key, scheme in self.schemes.items()}
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS argument_sessions "
                               "(session_key TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)")
        for key in self.schemes:
            self._source(key)

    @classmethod
    def load(cls, service: ReasoningService, path: str | Path, *, principal: str,
             session_id: str, authorised_schemes: Collection[str] | None = None,
             recogniser: ArgumentRecogniser | None = None,
             correspondence_validator: CorrespondenceValidator | None = None) -> "ArgumentHost":
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
        if (set(document) != {"schema", "schemes"} or document["schema"] != SCHEMA
                or not isinstance(document["schemes"], dict) or not 1 <= len(document["schemes"]) <= 128):
            raise ValueError("Expected a bounded eal2-argument-schemes/1 catalogue")
        schemes = {}
        required = {"source", "source_sha256", "claim", "kind", "forms"}
        optional = {"description", "parameters", "context", "followups", "adequacy", "method_registry_fingerprint"}
        for name, raw in document["schemes"].items():
            if not _ID.fullmatch(name) or not isinstance(raw, dict) or not required <= raw.keys() or raw.keys() - required - optional:
                raise ValueError("Scheme requires a valid ID and exact configuration fields")
            relative = raw["source"]
            if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts or not relative.endswith(".eal"):
                raise ValueError("Scheme source must be a workspace-relative EAL file")
            if not isinstance(raw["source_sha256"], str) or not _SHA.fullmatch(raw["source_sha256"]):
                raise ValueError("Scheme source_sha256 must be a lowercase SHA-256 digest")
            method_id = raw.get("method_registry_fingerprint", service.method_registry.fingerprint)
            if not isinstance(method_id, str) or not _SHA.fullmatch(method_id):
                raise ValueError("Scheme method fingerprint must be a lowercase SHA-256 digest")
            if not isinstance(raw["claim"], str) or not _ID.fullmatch(raw["claim"]) or raw["kind"] not in _KINDS:
                raise ValueError("Scheme requires a claim ID and kind claim, decision or action")
            forms, followups = raw["forms"], raw.get("followups", [])
            if not isinstance(forms, list) or not 1 <= len(forms) <= 32 or not isinstance(followups, list) or len(followups) > 16:
                raise ValueError("Scheme forms and followups must be bounded lists")
            for form in forms + followups:
                _text(form, "surface form", 512)
            raw_parameters = raw.get("parameters", {})
            if not isinstance(raw_parameters, dict) or len(raw_parameters) > 8:
                raise ValueError("Scheme has too many parameters")
            parameters = {}
            for key, spec in raw_parameters.items():
                if (not _ID.fullmatch(key) or not isinstance(spec, dict)
                        or not {"kind", "context_path"} <= spec.keys()
                        or spec.keys() - {"kind", "context_path", "source_literal", "values"}
                        or spec["kind"] not in {"string", "integer", "boolean"}
                        or not isinstance(spec["context_path"], str) or not _PATH.fullmatch(spec["context_path"])):
                    raise ValueError("Parameter requires a supported type and context path")
                marker = spec.get("source_literal", "$" + key)
                _text(marker, "source_literal", 128)
                values = spec.get("values")
                if values is not None and (not isinstance(values, list) or not 1 <= len(values) <= 256):
                    raise ValueError("Parameter values must be a nonempty bounded list")
                parameter = SchemeParameter(spec["kind"], spec["context_path"], marker,
                                            None if values is None else tuple(values))
                for value in values or []:
                    parameter.check(value)
                parameters[key] = parameter
            markers = [item.source_literal for item in parameters.values()]
            paths = [item.context_path for item in parameters.values()]
            if len(set(markers)) != len(markers) or len(set(paths)) != len(paths):
                raise ValueError("Parameters must have distinct source literals and context paths")
            if any(a.startswith(b + ".") for a in paths for b in paths if a != b):
                raise ValueError("Parameter context paths cannot overlap")
            adequacy = raw.get("adequacy")
            if adequacy is not None:
                adequacy = _object(adequacy, "adequacy")
                if set(adequacy) - {"correspondence", "obligations", "premise_bindings"}:
                    raise ValueError("Scheme adequacy supplies correspondence and obligations; claim identity is derived")
            schemes[name] = ArgumentScheme(relative, raw["source_sha256"], method_id,
                raw["claim"], raw["kind"], _text(raw.get("description", name), "description", 1024),
                tuple(forms), tuple(followups), parameters, _object(raw.get("context", {}), "context"), adequacy)
        return cls(service, schemes, principal=principal, session_id=session_id,
                   authorised_schemes=authorised_schemes, recogniser=recogniser,
                   correspondence_validator=correspondence_validator)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.service.store.path, timeout=30)

    def _session(self) -> tuple[int, dict]:
        with self._connect() as connection:
            row = connection.execute("SELECT revision,payload FROM argument_sessions WHERE session_key=?", (self._key,)).fetchone()
        return (0, {}) if row is None else (row[0], json.loads(row[1]))

    def _save_session(self, expected: int, payload: dict) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision FROM argument_sessions WHERE session_key=?", (self._key,)).fetchone()
            current = 0 if row is None else row[0]
            if current != expected:
                raise ValueError("Session changed concurrently; resolve the request again")
            connection.execute("INSERT INTO argument_sessions VALUES (?,?,?) ON CONFLICT(session_key) "
                               "DO UPDATE SET revision=excluded.revision,payload=excluded.payload",
                               (self._key, current + 1, _json(payload)))
        return current + 1

    def _source(self, scheme_id: str) -> str:
        scheme = self.schemes[scheme_id]
        if scheme.method_registry_fingerprint != self.service.method_registry.fingerprint:
            raise ValueError("Scheme method registry changed")
        path = bounded_path(self.service.workspace, scheme.source)
        if not path.is_file():
            raise ValueError("Scheme source must be a regular file")
        with path.open("rb") as stream:
            content = stream.read(MAX_SOURCE_BYTES + 1)
        if len(content) > MAX_SOURCE_BYTES or hashlib.sha256(content).hexdigest() != scheme.source_sha256:
            raise ValueError("Scheme source differs from its pinned digest")
        source = content.decode("utf-8")
        template = parse(source)
        if scheme.claim not in template.claims:
            raise ValueError("Scheme claim is absent from its EAL source")
        literals = {json.loads(token.text) for token in EALLexer(InputStream(source)).getAllTokens() if token.type == EALLexer.STRING}
        for parameter in scheme.parameters.values():
            if parameter.source_literal not in literals:
                raise ValueError("Scheme parameter has no complete source literal")
        return source

    def instantiate(self, scheme_id: str, bindings: dict, context: dict) -> str:
        """Generate and validate a scope-bound instance of the pinned programme."""
        if scheme_id not in self.schemes:
            raise ValueError("Unknown or ungranted scheme")
        scheme = self.schemes[scheme_id]
        if set(bindings) != set(scheme.parameters):
            raise ValueError("Bindings must name every scheme parameter exactly once")
        replacements = {}
        for key, parameter in scheme.parameters.items():
            value = parameter.check(bindings[key])
            actual = _get(context, parameter.context_path)
            if type(actual) is not type(value) or actual != value:
                raise ValueError("Scheme binding differs from context")
            replacements[parameter.source_literal] = value
        template_source = self._source(scheme_id)
        source = _substitute(template_source, replacements)
        template, program = parse(template_source), parse(source)
        # Typed literal substitution may never replace tools or inference methods.
        if program.tools != template.tools or {key: item.method for key, item in program.reasoning.items()} != {key: item.method for key, item in template.reasoning.items()}:
            raise ValueError("Parameter substitution cannot change tool or method selectors")
        checked = self.service.validate(source)
        if not checked["valid"]:
            raise ValueError("Instantiated scheme is invalid: " + "; ".join(item["message"] for item in checked["diagnostics"]))
        environment = program.environments[program.claims[scheme.claim].environment]
        for key, parameter in scheme.parameters.items():
            if not any(item.path == parameter.context_path and item.operator == "=="
                       and type(item.expected) is type(bindings[key]) and item.expected == bindings[key]
                       for item in environment.predicates):
                raise ValueError(f"Claim environment does not constrain binding {key!r}")
        return source

    def describe(self) -> dict:
        descriptions = {}
        for name, scheme in self.schemes.items():
            program = parse(self._source(name))
            closure = _claim_closure(program, scheme.claim)
            descriptions[name] = {"kind": scheme.kind, "description": scheme.description,
                "claim": scheme.claim, "forms": list(scheme.forms), "followups": list(scheme.followups),
                "parameters": {key: {"kind": value.kind, "context_path": value.context_path,
                                      "values": None if value.values is None else list(value.values)}
                               for key, value in scheme.parameters.items()},
                "argument_form": {"conclusion": program.claims[scheme.claim].statement,
                    "premises": sorted(closure.claims - {scheme.claim}),
                    "methods": sorted({program.reasoning[item].method for item in closure.reasoning}),
                    "evidence_roles": [{"id": item, "kind": program.evidence[item].kind,
                                        "tool": program.evidence[item].tool} for item in sorted(closure.evidence)],
                    "assumptions": sorted(closure.assumptions), "objections": sorted(closure.objections),
                    "adequacy_obligations": [] if scheme.adequacy is None else deepcopy(scheme.adequacy.get("obligations", []))}}
        return {"schema": SCHEMA, "catalogue_fingerprint": self.fingerprint,
                "recognition": "Reviewed typed surface forms; installed proposals require independent correspondence validation",
                "schemes": descriptions}

    def _bindings(self, scheme: ArgumentScheme, supplied: dict, explicit: dict,
                  previous: dict, *, captured: bool) -> tuple[dict, dict]:
        if set(supplied) - scheme.parameters.keys():
            raise ValueError("Candidate contains an undeclared parameter")
        context = _merge(_merge(scheme.context, previous), explicit)
        bindings = {}
        for key, parameter in scheme.parameters.items():
            if key in supplied:
                value = parameter.check(supplied[key], captured=captured)
                fixed = _get(explicit, parameter.context_path)
                if fixed is not None and (type(fixed) is not type(value) or fixed != value):
                    raise ValueError("Prose binding conflicts with explicit host context")
                _set(context, parameter.context_path, value)
            else:
                value = parameter.check(_get(context, parameter.context_path))
            bindings[key] = value
        return bindings, context

    def _candidate(self, prose: str, candidate: dict) -> None:
        if (not isinstance(candidate, dict) or set(candidate) != {"scheme_id", "bindings", "spans", "task_kind"}
                or candidate["scheme_id"] not in self.schemes or not isinstance(candidate["bindings"], dict)
                or candidate["task_kind"] != self.schemes[candidate["scheme_id"]].kind
                or not isinstance(candidate["spans"], list) or not 1 <= len(candidate["spans"]) <= 32):
            raise ValueError("Interpretation proposal requires a granted scheme, typed bindings, task kind and text spans")
        roles = set()
        for span in candidate["spans"]:
            if (not isinstance(span, dict) or set(span) != {"role", "start", "end", "text"}
                    or span["role"] not in {"conclusion", "premise", "decision", "action", "scope", "condition"}
                    or type(span["start"]) is not int or type(span["end"]) is not int
                    or not 0 <= span["start"] < span["end"] <= len(prose)
                    or prose[span["start"]:span["end"]] != span["text"]):
                raise ValueError("Interpretation text span differs from the actual request")
            roles.add(span["role"])
        required_role = "conclusion" if candidate["task_kind"] == "claim" else candidate["task_kind"]
        if required_role not in roles:
            raise ValueError("Interpretation omits the requested conclusion, decision or action")

    def resolve(self, prose: str, context: dict | None = None, proposal: dict | None = None, *,
                routing_candidate: dict | None = None) -> dict:
        prose = _text(prose, "prose")
        explicit = _object({} if context is None else context, "context")
        proposal = None if proposal is None else _object(proposal, "proposal")
        routing_candidate = None if routing_candidate is None else _object(routing_candidate, "routing_candidate")
        revision, previous = self._session()
        # Catalogue changes invalidate inherited interpretation, not merely a label.
        if previous.get("catalogue_fingerprint") != self.fingerprint:
            previous = {}
        matched, failures, candidates = [], [], []
        for name, scheme in self.schemes.items():
            for form, pattern, followup in self._patterns[name]:
                if followup and previous.get("scheme_id") != name:
                    continue
                match = pattern.fullmatch(prose.strip().rstrip("?.!"))
                if match is None:
                    continue
                try:
                    inherited = previous.get("context", {}) if previous.get("scheme_id") == name else {}
                    bindings, bound_context = self._bindings(scheme, match.groupdict(), explicit, inherited, captured=True)
                    source = self.instantiate(name, bindings, bound_context)
                    matched.append((name, bindings, bound_context, source,
                                    {"status": "satisfied", "profile": "typed_templates/1", "form": form}))
                except (ValueError, TypeError) as exc:
                    failures.append(str(exc))
        if routing_candidate is not None:
            candidates.append(routing_candidate)
        if self.recogniser is not None:
            proposed = self.recogniser.recognise(prose, _merge(previous.get("context", {}), explicit), self.describe()["schemes"])
            if not isinstance(proposed, list) or len(proposed) > 16:
                raise ValueError("Recogniser returned an invalid candidate list")
            candidates.extend(proposed)
        for candidate in candidates:
            try:
                self._candidate(prose, candidate)
                name = candidate["scheme_id"]
                scheme = self.schemes[name]
                inherited = previous.get("context", {}) if previous.get("scheme_id") == name else {}
                bindings, bound_context = self._bindings(scheme, candidate["bindings"], explicit, inherited, captured=False)
                source = self.instantiate(name, bindings, bound_context)
                if self.correspondence_validator is None:
                    failures.append("Candidate argument roles require independent correspondence validation")
                    continue
                checked = self.correspondence_validator.validate(prose, name, deepcopy(bindings), deepcopy(bound_context), deepcopy(candidate))
                if not isinstance(checked, dict) or checked.get("status") != "satisfied" or not isinstance(checked.get("method"), str) or not checked["method"]:
                    failures.append("Independent correspondence validation did not establish applicability")
                    continue
                matched.append((name, bindings, bound_context, source,
                                {"status": "satisfied", "profile": "installed_validator/1",
                                 "interpretation": deepcopy(candidate), "validation": _object(checked, "validation")}))
            except (ValueError, TypeError) as exc:
                failures.append(str(exc))
        unique = {}
        for entry in matched:
            unique[canonical_digest({"scheme": entry[0], "bindings": entry[1], "context": entry[2]})] = entry
        if len(unique) != 1:
            self._save_session(revision, {"catalogue_fingerprint": self.fingerprint, "assessment_id": None,
                "request_digest": canonical_digest({"prose": prose, "context": explicit,
                                                    "proposal": proposal, "routing_candidate": routing_candidate})})
            return {"status": "ambiguous" if len(unique) > 1 else "unresolved", "reasons": sorted(set(failures)) or ["No unique checked argument scheme represents this request"],
                    "candidate_schemes": sorted({item[0] for item in matched}),
                    "candidates": candidates, "tool_execution": False}
        name, bindings, bound_context, source, correspondence = next(iter(unique.values()))
        scheme, program = self.schemes[name], parse(source)
        closure = _claim_closure(program, scheme.claim)
        result = {"status": "resolved", "scheme_id": name, "task_kind": scheme.kind,
                  "bindings": bindings, "context": bound_context, "claim": scheme.claim,
                  "statement": program.claims[scheme.claim].statement,
                  "source_digest": program.source_digest, "template_digest": scheme.source_sha256,
                  "correspondence": correspondence, "catalogue_fingerprint": self.fingerprint,
                  "prose_digest": hashlib.sha256(prose.encode("utf-8")).hexdigest(),
                  "request_digest": canonical_digest({"prose": prose, "context": bound_context, "proposal": proposal}),
                  "proposal_digest": None if proposal is None else canonical_digest(proposal),
                  "obligations": {"evidence": sorted(closure.evidence), "premises": sorted(closure.claims - {scheme.claim}),
                                  "assumptions": sorted(closure.assumptions), "objections": sorted(closure.objections),
                                  "methods": sorted({program.reasoning[item].method for item in closure.reasoning})}}
        payload = {"catalogue_fingerprint": self.fingerprint, "scheme_id": name, "context": bound_context,
                   "request_digest": result["request_digest"], "assessment_id": None}
        result["session_revision"] = self._save_session(revision, payload)
        return result

    def _adequacy_contract(self, scheme: ArgumentScheme, resolution: dict, source: str):
        if scheme.adequacy is None:
            return None
        from .adequacy import AdequacyContract
        program = parse(source)
        replacements = {item.source_literal: resolution["bindings"][key] for key, item in scheme.parameters.items()}
        raw = _replace_values(scheme.adequacy, replacements)
        raw.update(source_digest=program.source_digest, claim=scheme.claim,
                   statement=program.claims[scheme.claim].statement,
                   environment=program.claims[scheme.claim].environment,
                   methods=resolution["obligations"]["methods"])
        return AdequacyContract.from_dict(raw)

    def _adequacy(self, scheme: ArgumentScheme, resolution: dict, source: str,
                  assessment: dict, collection: dict) -> dict:
        contract = self._adequacy_contract(scheme, resolution, source)
        if contract is None:
            return {"status": "unresolved", "reasons": ["The scheme has no evidence-adequacy contract"]}
        from .adequacy import AdequacyEvaluator
        return AdequacyEvaluator(method_registry=self.service.method_registry).assess(contract, source=source,
                    assessment=assessment, collection=collection, context=resolution["context"])

    def assess(self, prose: str, context: dict | None = None, proposal: dict | None = None, *,
               routing_candidate: dict | None = None) -> dict:
        resolution = self.resolve(prose, context, proposal, routing_candidate=routing_candidate)
        if resolution["status"] != "resolved":
            return resolution
        scheme = self.schemes[resolution["scheme_id"]]
        source = self.instantiate(resolution["scheme_id"], resolution["bindings"], resolution["context"])
        self._adequacy_contract(scheme, resolution, source)  # Reject malformed configuration before IO.
        collection = self.service.collect(source, resolution["context"], resolution["obligations"]["evidence"])
        assessment = self.service.reason(source, resolution["context"], collection["collection_id"])
        complete = True
        try:
            _require_complete_collection(parse(source), set(resolution["obligations"]["evidence"]), collection, assessment)
        except ValueError:
            complete = False
        adequacy = self._adequacy(scheme, resolution, source, assessment, collection)
        raw_status = assessment["claims"][scheme.claim]["status"]
        status = raw_status if complete and adequacy["status"] == "adequate" else "unresolved"
        answer_text = (f"Supported within the recorded scope: {resolution['statement']}"
                       if status == "supported" else
                       f"The claim remains {status}: {resolution['statement']} EAL status: {raw_status}; evidence adequacy: {adequacy['status']}.")
        packet = {"schema": "eal2-argument-answer/1", "assessment_id": assessment["assessment_id"],
                  "status": status, "raw_status": raw_status, "claim": scheme.claim,
                  "statement": resolution["statement"], "scheme_id": resolution["scheme_id"],
                  "task_kind": scheme.kind, "adequacy": adequacy, "collection_complete": complete,
                  "correspondence": resolution["correspondence"], "verification": "server_assessment",
                  "source_digest": resolution["source_digest"], "template_digest": scheme.source_sha256,
                  "method_registry_fingerprint": self.service.method_registry.fingerprint,
                  "context": resolution["context"], "context_fingerprint": canonical_digest(resolution["context"]),
                  "proposal_digest": resolution["proposal_digest"], "request_digest": resolution["request_digest"],
                  "prose_digest": resolution["prose_digest"],
                  "collection_id": collection["collection_id"], "assessed_at": assessment["assessed_at"],
                  "resolution": resolution,
                  "checked_answer": {"status": status, "statement": resolution["statement"], "text": answer_text,
                     "scope": resolution["context"], "assessment_id": assessment["assessment_id"],
                     "qualification": "Support is conditional on the declared scheme, evidence-adequacy contract and recorded context."}}
        revision, state = self._session()
        if revision != resolution["session_revision"] or state.get("request_digest") != resolution["request_digest"]:
            raise ValueError("Session changed during collection; reassess the active request")
        state["assessment_id"] = assessment["assessment_id"]
        packet["session_revision"] = self._save_session(revision, state)
        self.service.store.put("argument_packet", packet,
            record_id=f"argument:{self._key}:{assessment['assessment_id']}")
        return packet

    def finish(self, assessment_id: str) -> dict:
        assessment_id = _text(assessment_id, "assessment_id", 128)
        try:
            packet = self.service.store.get(f"argument:{self._key}:{assessment_id}", kind="argument_packet")
        except KeyError as exc:
            raise ValueError("Assessment was not issued for this principal and session") from exc
        revision, state = self._session()
        resolution = packet["resolution"]
        if (revision != packet["session_revision"] or state.get("assessment_id") != assessment_id
                or state.get("request_digest") != packet["request_digest"]
                or resolution["catalogue_fingerprint"] != self.fingerprint):
            raise ValueError("Assessment is no longer the active request; reassess")
        source = self.instantiate(resolution["scheme_id"], resolution["bindings"], resolution["context"])
        if parse(source).source_digest != packet["source_digest"]:
            raise ValueError("Instantiated source changed; reassess")
        collection = {**self.service.store.get(packet["collection_id"], kind="collection"),
                      "collection_id": packet["collection_id"]}
        original = {**self.service.store.get(assessment_id, kind="assessment"),
                    "assessment_id": assessment_id}
        current = evaluate(parse(source), collection["records"], now=utc_now(),
                           context=resolution["context"], registry=self.service.method_registry)
        _require_complete_collection(parse(source), set(resolution["obligations"]["evidence"]), collection, current)
        # Recheck temporal validity separately from the immutable assessment:
        # a historical ID must never be relabelled as a newly evaluated record.
        if any(current.get(key) != original.get(key) for key in
               ("claims", "evidence", "assumptions", "arguments", "objections", "environments")):
            raise ValueError("Assessment validity changed with time or evidence; reassess")
        adequacy = self._adequacy(self.schemes[resolution["scheme_id"]], resolution, source, original, collection)
        if adequacy != packet["adequacy"]:
            raise ValueError("Stored adequacy assessment differs from its checked dependencies")
        return packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve and execute a plain-text request through EAL argument schemes")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--schemes", type=Path, required=True)
    parser.add_argument("--principal", default="local")
    parser.add_argument("--session-id", default="default")
    parser.add_argument("--scheme-grant", action="append")
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--prose")
    request.add_argument("--input", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--routing-candidate", type=Path)
    parser.add_argument("--assessment-id")
    parser.add_argument("--resolve", action="store_true")
    args = parser.parse_args()
    try:
        service = ReasoningService(args.workspace, args.registry, args.database)
        host = ArgumentHost.load(service, args.schemes, principal=args.principal,
                                 session_id=args.session_id, authorised_schemes=args.scheme_grant)
        if args.assessment_id:
            result = host.finish(args.assessment_id)
        else:
            prose = args.prose if args.prose is not None else args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read(4097)
            context = strict_json(args.context.read_text(encoding="utf-8")) if args.context else None
            proposal = strict_json(args.proposal.read_text(encoding="utf-8")) if args.proposal else None
            candidate = strict_json(args.routing_candidate.read_text(encoding="utf-8")) if args.routing_candidate else None
            result = (host.resolve if args.resolve else host.assess)(prose, context, proposal, routing_candidate=candidate)
        print(_json(result))
    except (ValueError, TypeError, OSError, KeyError) as exc:
        print(_json({"status": "unresolved", "error": str(exc)}))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
