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


def test_trace_details_share_the_snapshot_transaction(tmp_path):
    store = TraceSQLiteStore(tmp_path / "atomic-snapshot.db")
    original = {
        "trace_id": "atomic",
        "group_id": "123",
        "extra": {"revision": "old"},
        "spans": [
            {
                "span_id": "atomic-stage",
                "stage_name": "LLM_ANALYSIS",
                "status": "running",
                "payload": {"revision": "old"},
            }
        ],
        "token_usage": {"total_tokens": 10},
    }
    store.save_trace(original)
    with pytest.raises(ValueError):
        store.save_trace(
            {
                **original,
                "extra": {"revision": "new"},
                "spans": [
                    {
                        "span_id": "atomic-stage",
                        "stage_name": "LLM_ANALYSIS",
                        "status": "success",
                        "payload": {"revision": "new"},
                    }
                ],
                "token_usage": {"total_tokens": 20},
                "performance_metrics": {"peak_memory_mb": "invalid"},
            }
        )
    restored = store.get_trace("atomic")
    assert restored["extra"]["revision"] == "old"
    assert restored["spans"][0]["payload"]["revision"] == "old"
    assert restored["spans"][0]["status"] == "running"
    assert restored["token_usage"]["total_tokens"] == 10
