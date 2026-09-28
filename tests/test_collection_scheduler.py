"""Operator-controlled collection concurrency and command environment."""

from __future__ import annotations

from threading import Barrier, Event, Lock, get_ident
import sys

import pytest

from eal.collection_scheduler import CollectionScheduler
from eal.tool_acquisition import MAX_REQUEST_BYTES, ToolBinding, ToolRegistry, strict_json


def test_unapproved_collectors_run_serially_in_requested_order():
    caller = get_ident()
    visited = []

    def collect_one(name):
        assert get_ident() == caller
        visited.append(name)
        return name.upper()

    results = CollectionScheduler(max_workers=4).run(
        ["first", "second", "third"], lambda _: False, collect_one)
    assert visited == ["first", "second", "third"]
    assert list(results) == visited
    assert list(results.values()) == ["FIRST", "SECOND", "THIRD"]


def test_approved_collectors_overlap_but_unsafe_collector_is_a_barrier():
    first_pair = Barrier(2, timeout=2)
    second_pair = Barrier(2, timeout=2)
    lock = Lock()
    completed = []

    def collect_one(name):
        if name in ("a", "b"):
            first_pair.wait()
        elif name in ("d", "e"):
            second_pair.wait()
        with lock:
            completed.append(name)
        return name.upper()

    names = ["a", "b", "unsafe", "d", "e"]
    results = CollectionScheduler(max_workers=2).run(
        names, lambda name: name != "unsafe", collect_one)
    assert list(results) == names
    assert [results[name] for name in names] == [name.upper() for name in names]
    assert set(completed[:2]) == {"a", "b"}
    assert completed[2] == "unsafe"
    assert set(completed[3:]) == {"d", "e"}


def test_only_max_workers_acquisitions_are_in_flight():
    rendezvous = Barrier(2, timeout=2)
    lock = Lock()
    active = 0
    maximum = 0

    def collect_one(name):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        if name in ("a", "b"):
            rendezvous.wait()
        with lock:
            active -= 1
        return name

    names = ["a", "b", "c", "d", "e", "f"]
    assert CollectionScheduler(2).run(names, lambda _: True, collect_one) == {
        name: name for name in names}
    assert maximum == 2


def test_free_parallel_slot_starts_next_call_while_another_remains_active():
    slow_started = Event()
    third_started = Event()

    def collect_one(name):
        if name == "slow":
            slow_started.set()
            assert third_started.wait(2)
        elif name == "fast":
            assert slow_started.wait(2)
        else:
            third_started.set()
        return name

    names = ["slow", "fast", "third"]
    assert CollectionScheduler(2).run(names, lambda _: True, collect_one) == {
        name: name for name in names}


@pytest.mark.parametrize("max_workers", [0, 33, True, 2.5, "2"])
def test_worker_limit_must_be_a_bounded_integer(max_workers):
    with pytest.raises(ValueError, match="max_workers"):
        CollectionScheduler(max_workers)


def test_scheduling_leaves_acquisition_identity_unchanged(tmp_path):
    base = '[tools.reader]\nkind="command"\nversion="1"\nargv=["true"]\n'
    path = tmp_path / "tools.toml"

    def binding(extra):
        path.write_text(base + extra)
        return ToolRegistry.load(path).binding_for("reader", version="1")

    original = binding("")
    assert original.parallel_safe is False
    assert binding('parallel_safe=false\n').binding_digest(
        b"x" * 32) == original.binding_digest(b"x" * 32)
    assert binding("parallel_safe=true\n").binding_digest(b"x" * 32) == original.binding_digest(b"x" * 32)
    assert binding('inherit_env=[]\n').binding_digest(b"x" * 32) != original.binding_digest(b"x" * 32)
    projected = binding('inherit_env=["PATH", "HOME"]\n').binding_digest(b"x" * 32)
    assert binding('inherit_env=["HOME", "PATH"]\n').binding_digest(b"x" * 32) == projected


def test_allowlisted_command_environment_is_exact_and_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("EAL_ALLOWED", "cluster-a")
    monkeypatch.setenv("EAL_IRRELEVANT", "first")
    script = tmp_path / "collector.py"
    script.write_text(
        "import json, os\n"
        "print(json.dumps({'value': {'allowed': os.environ.get('EAL_ALLOWED'), "
        "'irrelevant': os.environ.get('EAL_IRRELEVANT'), "
        "'configured': os.environ.get('EAL_CONFIGURED')}}))\n"
    )
    path = tmp_path / "tools.toml"
    path.write_text(
        '[tools.reader]\nkind="command"\nversion="1"\n'
        f'argv=[{sys.executable!r}, {str(script)!r}]\n'
        'inherit_env=["EAL_ALLOWED"]\n'
        '[tools.reader.env]\nEAL_CONFIGURED="from-operator"\n'
    )
    binding = ToolRegistry.load(path).binding_for("reader", version="1")
    identity = binding.process_environment_digest(b"x" * 32)
    result = ToolRegistry().acquire(binding, {"input": {}}, tmp_path, secret=b"x" * 32)
    assert result.error is None
    assert strict_json(result.stdout.decode())["value"] == {
        "allowed": "cluster-a", "irrelevant": None, "configured": "from-operator"}
    assert result.metadata["process_environment_digest"] == identity
    monkeypatch.setenv("EAL_IRRELEVANT", "second")
    assert binding.process_environment_digest(b"x" * 32) == identity
    monkeypatch.setenv("EAL_ALLOWED", "cluster-b")
    assert binding.process_environment_digest(b"x" * 32) != identity


@pytest.mark.parametrize("extra, expected", [
    ('parallel_safe="true"\n', "parallel_safe"),
    ('parallel_safe=1\n', "parallel_safe"),
    ('unrecognised=true\n', "Unknown registry settings"),
    ('inherit_env="PATH"\n', "inherit_env"),
    ('inherit_env=["PATH", "PATH"]\n', "inherit_env"),
    ('inherit_env=["INVALID-NAME"]\n', "inherit_env"),
])
def test_operator_binding_rejects_untyped_or_unknown_grants(tmp_path, extra, expected):
    path = tmp_path / "tools.toml"
    path.write_text('[tools.reader]\nkind="command"\nversion="1"\nargv=["true"]\n' + extra)
    with pytest.raises(ValueError, match=expected):
        ToolRegistry.load(path)


def test_file_import_cannot_declare_process_environment(tmp_path):
    path = tmp_path / "tools.toml"
    path.write_text('[tools.reader]\nkind="json_file"\nversion="1"\n'
                    'path="value.json"\ninherit_env=[]\n')
    with pytest.raises(ValueError, match="inherit_env"):
        ToolRegistry.load(path)


def test_oversized_tool_request_is_rejected_before_process_creation(tmp_path):
    marker = tmp_path / "started"
    script = tmp_path / "collector.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    binding = ToolBinding("collector", "command", "1", argv=(sys.executable, str(script)))
    request = {"input": "x" * MAX_REQUEST_BYTES}

    with pytest.raises(ValueError, match="Tool request exceeds"):
        ToolRegistry().acquire(binding, request, tmp_path, secret=b"x" * 32)
    assert not marker.exists()
