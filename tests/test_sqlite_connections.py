"""SQLite 事务连接释放与回滚测试。"""

import sqlite3

import pytest

from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("store_type", [TraceSQLiteStore, CheckpointStore])
def test_connection_is_closed_after_transaction(tmp_path, store_type):
    store = store_type(tmp_path / "store.db")
    with store._get_connection() as conn:
        conn.execute("CREATE TABLE test_values (value INTEGER)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with pytest.raises(ValueError), store._get_connection() as conn:
        conn.execute("INSERT INTO test_values VALUES (1)")
        raise ValueError("rollback")
    with store._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM test_values").fetchone()[0] == 0


