"""恢复真实 JSON 检查点及旧摘要的回归测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.application.services.task_guard import TaskGuard
from src.domain.services.statistics_service import StatisticsService
from src.domain.value_objects import SummaryTopic, TokenUsage
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_resume_json_messages_and_preserves_archive_date(tmp_path):
    checkpoints = CheckpointStore(tmp_path / "checkpoints.db")
    checkpoints.save_checkpoint(
        "123",
        "2026-10-01",
        "CLEAN_MESSAGES",
        {
            "statistics": {"message_count": 1},
            "user_activity": {},
            "top_users": [],
            "unified_messages": [
                {
                    "message_id": "m1",
                    "sender_id": "u1",
                    "sender_name": "成员",
                    "group_id": "123",
                    "text_content": "恢复消息",
                    "timestamp": 123,
                    "sender_card": "群名片",
                }
            ],
        },
    )
    config = MagicMock()
    config.get_topic_analysis_enabled.return_value = True
    config.get_user_title_analysis_enabled.return_value = False
    config.get_golden_quote_analysis_enabled.return_value = False
    config.get_chat_quality_analysis_enabled.return_value = False
    llm = MagicMock(
        analyze_all_concurrent=AsyncMock(
            return_value=(
                [SummaryTopic("话题", [], "详情")],
                [],
                [],
                TokenUsage(),
                None,
            )
        )
    )
    history = MagicMock(
        get_analysis=AsyncMock(return_value={"message_count": 1}),
        save_analysis=AsyncMock(return_value=True),
    )
    service = AnalysisRecoveryService(
        config,
        MagicMock(),
        history,
        MagicMock(),
        llm,
        StatisticsService(MagicMock()),
        TaskGuard(),
        checkpoints,
    )
    async with TraceContext(trace_id="resume-json"):
        result = await service.resume_analysis(
            "resume-json", "123", date_str="2026-10-01"
        )
    assert result["success"] is True
    messages = llm.analyze_all_concurrent.call_args.args[0]
    assert messages[0]["message"][0]["data"]["text"] == "恢复消息"
    assert messages[0]["sender"]["card"] == "群名片"
    assert history.save_analysis.call_args.kwargs["date_str"] == "2026-10-01"


@pytest.mark.asyncio
async def test_resume_legacy_summary_does_not_fake_complete_analysis():
    config = MagicMock()
    config.get_topic_analysis_enabled.return_value = False
    config.get_user_title_analysis_enabled.return_value = False
    config.get_golden_quote_analysis_enabled.return_value = False
    config.get_chat_quality_analysis_enabled.return_value = False
    service = AnalysisRecoveryService(
        config,
        MagicMock(),
        MagicMock(get_analysis=AsyncMock(return_value={"message_count": 1})),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        TaskGuard(),
    )
    async with TraceContext(trace_id="legacy-summary"):
        result = await service.resume_analysis("legacy-summary", "123")
    assert result["success"] is False
    assert result["reason"] == "checkpoint_missing"
