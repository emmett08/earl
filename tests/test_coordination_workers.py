"""Command workers bound and retain one independent execution without retries."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import pytest

from eal.coordination.workers import CommandWorker, WorkerInterrupted


pytestmark = pytest.mark.skipif(os.name != "posix", reason="Command workers require POSIX")


def worker(code, *, mode="software_test", timeout=3, cap=8192, environment=None, workspace=None):
    return CommandWorker((sys.executable, "-I", "-c", code), execution_mode=mode,
                         timeout_seconds=timeout, max_output_bytes=cap,
                         environment=environment, workspace=workspace)


def test_fresh_processes_consume_only_their_stdin_context(tmp_path, monkeypatch):
    monkeypatch.setenv("UNAUTHORIZED_WORKER_SECRET", "must not inherit")
    adapter = worker("import json, os, sys; context=json.load(sys.stdin); "
                     "print(json.dumps({'context':context,'pid':os.getpid(),'env':dict(os.environ)}))",
                     environment={"PERMITTED_VALUE": "public"}, workspace=tmp_path)
    first = adapter.execute({"private_input": "alpha", "literal": "$(touch forbidden)"}, "call-1", 3)
    second = adapter.execute({"private_input": "beta"}, "call-2", 3)
    assert first.response["context"] == {"private_input": "alpha", "literal": "$(touch forbidden)"}
    assert second.response["context"] == {"private_input": "beta"}
    assert first.response["pid"] != second.response["pid"]
    assert "UNAUTHORIZED_WORKER_SECRET" not in first.response["env"]
    assert first.response["env"]["PERMITTED_VALUE"] == "public"
    assert not (tmp_path / "forbidden").exists()
    assert first.execution_id.startswith("command:call-1:")
    assert first.execution_mode == "software_test"
    assert first.evidence["model"] is None
    assert first.evidence["usage"] is None
    assert first.evidence["returncode"] == 0
    assert first.raw_response == json.dumps(first.response).encode() + b"\n"


@pytest.mark.parametrize("raw", [
    b'{"answer":1,"answer":2}', b'{"answer":NaN}', b'{"answer":Infinity}', b'{"answer":1e9999}',
    b'{"answer":1}\n{"answer":2}', b'[]', b'{"answer":"\xff"}', b'not JSON', b'',
])
def test_rejects_malformed_or_nonfinal_json_and_retains_exact_raw(raw):
    adapter = worker(f"import sys; sys.stdout.buffer.write({raw!r})")
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "invalid-json", 3)
    failure = caught.value
    assert failure.reason == "invalid_response"
    assert failure.raw_response == raw
    assert failure.evidence["execution_error"] == "invalid_response"


def test_nonzero_exit_retains_output_and_redacts_explicit_environment(tmp_path):
    token = "supersecretworkercredential"
    adapter = worker("import json, os, sys; print(json.dumps({'partial':True})); "
                     "print('failure '+os.environ['API_KEY'],file=sys.stderr); sys.exit(17)",
                     environment={"API_KEY": token}, workspace=tmp_path)
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "exit-17", 3)
    failure = caught.value
    assert failure.reason == "nonzero_exit"
    assert failure.evidence["returncode"] == 17
    assert json.loads(failure.raw_response) == {"partial": True}
    assert failure.evidence["stderr"] == "failure [redacted]\n"
    assert token not in str(failure)
    assert token not in json.dumps(failure.evidence)


@pytest.mark.parametrize("mode", ["provider", "actual_host_agent"])
def test_live_command_requires_external_receipt_and_omits_stderr(mode):
    payload = {"response": {"answer": 7}, "execution": {
        "execution_id": "external-execution-42", "model": "operator-model",
        "usage": {"input_tokens": 19, "output_tokens": 5, "total_tokens": 24},
    }}
    raw = json.dumps(payload).encode() + b"\n"
    adapter = worker(f"import sys; sys.stdout.buffer.write({raw!r}); "
                     "print('unknown-provider-secret',file=sys.stderr)", mode=mode)
    result = adapter.execute({}, "reserved-live-call", 3)
    assert result.execution_id == "external-execution-42"
    assert result.execution_mode == mode
    assert result.response == {"answer": 7}
    assert result.raw_response == raw
    assert result.evidence["model"] == "operator-model"
    assert result.evidence["usage"]["total_tokens"] == 24
    assert result.evidence["receipt_verification"] == "operator_command_assertion"
    assert "stderr" not in result.evidence
    assert "unknown-provider-secret" not in json.dumps(result.evidence)


@pytest.mark.parametrize("mode", ["provider", "actual_host_agent"])
@pytest.mark.parametrize("execution", [
    None,
    {"execution_id": "live-call", "model": None, "usage": None},
    {"execution_id": "command:live-call:123", "model": None, "usage": None},
    {"execution_id": "real-id", "model": None, "usage": {"input_tokens": True}},
    {"execution_id": "real-id", "model": None, "usage": {"input_tokens": -1}},
    {"execution_id": "real-id", "model": None, "usage": {"cost": 0.1}},
    {"execution_id": "real-id", "model": None, "usage": None, "api_key": "secret"},
])
def test_refuses_fabricated_local_ids_missing_live_receipts_and_invalid_usage(mode, execution):
    payload = {"answer": 7} if execution is None else {"response": {"answer": 7}, "execution": execution}
    raw = json.dumps(payload).encode()
    adapter = worker(f"import sys; sys.stdout.buffer.write({raw!r})", mode=mode)
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "live-call", 3)
    assert caught.value.reason == "invalid_response"
    assert caught.value.execution_id.startswith("command:live-call:")
    assert caught.value.raw_response == raw
    assert caught.value.evidence["model"] is None


def test_live_receipt_can_retain_unknown_model_and_usage_without_inventing_costs():
    raw = b'{"response":{"answer":7},"execution":{"execution_id":"external-7","model":null,"usage":null}}'
    result = worker(f"import sys; sys.stdout.buffer.write({raw!r})", mode="provider").execute({}, "call-7", 3)
    assert result.evidence["usage"] is None
    assert result.evidence["model"] is None
    assert "usd" not in result.evidence


def test_combined_stdout_stderr_cap_is_enforced_while_streaming():
    adapter = worker("import os; os.write(1,b'x'*96); os.write(2,b'y'*96); "
                     "os.write(1,b'z'*1000000)", cap=128)
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "oversized", 3)
    failure = caught.value
    assert failure.reason == "output_limit"
    assert len(failure.raw_response) <= 128
    assert failure.evidence["stdout_bytes"] + failure.evidence["stderr_bytes"] == 128
    assert failure.evidence["output_truncated"] is True
    assert failure.evidence["returncode"] is not None


def test_context_is_written_nonblocking_even_if_worker_never_reads_stdin():
    adapter = worker("import time; time.sleep(10)", timeout=1)
    started = time.monotonic()
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({"large": "x" * 1_000_000}, "blocked-stdin", 3)
    assert caught.value.reason == "timeout"
    assert 0.8 <= time.monotonic() - started < 4


def test_remaining_run_budget_shortens_worker_timeout():
    adapter = worker("import time; time.sleep(10)", timeout=10)
    started = time.monotonic()
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "run-deadline", 1)
    assert caught.value.reason == "timeout"
    assert 0.8 <= time.monotonic() - started < 4


def test_cancelled_before_launch_has_no_process_effect(tmp_path):
    marker = tmp_path / "launched"
    adapter = worker(f"from pathlib import Path; Path({str(marker)!r}).touch()")
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "cancel-before", 3, should_stop=lambda: True)
    assert caught.value.reason == "cancelled"
    assert caught.value.evidence["supervisor_pid"] is None
    assert not marker.exists()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper makes descendant disappearance observable")
@pytest.mark.parametrize("outcome", ["completed", "timeout", "cancelled", "output_limit"])
def test_descendants_are_stopped_and_reaped_before_return(tmp_path, outcome):
    pidfile = tmp_path / "descendant.pid"
    code = (
        "import json, os, subprocess, sys, time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(30)']); "
        f"Path({str(pidfile)!r}).write_text(str(child.pid)); "
    )
    if outcome == "completed":
        code += "print(json.dumps({'child_pid':child.pid}))"
    elif outcome == "output_limit":
        code += "os.write(1,b'x'*1000000); time.sleep(30)"
    else:
        code += "time.sleep(30)"
    adapter = worker(code, timeout=1 if outcome == "timeout" else 4, cap=256)
    if outcome == "completed":
        result = adapter.execute({}, "descendants", 4)
        assert result.response["child_pid"] == int(pidfile.read_text())
    else:
        with pytest.raises(WorkerInterrupted) as caught:
            adapter.execute({}, "descendants", 4,
                            should_stop=(lambda: pidfile.exists()) if outcome == "cancelled" else None)
        assert caught.value.reason == outcome
    child_pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_failed_launch_does_not_expose_credentials_in_path(tmp_path):
    secret = "credential-command-path"
    adapter = CommandWorker((str(tmp_path / secret),), execution_mode="software_test",
                            timeout_seconds=2, max_output_bytes=1024)
    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "missing-command", 2)
    assert caught.value.reason == "nonzero_exit"
    assert secret not in str(caught.value)
    # Startup diagnostics can include argv, so trusted environments should not
    # place credentials in arguments; evidence only offers bounded software stderr.
    assert len(caught.value.evidence["stderr"]) <= 1024


@pytest.mark.parametrize("kwargs", [
    {"argv": "echo hi"}, {"argv": []}, {"argv": ["x\0"]},
    {"execution_mode": "live"}, {"execution_mode": {}}, {"timeout_seconds": True}, {"timeout_seconds": 0},
    {"max_output_bytes": 0}, {"max_output_bytes": True},
    {"environment": {"A": 3}}, {"environment": {"A=B": "x"}},
    {"environment": {"A": "x\0y"}},
])
def test_invalid_configuration_is_rejected_before_launch(kwargs):
    options = {"argv": [sys.executable], "execution_mode": "software_test",
               "timeout_seconds": 2, "max_output_bytes": 1024}
    options.update(kwargs)
    with pytest.raises(ValueError):
        CommandWorker(**options)


def test_invalid_context_and_reservation_inputs_are_rejected_before_launch():
    adapter = worker("raise AssertionError('must not execute')")
    with pytest.raises(ValueError):
        adapter.execute({"bad": float("nan")}, "call", 2)
    with pytest.raises(ValueError):
        adapter.execute({"huge": "x" * (4 * 1024 * 1024)}, "call", 2)
    with pytest.raises(ValueError):
        adapter.execute({}, "not\na valid ID", 2)
    with pytest.raises(ValueError):
        adapter.execute({}, "call", 0)


def test_no_automatic_repeat_after_interruption(tmp_path):
    counter = tmp_path / "effects"
    code = f"from pathlib import Path; import time; p=Path({str(counter)!r}); p.write_text(p.read_text()+'x' if p.exists() else 'x'); time.sleep(30)"
    with pytest.raises(WorkerInterrupted):
        worker(code, timeout=1).execute({}, "effect-once", 2)
    assert counter.read_text() == "x"


def test_cancellation_callback_failure_cleans_up_and_does_not_expose_private_text(tmp_path):
    marker = tmp_path / "started"
    adapter = worker(f"from pathlib import Path; import time; Path({str(marker)!r}).touch(); time.sleep(30)")

    def broken_cancellation():
        if marker.exists():
            raise RuntimeError("private-cancellation-controller-details")
        return False

    with pytest.raises(WorkerInterrupted) as caught:
        adapter.execute({}, "callback-failure", 3, should_stop=broken_cancellation)
    assert caught.value.reason == "supervisor_failure"
    assert marker.exists()
    assert "private-cancellation-controller-details" not in str(caught.value)


def test_prelaunch_callback_failure_retains_failure_without_private_exception_text():
    def broken_cancellation():
        raise RuntimeError("private-before-launch")

    with pytest.raises(WorkerInterrupted) as caught:
        worker("raise AssertionError('must not launch')").execute({}, "callback-start", 3,
                                                                    should_stop=broken_cancellation)
    assert caught.value.reason == "supervisor_failure"
    assert caught.value.evidence["supervisor_pid"] is None
    assert "private-before-launch" not in str(caught.value)
