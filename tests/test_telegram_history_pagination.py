import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from src.infrastructure.platform.adapters.telegram_adapter import TelegramAdapter


class OffsetHistoryManager:
    def __init__(self, pages):
        self.pages = pages
        self.pages_requested = []

    async def get(self, platform_id, user_id, page, page_size):
        assert platform_id == "telegram-main"
        assert user_id == "-10001"
        assert page_size == 2
        self.pages_requested.append(page)
        return self.pages.get(page, [])


def make_record(record_id, sender_id, timestamp, text):
    return SimpleNamespace(
        id=record_id,
        sender_id=sender_id,
        sender_name="Alice",
        created_at=datetime.fromtimestamp(timestamp, timezone.utc),
        content={"message": [{"type": "plain", "text": text}]},
    )


def test_telegram_history_offset_pagination_deduplicates_repeated_rows():
    repeated = make_record(4, "USER-1", 400, "fourth")
    history_manager = OffsetHistoryManager(
        {
            1: [
                repeated,
                make_record(5, "BOT", 500, "bot message"),
            ],
            2: [
                repeated,
                make_record(2, "USER-2", 200, "second"),
            ],
        }
    )
    adapter = TelegramAdapter(
        SimpleNamespace(),
        {"platform_id": "telegram-main", "bot_self_ids": ["BOT"]},
    )
    adapter.set_context(SimpleNamespace(message_history_manager=history_manager))

    messages = asyncio.run(adapter.fetch_messages("-10001", days=36500, max_count=2))

    assert [message.message_id for message in messages] == ["2", "4"]
    assert history_manager.pages_requested == [1, 2]
