"""Independent end-to-end checks for executable argument reuse.

The collector below supplies synthetic observations. It deliberately does not
claim that a passing numerical bound establishes population applicability.
"""

from __future__ import annotations

import hashlib
import json
import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.runtime import ReasoningService


STATISTICAL_SOURCE = '''language "EAL/2";
environment observed_service { require "service" == "$service"; }
tool sample_reader { version "1"; mode deterministic; }
evidence sample {
  tool sample_reader; kind sample; environment observed_service; max_age 60;
  input {"subject":"$service"};
  require "schema" == "EAL/typed-input/1";
}
reasoning interval {
  method "inductive/1";
  rationale "Calculate the declared two-sided Wilson interval for this sample.";
}
claim error_limit {
  statement "The declared Wilson upper bound on the request-failure probability is at most one percent.";
  environment observed_service;
  proposition {
    subject "$service"; quantity "probability"; unit "1";
    scope "fixed-sample-bernoulli";
    valid_from "2020-01-01T00:00:00Z";
    valid_until "2100-01-01T00:00:00Z";
    query {"confidence":0.95}; result "upper" <= 0.01;
  }
}
argument bounded_error {
  conclusion error_limit; reasoning interval; evidence sample; binding sample;
}
'''


COLLECTOR = '''import json, pathlib, sys
request = json.load(sys.stdin)
rows = json.loads(pathlib.Path(__file__).with_name("samples.json").read_text())
subject = request["input"]["subject"]
row = rows[subject]
value = {
    "schema": "EAL/typed-input/1", "method": "inductive/1",
    "subject": row.get("subject", subject), "quantity": "probability",
    "unit": "1", "scope": "fixed-sample-bernoulli",
    "valid_from": "2020-01-01T00:00:00Z",
    "valid_until": "2100-01-01T00:00:00Z",
    "payload": {"successes": row["failures"], "trials": row["trials"],
                "confidence": 0.95},
}
print(json.dumps({"value": value, "context": request["context"],
                 "request": {k: request[k] for k in
                     ("tool", "tool_version", "mode", "input", "context")}}))
'''


def _statistical_host_files(tmp_path: Path):
    """Build a real subprocess collector and a pinned reusable EAL source."""
    (tmp_path / "sample.eal").write_text(STATISTICAL_SOURCE)
    (tmp_path / "collector.py").write_text(COLLECTOR)
    (tmp_path / "samples.json").write_text(json.dumps({
        "orders": {"failures": 0, "trials": 100},
        "payments": {"failures": 0, "trials": 1000},
        "wrong-subject": {"failures": 0, "trials": 1000, "subject": "payments"},
    }))
    tools_path = tmp_path / "tools.toml"
    tools_path.write_text(
        '[tools.sample_reader]\nkind="command"\nmode="deterministic"\nversion="1"\n'
        'argv=' + json.dumps([sys.executable, str(tmp_path / "collector.py")]) + '\n'
    )
    service = ReasoningService(tmp_path, tools_path)
    return service, tools_path


def _run_sample(service: ReasoningService, subject: str):
    # Whole JSON-string substitution matches the scheme host's contract.
    source = STATISTICAL_SOURCE.replace(json.dumps("$service"), json.dumps(subject))
    context = {"service": subject}
    collection = service.collect(source, context)
    assessment = service.reason(source, context, collection["collection_id"])
    return source, collection, assessment


def _host_manifest(tmp_path: Path, service: ReasoningService, *, adequacy=True):
    path = tmp_path / "schemes.toml"
    lines = [
        'schema="eal2-argument-schemes/1"',
        '[schemes.error_probability]',
        'source="sample.eal"',
        'source_sha256=' + json.dumps(hashlib.sha256(STATISTICAL_SOURCE.encode()).hexdigest()),
        'method_registry_fingerprint=' + json.dumps(service.method_registry.fingerprint),
        'claim="error_limit"',
        'kind="claim"',
        'forms=["check the error limit for {service}", '
        '"assess request failures for {service}", "check the error limit again"]',
        '[schemes.error_probability.parameters.service]',
        'kind="string"',
        'context_path="service"',
        'source_literal="$service"',
        'values=["orders", "payments", "wrong-subject"]',
    ]
    if adequacy:
        lines.extend([
            '[schemes.error_probability.adequacy]',
            'correspondence="reviewed_source"',
            '[[schemes.error_probability.adequacy.obligations]]',
            'id="sample_count"',
            'role="coverage"',
            'target="evidence"',
            'reference="sample"',
            'path="payload.trials"',
            'operator=">="',
            'expected=100',
            'rationale="The numerical interval contract requires at least 100 observations."',
            '[[schemes.error_probability.adequacy.obligations]]',
            'id="wilson_threshold"',
            'role="threshold"',
            'target="argument"',
            'reference="bounded_error"',
            'path="reasoning_result.details.upper"',
            'operator="<="',
            'expected=0.01',
            'rationale="The declared Wilson upper bound must be no greater than one percent."',
        ])
    path.write_text("\n".join(lines) + "\n")
    return path


