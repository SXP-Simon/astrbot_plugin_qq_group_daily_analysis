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
        assert page_size > 0
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


def test_telegram_fetch_messages_clamps_stale_since_ts_to_days():
    """验证 Telegram 适配器在 since_ts 滞后数天时，将时间窗口截断至配置的 days 内，不拉取超期消息。"""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    stale_since_ts = now_ts - 5 * 86400  # 5 天前游标
    msg_within = now_ts - 1800  # 30 分钟前 (在 days=1 内)
    msg_out_of_window = now_ts - 2 * 86400  # 2 天前 (超出 days=1)

    history_manager = OffsetHistoryManager(
        {
            1: [
                make_record(101, "USER-1", msg_within, "窗口内消息"),
                make_record(102, "USER-2", msg_out_of_window, "窗口外消息 (2天前)"),
            ]
        }
    )
    adapter = TelegramAdapter(
        SimpleNamespace(),
        {"platform_id": "telegram-main", "bot_self_ids": []},
    )
    adapter.set_context(SimpleNamespace(message_history_manager=history_manager))

    messages = asyncio.run(
        adapter.fetch_messages("-10001", days=1, max_count=10, since_ts=stale_since_ts)
    )

    assert len(messages) == 1
    assert messages[0].message_id == "101"
    assert messages[0].text_content == "窗口内消息"

