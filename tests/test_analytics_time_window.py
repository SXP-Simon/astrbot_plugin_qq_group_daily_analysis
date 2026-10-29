"""统计趋势的分摊、时间边界和旧数据容错测试。"""

import time
from datetime import datetime

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("granularity", ["day", "hour"])
def test_analytics_excludes_future_traces(tmp_path, granularity, monkeypatch):
    now = (
        datetime.now().replace(hour=12, minute=30, second=0, microsecond=0).timestamp()
    )
    monkeypatch.setattr(time, "time", lambda: now)
    store = TraceSQLiteStore(tmp_path / "future.db")
    store.save_trace(
        {
            "trace_id": "current",
            "group_id": "123",
            "started_at": time.time() - 10,
            "token_usage": {"total_tokens": 3},
        }
    )
    store.save_trace(
        {
            "trace_id": "future",
            "group_id": "123",
            "started_at": time.time() + 30,
            "token_usage": {"total_tokens": 99},
        }
    )
    result = store.get_analytics_trends(granularity=granularity, range_count=1)
    assert sum(point["request_count"] for point in result["points"]) == 1
    assert sum(item["total_tokens"] for item in result["provider_breakdown"]) == 3
