"""A disconnected stdio client cannot release live serial collector work."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
import signal
import sys

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


pytestmark = pytest.mark.skipif(os.name != "posix", reason="Command collectors require POSIX")

SOURCE = '''language "EAL/3"
environment lab {
  require "site" == "bench"
}
tool runner {
  version "1"
}
evidence measured {
  tool runner
  kind test
  environment lab
  max_age 60
  require "passed" == true
}
reasoning measurement {
  method "structured/1"
  rationale "The bounded observation supplies support."
}
claim works {
  statement "The requested check passes."
  environment lab
}
argument result = [evidence measured] via measurement => works
'''


def _collector_workspace(workspace: Path, *, detached_descendant: bool = False) -> Path:
    # The child owns the activity lock itself. SIGKILL therefore cannot leave a
    # stale directory falsely reporting overlap after the execution has stopped.
    (workspace / "child.py").write_text('''import fcntl, os, pathlib, sys, time
workspace = pathlib.Path(__file__).parent
invocation = sys.argv[1]
with (workspace / "activity.lock").open("a") as activity:
    try:
        fcntl.flock(activity, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        (workspace / "overlap").write_text(invocation)
        raise SystemExit(17)
    (workspace / (invocation + ".child.pid")).write_text(str(os.getpid()))
    (workspace / (invocation + ".started")).touch()
    deadline = time.monotonic() + 20
    while invocation == "first" and not (workspace / "release-first").exists():
        if time.monotonic() >= deadline:
            raise SystemExit(18)
        time.sleep(0.01)
''')
    collector = workspace / "collector.py"
    collector.write_text('''import json, os, pathlib, subprocess, sys, time
workspace = pathlib.Path(__file__).parent
request = json.load(sys.stdin)
invocation = request["context"]["invocation"]
(workspace / (invocation + ".collector.pid")).write_text(str(os.getpid()))
(workspace / (invocation + ".attempted")).touch()
''' + f"detached_descendant = {detached_descendant!r}\n" + '''
child = subprocess.Popen([sys.executable, str(workspace / "child.py"), invocation],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
if detached_descendant and invocation == "first":
    deadline = time.monotonic() + 5
    while not (workspace / "first.started").exists():
        if child.poll() is not None or time.monotonic() >= deadline:
            raise SystemExit(19)
        time.sleep(0.01)
else:
    code = child.wait()
    if code:
        raise SystemExit(code)
print(json.dumps({"value": {"passed": True}}))
''')
    registry = workspace / "tools.toml"
    registry.write_text(
        '[tools.runner]\nkind = "command"\nversion = "1"\ntimeout_seconds = 25\n'
        + "argv = " + json.dumps([sys.executable, str(collector)]) + "\n"
    )
    return registry


def _arguments(invocation: str) -> dict:
    return {"source": SOURCE, "context": {"site": "bench", "invocation": invocation}}


def _transport(workspace: Path, registry: Path, *, pid_file: Path | None = None) -> StdioTransport:
    arguments = ["-m", "eal.server", "--workspace", str(workspace), "--registry", str(registry)]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("EAL_MCP_")}
    if pid_file is not None:
        # This launcher calls the public composition root in its own process;
        # it exposes the process we own without inspecting FastMCP internals.
        launcher = workspace / "server_launcher.py"
        launcher.write_text(
            "import os\nfrom pathlib import Path\n"
            "Path(os.environ['EAL_TEST_SERVER_PID_FILE']).write_text(str(os.getpid()))\n"
            "from eal.server import main\nmain()\n"
        )
        arguments = [str(launcher), *arguments[2:]]
        environment["EAL_TEST_SERVER_PID_FILE"] = str(pid_file)
    return StdioTransport(
        command=sys.executable,
        args=arguments,
        env=environment,
        keep_alive=False,
    )


async def _wait_until(condition, timeout: float = 5) -> bool:
    """Bound polling for an observed process event, without a fixed startup sleep."""
    try:
        async with asyncio.timeout(timeout):
            while not condition():
                await asyncio.sleep(0.01)
    except TimeoutError:
        return False
    return True


def _cleanup_collectors(workspace: Path) -> None:
    (workspace / "release-first").touch()
    for path in workspace.glob("*.collector.pid"):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(int(path.read_text()), signal.SIGKILL)
    for path in workspace.glob("*.child.pid"):
        with contextlib.suppress(ProcessLookupError):
            os.kill(int(path.read_text()), signal.SIGKILL)


async def _assert_next_collection_is_serial(workspace: Path, registry: Path) -> None:
    """The next real server must complete, with no simultaneous child execution."""
    async with Client(_transport(workspace, registry), mode="auto") as client:
        request = asyncio.create_task(client.call_tool("eal_collect", _arguments("second")))
        try:
            # Starting the second collector while the first is still running
            # would leave an overlap marker. A queued request is then released
            # explicitly so the test also verifies that admission progresses.
            await _wait_until(lambda: (workspace / "second.started").exists()
                              or (workspace / "overlap").exists(), timeout=1)
        finally:
            (workspace / "release-first").touch()
        result = await asyncio.wait_for(request, timeout=10)
    assert not result.is_error
    assert not (workspace / "overlap").exists(), "Serial collectors overlapped after client exit"
    assert result.structured_content["records"]["measured"]["status"] == "ok"
    assert (workspace / "second.started").exists(), "The second collector never executed"


def test_host_deadline_preserves_exclusion_until_collector_descendants_stop(tmp_path):
    """Exercise eal-host's actual deadline and subprocess context shutdown."""
    registry = _collector_workspace(tmp_path)

    async def exercise():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "eal.host", "--workspace", str(tmp_path),
            "--registry", str(registry), "--timeout", "2",
            env={key: value for key, value in os.environ.items() if not key.startswith("EAL_MCP_")},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output = asyncio.create_task(process.communicate(json.dumps(
            {"operation": "collect", **_arguments("first")}).encode()))
        try:
            assert await _wait_until(lambda: (tmp_path / "first.started").exists()), (
                "The host deadline expired before the collector started"
            )
            stdout, _ = await asyncio.wait_for(output, timeout=10)
            assert process.returncode == 2
            response = json.loads(stdout)
            assert response["is_error"] is True
            assert "configured deadline" in response["error"]
            await _assert_next_collection_is_serial(tmp_path, registry)
        finally:
            _cleanup_collectors(tmp_path)
            if process.returncode is None:
                process.kill()
            await process.wait()
            if not output.done():
                await output

    asyncio.run(exercise())


