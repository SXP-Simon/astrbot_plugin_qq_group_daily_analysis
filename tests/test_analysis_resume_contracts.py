"""恢复真实 JSON 检查点及旧摘要的回归测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.application.services.task_guard import TaskGuard
from src.domain.value_objects import SummaryTopic, TokenUsage
from src.domain.value_objects.unified_message import UnifiedMessage
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_repeated_resume_owns_reused_llm_checkpoint(tmp_path):
    store = CheckpointStore(tmp_path / "repeated-resume.db")
    store.save_checkpoint("g1", "2026-10-01", "LLM_ANALYSIS", {
        "statistics": {"message_count": 3, "token_usage": {"total_tokens": 99}},
        "topics": [{"topic": "已分析话题", "contributors": [], "detail": "复用内容"}],
    }, trace_id="original")
    config = MagicMock()
    config.get_topic_analysis_enabled.return_value = True
    config.get_user_title_analysis_enabled.return_value = False
    config.get_golden_quote_analysis_enabled.return_value = False
    config.get_chat_quality_analysis_enabled.return_value = False
    llm = MagicMock(analyze_all_concurrent=AsyncMock())
    fallback = AsyncMock()
    service = AnalysisRecoveryService(config, MagicMock(), MagicMock(), MagicMock(), llm, TaskGuard(), store)
    source = "original"
    for new_id in ("resumed-once", "resumed-twice", "resumed-three-times"):
        async with TraceContext(trace_id=new_id) as trace:
            result = await service.resume_analysis(new_id, "g1", date_str="2026-10-01", checkpoint_trace_id=source, fallback_daily_func=fallback)
            assert trace.metadata["checkpoint_trace_id"] == source
        assert result["success"] is True
        assert result["resumed_from"] == "LLM_ANALYSIS"
        assert result["analysis_result"]["topics"][0].topic == "已分析话题"
        assert result["analysis_result"]["statistics"].token_usage.total_tokens == 99
        assert store.get_checkpoint("g1", "2026-10-01", "LLM_ANALYSIS", trace_id=new_id)
        source = new_id
    llm.analyze_all_concurrent.assert_not_called()
    fallback.assert_not_called()


@pytest.mark.asyncio
async def test_cancelled_partial_resume_keeps_source_checkpoints(tmp_path):
    import asyncio

    store = CheckpointStore(tmp_path / "partial-resume.db")
    store.save_checkpoint("g1", "2026-10-01", "LLM_ANALYSIS", {
        "statistics": {"message_count": 3},
        "topics": [{"topic": "已完成话题", "contributors": [], "detail": "保留"}],
    }, trace_id="original")
    store.save_checkpoint("g1", "2026-10-01", "CLEAN_MESSAGES", {
        "statistics": {"message_count": 3}, "unified_messages": [], "user_activity": {}, "top_users": [],
    }, trace_id="original")
    config = MagicMock()
    config.get_topic_analysis_enabled.return_value = True
    config.get_user_title_analysis_enabled.return_value = True
    config.get_golden_quote_analysis_enabled.return_value = False
    config.get_chat_quality_analysis_enabled.return_value = False
    llm = MagicMock(analyze_all_concurrent=AsyncMock(side_effect=asyncio.CancelledError))
    service = AnalysisRecoveryService(config, MagicMock(), MagicMock(), MagicMock(), llm, TaskGuard(), store)
    async with TraceContext(trace_id="interrupted-resume"):
        with pytest.raises(asyncio.CancelledError):
            await service.resume_analysis("interrupted-resume", "g1", date_str="2026-10-01", checkpoint_trace_id="original")
    assert store.get_checkpoint("g1", "2026-10-01", "LLM_ANALYSIS", trace_id="interrupted-resume")
    assert store.get_checkpoint("g1", "2026-10-01", "CLEAN_MESSAGES", trace_id="interrupted-resume")
    assert llm.analyze_all_concurrent.call_args.kwargs["topic_enabled"] is False


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
        TaskGuard(),
        checkpoints,
    )
    async with TraceContext(trace_id="resume-json"):
        result = await service.resume_analysis(
            "resume-json", "123", date_str="2026-10-01"
        )
    assert result["success"] is True
    messages = llm.analyze_all_concurrent.call_args.args[0]
    assert isinstance(messages[0], UnifiedMessage)
    assert messages[0].text_content == "恢复消息"
    assert messages[0].sender_card == "群名片"
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
        TaskGuard(),
    )
    async with TraceContext(trace_id="legacy-summary"):
        result = await service.resume_analysis("legacy-summary", "123")
    assert result["success"] is False
    assert result["reason"] == "checkpoint_missing"


@pytest.mark.asyncio
async def test_resume_rejects_another_task_daily_history(monkeypatch):
    monkeypatch.setattr("src.shared.trace_context._global_trace_store", None)
    config = MagicMock()
    config.get_topic_analysis_enabled.return_value = False
    config.get_user_title_analysis_enabled.return_value = False
    config.get_golden_quote_analysis_enabled.return_value = False
    config.get_chat_quality_analysis_enabled.return_value = False
    history = MagicMock(
        get_analysis=AsyncMock(
            return_value={
                "trace_id": "another-task",
                "statistics": {"message_count": 99},
            }
        )
    )
    service = AnalysisRecoveryService(
        config, MagicMock(), history, MagicMock(), MagicMock(), TaskGuard()
    )
    async with TraceContext(trace_id="requested-task"):
        result = await service.resume_analysis(
            "requested-task", "123", date_str="2026-10-29"
        )
    assert result["success"] is False
    assert result["reason"] == "checkpoint_missing"
