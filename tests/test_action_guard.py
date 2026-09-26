"""The action boundary refuses unreviewed bytes and changed baselines."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

import pytest

from eal.action_guard import (ActionGate, ActionRefused, ActionScope, ChangeCheck,
                              ChangeValidation, GuardedFileChange, StagedCheckCommand,
                              StagedCommandValidator)
from eal.evaluator import canonical_digest


TASK = "Replace the solver configuration using the reviewed design and integration checks."
SOURCE = "1" * 64
ORIGINAL = b"mode = 'old'\n"
REPLACEMENT = b"mode = 'reviewed'\n"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def pinned(*files: str | Path) -> tuple[tuple[str, str], ...]:
    return tuple((str(path), sha(Path(path).read_bytes())) for path in files)


class CheckedReplacement:
    """A host-supplied example of concrete, byte-specific obligations."""

    status = "satisfied"
    contract_digest = canonical_digest({"schema": "test-checks/1", "names": ["design", "integration"]})

    def check(self, *, workspace: Path, change, proposal, context):
        assert workspace.is_dir()
        design = "satisfied" if change.replacement == REPLACEMENT else "violated"
        integration = "satisfied" if context["solver_interface"] == "v2" else "unresolved"
        return ChangeValidation(canonical_digest(proposal), canonical_digest(context), self.contract_digest, (
            ChangeCheck("design", design, "The reviewed solver value is present"),
            ChangeCheck("integration", integration, "The v2 interface was checked"),
        ))


class IssuedReview:
    """Test double for an issued and revalidated host assessment."""

    def __init__(self):
        self.status = "supported"
        self.adequacy = "adequate"
        self.correspondence = "satisfied"
        self.issued = None
        self.finish_calls = 0

    def assess(self, prose, context, proposal):
        self.issued = self._packet(prose, context, proposal)
        return self.issued

    def finish(self, assessment_id):
        assert self.issued["assessment_id"] == assessment_id
        self.finish_calls += 1
        return self._packet(TASK, {"solver_interface": "v2"}, self.proposal)

    def _packet(self, prose, context, proposal):
        self.proposal = proposal
        packet = {
            "assessment_id": "server-assessment-1", "verification": "server_assessment",
            "claim": "solver_change_allowed", "source_digest": SOURCE,
            "status": self.status, "task_kind": "action",
            "context_fingerprint": canonical_digest(context),
            "proposal_digest": canonical_digest(proposal),
            "prose_digest": sha(prose.encode("utf-8")),
            "correspondence": {"status": self.correspondence},
        }
        packet["adequacy"] = {
            "status": self.adequacy, "claim_status": self.status,
            "assessment_id": packet["assessment_id"], "claim": packet["claim"],
            "source_digest": packet["source_digest"],
            "context_fingerprint": packet["context_fingerprint"],
        }
        return packet


def gate(tmp_path, *, validator=None, reviewer=None, context=None):
    config = tmp_path / "solver.py"
    config.write_bytes(ORIGINAL)
    reviewer = reviewer or IssuedReview()
    validator = validator or CheckedReplacement()
    context = context or {"solver_interface": "v2"}
    scope = ActionScope(TASK, "solver.py", "solver_change_allowed", SOURCE,
                        canonical_digest(context), sha(ORIGINAL), validator.contract_digest)
    return ActionGate(tmp_path, scope, reviewer, validator, lambda: context), config, reviewer, context


def candidate(*, path="solver.py", original=ORIGINAL, replacement=REPLACEMENT):
    return GuardedFileChange(path, sha(original), replacement)


def test_preflight_and_commit_revalidate_before_single_file_replace(tmp_path):
    action, target, reviewer, _ = gate(tmp_path)
    prepared = action.preflight(candidate())
    assert target.read_bytes() == ORIGINAL
    assert prepared.assessment_id == "server-assessment-1"
    result = action.commit(prepared)
    assert result.replacement_sha256 == sha(REPLACEMENT)
    assert target.read_bytes() == REPLACEMENT
    assert reviewer.finish_calls == 1
    with pytest.raises(ActionRefused, match="already consumed"):
        action.commit(prepared)


@pytest.mark.parametrize("status,adequacy,correspondence", [
    ("unsupported", "adequate", "satisfied"),
    ("contested", "adequate", "satisfied"),
    ("supported", "unresolved", "satisfied"),
    ("supported", "insufficient", "satisfied"),
    ("supported", "adequate", "unresolved"),
])
def test_no_write_when_argument_or_evidence_is_unresolved(tmp_path, status, adequacy, correspondence):
    reviewer = IssuedReview()
    reviewer.status, reviewer.adequacy, reviewer.correspondence = status, adequacy, correspondence
    action, target, _, _ = gate(tmp_path, reviewer=reviewer)
    with pytest.raises(ActionRefused):
        action.preflight(candidate())
    assert target.read_bytes() == ORIGINAL


def test_bogus_path_wrong_baseline_and_unreviewed_bytes_are_rejected(tmp_path):
    action, target, reviewer, _ = gate(tmp_path)
    with pytest.raises(ActionRefused, match="host-pinned"):
        action.preflight(candidate(path="other.py"))
    with pytest.raises(ActionRefused, match="host-pinned"):
        action.preflight(candidate(original=b"wrong"))
    with pytest.raises(ActionRefused, match="design/integration"):
        action.preflight(candidate(replacement=b"mode = 'unsafe'\n"))
    assert reviewer.issued is None
    assert target.read_bytes() == ORIGINAL


def test_changed_bytes_or_replaced_identical_inode_invalidates_preflight(tmp_path):
    action, target, _, _ = gate(tmp_path)
    prepared = action.preflight(candidate())
    target.write_bytes(b"concurrent edit")
    with pytest.raises(ActionRefused, match="bytes changed"):
        action.commit(prepared)
    assert target.read_bytes() == b"concurrent edit"
    target.write_bytes(ORIGINAL)
    prepared = action.preflight(candidate())
    replacement = tmp_path / "external.tmp"
    replacement.write_bytes(ORIGINAL)
    os.replace(replacement, target)
    with pytest.raises(ActionRefused, match="identity changed"):
        action.commit(prepared)
    assert target.read_bytes() == ORIGINAL


def test_changed_design_context_and_revoked_assessment_refuse_commit(tmp_path):
    action, target, reviewer, context = gate(tmp_path)
    prepared = action.preflight(candidate())
    context["design_revision"] = "new"
    with pytest.raises(ActionRefused, match="context changed"):
        action.commit(prepared)
    assert target.read_bytes() == ORIGINAL
    del context["design_revision"]
    prepared = action.preflight(candidate())
    reviewer.adequacy = "insufficient"
    with pytest.raises(ActionRefused, match="lacks sufficient"):
        action.commit(prepared)
    assert target.read_bytes() == ORIGINAL


def test_symlinks_and_noncanonical_paths_are_refused(tmp_path):
    for name in ("../solver.py", "/tmp/solver.py", "x//solver.py", "x/../solver.py", "x\\solver.py"):
        with pytest.raises(ValueError, match="canonical"):
            GuardedFileChange(name, sha(ORIGINAL), REPLACEMENT)
    action, target, _, _ = gate(tmp_path)
    target.unlink()
    target.symlink_to(tmp_path / "elsewhere.py")
    with pytest.raises(OSError):
        action.preflight(candidate())


def test_review_packet_must_bind_task_source_context_proposal_and_adequacy(tmp_path):
    class WrongPacket(IssuedReview):
        field = ""

        def assess(self, prose, context, proposal):
            packet = super().assess(prose, context, proposal)
            packet[self.field] = "another value"
            return packet

    for field in ("claim", "source_digest", "context_fingerprint", "proposal_digest", "prose_digest",
                  "task_kind"):
        reviewer = WrongPacket()
        reviewer.field = field
        action, target, _, _ = gate(tmp_path, reviewer=reviewer)
        with pytest.raises(ActionRefused, match="bound to another task"):
            action.preflight(candidate())
        assert target.read_bytes() == ORIGINAL


def test_preflight_rejects_target_change_during_collection(tmp_path):
    class MutatingReview(IssuedReview):
        def assess(self, prose, context, proposal):
            (tmp_path / "solver.py").write_bytes(b"mutated by an external process")
            return super().assess(prose, context, proposal)

    action, target, _, _ = gate(tmp_path, reviewer=MutatingReview())
    with pytest.raises(ActionRefused, match="changed during assessment"):
        action.preflight(candidate())
    assert target.read_bytes() == b"mutated by an external process"


def test_staged_commands_check_exact_candidate_and_project_inputs(tmp_path):
    checker = tmp_path / "checker.py"
    checker.write_text(
        "import pathlib,sys\n"
        "candidate=pathlib.Path(sys.argv[1]); stage=pathlib.Path(sys.argv[2]); mode=sys.argv[3]\n"
        "assert candidate.read_bytes()==b\"mode = 'reviewed'\\n\"\n"
        "assert (stage / ('patterns/'+mode+'.txt')).read_text()==" 
        "('approved' if mode=='design' else 'v2')\n",
        encoding="utf-8")
    (tmp_path / "patterns").mkdir()
    (tmp_path / "patterns/design.txt").write_text("rejected")
    (tmp_path / "patterns/integration.txt").write_text("v2")
    commands = tuple(StagedCheckCommand(
        name, "1", (sys.executable, str(checker), "{candidate}", "{stage}", name),
        timeout_seconds=2, max_output_bytes=128)
        for name in ("design", "integration"))
    validator = StagedCommandValidator(
        commands, copy_paths=("patterns/design.txt", "patterns/integration.txt"),
        pinned_host_files=pinned(sys.executable, checker))
    action, target, reviewer, _ = gate(tmp_path, validator=validator)
    with pytest.raises(ActionRefused, match="design/integration"):
        action.preflight(candidate())
    assert reviewer.issued is None
    assert target.read_bytes() == ORIGINAL

    (tmp_path / "patterns/design.txt").write_text("approved")
    prepared = action.preflight(candidate())
    assert target.read_bytes() == ORIGINAL  # staging has no target-file side effect
    (tmp_path / "patterns/integration.txt").write_text("rejected")
    with pytest.raises(ActionRefused, match="design/integration"):
        action.commit(prepared)
    assert target.read_bytes() == ORIGINAL
    (tmp_path / "patterns/integration.txt").write_text("v2")
    prepared = action.preflight(candidate())
    action.commit(prepared)
    assert target.read_bytes() == REPLACEMENT


@pytest.mark.parametrize("program,timeout,output_limit", [
    ("import sys; sys.stdout.write('x'*10000)", 2, 32),
    ("import time; time.sleep(1)", 0.02, 32),
])
def test_staged_checker_output_and_timeout_are_bounded(tmp_path, program, timeout, output_limit):
    validator = StagedCommandValidator((
        StagedCheckCommand("design", "1", (sys.executable, "-c", program),
                           timeout_seconds=timeout, max_output_bytes=output_limit),
        StagedCheckCommand("integration", "1", (sys.executable, "-c", "pass")),
    ), pinned_host_files=pinned(sys.executable))
    action, target, reviewer, _ = gate(tmp_path, validator=validator)
    with pytest.raises(ActionRefused, match="design/integration"):
        action.preflight(candidate())
    assert target.read_bytes() == ORIGINAL
    assert reviewer.issued is None


def test_staged_checker_kills_orphan_child_holding_output_pipe(tmp_path):
    marker = tmp_path / "orphan-survived.txt"
    child = "import time,pathlib;time.sleep(.2);pathlib.Path(" + repr(str(marker)) + ").write_text('survived')"
    leader = "import subprocess,sys;subprocess.Popen([sys.executable,'-c'," + repr(child) + "])"
    validator = StagedCommandValidator((
        StagedCheckCommand("design", "1", (sys.executable, "-c", leader),
                           timeout_seconds=0.05, max_output_bytes=64),
        StagedCheckCommand("integration", "1", (sys.executable, "-c", "pass")),
    ), pinned_host_files=pinned(sys.executable))
    action, target, _, _ = gate(tmp_path, validator=validator)
    with pytest.raises(ActionRefused, match="design/integration"):
        action.preflight(candidate())
    time.sleep(0.3)
    assert not marker.exists()
    assert target.read_bytes() == ORIGINAL


def test_real_eal_collector_argument_host_and_staged_checker_gate_one_edit(tmp_path):
    """A synthetic design observation and exact staged check both must pass."""
    from eal.argument_host import ArgumentHost
    from eal.runtime import ReasoningService

    source = '''language "EAL/2";
environment repository { require "repository" == "pilot"; }
tool pattern_reader { version "1"; mode deterministic; }
evidence design_record {
  tool pattern_reader; kind test; environment repository; max_age 60;
  require "pattern" == "approved";
}
reasoning reviewed_pattern {
  method "structured/1"; rationale "The recorded design pattern applies to this scoped change.";
}
claim solver_change_allowed {
  statement "The reviewed solver pattern is available for this scoped file update.";
  environment repository;
}
argument design_route {
  conclusion solver_change_allowed; reasoning reviewed_pattern; evidence design_record;
}
'''
    (tmp_path / "design.eal").write_text(source)
    (tmp_path / "patterns").mkdir()
    (tmp_path / "patterns/design.txt").write_text("approved")
    (tmp_path / "patterns/integration.txt").write_text("v2")
    target = tmp_path / "solver.py"
    target.write_bytes(ORIGINAL)
    collector = tmp_path / "collector.py"
    collector.write_text('''import json, pathlib, sys
request=json.load(sys.stdin)
directory=pathlib.Path(__file__).parent
with (directory / "collector-calls.txt").open("a") as record:
    record.write(request["evidence_id"] + "\\n")
pattern=(directory / "patterns/design.txt").read_text()
print(json.dumps({"value":{"pattern":pattern},"context":request["context"],
                  "request":{key:request[key] for key in
                    ("tool","tool_version","mode","input","context")}}))
''')
    tools = tmp_path / "tools.toml"
    tools.write_text('[tools.pattern_reader]\nkind="command"\nmode="deterministic"\nversion="1"\n'
                     'argv=' + json.dumps([sys.executable, str(collector)]) + '\n')
    service = ReasoningService(tmp_path, tools)
    manifest = tmp_path / "schemes.toml"
    manifest.write_text('\n'.join([
        'schema="eal2-argument-schemes/1"',
        '[schemes.solver_update]',
        'source="design.eal"',
        'source_sha256=' + json.dumps(sha(source.encode())),
        'method_registry_fingerprint=' + json.dumps(service.method_registry.fingerprint),
        'claim="solver_change_allowed"',
        'kind="action"',
        'forms=[' + json.dumps(TASK) + ']',
        '[schemes.solver_update.context]',
        'repository="pilot"',
        '[schemes.solver_update.adequacy]',
        'correspondence="reviewed_source"',
        '[[schemes.solver_update.adequacy.obligations]]',
        'id="reviewed_pattern"',
        'role="threshold"',
        'target="evidence"',
        'reference="design_record"',
        'path="pattern"',
        'operator="=="',
        'expected="approved"',
        'rationale="The present design pattern is the reviewed value."',
    ]) + '\n')
    host = ArgumentHost.load(service, manifest, principal="file-editor", session_id="one-edit")
    checker = tmp_path / "static-check.py"
    checker.write_text('''import pathlib,sys
candidate=pathlib.Path(sys.argv[1])
stage=pathlib.Path(sys.argv[2])
kind=sys.argv[3]
assert candidate.read_bytes()==b"mode = 'reviewed'\\n"
assert (stage / ('patterns/'+kind+'.txt')).read_text()==('approved' if kind=='design' else 'v2')
''')
    commands = tuple(StagedCheckCommand(name, "1", (
        sys.executable, str(checker), "{candidate}", "{stage}", name), timeout_seconds=3)
        for name in ("design", "integration"))
    validator = StagedCommandValidator(commands,
                                       copy_paths=("patterns/design.txt", "patterns/integration.txt"),
                                       pinned_host_files=pinned(sys.executable, checker))
    context = {"repository": "pilot"}
    scope = ActionScope(TASK, "solver.py", "solver_change_allowed", sha(source.encode()),
                        canonical_digest(context), sha(ORIGINAL), validator.contract_digest)
    action = ActionGate(tmp_path, scope, host, validator, lambda: context)

    prepared = action.preflight(candidate())
    assert target.read_bytes() == ORIGINAL
    assert (tmp_path / "collector-calls.txt").read_text() == "design_record\n"
    action.commit(prepared)
    assert target.read_bytes() == REPLACEMENT
