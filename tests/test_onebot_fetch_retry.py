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
