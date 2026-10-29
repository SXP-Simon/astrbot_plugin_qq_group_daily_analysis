"""统计趋势的分摊、时间边界和旧数据容错测试。"""

import time

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("total", [1, 5, 17])
def test_analytics_breakdowns_preserve_all_tokens(tmp_path, total):
    store = TraceSQLiteStore(tmp_path / "analytics.db")
    store.save_trace(
        {
            "trace_id": "multi-provider",
            "group_id": "123",
            "started_at": time.time(),
            "extra": {
                "llm_prompts": {
                    "topics": {"provider_id": "p-b", "model": "m-b"},
                    "quotes": {"provider_id": "p-a", "model": "m-a"},
                }
            },
            "token_usage": {"total_tokens": total},
        }
    )
    result = store.get_analytics_trends(range_count=1)
    for key in ("provider_breakdown", "model_breakdown"):
        assert sum(item["total_tokens"] for item in result[key]) == total
        assert [item["name"] for item in result[key]] == sorted(
            item["name"] for item in result[key]
        )
