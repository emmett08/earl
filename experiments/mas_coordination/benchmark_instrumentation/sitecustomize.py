"""Count actual subprocess starts in isolated benchmark Python descendants.

Enabled only by the benchmark's explicit BENCHMARK_LAUNCH_LOG environment.
The log records classifications, not environment values or message contents.
"""
import json
import os
from pathlib import Path
import subprocess
import time


def classify(arguments):
    if isinstance(arguments, (str, bytes)):
        return {"category": "shell"}
    argv = [str(item) for item in arguments]
    executable = Path(argv[0]).name if argv else "unknown"
    if ("mas_protocol.mcp_server" in argv or "eal.coordination.lab_server" in argv
            or any(Path(argument).name == "lab_server.py" for argument in argv[1:])):
        category = "mcp_server"
    elif "mas_protocol.cli" in argv:
        category = "lab_cli"
    elif "codec" in executable or "transport" in executable:
        category = "rust_codec"
    else:
        category = "other"
    operations = {"encode", "parse", "serve", "init", "reserve", "finish", "status"}
    return {"category": category, "executable": executable,
            "operation": next((argument for argument in argv[1:] if argument in operations), None)}


def install(path):
    original = subprocess.Popen.__init__

    def traced(self, args, *positional, **keywords):
        original(self, args, *positional, **keywords)
        event = dict(classify(args), parent_pid=os.getpid(), child_pid=self.pid,
                     monotonic_ns=time.perf_counter_ns())
        encoded = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
        descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, encoded)
        finally:
            os.close(descriptor)

    subprocess.Popen.__init__ = traced
    return original


if os.environ.get("BENCHMARK_LAUNCH_LOG"):
    install(os.environ["BENCHMARK_LAUNCH_LOG"])


if os.environ.get("BENCHMARK_SERVER_PROFILE"):
    # Diagnostic cycles only. Profiling starts before runtime imports and its
    # cumulative times include startup and main-thread waiting, not just CPU.
    import atexit
    import cProfile
    import pstats
    import signal

    profile = cProfile.Profile()
    profile.enable()
    prefix = Path(os.environ["BENCHMARK_SERVER_PROFILE"])

    def save_profile():
        profile.disable()
        prefix.parent.mkdir(parents=True, exist_ok=True)
        with prefix.with_name(prefix.name + f"-{os.getpid()}.txt").open("w") as stream:
            pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(100)
            pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("tottime").print_stats(60)

    def terminate_profile(signum, frame):
        save_profile()
        raise SystemExit(0)

    atexit.register(save_profile)
    signal.signal(signal.SIGTERM, terminate_profile)
