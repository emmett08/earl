"""Host-owned, bounded file replacement after argument and change assessment.

EAL assessment concerns an authored claim. A supported claim alone does not
establish that arbitrary new bytes fit a repository's design. The host must
also supply a trusted ``ChangeValidator`` for the exact replacement and its
declared design/integration obligations. Neither model text nor a model-supplied
status enters the write path.

    The gate is for one existing regular file in a trusted workspace. Its context
provider must include the relevant design and integration baseline in the
context fingerprint; a fingerprint cannot discover omitted dependencies. The
gate coordinates cooperative writers and detects changes before replacement.
An uncooperative process modifying the file in the final check/rename interval
    requires stronger workspace isolation than this primitive supplies. Other
    application write paths are outside this gate; multiple files need an
    independently specified transaction and cannot be passed as one action.

    A trusted host wires ``ArgumentHost`` and ``StagedCommandValidator`` once,
    pins the resulting validator ``contract_digest`` and the current target
    SHA-256 in ``ActionScope``, and then calls::

        prepared = gate.preflight(GuardedFileChange(scope.path,
                                                   scope.prior_sha256,
                                                   candidate_bytes))
        record = gate.commit(prepared)

    ``preflight`` leaves the target untouched; ``commit`` consumes its token.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import selectors
import signal
import stat
import subprocess
import tempfile
import threading
import time
from typing import Any, Protocol

from .evaluator import canonical_digest


_SHA256_LENGTH = 64
_MAX_REPLACEMENT_BYTES = 2 * 1024 * 1024
_MAX_TASK_BYTES = 4096
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class ActionRefused(ValueError):
    """A proposal failed the host's exact scope or assessment contract."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: str) -> bool:
    return isinstance(value, str) and len(value) == _SHA256_LENGTH and all(c in "0123456789abcdef" for c in value)


def _relative_file(path: str) -> bool:
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        return False
    parsed = PurePosixPath(path)
    return (not parsed.is_absolute() and path == parsed.as_posix()
            and all(part not in (".", "..") for part in path.split("/")))


@dataclass(frozen=True)
class ActionScope:
    """Pinned by the trusted host, independently of the model's proposal."""

    task_text: str
    path: str
    claim: str
    source_digest: str
    context_fingerprint: str
    prior_sha256: str
    validation_contract_digest: str
    required_checks: tuple[str, ...] = ("design", "integration")

    def __post_init__(self) -> None:
        if (not isinstance(self.task_text, str) or not self.task_text.strip()
                or len(self.task_text.encode("utf-8")) > _MAX_TASK_BYTES):
            raise ValueError("The trusted task must contain at most 4096 UTF-8 bytes")
        if not _relative_file(self.path):
            raise ValueError("Action scope requires a canonical workspace-relative file")
        if not isinstance(self.claim, str) or not self.claim:
            raise ValueError("Action scope requires a claim ID")
        if any(not _digest(value) for value in (self.source_digest, self.context_fingerprint,
                                                self.prior_sha256, self.validation_contract_digest)):
            raise ValueError("Action scope requires pinned SHA-256 digests")
        if (not isinstance(self.required_checks, tuple) or not self.required_checks
                or len(set(self.required_checks)) != len(self.required_checks)
                or any(not isinstance(item, str) or not item for item in self.required_checks)):
            raise ValueError("Action scope requires distinct named change checks")


@dataclass(frozen=True)
class GuardedFileChange:
    """Untrusted candidate bytes; it cannot name a new claim or change scope."""

    path: str
    prior_sha256: str
    replacement: bytes

    def __post_init__(self) -> None:
        if not _relative_file(self.path) or not _digest(self.prior_sha256):
            raise ValueError("Change requires a canonical relative file and prior SHA-256")
        if not isinstance(self.replacement, bytes) or len(self.replacement) > _MAX_REPLACEMENT_BYTES:
            raise ValueError("Replacement must contain at most 2 MiB of bytes")