def test_cancelled_stdio_request_preserves_exclusion_after_client_context_exit(tmp_path):
    registry = _collector_workspace(tmp_path)

    async def exercise():
        try:
            async with Client(_transport(tmp_path, registry), mode="auto") as client:
                request = asyncio.create_task(client.call_tool("eal_collect", _arguments("first")))
                assert await _wait_until(lambda: (tmp_path / "first.started").exists())
                request.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await request
            await _assert_next_collection_is_serial(tmp_path, registry)
        finally:
            _cleanup_collectors(tmp_path)

    asyncio.run(exercise())


def test_server_sigkill_preserves_exclusion_until_collector_descendants_stop(tmp_path):
    """The collector lease must outlive the process serving the MCP request."""
    registry = _collector_workspace(tmp_path)
    server_pid = tmp_path / "server.pid"

    async def exercise():
        try:
            async with Client(_transport(tmp_path, registry, pid_file=server_pid), mode="auto") as client:
                request = asyncio.create_task(client.call_tool("eal_collect", _arguments("first")))
                assert await _wait_until(lambda: (tmp_path / "first.started").exists())
                os.kill(int(server_pid.read_text()), signal.SIGKILL)
                with pytest.raises(Exception):
                    await asyncio.wait_for(request, timeout=5)
            await _assert_next_collection_is_serial(tmp_path, registry)
        finally:
            _cleanup_collectors(tmp_path)

    asyncio.run(exercise())


def test_collector_completion_stops_residual_descendants_before_serial_admission(tmp_path):
    """Closing collector pipes does not establish that its process group stopped."""
    registry = _collector_workspace(tmp_path, detached_descendant=True)

    async def exercise():
        try:
            async with Client(_transport(tmp_path, registry), mode="auto") as client:
                first = await asyncio.wait_for(
                    client.call_tool("eal_collect", _arguments("first")), timeout=10)
                assert not first.is_error
                assert first.structured_content["records"]["measured"]["status"] == "ok"
                assert (tmp_path / "first.started").exists()
                await _assert_next_collection_is_serial(tmp_path, registry)
        finally:
            _cleanup_collectors(tmp_path)

    asyncio.run(exercise())
