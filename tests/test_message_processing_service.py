import asyncio
from types import SimpleNamespace

import pytest

from src.application.services.message_processing_service import (
    MessageProcessingService,
)


class FakeHistoryManager:
    def __init__(self):
        self.insert_calls = 0

    async def insert(self, **kwargs):
        self.insert_calls += 1
        if self.insert_calls == 1:
            raise RuntimeError("temporary database failure")


class RecordingHistoryManager:
    def __init__(self):
        self.calls = []

    async def insert(self, **kwargs):
        self.calls.append(kwargs)


class FakeGroupRegistry:
    def __init__(self):
        self.upsert_calls = 0

    async def upsert(self, **kwargs):
        self.upsert_calls += 1


class FakeOfficialEvent:
    def __init__(self, text="hello", mentions=None, platform_name="qq_official"):
        self.platform_name = platform_name
        self.message_obj = SimpleNamespace(
            message_id="OFFICIAL-MSG-1",
            raw_message=SimpleNamespace(
                timestamp=1710000000,
                mentions=list(mentions or []),
            ),
            sender=SimpleNamespace(nickname=""),
            message=[SimpleNamespace(type="Plain", text=text)],
        )
        self.message_str = text

    def get_group_id(self):
        return "GROUP_OPENID"

    def get_sender_id(self):
        return "MEMBER_OPENID"

    def get_sender_name(self):
        return ""

    def get_platform_id(self):
        return "official-main"

    def get_platform_name(self):
        return self.platform_name


def test_failed_history_insert_releases_official_message_id():
    history_manager = FakeHistoryManager()
    registry = FakeGroupRegistry()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), registry
    )
    event = FakeOfficialEvent()

    with pytest.raises(RuntimeError, match="temporary database failure"):
        asyncio.run(service.process_message(event))

    asyncio.run(service.process_message(event))
    asyncio.run(service.process_message(event))

    assert history_manager.insert_calls == 2
    assert registry.upsert_calls == 1


def test_new_qq_official_message_replaces_mentions_before_storage():
    history_manager = RecordingHistoryManager()
    registry = FakeGroupRegistry()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), registry
    )
    event = FakeOfficialEvent(
        text="请问 <@KNOWN_OPENID> 和 <@!UNKNOWN_OPENID> 怎么看",
        mentions=[
            SimpleNamespace(
                id="KNOWN_OPENID",
                username="随风潜入夜",
                is_you=False,
            )
        ],
    )

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [
        {"type": "plain", "text": "请问 @随风潜入夜 和 @群友 怎么看"}
    ]
    assert "KNOWN_OPENID" not in stored_parts[0]["text"]
    assert "UNKNOWN_OPENID" not in stored_parts[0]["text"]


def test_qq_official_bot_mention_is_removed_before_storage():
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )
    event = FakeOfficialEvent(
        text="<@BOT_OPENID> 帮我问问 <@MEMBER_OPENID>",
        mentions=[
            SimpleNamespace(id="BOT_OPENID", username="机器人", is_you=True),
            SimpleNamespace(
                id="MEMBER_OPENID",
                username="群友甲",
                is_you=False,
            ),
        ],
    )

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [{"type": "plain", "text": "帮我问问 @群友甲"}]


def test_non_qq_message_keeps_platform_mention_syntax_unchanged():
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )
    event = FakeOfficialEvent(
        text="请问 <@DISCORD_USER_ID> 怎么看",
        mentions=[
            SimpleNamespace(
                id="DISCORD_USER_ID",
                username="Discord 用户",
                is_you=False,
            )
        ],
        platform_name="discord",
    )

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [
        {"type": "plain", "text": "请问 <@DISCORD_USER_ID> 怎么看"}
    ]