@dataclass(frozen=True)
class ChangeCheck:
    name: str
    status: str  # satisfied, violated, or unresolved
    reason: str


@dataclass(frozen=True)
class ChangeValidation:
    """Result computed by the host's configured checker from exact bytes."""

    proposal_digest: str
    context_fingerprint: str
    contract_digest: str
    checks: tuple[ChangeCheck, ...]


class ChangeValidator(Protocol):
    @property
    def contract_digest(self) -> str:
        """Digest of immutable, versioned host-selected validation settings."""

    def check(self, *, workspace: Path, change: GuardedFileChange,
              proposal: Mapping[str, Any], context: Mapping[str, Any]) -> ChangeValidation:
        """Check exact replacement bytes against named design/test obligations."""


@dataclass(frozen=True)
class StagedCheckCommand:
    """A trusted, versioned executable and bounded check of the staged copy.

    ``{candidate}`` and ``{stage}`` are entire argv items, never shell text.
    The command is host configuration, and its executable must be an absolute
    path. The runner is trusted to inspect candidate bytes without executing
    untrusted candidate code outside a genuine OS/container sandbox.
    """

    name: str
    version: str
    argv: tuple[str, ...]
    timeout_seconds: float = 10.0
    max_output_bytes: int = 8192

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name
                or not isinstance(self.version, str) or not self.version):
            raise ValueError("A staged check needs a name and version")
        if (not isinstance(self.argv, tuple) or not self.argv
                or any(not isinstance(arg, str) or not arg for arg in self.argv)
                or not Path(self.argv[0]).is_absolute()
                or any("{" in arg or "}" in arg for arg in self.argv
                       if arg not in {"{candidate}", "{stage}"})):
            raise ValueError("Staged check needs an absolute executable and closed argv placeholders")
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float))
                or not 0 < self.timeout_seconds <= 120
                or type(self.max_output_bytes) is not int
                or not 0 <= self.max_output_bytes <= 65_536):
            raise ValueError("Staged check exceeds timeout or output limits")


def _read_snapshot_file(root: Path, relative: str, limit: int) -> bytes:
    """Read a regular input through no-follow descriptors, within a byte bound."""
    fd = os.open(root, _DIRECTORY_FLAGS)
    try:
        parts = relative.split("/")
        for part in parts[:-1]:
            opened = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = opened
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                raise ActionRefused("Staged input must be a bounded regular file")
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            path_info = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
            if (len(data) > limit or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or (after.st_dev, after.st_ino) != (path_info.st_dev, path_info.st_ino)):
                raise ActionRefused("Staged input changed during collection")
            return data
    finally:
        os.close(fd)


