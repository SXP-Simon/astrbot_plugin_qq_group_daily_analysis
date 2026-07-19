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


class FakeGroupRegistry:
    def __init__(self):
        self.upsert_calls = 0

    async def upsert(self, **kwargs):
        self.upsert_calls += 1


class FakeOfficialEvent:
    def __init__(self):
        self.message_obj = SimpleNamespace(
            message_id="OFFICIAL-MSG-1",
            raw_message=SimpleNamespace(timestamp=1710000000),
            sender=SimpleNamespace(nickname=""),
            message=[SimpleNamespace(type="Plain", text="hello")],
        )
        self.message_str = "hello"

    def get_group_id(self):
        return "GROUP_OPENID"

    def get_sender_id(self):
        return "MEMBER_OPENID"

    def get_sender_name(self):
        return ""

    def get_platform_id(self):
        return "official-main"

    def get_platform_name(self):
        return "qq_official"


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
