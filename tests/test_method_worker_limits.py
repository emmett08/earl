"""Spawn startup must not consume the registered callback's CPU allowance."""
import os
import time

import pytest

from eal.api_load_methods import CONTRACT, registry
from eal.methods import _worker
from eal.modes import assess_mode


def _worker_after_expensive_startup(payload, connection, contract, limits):
    # Model imports in a spawned MCP process on a slower runner. RLIMIT_CPU
    # counts process CPU from birth, including work before _worker is entered.
    while time.process_time() < 1.2:
        pass
    _worker(payload, connection, contract, limits)


@pytest.mark.skipif(os.name != "posix", reason="POSIX worker resource limits")
def test_spawn_startup_does_not_exhaust_callback_cpu_budget(monkeypatch):
    monkeypatch.setattr("eal.methods._worker", _worker_after_expensive_startup)
    result = assess_mode(CONTRACT.identifier, [{
        "id": "run", "kind": "api_report",
        "value": {"request_count": 100, "p95_ms": 200, "error_rate_percent": 1},
    }], [], registry=registry())
    assert result["status"] == "supported", result["reasons"]
    assert result["details"]["passes"] is True
