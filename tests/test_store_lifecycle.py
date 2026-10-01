"""Every SQLite operation closes its connection after committing or rolling back."""

import sqlite3

import pytest

from eal.store import RunStore


def test_connection_closes_after_successful_transaction(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    with store._connect() as connection:
        connection.execute("INSERT INTO records VALUES ('one', 'test', 'now', '{}')")
    assert store.get("one") == {}
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_connection_rolls_back_and_closes_after_failure(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    with pytest.raises(RuntimeError, match="abort"):
        with store._connect() as connection:
            connection.execute("INSERT INTO records VALUES ('one', 'test', 'now', '{}')")
            raise RuntimeError("abort")
    with pytest.raises(KeyError):
        store.get("one")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
