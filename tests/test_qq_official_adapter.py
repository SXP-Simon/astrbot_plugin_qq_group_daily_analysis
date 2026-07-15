import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.platform.factory import PlatformAdapterFactory


class FakeHistoryManager:
    def __init__(self, pages):
        self.pages = pages

    async def get(self, platform_id, user_id, page, page_size):
        assert platform_id == "official-main"
        assert user_id == "GROUP_OPENID"
        assert page_size == 500
        return self.pages.get(page, [])


def make_record(record_id, message_id, sender_id, timestamp, text):
    return SimpleNamespace(
        id=record_id,
        sender_id=sender_id,
        sender_name=sender_id,
        created_at=datetime.fromtimestamp(timestamp, timezone.utc),
        content={
            "type": "user",
            "message": [{"type": "plain", "text": text}],
            "_qq_official": {
                "message_id": message_id,
                "timestamp": timestamp,
            },
        },
    )


def make_adapter():
    platform = SimpleNamespace(config={"appid": "1029384756"})
    bot = SimpleNamespace(platform=platform)
    return QQOfficialAdapter(
        bot,
        {
            "platform_id": "official-main",
            "bot_self_ids": ["BOT_OPENID"],
        },
    )


def test_avatar_url_uses_appid_and_member_openid():
    adapter = make_adapter()
    assert asyncio.run(adapter.get_user_avatar_url("A1B2C3_OPENID")) == (
        "https://thirdqq.qlogo.cn/qqapp/1029384756/A1B2C3_OPENID/640"
    )


def test_local_history_is_deduplicated_filtered_and_sorted():
    adapter = make_adapter()
    adapter.set_context(
        SimpleNamespace(
            message_history_manager=FakeHistoryManager(
                {
                    1: [
                        make_record(1, "MSG-2", "B_OPENID", 200, "second"),
                        make_record(2, "MSG-1", "A_OPENID", 100, "first"),
                        make_record(3, "MSG-2", "B_OPENID", 200, "duplicate"),
                        make_record(4, "MSG-BOT", "BOT_OPENID", 300, "bot"),
                    ]
                }
            )
        )
    )

    messages = asyncio.run(
        adapter.fetch_messages("GROUP_OPENID", days=36500, max_count=20)
    )

    assert [message.message_id for message in messages] == ["MSG-1", "MSG-2"]
    assert [message.sender_id for message in messages] == ["A_OPENID", "B_OPENID"]
    assert [message.text_content for message in messages] == ["first", "second"]


def test_factory_registers_both_official_platform_types():
    assert PlatformAdapterFactory.is_supported("qq_official")
    assert PlatformAdapterFactory.is_supported("qq_official_webhook")
