"""任务提醒知晓标记的持久化与生命周期隔离测试。"""

import sqlite3

import pytest

from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import (
    TraceSQLiteStore,
)
from astrbot_plugin_qq_group_daily_analysis.src.domain.value_objects.task_event import TaskEvent
from astrbot_plugin_qq_group_daily_analysis.src.domain.value_objects.task_status import TaskStatus


def test_acknowledgement_survives_restart_and_snapshot_without_changing_result(tmp_path):
    path = tmp_path / "traces.db"
    store = TraceSQLiteStore(path)
    snapshot = {
        "trace_id": "failed-task",
        "group_id": "group",
        "status": "failed",
        "started_at": 100,
        "error_message": "模型连接失败",
    }
    store.save_trace(snapshot)
    store.transition_trace_status(
        "failed-task", TaskStatus.RUNNING, TaskEvent.FAIL,
        completed_at=101, duration_ms=1000, error_stage="LLM_ANALYSIS",
        error_message="模型连接失败", stack_trace=None,
    )
    stamp = store.set_trace_acknowledgement("failed-task", True)
    assert stamp > 0
    assert store.set_trace_acknowledgement("failed-task", True) == stamp
    store.save_trace(snapshot)
    reopened = TraceSQLiteStore(path)
    trace = reopened.get_trace("failed-task")
    assert trace["acknowledged_at"] == stamp
    assert trace["status"] == "failed"
    assert trace["error_message"] == "模型连接失败"
    assert reopened.list_traces()[0][0]["acknowledged_at"] == stamp
    assert reopened.set_trace_acknowledgement("failed-task", False) is None
    assert reopened.get_trace("failed-task")["acknowledged_at"] is None


def test_running_missing_and_unknown_tasks_are_not_silently_acknowledged(tmp_path):
    store = TraceSQLiteStore(tmp_path / "traces.db")
    with pytest.raises(KeyError):
        store.set_trace_acknowledgement("missing", True)
    store.save_trace({"trace_id": "active", "group_id": "g", "status": "running", "started_at": 1})
    with pytest.raises(ValueError):
        store.set_trace_acknowledgement("active", True)
    with store._get_connection() as conn:
        conn.execute("UPDATE analysis_traces SET status = 'unknown' WHERE trace_id = 'active'")
    with pytest.raises(ValueError):
        store.set_trace_acknowledgement("active", True)


def test_old_schema_is_migrated_without_losing_original_trace(tmp_path):
    path = tmp_path / "old.db"
    store = TraceSQLiteStore(path)
    store.save_trace({"trace_id": "old", "group_id": "g", "status": "warning", "started_at": 1})
    store.transition_trace_status(
        "old", TaskStatus.RUNNING, TaskEvent.WARN,
        completed_at=2, duration_ms=1000, error_stage=None,
        error_message=None, stack_trace=None,
    )
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE analysis_traces DROP COLUMN acknowledged_at")
    migrated = TraceSQLiteStore(path)
    assert migrated.get_trace("old")["status"] == "warning"
    assert migrated.set_trace_acknowledgement("old", True) > 0
