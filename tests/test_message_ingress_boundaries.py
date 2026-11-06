"""验证平台接入、历史往返及旧快照读取的真实数据链路。"""

import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.services.analysis_serializer import AnalysisResultSerializer
from src.application.services.message_processing_service import MessageProcessingService
from src.domain.services.message_cleaner_service import MessageCleanerService
from src.domain.services.statistics_service import StatisticsService
from src.domain.value_objects.unified_message import MessageContentType
from src.infrastructure.analysis.utils.analysis_messages import (
    extract_analysis_messages,
)
from src.infrastructure.analysis.utils.token_usage import parse_token_usage
from src.infrastructure.persistence.unified_message_codec import (
    restore_unified_messages,
)
from src.infrastructure.platform.adapters.discord_adapter import DiscordAdapter
from src.infrastructure.platform.adapters.onebot.message_converter import (
    OneBotMessageConverter,
)
from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.platform.adapters.satori_adapter import SatoriAdapter
from src.infrastructure.platform.adapters.telegram_message_converter import (
    TelegramMessageConverter,
)
from src.infrastructure.visualization.activity_charts import ActivityVisualizer
from test_message_processing_service import (
    FakeOfficialEvent,
    FakeGroupRegistry,
    RecordingHistoryManager,
)


@pytest.mark.parametrize("platform", ["telegram", "satori", "qq_official"])
def test_event_history_and_prompt_preserve_mention_and_reply(platform):
    event = FakeOfficialEvent(
        text="明天一起去", platform_name=platform, at_target="target-openid"
    )
    event.message_obj.message.insert(
        0, SimpleNamespace(type="Reply", id="original-message")
    )
    history = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history), FakeGroupRegistry()
    )
    assert asyncio.run(service.process_message(event))
    stored = json.loads(json.dumps(history.calls[0]["content"]))
    record = SimpleNamespace(
        id=1,
        content=stored,
        sender_id="sender-openid",
        sender_name="成员",
        created_at=datetime.now(timezone.utc),
    )
    if platform == "telegram":
        message = TelegramMessageConverter.to_unified_message(record, "group")
    else:
        adapter_type = SatoriAdapter if platform == "satori" else QQOfficialAdapter
        adapter = adapter_type(
            SimpleNamespace(platform=None), {"platform_id": "bot-main"}
        )
        message = adapter._convert_history_record(record, "group")
    assert message is not None
    assert message.message_id == "OFFICIAL-MSG-1"
    assert message.reply_to_id == "original-message"
    assert message.sender_id == "sender-openid"
    clean = MessageCleanerService().clean_messages([message])
    prompt_messages = extract_analysis_messages(clean, use_card=False, bot_self_ids=[])
    assert "[回复:original-message]" in prompt_messages[0]["content"]
    assert "@[target-openid]" in prompt_messages[0]["content"]
    assert "明天一起去" in prompt_messages[0]["content"]
    assert all("raw_data" not in asdict(part) for part in message.contents)


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"subType": 1}, 1),
        ({"sub_type": "1"}, 1),
        ({"summary": "动画表情"}, 1),
        ({"sub_type": 0, "summary": "动画表情"}, 0),
        ({"url": "https://example.test/表情.gif"}, 0),
    ],
)
def test_onebot_normalizes_emoji_before_domain_and_checkpoint(data, expected):
    original = {
        "message_id": "m",
        "time": 123,
        "sender": {"user_id": "0012"},
        "message": [
            {"type": "image", "data": data.copy()},
            {"type": "at", "data": {"qq": "target"}},
            {"type": "reply", "data": {"id": "parent"}},
        ],
    }
    message = OneBotMessageConverter.to_unified_message(original, "group")
    assert message is not None
    original["message"][0]["data"].clear()
    assert message.get_emoji_count() == expected
    assert message.reply_to_id == "parent"
    snapshot = json.loads(
        json.dumps(AnalysisResultSerializer.to_json_friendly([message]))
    )
    assert all("raw_data" not in item for item in snapshot[0]["contents"])
    restored = restore_unified_messages(snapshot, "group")
    assert restored == [message]
    assert (
        StatisticsService(ActivityVisualizer())
        .calculate_group_statistics(restored)
        .emoji_count
        == expected
    )