def _run_staged_check(argv: list[str], stage: Path, command: StagedCheckCommand) -> tuple[str, str]:
    """Bound process time and combined output without retaining output in RAM."""
    started = time.monotonic()
    try:
        process = subprocess.Popen(argv, cwd=stage, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    except OSError as exc:
        return "unresolved", f"Checker {command.name}/{command.version} failed: {type(exc).__name__}"
    streams = selectors.DefaultSelector()
    output_bytes = 0
    status = "unresolved"
    reason = "Checker did not complete"
    try:
        assert process.stdout is not None and process.stderr is not None
        streams.register(process.stdout, selectors.EVENT_READ)
        streams.register(process.stderr, selectors.EVENT_READ)
        while streams.get_map():
            remaining = command.timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                reason = "Checker exceeded its configured timeout"
                break
            readable = streams.select(remaining)
            if not readable:
                reason = "Checker exceeded its configured timeout"
                break
            for key, _ in readable:
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    streams.unregister(key.fileobj)
                    continue
                output_bytes += len(chunk)
                if output_bytes > command.max_output_bytes:
                    reason = "Checker output exceeded its configured limit"
                    break
            if output_bytes > command.max_output_bytes:
                break
        else:
            remaining = max(0, command.timeout_seconds - (time.monotonic() - started))
            try:
                code = process.wait(timeout=remaining)
                status = "satisfied" if code == 0 else "violated"
                reason = f"Checker {command.name}/{command.version} exited {code}"
            except subprocess.TimeoutExpired:
                reason = "Checker exceeded its configured timeout"
    finally:
        if status == "unresolved" or process.poll() is None:
            # The leader may already have exited while a child still holds
            # stdout/stderr. Kill the private group even in that case.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        streams.close()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
    return status, reason


class StagedCommandValidator:
    """Run trusted static/design checkers against a bounded staged file set.

    ``copy_paths`` is a host-selected list of project inputs relevant to these
    checks. It cannot establish whole-repository consistency when an input is
    omitted. The temporary directory isolates staged file *locations*, not
    processes: commands which execute candidate code need a separate sandbox.
    """

    SCHEMA = "eal2-staged-checks/1"
    __slots__ = ("checks", "copy_paths", "max_input_bytes", "pinned_host_files", "contract_digest")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Staged validation settings are immutable")

    def __init__(self, checks: tuple[StagedCheckCommand, ...], *,
                 copy_paths: tuple[str, ...] = (), max_input_bytes: int = 2 * 1024 * 1024,
                 pinned_host_files: tuple[tuple[str, str], ...]):
        if (not isinstance(checks, tuple) or not checks or len(checks) > 32
                or any(not isinstance(item, StagedCheckCommand) for item in checks)
                or len({item.name for item in checks}) != len(checks)):
            raise ValueError("Staged validator requires distinct trusted checks")
        if (not isinstance(copy_paths, tuple) or len(copy_paths) > 128
                or any(not _relative_file(item) for item in copy_paths)
                or len(set(copy_paths)) != len(copy_paths)
                or type(max_input_bytes) is not int or not 0 < max_input_bytes <= 16 * 1024 * 1024):
            raise ValueError("Staged inputs require bounded canonical paths")
        if (not isinstance(pinned_host_files, tuple) or not pinned_host_files
                or len(pinned_host_files) > 128 or any(
                    not isinstance(item, tuple) or len(item) != 2
                    or not isinstance(item[0], str) or not Path(item[0]).is_absolute()
                    or not _digest(item[1]) for item in pinned_host_files)):
            raise ValueError("Host checker files require pinned absolute paths and SHA-256 digests")
        pinned = dict(pinned_host_files)
        if (len(pinned) != len(pinned_host_files)
                or any(arg not in pinned for command in checks for arg in command.argv
                       if Path(arg).is_absolute())):
            raise ValueError("Every absolute checker argv file must be pinned")
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "copy_paths", copy_paths)
        object.__setattr__(self, "max_input_bytes", max_input_bytes)
        object.__setattr__(self, "pinned_host_files", pinned_host_files)
        object.__setattr__(self, "contract_digest", canonical_digest({
            "schema": self.SCHEMA,
            "checks": [{"name": c.name, "version": c.version, "argv": list(c.argv),
                        "timeout_seconds": c.timeout_seconds,
                        "max_output_bytes": c.max_output_bytes} for c in checks],
            "copy_paths": list(copy_paths), "max_input_bytes": max_input_bytes,
            "pinned_host_files": [list(item) for item in pinned_host_files],
        }))
        self._snapshot_pins()  # fail before accepting a broken host configuration

    def _snapshot_pins(self) -> dict[str, bytes]:
        snapshot = {}
        for path, expected in self.pinned_host_files:
            target = Path(path).resolve(strict=True)
            before = target.stat()
            if not stat.S_ISREG(before.st_mode) or before.st_size > 32 * 1024 * 1024:
                raise ActionRefused("Pinned checker/dependency must be a bounded regular file")
            with target.open("rb") as stream:
                data = stream.read(32 * 1024 * 1024 + 1)
            after = target.stat()
            if (len(data) > 32 * 1024 * 1024 or _sha256(data) != expected
                    or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or Path(path).resolve(strict=True) != target):
                raise ActionRefused("Pinned checker/dependency bytes changed")
            snapshot[path] = data
        return snapshot

    def check(self, *, workspace: Path, change: GuardedFileChange,
              proposal: Mapping[str, Any], context: Mapping[str, Any]) -> ChangeValidation:
        pins = self._snapshot_pins()
        if change.path in self.copy_paths:
            raise ActionRefused("Candidate path cannot also be copied from the baseline")
        with tempfile.TemporaryDirectory(prefix="eal-action-stage-") as temporary:
            stage = Path(temporary)
            total = 0
            for relative in self.copy_paths:
                data = _read_snapshot_file(workspace, relative, self.max_input_bytes - total)
                total += len(data)
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            candidate = stage / change.path
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(change.replacement)
            staged_pins = {}
            for index, (path, _) in enumerate(self.pinned_host_files):
                if path == self.checks[0].argv[0] or any(path == item.argv[0] for item in self.checks):
                    # Executables such as Python can depend on a fixed runtime
                    # layout; keep their trusted absolute path but verify bytes.
                    continue
                target = stage / ".eal-trusted" / f"{index}-{Path(path).name}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(pins[path])
                target.chmod(0o500)
                staged_pins[path] = str(target)
            findings = []
            for command in self.checks:
                argv = [str(candidate) if arg == "{candidate}" else
                        str(stage) if arg == "{stage}" else staged_pins.get(arg, arg)
                        for arg in command.argv]
                status, reason = _run_staged_check(argv, stage, command)
                if _sha256(candidate.read_bytes()) != proposal.get("replacement_sha256"):
                    status, reason = "unresolved", "Checker modified the staged candidate"
                findings.append(ChangeCheck(command.name, status, reason))
            self._snapshot_pins()
        return ChangeValidation(canonical_digest(proposal), canonical_digest(context),
                                self.contract_digest, tuple(findings))


