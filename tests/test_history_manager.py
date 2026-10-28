"""历史存取与重绘产物契约回归测试。"""

import json
from unittest.mock import MagicMock

import pytest

from src.application.services.analysis_serializer import AnalysisResultSerializer
from src.domain.value_objects import GroupStatistics, SummaryTopic
from src.infrastructure.persistence.history_manager import HistoryManager


@pytest.fixture
def analysis():
    return {
        "statistics": GroupStatistics(10, 40, 2, "12:00", [], 0),
        "topics": [SummaryTopic("话题", ["成员"], "详情", ["123"])],
        "user_titles": [],
        "user_analysis": {"123": {"message_count": 10}},
        "chat_quality_review": None,
    }


@pytest.fixture
def history():
    records = {}

    async def put(key, value):
        records[key] = json.loads(json.dumps(value))

    async def get(key, default=None):
        return records.get(key, default)

    return HistoryManager(MagicMock(put_kv_data=put, get_kv_data=get)), records


@pytest.mark.asyncio
async def test_history_round_trip_and_latest(history, analysis):
    manager, _ = history
    assert await manager.save_analysis("123", analysis, "2026-10-29", "12:00")
    restored = AnalysisResultSerializer.deserialize(
        await manager.get_analysis("123", "2026-10-29")
    )
    assert restored == analysis
    assert (await manager.get_history("123", "2026-10-29", "12:00"))[
        "message_count"
    ] == 10
    analysis["statistics"].message_count = 20
    assert await manager.save_analysis("123", analysis, "2026-10-29", "13:00")
    assert (await manager.get_analysis("123", "2026-10-29"))["statistics"][
        "message_count"
    ] == 20
    assert (await manager.get_analysis("123", "2026-10-29", "12:00"))["statistics"][
        "message_count"
    ] == 10
    assert await manager.get_analysis("other", "2026-10-29") is None


@pytest.mark.asyncio
async def test_legacy_history_summary_is_preserved(history):
    manager, records = history
    summary = {"message_count": 7, "topics": []}
    records["analysis_123_2026-10-29"] = summary
    records["analysis_123_2026-10-29_12-00"] = summary
    assert await manager.get_analysis("123", "2026-10-29") == summary
    assert await manager.get_history("123", "2026-10-29", "12:00") == summary
