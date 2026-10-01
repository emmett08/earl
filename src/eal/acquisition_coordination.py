"""Own local acquisition leases that survive their server through inherited descriptors."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import stat
import time

from filelock import FileLock, Timeout


_ACTIVE_DESCRIPTOR: ContextVar[int | None] = ContextVar("eal_acquisition_descriptor", default=None)


def inherited_acquisition_descriptor() -> int | None:
    """Borrow the current lease for a command supervisor; ownership stays with the caller."""
    return _ACTIVE_DESCRIPTOR.get()


class WorkspaceAcquisition:
    """Exclude local acquisitions until every owning process closes its lease."""

    def __init__(self, workspace: Path):
        directory = workspace / ".eal"
        directory.mkdir(parents=True, exist_ok=True)
        details = directory.lstat()
        if not stat.S_ISDIR(details.st_mode):
            raise PermissionError("The MCP acquisition directory must be a regular directory")
        if os.name == "posix" and (details.st_uid != os.getuid() or details.st_mode & 0o022):
            raise PermissionError("The MCP acquisition directory must be owned by the process and not writable by others")
        self.path = directory / "mcp-acquisition.lock"
        if self.path.is_symlink():
            raise PermissionError("The MCP acquisition lock must not be a symlink")

    @contextmanager
    def hold(self, *, timeout: float = 120):
        if os.name != "posix":
            # The command adapter requires POSIX; file-only operations retain
            # the portable server-process exclusion used by FileLock.
            with FileLock(self.path, timeout=timeout, mode=0o600):
                yield
            return
        import fcntl

        try:
            existing = self.path.lstat()
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(existing.st_mode):
                raise PermissionError("The MCP acquisition lock must be a private regular file")
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            details = os.fstat(descriptor)
            named = self.path.lstat()
            if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid()
                    or stat.S_IMODE(details.st_mode) != 0o600 or details.st_nlink != 1
                    or (details.st_dev, details.st_ino) != (named.st_dev, named.st_ino)):
                raise PermissionError("The MCP acquisition lock must be a private regular file")
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise Timeout(str(self.path)) from None
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
            token = _ACTIVE_DESCRIPTOR.set(descriptor)
            try:
                yield
            finally:
                _ACTIVE_DESCRIPTOR.reset(token)
        finally:
            # flock belongs to the open file description. Closing this copy,
            # rather than LOCK_UN, preserves ownership in a live supervisor.
            os.close(descriptor)
