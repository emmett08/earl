"""Launch and cancel a collector supervisor through an owned pipe."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys

from .acquisition_coordination import inherited_acquisition_descriptor
from .command_supervisor import MAX_CONFIG_BYTES


@dataclass(frozen=True)
class CollectorStatus:
    """Report the collector's exit independently of supervisor termination."""

    returncode: int
    timed_out: bool


@dataclass
class SupervisedCommand:
    """Expose collector status separately from the supervising process status."""

    process: subprocess.Popen[bytes]
    status_descriptor: int
    _status: CollectorStatus | None = field(default=None, init=False, repr=False)

    def collector_status(self) -> CollectorStatus:
        if self._status is not None:
            return self._status
        if self.process.returncode is None:
            raise RuntimeError("The command supervisor has not exited")
        encoded = os.read(self.status_descriptor, 128)
        if not encoded:
            if self.process.returncode != 0:
                self._status = CollectorStatus(self.process.returncode, False)
                return self._status
            raise RuntimeError("The command supervisor returned no collector status")
        try:
            result = json.loads(encoded)
        except ValueError:
            raise RuntimeError("Invalid collector status from command supervisor") from None
        if (not isinstance(result, dict) or set(result) != {"returncode", "timed_out"}
                or type(result["returncode"]) is not int
                or not -127 <= result["returncode"] <= 255
                or type(result["timed_out"]) is not bool):
            raise RuntimeError("Invalid collector status from command supervisor")
        self._status = CollectorStatus(result["returncode"], result["timed_out"])
        return self._status


@contextmanager
def supervised_command(argv: Sequence[str], *, workspace: Path,
                       environ: Mapping[str, str], timeout: float) -> Iterator[SupervisedCommand]:
    configuration = json.dumps({"argv": list(argv), "environment": dict(environ)},
                               ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(configuration) > MAX_CONFIG_BYTES:
        raise ValueError("Command supervisor configuration exceeds its byte limit")
    owner_read = owner_write = config_read = config_write = status_read = status_write = -1
    process = None
    try:
        owner_read, owner_write = os.pipe()
        config_read, config_write = os.pipe()
        status_read, status_write = os.pipe()
        lease = inherited_acquisition_descriptor()
        inherited = (owner_read, config_read, status_write)
        if lease is not None:
            inherited += (lease,)
        supervisor = Path(__file__).with_name("command_supervisor.py")
        process = subprocess.Popen(
            [sys.executable, "-I", str(supervisor), str(owner_read),
             str(lease if lease is not None else -1), str(config_read),
             str(status_write), str(timeout)],
            cwd=workspace, env={}, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, pass_fds=inherited,
        )
        os.close(owner_read)
        owner_read = -1
        os.close(config_read)
        config_read = -1
        os.close(status_write)
        status_write = -1
        with os.fdopen(config_write, "wb") as stream:
            config_write = -1
            stream.write(configuration)
        yield SupervisedCommand(process, status_read)
    finally:
        # EOF also occurs automatically if the application is killed. The
        # independently running supervisor cleans the group while owning
        # the shared lease, then exits and releases its descriptor.
        if owner_write >= 0:
            os.close(owner_write)
        if owner_read >= 0:
            os.close(owner_read)
        if config_read >= 0:
            os.close(config_read)
        if config_write >= 0:
            os.close(config_write)
        if status_write >= 0:
            os.close(status_write)
        if process is not None:
            try:
                process.wait(timeout=5)
            finally:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
                if status_read >= 0:
                    os.close(status_read)
        elif status_read >= 0:
            os.close(status_read)