@pytest.mark.parametrize("reply_key", ["reply_id", "reply_message_id"])
def test_old_snapshot_normalization_does_not_retain_mutable_protocol_data(reply_key):
    raw = [
        {
            "message_id": "m",
            "sender_id": "openid",
            "text_content": "你好",
            "contents": [
                {"type": "image", "raw_data": {"summary": "动画表情"}},
                {"type": "reply", "raw_data": {reply_key: "old-parent"}},
            ],
        }
    ]
    messages = restore_unified_messages(raw, "g")
    raw[0]["contents"][0]["raw_data"].clear()
    assert messages[0].get_emoji_count() == 1
    assert messages[0].reply_to_id == "old-parent"
    assert "raw_data" not in json.dumps(
        AnalysisResultSerializer.to_json_friendly(messages)
    )


def test_current_snapshot_boolean_overrides_old_sticker_hint():
    messages = restore_unified_messages(
        [
            {
                "contents": [
                    {
                        "type": "image",
                        "is_sticker": False,
                        "raw_data": {"summary": "动画表情"},
                    }
                ]
            }
        ],
        "g",
    )
    assert messages[0].get_emoji_count() == 0


def test_discord_mentions_custom_emoji_and_stickers_survive_cleaning():
    source = SimpleNamespace(
        id="discord-m",
        author=SimpleNamespace(id="0012", name="成员", nick=None, global_name=None),
        content="<@123> 明天见 <a:smile:456>",
        attachments=[],
        embeds=[],
        stickers=[
            SimpleNamespace(id=789, name="贴纸", url="https://example.test/sticker")
        ],
        reference=SimpleNamespace(message_id="parent"),
        created_at=datetime.now(timezone.utc),
    )
    adapter = DiscordAdapter(SimpleNamespace(user=SimpleNamespace(id="bot")))
    message = adapter._convert_message(source, "group")
    assert message is not None
    cleaned = MessageCleanerService().clean_messages([message])
    assert cleaned[0].get_emoji_count() == 2
    assert cleaned[0].reply_to_id == "parent"
    prompt = extract_analysis_messages(cleaned, use_card=False, bot_self_ids=[])[0][
        "content"
    ]
    assert "@[123]" in prompt
    assert "[回复:parent]" in prompt
    assert "<a:smile:" not in prompt


@pytest.mark.parametrize(
    "response,expected",
    [
        (SimpleNamespace(usage=SimpleNamespace(input=2, output=3, total=0)), (2, 3, 5)),
        (
            {"usage": {"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6}},
            (2, 4, 6),
        ),
        (
            SimpleNamespace(raw_completion={"usage": {"input": "2", "output": "4"}}),
            (2, 4, 6),
        ),
        ({"usage": {"input": "bad", "output": None}}, (0, 0, 0)),
        (None, (0, 0, 0)),
    ],
)
def test_token_usage_boundary_keeps_host_and_provider_fallbacks(response, expected):
    usage = parse_token_usage(response)
    assert (
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.total_tokens,
    ) == expected


@pytest.mark.parametrize("platform", ["telegram", "satori"])
def test_explicit_face_and_all_mention_survive_event_history(platform):
    event = FakeOfficialEvent(text="集合", platform_name=platform)
    event.message_obj.message.extend(
        [
            SimpleNamespace(type="AtAll"),
            SimpleNamespace(type="Face", id="face-1", name="笑"),
        ]
    )
    history = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history), FakeGroupRegistry()
    )
    assert asyncio.run(service.process_message(event))
    record = SimpleNamespace(
        id=1,
        content=json.loads(json.dumps(history.calls[0]["content"])),
        sender_id="sender",
        sender_name="成员",
        created_at=datetime.now(timezone.utc),
    )
    if platform == "telegram":
        message = TelegramMessageConverter.to_unified_message(record, "group")
    else:
        message = SatoriAdapter(
            SimpleNamespace(platform=None), {"platform_id": "main"}
        )._convert_history_record(record, "group")
    assert message is not None
    assert message.get_emoji_count() == 1
    assert any(part.at_user_id == "all" for part in message.contents)
