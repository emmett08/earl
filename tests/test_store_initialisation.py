"""First startup and index setup are coordinated across local processes."""

from concurrent.futures import ThreadPoolExecutor
import json
import multiprocessing
import os
import sqlite3
import stat
import threading
import time

from filelock import Timeout
import pytest

from eal.store import RunStore, _store_initialisation_lock


def _start_store(path, barrier, results):
    try:
        barrier.wait(timeout=10)
        store = RunStore(path)
        results.put(("ok", store._binding_key.hex()))
    except Exception as error:
        results.put(("error", repr(error)))


def _backfill_store(path, indexed, contender_entered, results, *, slow):
    try:
        if slow:
            index_observation = RunStore._index_observation

            def delayed_index(connection, record_id, payload):
                index_observation(connection, record_id, payload)
                if record_id == "first":
                    indexed.set()
                    if not contender_entered.wait(timeout=10):
                        raise RuntimeError("Contender did not start")
                    time.sleep(0.15)

            RunStore._index_observation = staticmethod(delayed_index)
        else:
            if not indexed.wait(timeout=10):
                raise RuntimeError("Backfill did not start")
            contender_entered.set()
        RunStore(path)
        results.put(("ok", None))
    except Exception as error:
        results.put(("error", repr(error)))


def _join(processes, results):
    try:
        values = [results.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
            assert process.exitcode == 0
        assert all(status == "ok" for status, _ in values), values
        return values
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()
        results.join_thread()


def _legacy_store(path):
    payloads = {
        "first": {"status": "ok", "evidence_id": "evidence", "environment": "site",
                  "request_digest": "request", "tool_binding_digest": "binding"},
        "second": {"status": "ok", "evidence_id": "evidence", "environment": "site",
                   "request_digest": "request", "tool_binding_digest": "binding"},
        "failed": {"status": "error"},
        "incomplete": {"status": "ok", "evidence_id": "evidence"},
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE records "
            "(id TEXT PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        connection.executemany("INSERT INTO records VALUES (?, 'observation', 'now', ?)",
                               [(record_id, json.dumps(payload)) for record_id, payload in payloads.items()])
    path.chmod(0o600)


def test_simultaneous_threads_establish_one_private_store(tmp_path):
    path = tmp_path / "runs.sqlite3"
    barrier = threading.Barrier(8)

    def start_store(_):
        barrier.wait(timeout=10)
        return RunStore(path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        stores = list(executor.map(start_store, range(8)))
    assert len({store._binding_key for store in stores}) == 1
    assert all(store.list() == [] for store in stores)
    with stores[0]._connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connection.execute("SELECT * FROM store_metadata").fetchall() == [
            ("observation-index-version", "1")
        ]


def test_simultaneous_processes_establish_one_private_store(tmp_path):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(4)
    results = context.Queue()
    processes = [context.Process(target=_start_store, args=(tmp_path / "runs.sqlite3", barrier, results))
                 for _ in range(4)]
    for process in processes:
        process.start()
    values = _join(processes, results)
    assert len({key for _, key in values}) == 1
    assert RunStore(tmp_path / "runs.sqlite3").list() == []


def test_concurrent_existing_store_backfill_is_completed_once(tmp_path):
    path = tmp_path / "runs.sqlite3"
    _legacy_store(path)
    context = multiprocessing.get_context("spawn")
    indexed = context.Event()
    contender_entered = context.Event()
    results = context.Queue()
    processes = [context.Process(target=_backfill_store,
                                 args=(path, indexed, contender_entered, results), kwargs={"slow": slow})
                 for slow in (True, False)]
    for process in processes:
        process.start()
    _join(processes, results)
    store = RunStore(path)
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM records").fetchone() == (4,)
        assert connection.execute("SELECT record_id FROM observation_index ORDER BY sequence").fetchall() == [
            ("first",), ("second",)
        ]
        assert connection.execute("SELECT * FROM store_metadata").fetchall() == [
            ("observation-index-version", "1")
        ]
    assert len(store.find_observations(evidence_id="evidence", environment="site",
                                     request_digest="request", tool_binding_digest="binding")) == 2


def test_initialisation_lock_is_private_and_retains_its_inode(tmp_path):
    path = tmp_path / "runs.sqlite3"
    RunStore(path)
    lock = path.with_name(path.name + ".initialisation.lock")
    before = lock.lstat()
    assert stat.S_ISREG(before.st_mode)
    assert stat.S_IMODE(before.st_mode) == 0o600
    if os.name == "posix":
        assert before.st_uid == os.getuid()
    RunStore(path)
    assert (lock.lstat().st_dev, lock.lstat().st_ino) == (before.st_dev, before.st_ino)


@pytest.mark.parametrize("kind", ["public", "directory", "symlink"])
def test_unsafe_initialisation_lock_is_refused_before_storage_creation(tmp_path, kind):
    path = tmp_path / "runs.sqlite3"
    lock = path.with_name(path.name + ".initialisation.lock")
    if kind == "public":
        lock.write_text("unchanged")
        lock.chmod(0o644)
    elif kind == "directory":
        lock.mkdir()
    else:
        target = tmp_path / "target"
        target.write_text("unchanged")
        target.chmod(0o600)
        lock.symlink_to(target)
    with pytest.raises((PermissionError, OSError)):
        RunStore(path)
    assert not path.exists()
    assert not path.with_name(path.name + ".binding-key").exists()
    if kind != "directory":
        assert lock.read_text() == "unchanged"


def test_initialisation_wait_has_a_bounded_timeout(tmp_path):
    path = tmp_path / "runs.sqlite3"
    held = threading.Event()
    release = threading.Event()

    def hold_lock():
        with _store_initialisation_lock(path):
            held.set()
            assert release.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        holder = executor.submit(hold_lock)
        assert held.wait(timeout=5)
        started = time.monotonic()
        try:
            with pytest.raises(Timeout):
                with _store_initialisation_lock(path, timeout=0.05):
                    pytest.fail("A contender acquired the held initialisation lock")
            assert time.monotonic() - started < 1
        finally:
            release.set()
        holder.result(timeout=5)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory permissions")
def test_shared_writeable_store_directory_is_refused_before_lock_creation(tmp_path):
    directory = tmp_path / "shared"
    directory.mkdir()
    directory.chmod(0o777)
    with pytest.raises(PermissionError, match="not writable by others"):
        RunStore(directory / "runs.sqlite3")
    assert list(directory.iterdir()) == []


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Requires FIFO creation")
def test_fifo_lock_is_refused_before_opening(tmp_path):
    path = tmp_path / "runs.sqlite3"
    lock = path.with_name(path.name + ".initialisation.lock")
    os.mkfifo(lock, 0o600)
    with pytest.raises(PermissionError, match="private regular"):
        RunStore(path)
    assert not path.exists()


def test_unsupported_index_version_rolls_back_and_closes(tmp_path, monkeypatch):
    path = tmp_path / "runs.sqlite3"
    store = RunStore(path)
    store.put("test", {"retained": True}, record_id="existing")
    with store._connect() as connection:
        connection.execute("UPDATE store_metadata SET value = 'corrupt' WHERE key = 'observation-index-version'")
        connection.execute("DROP INDEX records_kind")
    connections = []
    connect = sqlite3.connect

    def track_connection(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track_connection)
    with pytest.raises(ValueError, match="Unsupported observation index version"):
        RunStore(path)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
    with connect(path) as connection:
        assert connection.execute("SELECT value FROM store_metadata").fetchall() == [("corrupt",)]
        assert connection.execute("SELECT payload FROM records WHERE id = 'existing'").fetchone() == (
            '{"retained": true}',
        )
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'records_kind'").fetchall() == []
    with _store_initialisation_lock(path, timeout=0.05):
        pass
