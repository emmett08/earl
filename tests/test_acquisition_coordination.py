"""Process ownership and thread propagation of local acquisition leases."""

from __future__ import annotations

from contextvars import ContextVar
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from filelock import Timeout
import pytest

from eal.acquisition_coordination import WorkspaceAcquisition, inherited_acquisition_descriptor
from eal.collection_scheduler import CollectionScheduler


pytestmark = pytest.mark.skipif(os.name != "posix", reason="Descriptor-owned leases require POSIX")


def _wait_for(path: Path, process: subprocess.Popen, timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        assert process.poll() is None, "Lease owner exited before reporting its state"
        assert time.monotonic() < deadline, "Lease owner did not report its state"
        time.sleep(0.01)


def _stop_child(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    try:
        process.communicate(b"x", timeout=3)
    except (subprocess.TimeoutExpired, BrokenPipeError):
        process.kill()
        process.communicate(timeout=3)


@pytest.mark.parametrize("exceptional_exit", [False, True])
def test_inherited_descriptor_owns_lease_after_parent_context_closes(tmp_path, exceptional_exit):
    """A live supervisor owns the lock until its descriptor closes, not until exit."""
    coordination = WorkspaceAcquisition(tmp_path)
    child = None
    assert inherited_acquisition_descriptor() is None

    class InterruptedAcquisition(Exception):
        pass

    try:
        try:
            with coordination.hold(timeout=0):
                descriptor = inherited_acquisition_descriptor()
                assert descriptor is not None
                child = subprocess.Popen(
                    [sys.executable, "-u", "-c", '''import os, pathlib, sys
descriptor = int(sys.argv[1])
workspace = pathlib.Path(sys.argv[2])
os.fstat(descriptor)
(workspace / "inherited").touch()
sys.stdin.buffer.read(1)
os.close(descriptor)
(workspace / "closed").touch()
sys.stdin.buffer.read(1)
''', str(descriptor), str(tmp_path)],
                    pass_fds=(descriptor,),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                _wait_for(tmp_path / "inherited", child)
                if exceptional_exit:
                    raise InterruptedAcquisition
        except InterruptedAcquisition:
            assert exceptional_exit

        assert inherited_acquisition_descriptor() is None
        with pytest.raises(Timeout):
            with WorkspaceAcquisition(tmp_path).hold(timeout=0):
                pytest.fail("Parent exit unlocked a descriptor still owned by its child")

        child.stdin.write(b"c")
        child.stdin.flush()
        _wait_for(tmp_path / "closed", child)
        assert child.poll() is None, "The test must prove admission before child exit"
        with WorkspaceAcquisition(tmp_path).hold(timeout=0):
            assert inherited_acquisition_descriptor() is not None
        assert inherited_acquisition_descriptor() is None
    finally:
        _stop_child(child)


@pytest.mark.parametrize("unsafe_kind", ["fifo", "symlink", "public_mode", "hardlink"])
def test_unsafe_lock_nodes_are_rejected_before_locking(tmp_path, monkeypatch, unsafe_kind):
    import fcntl

    coordination = WorkspaceAcquisition(tmp_path)
    path = coordination.path
    if unsafe_kind == "fifo":
        os.mkfifo(path, mode=0o600)
    elif unsafe_kind == "symlink":
        target = tmp_path / "target"
        target.write_text("")
        target.chmod(0o600)
        path.symlink_to(target)
    elif unsafe_kind == "public_mode":
        path.write_text("")
        path.chmod(0o644)
    else:
        target = tmp_path / "target"
        target.write_text("")
        target.chmod(0o600)
        os.link(target, path)

    def refuse_locking(*args, **kwargs):
        pytest.fail("An unsafe acquisition node reached OS lock acquisition")

    monkeypatch.setattr(fcntl, "flock", refuse_locking)
    with pytest.raises(PermissionError):
        with coordination.hold(timeout=0):
            pytest.fail("An unsafe acquisition node was admitted")


def test_independent_collectors_receive_lease_and_isolated_request_context(tmp_path):
    """Both initial scheduling and slot refills retain supervisor ownership context."""
    coordination = WorkspaceAcquisition(tmp_path)
    request_id = ContextVar("request_id", default=None)
    token = request_id.set("assessment-request")
    rendezvous = threading.Barrier(2)

    def collect(name):
        inherited = inherited_acquisition_descriptor()
        request = request_id.get()
        # Each scheduled job gets its own context, including when a pool worker
        # is reused. A collector's changes cannot contaminate the following job.
        request_id.set(name)
        rendezvous.wait(timeout=3)
        return inherited, request, threading.get_ident()

    try:
        with coordination.hold(timeout=0):
            descriptor = inherited_acquisition_descriptor()
            assert descriptor is not None
            results = CollectionScheduler(max_workers=2).run(
                ["first", "second", "third", "fourth"], lambda _: True, collect)
            assert all(value[:2] == (descriptor, "assessment-request") for value in results.values())
            assert len({value[2] for value in results.values()}) == 2
            assert request_id.get() == "assessment-request"
        assert inherited_acquisition_descriptor() is None
    finally:
        request_id.reset(token)
