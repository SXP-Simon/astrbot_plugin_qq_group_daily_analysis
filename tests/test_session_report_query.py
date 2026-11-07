"""报告热快照及冷存档在同号群之间保持会话隔离。"""

from unittest.mock import Mock

import pytest

from src.application.services.report_query_service import ReportQueryService
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.asyncio
@pytest.mark.parametrize("date_range", [("", ""), ("2026-11-07", "2026-11-07")])
async def test_report_query_filters_platform_before_choosing_latest(tmp_path, date_range):
    path = tmp_path / "traces.db"
    traces = TraceSQLiteStore(path)
    checkpoints = CheckpointStore(path)
    for platform in ("first", "second"):
        traces.save_trace({"trace_id": platform, "group_id": "123", "group_name": platform, "platform": platform, "status": "running"})
        checkpoints.save_checkpoint("123", "2026-11-07", "LLM_ANALYSIS", {
            "statistics": {"message_count": 1}, "topics": [{"topic": platform, "detail": platform}],
        }, trace_id=platform)
    service = ReportQueryService(Mock(), checkpoints, None, traces)
    text = await service.query_reports("123", *date_range, platform_id="first")
    assert "first" in text
    assert "second" not in text