def _host(tmp_path, *, adequacy=True, principal="engineer", session_id="conversation"):
    from eal.argument_host import ArgumentHost

    service, tools = _statistical_host_files(tmp_path)
    manifest = _host_manifest(tmp_path, service, adequacy=adequacy)
    return ArgumentHost.load(service, manifest, principal=principal, session_id=session_id), service, manifest, tools


def test_sufficient_report_count_does_not_establish_population_threshold(tmp_path):
    service, _ = _statistical_host_files(tmp_path)
    _, collection, result = _run_sample(service, "orders")
    assert collection["records"]["sample"]["status"] == "ok"
    assert result["evidence"]["sample"]["status"] == "available"
    method = result["arguments"]["bounded_error"]["reasoning_result"]
    assert method["status"] == "supported"  # the calculation completed
    assert method["details"]["estimate"] == 0
    assert method["details"]["upper"] > 0.01
    assert result["claims"]["error_limit"]["status"] == "unsupported"


def test_population_criterion_changes_with_sample_information(tmp_path):
    service, _ = _statistical_host_files(tmp_path)
    _, _, result = _run_sample(service, "payments")
    method = result["arguments"]["bounded_error"]["reasoning_result"]
    assert method["details"]["upper"] < 0.01
    assert result["claims"]["error_limit"]["status"] == "supported"
    # Correct numerical binding still does not verify arbitrary prose or its
    # physical interpretation; an adequacy contract supplies separate checks.
    assert method["binding"]["prose_verified"] is False
    assert method["binding"]["physical_interpretation_verified"] is False


def test_successful_typed_tool_output_for_another_subject_cannot_support_claim(tmp_path):
    service, _ = _statistical_host_files(tmp_path)
    _, collection, result = _run_sample(service, "wrong-subject")
    assert collection["records"]["sample"]["status"] == "ok"
    assert result["claims"]["error_limit"]["status"] == "unsupported"
    binding = result["arguments"]["bounded_error"]["reasoning_result"]["binding"]
    assert binding["status"] == "unsupported"
    assert any("subject" in reason for reason in binding["reasons"])


def test_adequacy_does_not_verify_a_stronger_generated_sentence(tmp_path):
    from eal.adequacy import AdequacyContract, AdequacyEvaluator
    from eal.parser import parse

    service, _ = _statistical_host_files(tmp_path)
    source, collection, result = _run_sample(service, "payments")
    program = parse(source)
    contract = AdequacyContract.from_dict({
        "source_digest": program.source_digest,
        "claim": "error_limit",
        "statement": program.claims["error_limit"].statement,
        "environment": "observed_service",
        "methods": ["inductive/1"],
        "correspondence": "reviewed_source",
        "obligations": [{
            "id": "upper_bound", "role": "threshold", "target": "argument",
            "reference": "bounded_error", "path": "reasoning_result.details.upper",
            "operator": "<=", "expected": 0.01,
            "rationale": "Check the stated numerical confidence-bound criterion.",
        }],
    })
    evaluator = AdequacyEvaluator()
    numerical = evaluator.assess(contract, source=source, assessment=result,
                                 collection=collection, context={"service": "payments"})
    assert numerical["status"] == "adequate"
    strengthened = evaluator.assess(
        contract, source=source, assessment=result, collection=collection,
        context={"service": "payments"},
        prose="Payments is permanently reliable in every production workload and may be deployed immediately.",
    )
    assert strengthened["status"] == "unresolved"
    assert strengthened["correspondence"]["prose_verified"] is False


def test_adequacy_refuses_cross_collection_replay_of_a_positive_assessment(tmp_path):
    from eal.adequacy import AdequacyContract, AdequacyEvaluator
    from eal.parser import parse

    service, _ = _statistical_host_files(tmp_path)
    source, first_collection, positive = _run_sample(service, "payments")
    (tmp_path / "samples.json").write_text(json.dumps({"payments": {"failures": 0, "trials": 10}}))
    _, second_collection, _ = _run_sample(service, "payments")
    assert first_collection["collection_id"] != second_collection["collection_id"]
    program = parse(source)
    contract = AdequacyContract.from_dict({
        "source_digest": program.source_digest,
        "claim": "error_limit",
        "statement": program.claims["error_limit"].statement,
        "environment": "observed_service",
        "methods": ["inductive/1"],
        "correspondence": "reviewed_source",
        "obligations": [{
            "id": "upper_bound", "role": "threshold", "target": "argument",
            "reference": "bounded_error", "path": "reasoning_result.details.upper",
            "operator": "<=", "expected": 0.01,
            "rationale": "Bind this confidence bound to its original sample.",
        }],
    })
    attempted = AdequacyEvaluator().assess(
        contract, source=source, assessment=positive,
        collection=second_collection, context={"service": "payments"},
    )
    assert attempted["status"] != "adequate"
    assert any("different evidence collection" in reason for reason in attempted["reasons"])


