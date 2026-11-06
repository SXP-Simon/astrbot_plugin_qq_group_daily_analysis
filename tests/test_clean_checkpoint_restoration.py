"""清洗快照的 JSON 与内存消息还原边界。"""

from copy import deepcopy

import pytest

from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.domain.value_objects import UnifiedMessage


@pytest.mark.parametrize("serialized", [True, False])
def test_clean_checkpoint_restores_domain_data_without_mutating_snapshot(serialized):
    fields = {"message_id": "m", "sender_id": "u", "sender_name": "成员", "text_content": "恢复正文", "timestamp": 123, "sender_card": "名片"}
    message = fields if serialized else UnifiedMessage(group_id="123", **fields)
    checkpoint = {
        "statistics": {"message_count": 1},
        "user_activity": {"u": {"message_count": 1}},
        "top_users": [{"user_id": "u"}],
        "unified_messages": [None, message, 7],
    }
    before = deepcopy(checkpoint)
    result, messages, top_users = AnalysisRecoveryService._restore_clean_checkpoint(checkpoint, "123")
    assert result["statistics"].message_count == 1
    assert result["user_analysis"] == {"u": {"message_count": 1}}
    assert top_users == [{"user_id": "u", "message_count": 0}]
    assert len(messages) == 1
    assert messages[0].text_content == "恢复正文"
    assert messages[0].group_id == "123"
    assert messages[0].sender_card == "名片"
    assert checkpoint == before
    if not serialized:
        assert messages[0] is message


@pytest.mark.parametrize("timestamp,expected", [("", 0), ("not-a-time", 0), (float("nan"), 0), (float("inf"), 0), (None, 0), ("123", 123)])
def test_clean_checkpoint_keeps_text_when_legacy_timestamp_is_invalid(timestamp, expected):
    checkpoint = {"unified_messages": [{"message_id": "m", "text_content": "必须保留的正文", "timestamp": timestamp}]}
    _, messages, _ = AnalysisRecoveryService._restore_clean_checkpoint(checkpoint, "123")
    assert len(messages) == 1
    assert messages[0].text_content == "必须保留的正文"
    assert messages[0].timestamp == expected


@pytest.mark.asyncio
async def test_json_checkpoint_keeps_relations_through_resumed_llm_call():
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from src.application.services.analysis_serializer import AnalysisResultSerializer
    from src.application.services.pipeline_context import PipelineContext
    from src.application.services.task_guard import TaskGuard
    from src.domain.value_objects import SummaryTopic, TokenUsage
    from src.domain.value_objects.unified_message import MessageContent, MessageContentType
    from src.infrastructure.analysis.utils.analysis_messages import extract_analysis_messages

    original = UnifiedMessage(
        message_id="message-abc", sender_id="openid-abc", sender_name="用户甲",
        group_id="channel-abc", platform="discord", timestamp=123,
        text_content="明天见", reply_to_id="reply-abc",
        contents=(
            MessageContent(type=MessageContentType.AT, at_user_id="openid-def"),
            MessageContent(type=MessageContentType.TEXT, text="明天见"),
            MessageContent(type=MessageContentType.EMOJI, emoji_id="smile"),
            MessageContent(type=MessageContentType.IMAGE, url="https://invalid.example/picture", is_sticker=True),
        ),
    )
    checkpoint = json.loads(json.dumps(AnalysisResultSerializer.to_json_friendly({
        "statistics": {"message_count": 1}, "unified_messages": [original],
        "user_activity": {}, "top_users": [],
    })))
    before = deepcopy(checkpoint)
    analysis, restored, top_users = AnalysisRecoveryService._restore_clean_checkpoint(checkpoint, "channel-abc")
    assert restored == [original]
    assert checkpoint == before
    expected = extract_analysis_messages([original], use_card=False, bot_self_ids=[])
    assert extract_analysis_messages(restored, use_card=False, bot_self_ids=[]) == expected

    service = object.__new__(AnalysisRecoveryService)
    service.config_manager = SimpleNamespace(
        get_topic_analysis_enabled=lambda: True,
        get_user_title_analysis_enabled=lambda: False,
        get_golden_quote_analysis_enabled=lambda: False,
        get_chat_quality_analysis_enabled=lambda: False,
    )
    service.task_guard = TaskGuard()
    service.llm_analyzer = SimpleNamespace(analyze_all_concurrent=AsyncMock(return_value=(
        [SummaryTopic(topic="约定", detail="明天见", contributors=[])], [], [], TokenUsage(), None,
    )))
    pipeline = PipelineContext(trace=None, checkpoint_store=None, group_id="channel-abc", date_str="2026-11-06")
    result = await service._complete_missing_sections(pipeline, analysis, restored, top_users, "discord-main")
    assert result["topics"][0].topic == "约定"
    call = service.llm_analyzer.analyze_all_concurrent.call_args
    assert call.args[0] is restored
    assert call.kwargs["umo"] == "discord-main:GroupMessage:channel-abc"
    assert call.kwargs["topic_enabled"] is True
    assert call.kwargs["golden_quote_enabled"] is False


def test_restore_unknown_segments_keeps_text_and_known_mentions():
    from src.infrastructure.analysis.utils.analysis_messages import extract_analysis_messages

    checkpoint = {"unified_messages": [{
        "message_id": "m", "sender_id": "u", "text_content": "旧快照正文",
        "contents": [None, 42, {"type": "future-kind"}, {"type": "at", "at_user_id": "other-id"}],
    }]}
    _, messages, _ = AnalysisRecoveryService._restore_clean_checkpoint(checkpoint, "g")
    extracted = extract_analysis_messages(messages, use_card=False, bot_self_ids=[])
    assert extracted[0]["content"] == "旧快照正文 @[other-id]"
