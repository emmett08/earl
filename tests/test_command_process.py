"""Collector supervision preserves the environment recorded in its acquisition."""

from __future__ import annotations

import errno
import os
import shutil
import signal
import subprocess
import sys
import time

import pytest

from eal.acquisition_coordination import WorkspaceAcquisition
from eal.command_process import supervised_command
from eal.tool_acquisition import ToolBinding, _execute


ENV_COMMAND = shutil.which("env")
pytestmark = pytest.mark.skipif(
    os.name != "posix" or ENV_COMMAND is None,
    reason="The bounded command adapter requires POSIX and an env command",
)


@pytest.mark.parametrize("environment", [
    {},
    {"LANG": "C", "LC_CTYPE": "C", "PYTHONCOERCECLOCALE": "0"},
    {"LANG": "C.UTF-8", "LC_CTYPE": "C.UTF-8", "EAL_TEST_VALUE": "literal value"},
])
def test_supervisor_passes_exact_effective_environment_without_locale_mutation(tmp_path, environment):
    binding = ToolBinding(
        name="environment", kind="command", version="1",
        argv=(ENV_COMMAND,), inherit_env=(), env=environment,
    )
    effective_environment = binding.effective_environment()
    private_key = b"x" * 32
    with WorkspaceAcquisition(tmp_path).hold(timeout=1):
        stdout, stderr, returncode, metadata = _execute(binding, {}, tmp_path, private_key)
    actual_environment = dict(line.split("=", 1) for line in stdout.decode("utf-8").splitlines())
    assert returncode == 0, stderr
    assert actual_environment == effective_environment
    assert metadata["process_environment_digest"] == binding.process_environment_digest(
        private_key, effective_env=actual_environment,
    )


@pytest.mark.parametrize(("code", "timeout", "expected_returncode", "execution_error"), [
    ("raise SystemExit(17)", 2, 17, None),
    ("import os, signal; os.kill(os.getpid(), signal.SIGTERM)", 2, -signal.SIGTERM, None),
    ("import time; time.sleep(10)", 2, -signal.SIGKILL, "timeout"),
])
def test_observation_records_actual_collector_status_after_supervisor_cleanup(
    tmp_path, code, timeout, expected_returncode, execution_error,
):
    binding = ToolBinding(
        name="status", kind="command", version="1",
        argv=(sys.executable, "-c", code), inherit_env=(), timeout_seconds=timeout,
    )
    with WorkspaceAcquisition(tmp_path).hold(timeout=1):
        stdout, stderr, returncode, metadata = _execute(binding, {}, tmp_path, b"x" * 32)
    assert returncode == expected_returncode
    assert metadata["returncode"] == expected_returncode
    assert metadata.get("execution_error") == execution_error
    assert len(stdout) + len(stderr) <= binding.max_output_bytes


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Requires FIFO creation")
def test_workspace_acquisition_refuses_fifo_before_opening_it(tmp_path, monkeypatch):
    coordinator = WorkspaceAcquisition(tmp_path)
    os.mkfifo(coordinator.path, 0o600)

    def unexpected_open(*args, **kwargs):
        raise AssertionError("The special lock file was opened")

    monkeypatch.setattr("eal.acquisition_coordination.os.open", unexpected_open)
    with pytest.raises(PermissionError, match="private regular file"):
        with coordinator.hold(timeout=1):
            pytest.fail("A FIFO was admitted as an acquisition lock")


@pytest.mark.parametrize("failed_pipe", [2, 3])
def test_partial_pipe_allocation_failure_closes_every_owned_descriptor(
    tmp_path, monkeypatch, failed_pipe,
):
    create_pipe = os.pipe
    allocated = []
    calls = 0

    def exhausted_pipe():
        nonlocal calls
        calls += 1
        if calls == failed_pipe:
            raise OSError(errno.EMFILE, "Too many open files")
        descriptors = create_pipe()
        allocated.extend(descriptors)
        return descriptors

    monkeypatch.setattr("eal.command_process.os.pipe", exhausted_pipe)
    with pytest.raises(OSError) as failure:
        with supervised_command((ENV_COMMAND,), workspace=tmp_path, environ={}, timeout=2):
            pytest.fail("A command started after ownership-pipe allocation failed")
    assert failure.value.errno == errno.EMFILE
    unclosed = []
    for descriptor in allocated:
        try:
            os.fstat(descriptor)
        except OSError as error:
            assert error.errno == errno.EBADF
        else:
            unclosed.append(descriptor)
            # Restore process state even when the regression assertion fails.
            os.close(descriptor)
    assert unclosed == [], "Partial pipe allocation leaked descriptors"


