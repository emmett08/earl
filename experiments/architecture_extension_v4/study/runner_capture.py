"""Small, auditable capture primitives for the v4 sequence runner.

The agent receives a copy of the candidate in an OS mount namespace. The
hidden assessor and future briefs are outside that namespace. A stub process
is supported only for local smoke tests and is explicitly marked ineligible.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXCLUDED = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", ".venv", "node_modules"}
RESERVED = {"FEATURE.md", "AGENTS.md", "PACKET.md"}
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "cache_read_input_tokens",
                "cache_write_input_tokens", "cache_creation_input_tokens",
                "output_tokens", "reasoning_output_tokens")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tree_entries(source: Path, *, omit_agent_inputs: bool = False) -> list[dict[str, Any]]:
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"source must be an ordinary directory: {source}")
    entries: list[dict[str, Any]] = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if any(part in EXCLUDED for part in rel.parts) or path.name.endswith(".pyc"):
            continue
        if path.is_symlink():
            raise ValueError(f"symlink in source snapshot: {rel}")
        if path.is_file():
            if rel.parts[0] in RESERVED:
                if omit_agent_inputs and len(rel.parts) == 1:
                    continue
                raise ValueError(f"reserved agent input in source: {rel}")
            entries.append({"path": rel.as_posix(), "sha256": digest(path), "bytes": path.stat().st_size})
        elif not path.is_dir():
            raise ValueError(f"unsupported file in source snapshot: {rel}")
    if not entries:
        raise ValueError("empty source snapshot")
    return entries


def tree_digest(entries: list[dict[str, Any]]) -> str:
    payload = "".join(f"{row['path']}\0{row['sha256']}\n" for row in entries)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def copy_source(source: Path, destination: Path, *, omit_agent_inputs: bool = False) -> tuple[str, list[dict[str, Any]]]:
    entries = tree_entries(source, omit_agent_inputs=omit_agent_inputs)
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    for row in entries:
        target = destination / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / row["path"], target)
        target.chmod((source / row["path"]).stat().st_mode & 0o777)
    copied = tree_entries(destination)
    if entries != copied:
        raise RuntimeError("source changed during snapshot copy")
    return tree_digest(entries), entries


def snapshot_candidate(trial: Path, destination: Path) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Retain regular candidate files while quarantining agent-created oddities.

    An agent-created symlink or socket is a candidate validity failure, not a
    reason to dereference host paths or discard subsequent assigned stages.
    """
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    rejected: list[str] = []
    for path in sorted(trial.rglob("*")):
        rel = path.relative_to(trial)
        if any(part in EXCLUDED for part in rel.parts) or path.name.endswith(".pyc"):
            continue
        if path.is_symlink():
            rejected.append(rel.as_posix())
            continue
        if path.is_dir():
            continue
        if rel.parts[0] in RESERVED and len(rel.parts) == 1:
            continue
        if not path.is_file() or rel.parts[0] in RESERVED:
            rejected.append(rel.as_posix())
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(path.stat().st_mode & 0o777)
    entries = tree_entries(destination)
    return tree_digest(entries), entries, rejected


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute(argv: list[str], *, cwd: Path, env: dict[str, str], timeout: int,
            stdout: Path, stderr: Path) -> dict[str, Any]:
    """Capture real elapsed time and terminate a whole timed-out process group."""
    started = timestamp()
    clock = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                   stdout=out, stderr=err, start_new_session=True)
        timed_out = False
        try:
            process.communicate(input=(cwd / "FEATURE.md").read_bytes(), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
    return {"started_utc": started, "ended_utc": timestamp(),
            "actual_wall_seconds": time.monotonic() - clock,
            "wall_cap_seconds": timeout, "exit_code": process.returncode,
            "timed_out": timed_out}


def redact(paths: list[Path], secrets: list[str]) -> tuple[bool, dict[str, str | None]]:
    """Replace exact credential values before artifacts can leave this host."""
    raw_sha = {str(path): digest(path) if path.exists() else None for path in paths}
    exposed = False
    raw_secrets = [secret.encode("utf-8") for secret in secrets if secret]
    for path in paths:
        if not path.is_file():
            continue
        value = path.read_bytes()
        replacement = value
        for secret in raw_secrets:
            if secret in replacement:
                replacement = replacement.replace(secret, b"[REDACTED_PROVIDER_CREDENTIAL]")
        if replacement != value:
            path.write_bytes(replacement)
            exposed = True
    return exposed, raw_sha


def usage_from_jsonl(trace: Path) -> dict[str, Any]:
    """Preserve missing counters as unknown, including cache writes.

    Codex reports completed-turn usage. Totals are sums only when each
    completed turn reports the field; an absent field is never zero-filled.
    """
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(trace.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError(f"non-object JSONL event on line {line_number}")
        events.append(event)
    turns = [event["usage"] for event in events if event.get("type") == "turn.completed"
             and isinstance(event.get("usage"), dict)]
    if not turns:
        return {"status": "unreported", "events": len(events), "completed_turns": 0,
                "per_turn_usage": [], "totals": {field: None for field in TOKEN_FIELDS}}
    totals: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        values = [turn.get(field) for turn in turns]
        if any(value is None for value in values):
            totals[field] = None
        elif any(type(value) is not int or value < 0 for value in values):
            raise ValueError(f"invalid reported {field}")
        else:
            totals[field] = sum(values)
    return {"status": "reported", "events": len(events),
            "completed_turns": len(turns), "per_turn_usage": turns, "totals": totals,
            "accounting": "sum of CLI completed-turn events; billed units unverified"}


def bwrap_prefix(trial: Path, home: Path, *, read_only_trial: bool = False) -> list[str]:
    """Construct a closed filesystem view; network remains available to API."""
    if not shutil.which("bwrap"):
        raise RuntimeError("bwrap is required for a live Codex run")
    command = ["bwrap", "--die-with-parent", "--new-session", "--unshare-pid",
               "--unshare-ipc", "--unshare-uts", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/etc", "/etc", "--proc", "/proc", "--dev", "/dev",
               "--tmpfs", "/tmp", "--dir", "/home", "--bind", str(home), "/home/agent",
               "--ro-bind" if read_only_trial else "--bind", str(trial), "/trial",
               "--chdir", "/trial", "--setenv", "HOME", "/home/agent"]
    for short, target in (("/bin", "usr/bin"), ("/lib", "usr/lib"), ("/lib64", "usr/lib64"),
                          ("/sbin", "usr/sbin")):
        if Path(short).is_symlink():
            command.extend(["--symlink", target, short])
        elif Path(short).exists():
            command.extend(["--ro-bind", short, short])
    # GitHub setup-node can place the Node interpreter here even when npm's
    # globally installed Codex package is deliberately pinned under /usr/local.
    if Path("/opt/hostedtoolcache").is_dir():
        command.extend(["--dir", "/opt", "--ro-bind", "/opt/hostedtoolcache",
                        "/opt/hostedtoolcache"])
    resolver = Path("/etc/resolv.conf")
    if not resolver.is_file():
        raise RuntimeError("host resolver configuration is missing")
    resolved = resolver.resolve(strict=True)
    if not resolved.is_relative_to(Path("/etc")):
        command.extend(_resolver_mount_args(resolved))
    return command + ["--"]


def _resolver_mount_args(resolved: Path) -> list[str]:
    """Expose only the resolver file, never the rest of host /run."""
    if not resolved.is_relative_to(Path("/run")) or resolved == Path("/run"):
        raise RuntimeError("resolver target outside /etc or /run requires review")
    parents = []
    current = resolved.parent
    while current != Path("/"):
        parents.append(current)
        current = current.parent
    return [part for parent in reversed(parents) for part in ("--dir", str(parent))] + [
        "--ro-bind", str(resolved), str(resolved)]


def codex_preflight(trial: Path, home: Path, *, read_only_trial: bool = False) -> None:
    probe = """from pathlib import Path
import errno, secrets
from urllib.error import HTTPError
from urllib.request import urlopen
assert Path('/trial/FEATURE.md').is_file()
assert not Path('/workspace').exists()
assert not Path('/proc/1/root/workspace').exists()
assert Path('/etc/resolv.conf').is_file()
try:
    urlopen('https://api.openai.com/v1/models', timeout=10)
except HTTPError as response:
    assert response.code == 401, f'provider probe returned HTTP {response.code}'
else:
    raise AssertionError('unauthenticated provider probe unexpectedly succeeded')
p = Path('/trial') / ('.runner-probe-' + secrets.token_hex(16))
if p.exists() or p.is_symlink():
    raise AssertionError('probe path collided with candidate source')
if READ_ONLY:
    try:
        p.open('x').close()
    except OSError as error:
        if error.errno not in (errno.EROFS, errno.EACCES, errno.EPERM):
            raise
    else:
        p.unlink()
        raise AssertionError('decision source is writable')
else:
    with p.open('x') as handle:
        handle.write('ok')
    assert p.read_text() == 'ok'
    p.unlink()
""".replace("READ_ONLY", "True" if read_only_trial else "False")
    prefix = bwrap_prefix(trial, home, read_only_trial=read_only_trial)
    clean_env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                 "HOME": str(home), "LANG": os.environ.get("LANG", "C.UTF-8")}
    # Exercise the exact effective network route that the live runner passes
    # to Codex.  The probe sends no provider key and consumes no model tokens.
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
        if os.environ.get(name):
            clean_env[name] = os.environ[name]
    result = subprocess.run(prefix + ["/usr/bin/python3", "-c", probe],
                            env=clean_env, capture_output=True, timeout=20, check=False)
    if result.returncode != 0:
        raise RuntimeError("agent filesystem isolation preflight failed: " +
                           result.stderr.decode("utf-8", "replace")[:600])
    executable = shutil.which("codex")
    if not executable or not Path(executable).resolve().is_relative_to(Path("/usr")):
        raise RuntimeError("pinned Codex executable is missing from the isolated tool mount")
    # The outer mount is the sole filesystem boundary.  CI permits this
    # namespace but refuses a second namespace inside it.  Check that the
    # pinned CLI starts within that boundary without a credential or request.
    # The live command uses danger-full-access *inside* this closed mount to
    # avoid Codex creating a second sandbox; the trial bind above determines
    # whether source is writable or read-only.
    result = subprocess.run(prefix + [executable, "exec", "--help"],
                            env=clean_env, capture_output=True, timeout=45, check=False)
    if result.returncode != 0:
        raise RuntimeError("isolated Codex CLI preflight failed: " +
                           result.stderr.decode("utf-8", "replace")[:600])


def codex_command(trial: Path, home: Path, model: str, effort: str,
                  *, read_only_trial: bool = False) -> list[str]:
    binary = shutil.which("codex")
    if binary is None or not Path(binary).resolve().is_relative_to(Path("/usr")):
        raise RuntimeError("live Codex executable must be installed under /usr")
    return bwrap_prefix(trial, home, read_only_trial=read_only_trial) + [
        binary, "exec", "--skip-git-repo-check", "--ephemeral", "--json",
        "--sandbox", "danger-full-access", "--model", model,
        "-c", f"model_reasoning_effort={effort}", "-"]