class ArgumentReviewer(Protocol):
    def assess(self, prose: str, context: Mapping[str, Any],
               proposal: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a server-issued packet for this task and proposal."""

    def finish(self, assessment_id: str) -> Mapping[str, Any]:
        """Revalidate the server-issued assessment before the write."""


@dataclass(frozen=True)
class PreparedAction:
    token: str
    path: str
    proposal_digest: str
    assessment_id: str


@dataclass(frozen=True)
class CommittedAction:
    path: str
    prior_sha256: str
    replacement_sha256: str
    assessment_id: str
    proposal_digest: str


@dataclass(frozen=True)
class _Pending:
    prepared: PreparedAction
    change: GuardedFileChange
    proposal: dict[str, Any]
    inode: tuple[int, int]


class ActionGate:
    """Preflight and atomically replace one host-authorised file.

    The application constructs this object with a trusted reviewer and change
    validator; callers with only a text-model response cannot issue a review.
    Pending actions live only in this process and are single use. A retry must
    recollect/reassess and repeat preflight.
    """

    def __init__(self, workspace: str | Path, scope: ActionScope,
                 reviewer: ArgumentReviewer, validator: ChangeValidator,
                 context_provider: Callable[[], Mapping[str, Any]]):
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError("Action workspace must be a directory")
        self.scope = scope
        self.reviewer = reviewer
        self.validator = validator
        self.context_provider = context_provider
        if getattr(validator, "contract_digest", None) != scope.validation_contract_digest:
            raise ValueError("Change validator differs from its host-pinned contract")
        self._root_identity = self._root_stat()
        self._lock = threading.RLock()
        self._pending: dict[str, _Pending] = {}

    def _root_stat(self) -> tuple[int, int]:
        fd = os.open(self.workspace, _DIRECTORY_FLAGS)
        try:
            info = os.fstat(fd)
            return info.st_dev, info.st_ino
        finally:
            os.close(fd)

    def _parent(self, path: str) -> tuple[int, str]:
        fd = os.open(self.workspace, _DIRECTORY_FLAGS)
        try:
            root = os.fstat(fd)
            if (root.st_dev, root.st_ino) != self._root_identity:
                raise ActionRefused("Workspace identity changed")
            parts = path.split("/")
            for part in parts[:-1]:
                opened = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = opened
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def _current_file(self) -> tuple[str, tuple[int, int], int]:
        parent_fd, name = self._parent(self.scope.path)
        try:
            file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
            with os.fdopen(file_fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                    raise ActionRefused("The authorised target must be a regular, singly linked file")
                if before.st_size > _MAX_REPLACEMENT_BYTES:
                    raise ActionRefused("The authorised target exceeds the byte limit")
                content = stream.read(_MAX_REPLACEMENT_BYTES + 1)
                after = os.fstat(stream.fileno())
            path_info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or (after.st_dev, after.st_ino) != (path_info.st_dev, path_info.st_ino)):
                raise ActionRefused("Target changed while it was read")
            return _sha256(content), (after.st_dev, after.st_ino), stat.S_IMODE(after.st_mode)
        finally:
            os.close(parent_fd)

    def _context(self) -> dict[str, Any]:
        provided = self.context_provider()
        if not isinstance(provided, Mapping):
            raise ActionRefused("Context provider did not return a mapping")
        # Freeze caller-owned objects before assessment; do not retain a mutable
        # reference that can change between digesting and invoking the reviewer.
        try:
            context = json.loads(json.dumps(dict(provided), sort_keys=True,
                                            ensure_ascii=False, allow_nan=False))
            fingerprint = canonical_digest(context)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ActionRefused("Context is not bounded JSON") from exc
        if fingerprint != self.scope.context_fingerprint:
            raise ActionRefused("Design or integration context changed")
        return context

    def _check_candidate(self, change: GuardedFileChange) -> tuple[dict[str, Any], tuple[int, int], dict[str, Any]]:
        if change.path != self.scope.path or change.prior_sha256 != self.scope.prior_sha256:
            raise ActionRefused("Change differs from the host-pinned path or prior bytes")
        current, inode, _ = self._current_file()
        if current != self.scope.prior_sha256:
            raise ActionRefused("Target bytes changed since the host pinned them")
        context = self._context()
        proposal = {"schema": "eal2-file-change/1", "path": change.path,
                    "prior_sha256": change.prior_sha256,
                    "replacement_sha256": _sha256(change.replacement),
                    "replacement_size": len(change.replacement),
                    "task_sha256": _sha256(self.scope.task_text.encode("utf-8"))}
        return proposal, inode, context

    def _check_validation(self, change: GuardedFileChange, proposal: dict[str, Any],
                          context: dict[str, Any]) -> None:
        validation = self.validator.check(workspace=self.workspace, change=change,
                                          proposal=proposal, context=context)
        if not isinstance(validation, ChangeValidation):
            raise ActionRefused("Change validator did not return a checked result")
        if (validation.proposal_digest != canonical_digest(proposal)
                or validation.context_fingerprint != self.scope.context_fingerprint
                or validation.contract_digest != self.scope.validation_contract_digest
                or self.validator.contract_digest != self.scope.validation_contract_digest):
            raise ActionRefused("Change validation concerns a different proposal or context")
        checks = validation.checks
        if (not isinstance(checks, tuple) or len(checks) != len(self.scope.required_checks)
                or {item.name for item in checks if isinstance(item, ChangeCheck)}
                != set(self.scope.required_checks)
                or any(not isinstance(item, ChangeCheck) or item.status != "satisfied"
                       or not isinstance(item.reason, str) or not item.reason.strip() for item in checks)):
            raise ActionRefused("Required design/integration checks are violated or unresolved")

    def _check_packet(self, packet: Mapping[str, Any], proposal: dict[str, Any],
                      *, assessment_id: str | None = None) -> str:
        if not isinstance(packet, Mapping):
            raise ActionRefused("Argument reviewer did not return a packet")
        issued_id = packet.get("assessment_id")
        if (not isinstance(issued_id, str) or not issued_id
                or (assessment_id is not None and issued_id != assessment_id)
                or packet.get("verification") != "server_assessment"
                or packet.get("status") != "supported"
                or packet.get("task_kind") != "action"
                or packet.get("claim") != self.scope.claim
                or packet.get("source_digest") != self.scope.source_digest
                or packet.get("context_fingerprint") != self.scope.context_fingerprint
                or packet.get("proposal_digest") != canonical_digest(proposal)
                or packet.get("prose_digest") != _sha256(self.scope.task_text.encode("utf-8"))):
            raise ActionRefused("Argument assessment is unsupported, stale or bound to another task")
        adequacy = packet.get("adequacy")
        correspondence = packet.get("correspondence")
        if (not isinstance(adequacy, Mapping) or adequacy.get("status") != "adequate"
                or adequacy.get("claim_status") != "supported"
                or adequacy.get("assessment_id") != issued_id
                or adequacy.get("claim") != self.scope.claim
                or adequacy.get("source_digest") != self.scope.source_digest
                or adequacy.get("context_fingerprint") != self.scope.context_fingerprint
                or not isinstance(correspondence, Mapping)
                or correspondence.get("status") != "satisfied"):
            raise ActionRefused("The reviewed claim lacks sufficient evidence or correspondence")
        return issued_id

    def preflight(self, change: GuardedFileChange) -> PreparedAction:
        """Stage exact candidate bytes in memory after two independent reviews."""
        with self._lock:
            proposal, inode, context = self._check_candidate(change)
            self._check_validation(change, proposal, context)
            packet = self.reviewer.assess(self.scope.task_text, context, proposal)
            assessment_id = self._check_packet(packet, proposal)
            # Tool acquisition/checks may have changed repository state.
            current, new_inode, _ = self._current_file()
            if current != self.scope.prior_sha256 or new_inode != inode:
                raise ActionRefused("Target changed during assessment")
            self._context()
            prepared = PreparedAction(secrets.token_urlsafe(24), change.path,
                                      canonical_digest(proposal), assessment_id)
            self._pending[prepared.token] = _Pending(prepared, change, proposal, inode)
            return prepared

    def commit(self, prepared: PreparedAction) -> CommittedAction:
        """Revalidate the assessment and baseline, then perform one atomic replace."""
        with self._lock:
            if not isinstance(prepared, PreparedAction):
                raise ActionRefused("A host-issued preflight is required")
            pending = self._pending.pop(prepared.token, None)
            if pending is None or pending.prepared != prepared:
                raise ActionRefused("Unknown or already consumed preflight")
            change = pending.change
            proposal, inode, context = self._check_candidate(change)
            if canonical_digest(proposal) != prepared.proposal_digest or inode != pending.inode:
                raise ActionRefused("Staged proposal or target identity changed")
            self._check_validation(change, proposal, context)
            packet = self.reviewer.finish(prepared.assessment_id)
            self._check_packet(packet, proposal, assessment_id=prepared.assessment_id)
            if self._context() != context:
                raise ActionRefused("Context changed after final assessment")
            parent_fd, name = self._parent(change.path)
            temporary = f".eal-action-{secrets.token_hex(16)}"
            created = False
            try:
                # Recheck immediately before replacement, including inode to
                # reject replacement with identical bytes after preflight.
                digest, live_inode, mode = self._current_file()
                if digest != change.prior_sha256 or live_inode != inode:
                    raise ActionRefused("Target changed before replacement")
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=parent_fd)
                created = True
                with os.fdopen(descriptor, "wb") as output:
                    output.write(change.replacement)
                    output.flush()
                    os.fchmod(output.fileno(), mode & 0o777)
                    os.fsync(output.fileno())
                os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                created = False
                os.fsync(parent_fd)
            finally:
                if created:
                    os.unlink(temporary, dir_fd=parent_fd)
                os.close(parent_fd)
            return CommittedAction(change.path, change.prior_sha256,
                                   proposal["replacement_sha256"], prepared.assessment_id,
                                   prepared.proposal_digest)
