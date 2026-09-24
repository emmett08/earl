"""Authoring feedback retains real EAL parser and semantic results."""

import hashlib

import pytest

from eal.authoring import AuthoringSession
from eal.parser import MAX_SOURCE_BYTES
from eal.runtime import ReasoningService


def test_reference_exposes_exact_example_and_installed_method_contracts(tmp_path):
    session = AuthoringSession(ReasoningService(tmp_path), required_claims=("checked",))
    reference = session.reference()

    assert reference["header"] == 'language "EAL/2";'
    assert reference["example"].startswith(reference["header"])
    assert session.service.validate(reference["example"])["valid"]
    assert reference["method_contracts"]["structured/1"]["input_schema"]["type"] == "object"
    assert reference["method_contracts"]["inductive/1"]["query_schema"]["type"] == "object"
    assert reference["language_reference"]["method_registry_fingerprint"] == session.service.method_registry.fingerprint


def test_submission_preserves_validation_diagnostics_and_digest_only_when_accepted(tmp_path):
    session = AuthoringSession(ReasoningService(tmp_path), required_claims=("checked",))
    source = session.reference()["example"]
    broken = source.replace('method "structured/1";', 'method "invented/1";')
    invalid = session.submit(broken)

    assert invalid["validation"] == session.service.validate(broken)
    assert invalid["validation"]["diagnostics"][0]["code"] == "unknown_method"
    assert invalid["validation"]["diagnostics"][0]["span"] is not None
    assert "accepted_source_digest" not in invalid
    assert invalid["fidelity_unverified"] is True

    valid = session.submit(source)
    assert valid["status"] == "valid_needs_review"
    assert valid["accepted_source_digest"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert valid["fidelity_unverified"] is True


def test_claim_anchor_is_presence_only_and_does_not_change_static_diagnostics(tmp_path):
    service = ReasoningService(tmp_path)
    session = AuthoringSession(service, required_claims=("some_other_claim",))
    source = session.reference()["example"]
    result = session.submit(source)

    assert result["validation"] == service.validate(source)
    assert result["validation"]["valid"] is True
    assert result["missing_required_claims"] == ["some_other_claim"]
    assert "accepted_source_digest" not in result


def test_empty_valid_program_does_not_pass_argument_authoring(tmp_path):
    session = AuthoringSession(ReasoningService(tmp_path))
    source = 'language "EAL/2";'
    result = session.submit(source)

    assert result["validation"] == session.service.validate(source)
    assert result["missing_required_declarations"] == ["claim", "argument"]
    assert result["status"] == "revise"
    assert "accepted_source_digest" not in result


def test_revision_supplies_exact_failure_and_stops_at_first_valid_source(tmp_path):
    session = AuthoringSession(ReasoningService(tmp_path), required_claims=("checked",))
    source = session.reference()["example"]
    broken = source.replace('language "EAL/2";', 'language "EAL/2"')
    requests = []

    def propose(request):
        requests.append(request)
        if request["stage"] == "draft":
            request["reference"]["header"] = "tampered"
            return broken
        assert request["reference"]["header"] == 'language "EAL/2";'
        assert request["previous_source"] == broken
        assert request["previous_result"]["validation"] == session.service.validate(broken)
        return source

    result = session.revise("Assess the supplied test in its stated context", propose, max_attempts=3)
    assert result["status"] == "valid_needs_review"
    assert len(result["attempts"]) == len(requests) == 2
    assert "accepted_source_digest" not in result["attempts"][0]["result"]
    assert result["accepted_source_digest"] == session.service.validate(source)["source_digest"]


def test_revision_exhaustion_never_returns_a_checked_source(tmp_path):
    session = AuthoringSession(ReasoningService(tmp_path))
    calls = []

    def propose(request):
        calls.append(request)
        return 'language "EAL/2"'

    result = session.revise("Assess the supplied test", propose, max_attempts=2)
    assert len(calls) == 2
    assert result["status"] == "invalid"
    assert result["source"] is None
    assert "accepted_source_digest" not in result
    assert all(attempt["result"]["validation"]["valid"] is False for attempt in result["attempts"])


def test_callback_failure_and_excess_output_return_no_accepted_source(tmp_path):
    session = AuthoringSession(ReasoningService(tmp_path))

    def fail(_):
        raise RuntimeError("provider secret must not be exposed")

    failed = session.revise("Assess the supplied test", fail)
    assert failed["status"] == "generation_error"
    assert failed["attempts"] == []
    assert "secret" not in str(failed)
    assert "accepted_source_digest" not in failed

    excessive = session.revise("Assess the supplied test", lambda _: "x" * (MAX_SOURCE_BYTES + 1))
    assert excessive["status"] == "generation_error"
    assert excessive["error"]["type"] == "SourceLimit"
    assert excessive["source"] is None


def test_required_claims_collection_is_bounded(tmp_path):
    service = ReasoningService(tmp_path)
    with pytest.raises(ValueError, match="collection"):
        AuthoringSession(service, required_claims="checked")
    with pytest.raises(ValueError, match="cannot exceed"):
        AuthoringSession(service, required_claims=(f"claim_{i}" for i in range(65)))


@pytest.mark.parametrize("attempts", [0, 9, True, 1.5])
def test_revision_budget_rejects_unbounded_or_invalid_attempts(tmp_path, attempts):
    session = AuthoringSession(ReasoningService(tmp_path))
    with pytest.raises(ValueError, match="max_attempts"):
        session.revise("Assess the supplied test", lambda _: "", max_attempts=attempts)
