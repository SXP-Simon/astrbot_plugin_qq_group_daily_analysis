"""统计趋势的分摊、时间边界和旧数据容错测试。"""

import time

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("metadata", ["[]", "null", "7", '"legacy"', "broken-json"])
def test_analytics_tolerates_non_object_legacy_metadata(tmp_path, metadata):
    store = TraceSQLiteStore(tmp_path / "legacy.db")
    store.save_trace(
        {
            "trace_id": "legacy",
            "group_id": "123",
            "started_at": time.time(),
            "token_usage": {"total_tokens": 7},
        }
    )
    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET extra_json = ? WHERE trace_id = ?",
            (metadata, "legacy"),
        )
    result = store.get_analytics_trends(range_count=1)
    assert result["provider_breakdown"][0]["total_tokens"] == 7
    assert result["model_breakdown"][0]["total_tokens"] == 7
