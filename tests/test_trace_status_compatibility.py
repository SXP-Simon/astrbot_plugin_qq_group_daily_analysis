"""历史任务状态在 SQLite、统计和 Dashboard 筛选中的兼容性测试。"""

import time
from pathlib import Path

from src.domain.value_objects.task_status import TaskStatus
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


def test_legacy_statuses_keep_dashboard_filters_and_metrics(tmp_path: Path):
    store = TraceSQLiteStore(tmp_path / "trace_status_compatibility.db")
    store.save_trace(
        {
            "trace_id": "legacy-completed",
            "group_id": "legacy-group",
            "status": "running",
            "started_at": time.time(),
        }
    )
    store.save_trace(
        {
            "trace_id": "legacy-cancelled",
            "group_id": "legacy-group",
            "status": "running",
            "started_at": time.time(),
        }
    )
    store.save_trace(
        {
            "trace_id": "legacy-pending",
            "group_id": "legacy-group",
            "status": TaskStatus.PENDING.value,
            "started_at": time.time(),
        }
    )
    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET status = ?, duration_ms = ? WHERE trace_id = ?",
            (TaskStatus.COMPLETED.value, 1200.0, "legacy-completed"),
        )
        conn.execute(
            "UPDATE analysis_traces SET status = ? WHERE trace_id = ?",
            (TaskStatus.CANCELLED.value, "legacy-cancelled"),
        )

    succeeded, succeeded_total = store.list_traces(status=TaskStatus.SUCCEEDED.value)
    aborted, aborted_total = store.list_traces(status=TaskStatus.ABORTED.value)
    pending, pending_total = store.list_traces(status=TaskStatus.PENDING.value)

    assert succeeded_total == 1
    assert succeeded[0]["status"] == TaskStatus.COMPLETED.value
    assert aborted_total == 1
    assert aborted[0]["status"] == TaskStatus.CANCELLED.value
    assert pending_total == 1
    assert pending[0]["status"] == TaskStatus.PENDING.value

    summary = store.get_metrics_summary()
    assert summary["succeeded_count"] == 1
    assert summary["avg_duration_ms"] == 1200.0
    daily_points = store.get_analytics_trends(granularity="day", range_count=1)[
        "points"
    ]
    hourly_points = store.get_analytics_trends(granularity="hour", range_count=1)[
        "points"
    ]
    assert daily_points[0]["succeeded_count"] == 1
    assert hourly_points[0]["succeeded_count"] == 1