def test_host_does_not_promote_computed_support_without_adequacy_contract(tmp_path):
    host, service, _, _ = _host(tmp_path, adequacy=False)
    packet = host.assess("check the error limit for payments")
    assert packet["status"] == "unresolved"
    # This is a substantive adequacy gap, not a failed arithmetic computation.
    result = service.explain(packet["assessment_id"])
    assert result["claims"]["error_limit"]["status"] == "supported"


def test_host_exposes_a_failed_numerical_criterion_without_claiming_its_negation(tmp_path):
    host, service, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for orders")
    assert packet["status"] != "supported"
    result = service.explain(packet["assessment_id"])
    calculation = result["arguments"]["bounded_error"]["reasoning_result"]
    assert calculation["details"]["estimate"] == 0
    assert calculation["details"]["upper"] > 0.01
    assert result["claims"]["error_limit"]["status"] == "unsupported"


def test_changed_later_subject_gets_new_evidence_and_survives_restart(tmp_path):
    from eal.argument_host import ArgumentHost

    host, service, manifest, tools = _host(tmp_path)
    first = host.assess("check the error limit for orders")
    second = host.assess("assess request failures for payments")
    assert second["status"] == "supported"
    assert first["assessment_id"] != second["assessment_id"]
    assert service.explain(second["assessment_id"])["claims"]["error_limit"]["proposition"]["subject"] == "payments"
    restarted_service = ReasoningService(tmp_path, tools)
    restarted = ArgumentHost.load(restarted_service, manifest, principal="engineer", session_id="conversation")
    followup = restarted.assess("check the error limit again")
    assert followup["status"] == "supported"
    assert followup["assessment_id"] != second["assessment_id"]
    assert restarted_service.explain(followup["assessment_id"])["claims"]["error_limit"]["proposition"]["subject"] == "payments"


def test_new_conversation_cannot_inherit_another_conversations_implicit_subject(tmp_path):
    from eal.argument_host import ArgumentHost

    host, service, manifest, _ = _host(tmp_path)
    original = host.assess("check the error limit for payments")
    other = ArgumentHost.load(service, manifest, principal="engineer", session_id="unrelated")
    assert other.resolve("check the error limit again")["status"] == "unresolved"
    with pytest.raises((ValueError, PermissionError)):
        other.finish(original["assessment_id"])


def test_other_principal_cannot_recover_a_checked_answer_in_the_same_named_session(tmp_path):
    from eal.argument_host import ArgumentHost

    host, service, manifest, _ = _host(tmp_path)
    original = host.assess("check the error limit for payments")
    other = ArgumentHost.load(service, manifest, principal="another_engineer", session_id="conversation")
    assert other.resolve("check the error limit again")["status"] == "unresolved"
    with pytest.raises((ValueError, PermissionError)):
        other.finish(original["assessment_id"])


def test_unresolved_scope_change_cannot_silently_restore_the_previous_subject(tmp_path):
    host, _, _, _ = _host(tmp_path)
    host.assess("check the error limit for payments")
    changed = host.resolve("Switch to production workloads with a different population")
    assert changed["status"] == "unresolved"
    assert host.assess("check the error limit again")["status"] == "unresolved"


def test_supported_answer_can_be_finalised_without_regenerating_its_conclusion(tmp_path):
    host, _, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    assert packet["status"] == "supported"
    assert host.finish(packet["assessment_id"]) == packet


