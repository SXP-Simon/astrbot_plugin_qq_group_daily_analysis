import asyncio

from src.infrastructure.platform.adapters.onebot_adapter import OneBotAdapter


class FakeOneBot:
    """记录动作调用并按动作名返回预设结果的 OneBot 测试替身。"""

    def __init__(self, results: dict[str, object]):
        self.results = results
        self.actions: list[str] = []

    async def call_action(self, action: str, **params):
        self.actions.append(action)
        result = self.results.get(action)
        if isinstance(result, BaseException):
            raise result
        return result


def make_adapter(bot: FakeOneBot) -> OneBotAdapter:
    adapter = OneBotAdapter(bot, {"filter_bot_messages": False})
    adapter._snowluma_checked = True
    return adapter


def test_protocol_avatar_url_takes_priority():
    remote = "https://wx.qlogo.cn/mmhead/ver_1/demo/0"
    bot = FakeOneBot({"get_stranger_info": {"user_id": 10001, "avatar_url": remote}})
    adapter = make_adapter(bot)

    url = asyncio.run(adapter.get_user_avatar_url("10001"))
    repeated = asyncio.run(adapter.get_user_avatar_url("10001"))

    assert url == remote
    assert repeated == remote
    assert bot.actions == ["get_stranger_info"]


def test_falls_back_to_qq_cdn_when_protocol_has_no_avatar():
    bot = FakeOneBot(
        {
            "get_stranger_info": {"nickname": "测试用户"},
            "get_user_info": {"nickname": "测试用户"},
        }
    )
    adapter = make_adapter(bot)

    url = asyncio.run(adapter.get_user_avatar_url("10001"))
    repeated = asyncio.run(adapter.get_user_avatar_url("10001"))

    assert url == "https://q1.qlogo.cn/g?b=qq&nk=10001&s=100"
    assert repeated == url
    assert bot.actions == ["get_stranger_info", "get_user_info"]


def test_negative_cache_skips_failed_protocol_after_timeout():
    bot = FakeOneBot(
        {
            "get_stranger_info": TimeoutError("WebSocket timeout"),
            "get_user_info": TimeoutError("WebSocket timeout"),
        }
    )
    adapter = make_adapter(bot)

    url = asyncio.run(adapter.get_user_avatar_url("10001"))
    repeated = asyncio.run(adapter.get_user_avatar_url("10001"))

    assert url == "https://q1.qlogo.cn/g?b=qq&nk=10001&s=100"
    assert repeated == url
    assert bot.actions == ["get_stranger_info", "get_user_info"]


def test_empty_user_id_returns_none():
    bot = FakeOneBot({})
    adapter = make_adapter(bot)

    assert asyncio.run(adapter.get_user_avatar_url("")) is None
    assert bot.actions == []
