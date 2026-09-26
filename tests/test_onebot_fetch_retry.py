import asyncio
from datetime import datetime

from src.infrastructure.platform.adapters.onebot_adapter import OneBotAdapter


def make_message(message_id: str, timestamp: int, text: str) -> dict:
    """构造 OneBot 历史消息测试数据。

    Args:
        message_id: 消息 ID。
        timestamp: Unix 时间戳。
        text: 消息文本。

    Returns:
        OneBot 原始消息字典。
    """
    return {
        "message_id": message_id,
        "message_seq": message_id,
        "time": timestamp,
        "sender": {"user_id": "10001", "nickname": "测试用户"},
        "message": [{"type": "text", "data": {"text": text}}],
    }


class FakeOneBot:
    """按顺序返回结果或抛出异常的 OneBot 测试替身。"""

    def __init__(self, responses: list[object]):
        self.responses = iter(responses)
        self.history_call_count = 0

    async def call_action(self, action: str, **params):
        """模拟 OneBot 动作调用。

        Args:
            action: OneBot 动作名称。
            **params: 动作参数。

        Returns:
            当前预设的动作结果。

        Raises:
            BaseException: 当前预设值为异常时原样抛出。
        """
        assert action == "get_group_msg_history"
        assert params["group_id"] == 123456
        self.history_call_count += 1
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


def make_adapter(bot: FakeOneBot) -> OneBotAdapter:
    """创建跳过协议探测的 OneBot 适配器。

    Args:
        bot: OneBot 测试替身。

    Returns:
        已配置的 OneBot 适配器。
    """
    adapter = OneBotAdapter(bot, {"filter_bot_messages": False})
    adapter._snowluma_checked = True
    return adapter


def test_fetch_messages_retries_failed_page(monkeypatch):
    now = int(datetime.now().timestamp())
    bot = FakeOneBot(
        [
            TimeoutError("WebSocket timeout"),
            {"messages": [make_message("101", now, "重试成功")]},
        ]
    )
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    messages = asyncio.run(adapter.fetch_messages("123456", max_count=1))

    assert bot.history_call_count == 2
    assert [message.message_id for message in messages] == ["101"]
    assert [message.text_content for message in messages] == ["重试成功"]


def test_fetch_messages_returns_partial_results_after_retries(monkeypatch):
    now = int(datetime.now().timestamp())
    bot = FakeOneBot(
        [
            {"messages": [make_message("201", now, "已获取消息")]},
            TimeoutError("WebSocket timeout 1"),
            TimeoutError("WebSocket timeout 2"),
            TimeoutError("WebSocket timeout 3"),
        ]
    )
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    messages = asyncio.run(adapter.fetch_messages("123456", max_count=2))

    assert bot.history_call_count == 4
    assert [message.message_id for message in messages] == ["201"]
    assert [message.text_content for message in messages] == ["已获取消息"]


def test_fetch_messages_deduplicates_overlapping_pages(monkeypatch):
    now = int(datetime.now().timestamp())
    bot = FakeOneBot(
        [
            {
                "messages": [
                    make_message("303", now, "第三条"),
                    make_message("302", now - 1, "第二条"),
                ]
            },
            {
                "messages": [
                    make_message("302", now - 1, "重复的第二条"),
                    make_message("301", now - 2, "第一条"),
                ]
            },
        ]
    )
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    messages = asyncio.run(adapter.fetch_messages("123456", max_count=3))

    assert bot.history_call_count == 2
    assert [message.message_id for message in messages] == ["301", "302", "303"]
    assert [message.text_content for message in messages] == [
        "第一条",
        "第二条",
        "第三条",
    ]


def test_fetch_messages_clamps_stale_since_ts_to_days_window(monkeypatch):
    """测试当 since_ts 早于 days (例如停机多天或游标过旧) 时，自动将起始时间截断至 days 窗口内，绝不过界拉取。"""
    now = int(datetime.now().timestamp())
    stale_since_ts = now - 5 * 86400  # 5 天前的旧游标
    within_window_ts = now - 1800  # 30 分钟前
    out_of_window_ts = now - 2 * 86400  # 2 天前 (超过 days=1)

    bot = FakeOneBot(
        [
            {
                "messages": [
                    make_message("402", within_window_ts, "窗口内消息"),
                    make_message("401", out_of_window_ts, "窗口外消息 (2天前)"),
                ]
            },
        ]
    )
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    # days=1, since_ts=5天前，应当只拉取 1 天内的消息
    messages = asyncio.run(
        adapter.fetch_messages("123456", days=1, max_count=10, since_ts=stale_since_ts)
    )

    # 401 (2天前) 超出 days=1 窗口，被过滤；只保留 402
    assert [message.message_id for message in messages] == ["402"]
    assert [message.text_content for message in messages] == ["窗口内消息"]


def test_fetch_messages_with_recent_since_ts_honors_cursor(monkeypatch):
    """测试当 since_ts 在 days 窗口内时，以 since_ts 为起始点。"""
    now = int(datetime.now().timestamp())
    recent_since_ts = now - 3600  # 1 小时前
    msg_after_cursor = now - 1800  # 30 分钟前
    msg_before_cursor = now - 7200  # 2 小时前

    bot = FakeOneBot(
        [
            {
                "messages": [
                    make_message("502", msg_after_cursor, "游标后新消息"),
                    make_message("501", msg_before_cursor, "游标前旧消息"),
                ]
            },
        ]
    )
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    messages = asyncio.run(
        adapter.fetch_messages("123456", days=1, max_count=10, since_ts=recent_since_ts)
    )

    assert [message.message_id for message in messages] == ["502"]
    assert [message.text_content for message in messages] == ["游标后新消息"]


def test_fetch_messages_handles_ascending_and_descending_batch_orders(monkeypatch):
    """测试当协议端分别返回正序与逆序消息切片时，均能正确识别最旧消息并完成回溯。"""
    now = int(datetime.now().timestamp())
    # 模拟逆序切片（首条较新，末条较旧）
    descending_batch = {
        "messages": [
            make_message("602", now - 100, "较新消息"),
            make_message("601", now - 200, "最旧消息"),
        ]
    }
    # 模拟正序切片（首条较旧，末条较新）
    ascending_batch = {
        "messages": [
            make_message("600", now - 300, "更旧消息"),
            make_message("600.5", now - 250, "中间消息"),
        ]
    }

    bot = FakeOneBot([descending_batch, ascending_batch, {"messages": []}])
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    messages = asyncio.run(adapter.fetch_messages("123456", days=1, max_count=10))

    assert len(messages) == 4
    # 最终输出统一按时间升序排序
    assert [m.message_id for m in messages] == ["600", "600.5", "601", "602"]


def test_fetch_messages_stops_on_stalled_anchor(monkeypatch):
    """测试当分页拉取由于到达历史尽头导致锚点无法继续前移时，能安全终止循环避免死循环。"""
    now = int(datetime.now().timestamp())
    # 连续返回相同锚点的消息批次
    same_batch = {
        "messages": [
            make_message("701", now - 100, "历史顶端消息"),
        ]
    }

    bot = FakeOneBot([same_batch, same_batch])
    adapter = make_adapter(bot)

    async def skip_sleep(delay: float):
        return None

    monkeypatch.setattr(asyncio, "sleep", skip_sleep)
    # 即使 max_count 请求 100 条，遇到锚点停滞也应当在第 2 次比对后安全退出
    messages = asyncio.run(
        adapter.fetch_messages("123456", days=1, max_count=100, before_id="701")
    )

    assert len(messages) == 1
    assert messages[0].message_id == "701"