@pytest.mark.skipif(shutil.which("false") is None, reason="Requires a false command")
def test_supervisor_startup_failure_closes_process_streams_before_yield(tmp_path, monkeypatch):
    create_process = subprocess.Popen
    processes = []

    def supervisor_that_exits_before_reading_configuration(arguments, **options):
        process = create_process((shutil.which("false"),), **options)
        processes.append(process)
        return process

    monkeypatch.setattr("eal.command_process.subprocess.Popen",
                        supervisor_that_exits_before_reading_configuration)
    with pytest.raises(BrokenPipeError):
        with supervised_command((ENV_COMMAND,), workspace=tmp_path,
                                environ={"LARGE": "x" * 1_000_000}, timeout=2):
            pytest.fail("An exited supervisor accepted a collector")
    assert processes[0].returncode is not None
    streams = [processes[0].stdin, processes[0].stdout, processes[0].stderr]
    unclosed = [stream for stream in streams if stream is not None and not stream.closed]
    for stream in unclosed:
        stream.close()
    assert unclosed == [], "Supervisor startup failure leaked its process streams"


def test_supervisor_deadline_during_configuration_transfer_records_timeout(tmp_path, monkeypatch):
    open_stream = os.fdopen

    class DelayedConfigurationWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *arguments):
            return self.stream.__exit__(*arguments)

        def write(self, configuration):
            # The supervisor's deadline starts before reading this pipe; the
            # parent starts its command deadline after configuration transfer.
            time.sleep(0.5)
            return self.stream.write(configuration)

    def delayed_configuration_stream(descriptor, mode="r", *arguments, **options):
        stream = open_stream(descriptor, mode, *arguments, **options)
        return DelayedConfigurationWriter(stream) if mode == "wb" else stream

    monkeypatch.setattr("eal.command_process.os.fdopen", delayed_configuration_stream)
    binding = ToolBinding(
        name="deadline", kind="command", version="1",
        argv=(sys.executable, "-c", "import time; time.sleep(1)"),
        inherit_env=(), timeout_seconds=0.2,
    )
    with WorkspaceAcquisition(tmp_path).hold(timeout=1):
        _, _, returncode, metadata = _execute(binding, {}, tmp_path, b"x" * 32)
    assert returncode == -signal.SIGKILL
    assert metadata["execution_error"] == "timeout"


def test_output_limit_retains_priority_when_supervisor_cleanup_exceeds_wait_budget(
    tmp_path, monkeypatch,
):
    create_process = subprocess.Popen
    cleanup_deadlines = []

    def supervisor_with_delayed_initial_wait(arguments, **options):
        process = create_process(arguments, **options)
        wait = process.wait
        first_wait = True

        def wait_beyond_initial_budget(timeout=None):
            nonlocal first_wait
            if first_wait:
                first_wait = False
                cleanup_deadlines.append(timeout)
                raise subprocess.TimeoutExpired(process.args, timeout)
            return wait(timeout=timeout)

        process.wait = wait_beyond_initial_budget
        return process

    monkeypatch.setattr("eal.command_process.subprocess.Popen",
                        supervisor_with_delayed_initial_wait)
    binding = ToolBinding(
        name="output", kind="command", version="1",
        argv=(sys.executable, "-c", "print('x' * 10000)"),
        inherit_env=(), timeout_seconds=2, max_output_bytes=128,
    )
    with WorkspaceAcquisition(tmp_path).hold(timeout=1):
        stdout, stderr, _, metadata = _execute(binding, {}, tmp_path, b"x" * 32)
    assert len(cleanup_deadlines) == 1
    assert len(stdout) + len(stderr) == binding.max_output_bytes
    assert metadata["execution_error"] == "output_limit"
    assert metadata["output_truncated"] is True