def test_finish_rejects_expired_evidence_in_an_unchanged_session(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    import eal.argument_host

    host, _, _, _ = _host(tmp_path)
    packet = host.assess("check the error limit for payments")
    instant = datetime.fromisoformat(packet["assessed_at"].replace("Z", "+00:00"))
    monkeypatch.setattr(eal.argument_host, "utc_now", lambda: (instant + timedelta(seconds=120)).isoformat())
    with pytest.raises(ValueError):
        host.finish(packet["assessment_id"])


def test_previous_answer_cannot_be_finalised_as_a_new_request(tmp_path):
    host, _, _, _ = _host(tmp_path)
    first = host.assess("check the error limit for payments")
    host.assess("check the error limit for orders")
    with pytest.raises(ValueError, match="active request"):
        host.finish(first["assessment_id"])


def test_arbitrary_prose_cannot_reuse_a_numeric_scheme_to_certify_deployment(tmp_path):
    host, _, _, _ = _host(tmp_path)
    host.assess("check the error limit for payments")
    decision = host.resolve("Deploy payments to every production service because it is permanently safe")
    assert decision["status"] == "unresolved"


def test_changed_registered_source_invalidates_the_previously_loaded_scheme(tmp_path):
    host, _, _, _ = _host(tmp_path)
    (tmp_path / "sample.eal").write_text(STATISTICAL_SOURCE.replace('result "upper" <= 0.01', 'result "upper" <= 1'))
    try:
        packet = host.assess("check the error limit for orders")
    except ValueError:
        return
    assert packet["status"] != "supported"


def test_recipient_mcp_reuses_argument_form_without_general_collection_access(tmp_path):
    _, _, manifest, tools_path = _host(tmp_path)
    first_input = tmp_path / "first-user-request.txt"
    first_input.write_text("check the error limit for orders")
    later_input = tmp_path / "later-user-request.txt"
    later_input.write_text("assess request failures for payments")

    async def exercise(input_file):
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "eal.server", "--workspace", str(tmp_path),
                  "--registry", str(tools_path), "--schemes", str(manifest),
                  "--recipient-only", "--recipient-principal", "engineer",
                  "--session-id", "mcp_conversation", "--scheme-grant", "error_probability",
                  "--bound-prose-file", str(input_file)],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        )
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {item.name for item in (await session.list_tools()).tools}
                assert names == {"eal_resolve_bound_prose", "eal_assess_bound_prose", "eal_finish_prose"}
                denied = await session.call_tool("eal_collect", {"source": STATISTICAL_SOURCE, "context": {}})
                assert denied.isError
                rewritten = await session.call_tool("eal_assess_prose", {
                    "prose": "check the error limit for payments",
                })
                assert rewritten.isError
                override_input = await session.call_tool("eal_assess_bound_prose", {
                    "prose": "check the error limit for payments",
                })
                assert override_input.isError
                assessed = await session.call_tool("eal_assess_bound_prose", {})
                assert not assessed.isError, assessed
                packet = assessed.structuredContent
                if packet["status"] == "supported":
                    final = await session.call_tool("eal_finish_prose", {"assessment_id": packet["assessment_id"]})
                    assert not final.isError, final
                    assert final.structuredContent == packet
                override = await session.call_tool("eal_finish_prose", {
                    "assessment_id": packet["assessment_id"], "status": "unsupported",
                })
                assert override.isError
                return packet

    first = asyncio.run(exercise(first_input))
    second = asyncio.run(exercise(later_input))
    assert first["raw_status"] == "unsupported"
    assert second["status"] == "supported"
    assert second["context"]["service"] == "payments"
    assert first["assessment_id"] != second["assessment_id"]


def test_changed_checker_implementation_cannot_reuse_a_preflight(tmp_path):
    from eal.action_guard import ActionRefused, StagedCheckCommand, StagedCommandValidator
    from test_action_guard import ORIGINAL, candidate, gate

    checker = tmp_path / "trusted-check.py"
    checker.write_text("import pathlib, sys\nassert pathlib.Path(sys.argv[1]).is_file()\n")
    checks = tuple(StagedCheckCommand(name, "1", (sys.executable, str(checker), "{candidate}"))
                   for name in ("design", "integration"))
    validator = StagedCommandValidator(checks, pinned_host_files=(
        (sys.executable, hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()),
        (str(checker), hashlib.sha256(checker.read_bytes()).hexdigest()),
    ))
    action, target, _, _ = gate(tmp_path, validator=validator)
    prepared = action.preflight(candidate())
    assert target.read_bytes() == ORIGINAL
    # Same filename/version/argv, different method implementation. A repeated
    # zero exit status must not preserve the old validation-contract identity.
    checker.write_text("raise SystemExit(0)\n")
    with pytest.raises(ActionRefused):
        action.commit(prepared)
    assert target.read_bytes() == ORIGINAL


def test_changed_checker_configuration_cannot_reuse_a_preflight(tmp_path):
    from eal.action_guard import ActionRefused, StagedCheckCommand, StagedCommandValidator
    from test_action_guard import ORIGINAL, candidate, gate

    checks = tuple(StagedCheckCommand(name, "1", (sys.executable, "-c", "assert True"))
                   for name in ("design", "integration"))
    validator = StagedCommandValidator(checks, pinned_host_files=(
        (sys.executable, hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()),
    ))
    action, target, _, _ = gate(tmp_path, validator=validator)
    prepared = action.preflight(candidate())
    replacement = tuple(StagedCheckCommand(name, "2", (sys.executable, "-c", "pass"))
                        for name in ("design", "integration"))
    try:
        validator.checks = replacement
    except (AttributeError, TypeError):
        # An immutable public configuration prevents the attempted change.
        assert target.read_bytes() == ORIGINAL
        return
    with pytest.raises(ActionRefused):
        action.commit(prepared)
    assert target.read_bytes() == ORIGINAL
