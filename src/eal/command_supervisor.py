"""Stop and reap one collector process group before releasing its inherited lease.

This executable helper receives an ownership-pipe descriptor, an optional
acquisition descriptor, a timeout and the trusted argv. Its stdin, stdout,
stderr, working directory and environment pass directly to the collector.
"""

from __future__ import annotations

import ctypes
import json
import os
import select
import signal
import subprocess
import sys
import time


MAX_CONFIG_BYTES = 4 * 1024 * 1024


def _adopt_descendants() -> None:
    if sys.platform.startswith("linux"):
        # Reap orphaned group members ourselves instead of relying on a
        # container's PID 1 to reap them before the next acquisition.
        library = ctypes.CDLL(None, use_errno=True)
        if library.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "Cannot supervise collector descendants")


def _stop_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    # Linux adopts the descendants above; other POSIX init processes reap
    # them. Retain the lease while any member of this group still exists.
    while True:
        try:
            while os.waitpid(-process.pid, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            pass
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)


def main() -> None:
    owner = int(sys.argv[1])
    lease = int(sys.argv[2])
    configuration = int(sys.argv[3])
    status = int(sys.argv[4])
    deadline = time.monotonic() + float(sys.argv[5])
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, request_stop)
    process = None
    returncode = 127
    timed_out = False
    try:
        _adopt_descendants()
        with os.fdopen(configuration, "rb") as stream:
            encoded = stream.read(MAX_CONFIG_BYTES + 1)
        if len(encoded) > MAX_CONFIG_BYTES:
            raise ValueError("Command supervisor configuration exceeds its byte limit")
        settings = json.loads(encoded)
        if stopping or select.select([owner], [], [], 0)[0]:
            return
        process = subprocess.Popen(settings["argv"], env=settings["environment"],
                                   stdin=sys.stdin, stdout=sys.stdout,
                                   stderr=sys.stderr, start_new_session=True)
        while not stopping and time.monotonic() < deadline:
            if process.poll() is not None:
                returncode = process.returncode
                break
            if select.select([owner], [], [], 0.05)[0]:
                stopping = True
        else:
            timed_out = not stopping
    except OSError as error:
        print(str(error), file=sys.stderr)
    except (ValueError, KeyError, TypeError):
        print("Invalid command supervisor configuration", file=sys.stderr)
    finally:
        if process is not None:
            _stop_group(process)
            returncode = process.returncode
        try:
            os.write(status, json.dumps({"returncode": returncode,
                                       "timed_out": timed_out}).encode("ascii"))
        except BrokenPipeError:
            pass
        finally:
            os.close(status)
        os.close(owner)
        if lease >= 0:
            os.close(lease)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
