import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from src.domain.value_objects.unified_group import UnifiedMember
from src.domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from src.infrastructure.platform.adapters.telegram_adapter import TelegramAdapter
from src.infrastructure.platform.adapters.telegram_message_converter import (
    TelegramMessageConverter,
)


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


def test_telegram_message_converter_parse_group_id():
    """测试 Telegram 话题群组 ID 分解。"""
    chat_id, thread_id = TelegramMessageConverter.parse_group_id("-100123456#42")
    assert chat_id == "-100123456"
    assert thread_id == "42"

    chat_id_simple, thread_id_simple = TelegramMessageConverter.parse_group_id(
        "-100123456"
    )
    assert chat_id_simple == "-100123456"
    assert thread_id_simple is None


def test_telegram_message_converter_placeholder_detection():
    """测试 Telegram 占位昵称识别规则。"""
    assert TelegramMessageConverter.is_placeholder_sender_name("", "12345") is True
    assert TelegramMessageConverter.is_placeholder_sender_name(None, "12345") is True
    assert (
        TelegramMessageConverter.is_placeholder_sender_name("Unknown", "12345") is True
    )
    assert TelegramMessageConverter.is_placeholder_sender_name("none", "12345") is True
    assert TelegramMessageConverter.is_placeholder_sender_name("12345", "12345") is True
    assert (
        TelegramMessageConverter.is_placeholder_sender_name("Alice", "12345") is False
    )


def test_telegram_message_converter_fix_sender_name():
    """测试通过成员抓取器自动修复占位昵称与多级缓存机制。"""

    async def scenario():
        msg = UnifiedMessage(
            message_id="1",
            sender_id="999",
            sender_name="Unknown",
            sender_card=None,
            group_id="-1001",
            text_content="Hello",
            contents=(MessageContent(type=MessageContentType.TEXT, text="Hello"),),
            timestamp=1700000000,
            platform="telegram",
        )

        async def fetcher(group_id: str, user_id: str):
            return UnifiedMember(
                user_id=user_id,
                nickname="Bob",
                card="bob_tg",
                role="member",
            )

        cache: dict[str, str] = {}
        fixed = await TelegramMessageConverter.fix_sender_name_if_needed(
            "-1001", msg, cache, fetcher
        )
        assert fixed.sender_name == "Bob"
        assert cache["999"] == "Bob"

        # 二次自愈直接使用缓存
        fixed_cached = await TelegramMessageConverter.fix_sender_name_if_needed(
            "-1001", msg, cache, fetcher
        )
        assert fixed_cached.sender_name == "Bob"

    asyncio.run(scenario())


def test_telegram_message_converter_to_unified_message_and_raw():
    """测试历史记录转换为 UnifiedMessage 以及后续转换为 OneBot 原始字典。"""
    record = SimpleNamespace(
        id=88,
        sender_id="1000",
        sender_name="Charlie",
        created_at=datetime.fromtimestamp(1700000000, timezone.utc),
        content={
            "message": [
                {"type": "plain", "text": "Check image "},
                {"type": "image", "url": "https://example.com/img.png"},
                {"type": "at", "target_id": "2000"},
            ]
        },
    )

    unified = TelegramMessageConverter.to_unified_message(record, "-1001")
    assert unified is not None
    assert unified.message_id == "88"
    assert unified.sender_id == "1000"
    assert unified.sender_name == "Charlie"
    assert len(unified.contents) == 3
    assert unified.contents[0].type == MessageContentType.TEXT
    assert unified.contents[1].type == MessageContentType.IMAGE
    assert unified.contents[2].type == MessageContentType.AT
    assert unified.contents[2].at_user_id == "2000"

    raw_list = TelegramMessageConverter.to_raw_format([unified])
    assert len(raw_list) == 1
    raw = raw_list[0]
    assert raw["message_id"] == "88"
    assert raw["sender"]["nickname"] == "Charlie"
    assert len(raw["message"]) == 3
    assert raw["message"][0]["type"] == "text"
    assert raw["message"][1]["type"] == "image"
    assert raw["message"][2]["type"] == "at"


def test_telegram_message_converter_format_forward_nodes():
    """测试将合并转发节点排版为文本。"""
    nodes = [
        {"data": {"name": "Bot1", "content": "第一条信息"}},
        {
            "data": {
                "name": "Bot2",
                "content": [{"type": "text", "data": {"text": "图表分析结果"}}],
            }
        },
    ]
    formatted = TelegramMessageConverter.format_forward_nodes_to_text(nodes)
    assert "📊 **分析报告**" in formatted
    assert "**[Bot1]**\n第一条信息" in formatted
    assert "**[Bot2]**\n图表分析结果" in formatted
