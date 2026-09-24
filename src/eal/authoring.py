"""Bounded EAL/2 source authoring with the installed language contracts.

This is a static authoring aid. It never collects observations or awards a
claim status. A valid source still requires independent brief-to-source review.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from itertools import islice
from typing import Any

from .parser import MAX_SOURCE_BYTES, parse
from .runtime import ReasoningService


MAX_TASK_BYTES = 4096
MAX_ATTEMPTS = 8
MAX_REQUIRED_CLAIMS = 64


class AuthoringSession:
    """Supply actual contracts and validate each proposed complete EAL source.

    ``required_claims`` checks identifier presence only. It cannot determine
    whether the claims, their evidence or their rationale express the brief.
    ``propose`` is supplied by the caller and may be a model adapter, a scripted
    fixture or a human interface; it receives a plain JSON-compatible request.
    """

    def __init__(self, service: ReasoningService, *, required_claims: Iterable[str] = ()):
        if not isinstance(service, ReasoningService):
            raise TypeError("service must be a ReasoningService")
        if isinstance(required_claims, (str, bytes)):
            raise ValueError("required_claims must be a collection of claim identifiers")
        claims = tuple(islice(required_claims, MAX_REQUIRED_CLAIMS + 1))
        if len(claims) > MAX_REQUIRED_CLAIMS:
            raise ValueError(f"required_claims cannot exceed {MAX_REQUIRED_CLAIMS} identifiers")
        if any(not isinstance(name, str) or not name for name in claims) or len(set(claims)) != len(claims):
            raise ValueError("required_claims must be unique nonempty strings")
        self.service = service
        self.required_claims = claims

    def reference(self) -> dict[str, Any]:
        """Expose the exact header, complete example and installed method schemas.

        Method contracts come from the *configured* host registry, so custom
        methods are discoverable and model-authored source cannot invent an
        uninstalled version. The bundled example must validate in this host.
        """
        language = self.service.describe()
        example = language["example"]
        if not self.service.validate(example)["valid"]:
            raise ValueError("The configured method registry does not accept the language example")
        return {
            "language": "EAL/2",
            "header": 'language "EAL/2";',
            "language_reference": deepcopy(language),
            "method_contracts": self.service.method_registry.describe(),
            "required_claims": list(self.required_claims),
            "example": example,
            "review_requirement": "Static validity and claim-name presence do not establish brief-to-source fidelity; review scope, evidence, rationale and adverse states independently.",
        }

    def submit(self, source: str) -> dict[str, Any]:
        """Return the service's exact diagnostics and an accepted digest if valid.

        A missing required claim is reported separately from EAL static
        diagnostics; even an accepted candidate remains fidelity-unverified.
        """
        if not isinstance(source, str):
            raise TypeError("source must be a string")
        validation = self.service.validate(source)
        missing = []
        missing_declarations = []
        if validation["valid"]:
            program = parse(source)
            missing = sorted(set(self.required_claims) - set(program.claims))
            if not program.claims:
                missing_declarations.append("claim")
            if not program.arguments:
                missing_declarations.append("argument")
        accepted = validation["valid"] and not missing and not missing_declarations
        result = {
            "status": "valid_needs_review" if accepted else "revise",
            "validation": validation,
            "missing_required_claims": missing,
            "missing_required_declarations": missing_declarations,
            "fidelity_unverified": True,
        }
        if accepted:
            result["accepted_source_digest"] = validation["source_digest"]
        return result

    def revise(self, task: str, propose: Callable[[dict[str, Any]], str], *, max_attempts: int = 4) -> dict[str, Any]:
        """Request and validate up to ``max_attempts`` complete source drafts.

        The callback receives the language reference on every turn, followed
        by the exact previous source and diagnostics after a failed attempt.
        No source is silently rewritten, formatted, collected or assessed.
        """
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be nonempty text")
        try:
            if len(task.encode("utf-8")) > MAX_TASK_BYTES:
                raise ValueError(f"task exceeds {MAX_TASK_BYTES} UTF-8 bytes")
        except UnicodeError as exc:
            raise ValueError("task must contain valid Unicode") from exc
        if not callable(propose):
            raise TypeError("propose must be callable")
        if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_ATTEMPTS:
            raise ValueError(f"max_attempts must be an integer from 1 to {MAX_ATTEMPTS}")
        reference = self.reference()
        attempts = []
        for number in range(1, max_attempts + 1):
            request: dict[str, Any] = {
                "stage": "draft" if number == 1 else "repair",
                "task": task,
                "attempt": number,
                "attempts_remaining_after_this": max_attempts - number,
                "reference": deepcopy(reference),
                "instruction": "Return one complete raw EAL/2 source, beginning with the exact header. Preserve the engineering question and declare evidence and adverse objections where required.",
            }
            if attempts:
                request["previous_source"] = attempts[-1]["source"]
                request["previous_result"] = deepcopy(attempts[-1]["result"])
            try:
                source = propose(request)
            except Exception as exc:
                # Provider exceptions can include request or credential data;
                # return the type while leaving detailed logging to the caller.
                return {"status": "generation_error", "source": None,
                        "fidelity_unverified": True, "attempts": attempts,
                        "error": {"type": type(exc).__name__, "message": "proposer failed"}}
            if not isinstance(source, str):
                return {"status": "generation_error", "source": None,
                        "fidelity_unverified": True, "attempts": attempts,
                        "error": {"type": "TypeError", "message": "proposer must return source text"}}
            try:
                source_size = len(source.encode("utf-8"))
            except UnicodeError:
                return {"status": "generation_error", "source": None,
                        "fidelity_unverified": True, "attempts": attempts,
                        "error": {"type": "UnicodeError", "message": "proposer must return valid Unicode"}}
            if source_size > MAX_SOURCE_BYTES:
                return {"status": "generation_error", "source": None,
                        "fidelity_unverified": True, "attempts": attempts,
                        "error": {"type": "SourceLimit", "message": f"proposer exceeded {MAX_SOURCE_BYTES} UTF-8 bytes"}}
            result = self.submit(source)
            attempts.append({"source": source, "result": result})
            if result["status"] == "valid_needs_review":
                return {"status": "valid_needs_review", "source": source,
                        "accepted_source_digest": result["accepted_source_digest"],
                        "fidelity_unverified": True, "attempts": attempts}
        return {"status": "invalid", "source": None, "fidelity_unverified": True,
                "attempts": attempts}
